"""Explicação de regras do rule-engine por comparação.

Divide a regra em trechos e mostra, para cada um, o campo, o valor esperado, o valor encontrado no
contexto e se o trecho foi atendido. Tudo é avaliado com o próprio ``rule_engine`` (sem fork nem
interpretador paralelo): a divisão em trechos é apenas textual e serve para escolher o que avaliar.

Exemplo::

    from django_rule_engine.explain import explain

    explain("idade >= 18 and status == 'ativo'", {"idade": 16, "status": "ativo"})
    # {"regra": ..., "resultado": False, "atendido": False, "erro": "", "operador": "and",
    #  "condicoes": [{"condicao": "idade >= 18", "atendido": False, ...}, ...]}

Compreensões dentro de ``$any``/``$all`` (``$any([m['tipo'] == 'aluno' for m in vinculos])``) são
detalhadas por item da lista: cada linha traz ``valores`` e ``resultados`` com um elemento por item.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from functools import lru_cache
from typing import Any, Dict, List, Optional, Pattern, Tuple, Union

import rule_engine
import rule_engine.errors

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_SENSITIVE_FIELDS",
    "OPERATORS",
    "UNEXPECTED_ERROR",
    "explain",
    "split_conditions",
    "split_comparison",
    "parse_comprehension",
    "field_label",
    "to_json",
]

#: Padrão (sem diferenciar maiúsculas) dos campos cujo valor nunca é exibido na explicação.
DEFAULT_SENSITIVE_FIELDS = (
    r"cpf|rg|passaporte|passport|email|e_mail|nascimento|birth|telefone|phone|filiacao|foto|photo"
    r"|endereco|address|senha|password|token|secret"
)

#: Operadores de comparação reconhecidos, na ordem de busca (os mais longos primeiro).
OPERATORS = ("==", "!=", ">=", "<=", "=~~", "!~~", "=~", "!~", ">", "<", "not in", "in")

#: Texto exibido no lugar de erros que não vêm do ``rule_engine``.
UNEXPECTED_ERROR = "Erro inesperado ao avaliar este trecho"

SensitiveArg = Union[str, Pattern[str], None]

_SYMBOLIC_OPERATORS = tuple(op for op in OPERATORS if op[0] in "=!<>")
_NOT_IN = re.compile(r"not\s+in\b")
_KEY_IN_BRACKETS = re.compile(r"\[\s*'([^']*)'\s*\]|\[\s*\"([^\"]*)\"\s*\]")
_COMPREHENSION_CALL = re.compile(r"^\$(?P<func>any|all)\(\s*\[(?P<body>.*)\]\s*\)$", re.S)
_EXPECTED_TRUE = "verdadeiro"


# --- Análise textual -----------------------------------------------------------------------------


def _top_level_mask(text: str) -> List[bool]:
    """Para cada posição: está fora de aspas e de parênteses/colchetes/chaves?"""
    mask: List[bool] = []
    depth, quote, escape = 0, None, False
    for c in text:
        if quote:
            mask.append(False)
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == quote:
                quote = None
            continue
        if c in "'\"":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        mask.append(depth == 0 and not quote and c not in ")]}")
    return mask


def _closes_at_end(text: str, opening: str = "(", closing: str = ")") -> bool:
    """O delimitador aberto no primeiro caractere só fecha no último?"""
    depth, quote, escape = 0, None, False
    for i, c in enumerate(text):
        if quote:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == quote:
                quote = None
            continue
        if c in "'\"":
            quote = c
        elif c == opening:
            depth += 1
        elif c == closing:
            depth -= 1
            if depth == 0 and i != len(text) - 1:
                return False
    return depth == 0


def _strip_parens(text: str) -> str:
    text = text.strip()
    while text.startswith("(") and text.endswith(")") and _closes_at_end(text):
        text = text[1:-1].strip()
    return text


def _word_at(text: str, i: int, word: str) -> bool:
    end = i + len(word)
    return (
        text.startswith(word, i)
        and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] in "_$"))
        and (end >= len(text) or not (text[end].isalnum() or text[end] == "_"))
    )


def _find_top_level_words(text: str, words: Tuple[str, ...]) -> List[Tuple[int, str]]:
    mask = _top_level_mask(text)
    found = []
    i = 0
    while i < len(text):
        if mask[i]:
            for word in words:
                if _word_at(text, i, word):
                    found.append((i, word))
                    i += len(word) - 1
                    break
        i += 1
    return found


def _split_top_level(text: str) -> Tuple[List[str], Optional[str]]:
    """Partes e operador da divisão nos ``and``/``or`` de nível superior.

    Devolve ``([], None)`` quando não há divisão confiável.
    """
    text = _strip_parens(text)
    found = _find_top_level_words(text, ("and", "or"))
    operators = {word for _, word in found}
    if len(operators) != 1:
        return [], None
    parts, start = [], 0
    for i, word in found:
        parts.append(text[start:i].strip())
        start = i + len(word)
    parts.append(text[start:].strip())
    if len(parts) < 2 or not all(parts):
        return [], None
    return parts, operators.pop()


def split_conditions(rule: str) -> List[str]:
    """Divide a regra nos ``and``/``or`` de nível superior, se todos forem do mesmo operador.

    Respeita aspas, parênteses, colchetes e chaves. Devolve ``[]`` quando não há divisão confiável
    (operadores misturados no mesmo nível, uma só condição ou parte vazia).
    """
    return _split_top_level(rule)[0]


def split_comparison(atom: str) -> Optional[Tuple[str, str, str]]:
    """``(campo, operador, esperado)`` no primeiro operador de comparação de nível superior.

    Devolve ``None`` se o átomo não tiver comparação (ex.: ``ativo`` ou ``$any([...])``).
    """
    mask = _top_level_mask(atom)
    for i in range(len(atom)):
        if not mask[i]:
            continue
        for op in _SYMBOLIC_OPERATORS:
            if atom.startswith(op, i):
                return atom[:i].strip(), op, atom[i + len(op) :].strip()
        if _word_at(atom, i, "not"):
            not_in = _NOT_IN.match(atom, i)
            if not_in and i > 0:
                return atom[:i].strip(), "not in", atom[not_in.end() :].strip()
        if i > 0 and _word_at(atom, i, "in"):
            return atom[:i].strip(), "in", atom[i + 2 :].strip()
    return None


def parse_comprehension(condition: str) -> Optional[Dict[str, str]]:
    """Reconhece ``$any([EXPR for VAR in LISTA])`` e ``$all(...)`` (com ``if FILTRO`` opcional).

    Devolve ``{"funcao", "expressao", "variavel", "lista", "filtro"}`` ou ``None``.
    """
    text = _strip_parens(condition)
    match = _COMPREHENSION_CALL.match(text)
    if not match or not _closes_at_end(text[match.start("func") + len(match.group("func")) :]):
        return None
    body = match.group("body").strip()
    if not _closes_at_end("[" + body + "]", "[", "]"):
        return None
    words = _find_top_level_words(body, ("for", "in", "if"))
    fors = [i for i, w in words if w == "for"]
    if len(fors) != 1:
        return None
    for_at = fors[0]
    ins = [i for i, w in words if w == "in" and i > for_at]
    if not ins:
        return None
    in_at = ins[0]
    variable = body[for_at + 3 : in_at].strip()
    if not re.fullmatch(r"[A-Za-z_]\w*", variable):
        return None
    ifs = [i for i, w in words if w == "if" and i > in_at]
    iterable_end = ifs[0] if ifs else len(body)
    expression = body[:for_at].strip()
    iterable = body[in_at + 2 : iterable_end].strip()
    if not expression or not iterable:
        return None
    return {
        "funcao": match.group("func"),
        "expressao": expression,
        "variavel": variable,
        "lista": iterable,
        "filtro": body[ifs[0] + 2 :].strip() if ifs else "",
    }


def field_label(field: str, variable: str = "") -> str:
    """Rótulo legível: ``m['detalhamento']['modalidade']`` vira ``detalhamento.modalidade``."""
    label = _KEY_IN_BRACKETS.sub(
        lambda m: "." + (m.group(1) if m.group(1) is not None else m.group(2)), field
    )
    if variable and label.startswith(variable + "."):
        label = label[len(variable) + 1 :]
    return label


# --- Avaliação -----------------------------------------------------------------------------------


def to_json(value: Any) -> Any:
    """Converte o valor devolvido pelo ``rule_engine`` em algo serializável em JSON."""
    if isinstance(value, bool) or value is None or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, Decimal):
        if value.is_finite() and value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {str(k): to_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((to_json(v) for v in value), key=repr)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


@lru_cache(maxsize=512)
def _compiled(expression: str) -> rule_engine.Rule:
    return rule_engine.Rule(expression)


def _error_text(exc: Exception) -> str:
    """Mensagem exibível do erro.

    Só erros do próprio ``rule_engine`` (sobre a regra e os dados avaliados) têm a mensagem
    exibida; qualquer outra exceção vira texto genérico, para não expor detalhes internos.
    """
    if isinstance(exc, rule_engine.errors.EngineError):
        return f"{type(exc).__name__}: {exc.message}"
    logger.warning("Erro inesperado ao avaliar trecho de regra", exc_info=exc)
    return UNEXPECTED_ERROR


def _evaluate(expression: str, context: dict) -> Tuple[Any, str]:
    try:
        return to_json(_compiled(expression).evaluate(context)), ""
    except Exception as exc:  # noqa: BLE001 - o erro é parte da explicação
        return None, _error_text(exc)


def _sensitive_pattern(sensitive: SensitiveArg) -> Optional[Pattern[str]]:
    if not sensitive:
        return None
    if isinstance(sensitive, str):
        return re.compile(sensitive, re.IGNORECASE)
    return sensitive


def _row(atom: str, variable: str, sensitive: Optional[Pattern[str]]) -> Dict[str, Any]:
    comparison = split_comparison(atom)
    field, operator, expected = comparison if comparison else (atom, "", _EXPECTED_TRUE)
    return {
        "atomo": atom,
        "campo": field,
        "rotulo": field_label(field, variable),
        "operador": operator,
        "esperado": expected,
        "sensivel": bool(sensitive and sensitive.search(field)),
    }


def _detail_comprehension(
    comp: Dict[str, str], context: dict, sensitive: Optional[Pattern[str]]
) -> Dict[str, Any]:
    variable, iterable, func = comp["variavel"], comp["lista"], comp["funcao"]
    suffix = f" for {variable} in {iterable}" + (f" if {comp['filtro']}" if comp["filtro"] else "")
    items, items_error = _evaluate(f"[{variable}{suffix}]", context)
    total = len(items) if isinstance(items, list) else None
    rows = []
    for atom in split_conditions(comp["expressao"]) or [_strip_parens(comp["expressao"])]:
        row = _row(atom, variable, sensitive)
        values, error = (None, "")
        if not row["sensivel"]:
            values, error = _evaluate(f"[{row['campo']}{suffix}]", context)
        results, results_error = _evaluate(f"[{atom}{suffix}]", context)
        matched = None
        if isinstance(results, list) and all(isinstance(r, bool) for r in results):
            matched = any(results) if func == "any" else all(results)
        row.update(
            valores=values, resultados=results, atendido=matched, erro=error or results_error
        )
        rows.append(row)
    return {
        "tipo": "por_item",
        "funcao": func,
        "variavel": variable,
        "lista": iterable,
        "filtro": comp["filtro"],
        "itens": total,
        "erro": items_error,
        "linhas": rows,
    }


def _detail(condition: str, context: dict, sensitive: Optional[Pattern[str]]) -> Dict[str, Any]:
    """Campo, esperado e valor de cada comparação da condição (por item em ``$any``/``$all``)."""
    comp = parse_comprehension(condition)
    if comp:
        return _detail_comprehension(comp, context, sensitive)
    text = _strip_parens(condition)
    rows = []
    for atom in split_conditions(text) or [text]:
        row = _row(atom, "", sensitive)
        value, error = (None, "") if row["sensivel"] else _evaluate(row["campo"], context)
        result, result_error = _evaluate(atom, context)
        row.update(
            valor=value,
            resultado=result,
            atendido=result if isinstance(result, bool) else None,
            erro=error or result_error,
        )
        rows.append(row)
    return {"tipo": "simples", "linhas": rows}


def _outcome(condition: str, context: dict) -> Dict[str, Any]:
    result, error = _evaluate(condition, context)
    matched = None
    if not error:
        try:
            matched = bool(_compiled(condition).matches(context))
        except Exception as exc:  # noqa: BLE001
            error = _error_text(exc)
    return {"condicao": condition, "resultado": result, "atendido": matched, "erro": error}


def _condition(condition: str, context: dict, sensitive: Optional[Pattern[str]]) -> Dict[str, Any]:
    outcome = _outcome(condition, context)
    outcome["detalhes"] = _detail(condition, context, sensitive)
    return outcome


def explain(
    rule: str,
    context: Optional[dict] = None,
    *,
    sensitive: SensitiveArg = DEFAULT_SENSITIVE_FIELDS,
) -> Dict[str, Any]:
    """Explica por que a regra é (ou não) atendida pelo contexto.

    Args:
        rule: texto da regra do ``rule_engine``.
        context: dados avaliados (o mesmo ``dict`` passado a ``Rule.matches``).
        sensitive: regex (texto ou compilada) dos campos cujo valor não é exibido; ``None`` ou
            ``""`` exibe tudo. Padrão: :data:`DEFAULT_SENSITIVE_FIELDS`.

    Returns:
        ``dict`` serializável em JSON::

            {
              "regra": str, "resultado": Any, "atendido": bool | None, "erro": str,
              "operador": "and" | "or" | "",
              "condicoes": [{
                "condicao": str, "resultado": Any, "atendido": bool | None, "erro": str,
                "detalhes": {
                  "tipo": "simples" | "por_item",
                  # por_item: "funcao", "variavel", "lista", "filtro", "itens", "erro"
                  "linhas": [{
                    "atomo", "campo", "rotulo", "operador", "esperado", "sensivel",
                    "atendido", "erro",
                    # simples: "valor", "resultado"; por_item: "valores", "resultados" (listas)
                  }]
                }
              }]
            }

        ``atendido`` é ``None`` quando a avaliação deu erro. Valores de campos sensíveis vêm
        como ``None`` (o resultado da comparação continua sendo informado).
    """
    rule = (rule or "").strip()
    context = context if context is not None else {}
    pattern = _sensitive_pattern(sensitive)
    if not rule:
        return {
            "regra": "",
            "resultado": None,
            "atendido": None,
            "erro": "Regra vazia",
            "operador": "",
            "condicoes": [],
        }
    parts, operator = _split_top_level(rule)
    main = _outcome(rule, context)
    conditions = [_condition(part, context, pattern) for part in parts or [rule]]
    return {
        "regra": rule,
        "resultado": main["resultado"],
        "atendido": main["atendido"],
        "erro": main["erro"],
        "operador": operator or "",
        "condicoes": conditions,
    }
