"""Explicação de regras do rule-engine em árvore, nó a nó.

Diferente de :func:`django_rule_engine.explain.explain` (que divide o texto da regra em dois
níveis), aqui a árvore é montada a partir do AST do próprio ``rule_engine`` e cada nó é avaliado
com o ``evaluate()`` da biblioteca. Assim qualquer regra é explicada, com qualquer aninhamento:
``and``/``or`` misturados, ``not``, compreensões dentro de compreensões, ternários, funções e
aritmética.

Exemplo::

    from django_rule_engine.explain_tree import explain_tree

    contexto = {"idade": 16, "pais": True, "bloqueado": False}
    explain_tree("idade >= 18 or (pais and not bloqueado)", contexto)
    # {"regra": ..., "resultado": True, "atendido": True, "erro": "",
    #  "raiz": {"tipo": "logico", "operador": "or", "atendido": True, "filhos": [...]}}

Tipos de nó (campo ``tipo``):

- ``logico``: ``and``/``or``; cadeias do mesmo operador viram um só nó com vários ``filhos``.
- ``nao``: ``not``; ``filho``.
- ``comparacao``: ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``, ``=~``, ``=~~``, ``!~``, ``!~~``;
  ``esquerda`` e ``direita``.
- ``contem``: ``in`` e ``not in``; ``esquerda`` (membro) e ``direita`` (contêiner).
- ``funcao``: chamada de função (``$any``, ``$len``...); ``nome`` e ``argumentos``.
- ``compreensao``: ``[expr for v in lista if filtro]``; ``variavel``, ``lista``, ``itens``
  (avaliados um a um), ``melhor_item``, ``total`` e ``truncado``.
- ``ternario``: ``cond ? a : b``; ``condicao``, ``se_verdadeiro``, ``se_falso``.
- ``aritmetica``: ``+``, ``-``, ``*``, ``/``, ``//``, ``%``, ``**``, bit a bit e ``??``;
  ``operador``, ``esquerda`` e ``direita`` (``-x`` usa só ``direita``).
- ``campo``: símbolo ou acesso (``a``, ``m.x``, ``m['x'][0]``); ``rotulo``, ``valor``, ``sensivel``.
- ``literal``: valor fixo da regra; ``valor``.
- ``expressao``: qualquer outro nó (fatia ``s[1:2]``, nós de versões futuras); ``valor``.

Todo nó traz ``tipo``, ``trecho`` (texto do nó, regerado a partir do AST), ``valor`` (resultado
da avaliação, serializável em JSON), ``atendido`` (``True``/``False`` quando o valor é booleano,
senão ``None``) e ``erro`` (texto vazio quando a avaliação deu certo).
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import rule_engine
import rule_engine.ast as re_ast

from .explain import (
    DEFAULT_SENSITIVE_FIELDS,
    SensitiveArg,
    _error_text,
    _sensitive_pattern,
    field_label,
    to_json,
)

logger = logging.getLogger(__name__)

__all__ = [
    "COMPARISON_SYMBOLS",
    "ARITHMETIC_SYMBOLS",
    "DEFAULT_ITEM_LABEL_KEYS",
    "explain_tree",
    "unparse",
]

#: Símbolo de cada tipo de comparação do ``rule_engine``.
COMPARISON_SYMBOLS = {
    "eq": "==",
    "ne": "!=",
    "lt": "<",
    "le": "<=",
    "gt": ">",
    "ge": ">=",
    "eq_fzm": "=~",
    "eq_fzs": "=~~",
    "ne_fzm": "!~",
    "ne_fzs": "!~~",
}

#: Símbolo de cada operação aritmética ou bit a bit do ``rule_engine``.
ARITHMETIC_SYMBOLS = {
    "add": "+",
    "sub": "-",
    "mul": "*",
    "tdiv": "/",
    "fdiv": "//",
    "mod": "%",
    "pow": "**",
    "bwand": "&",
    "bwor": "|",
    "bwxor": "^",
    "bwlsh": "<<",
    "bwrsh": ">>",
    "uminus": "-",
    "coalesce": "??",
}

#: Chaves usadas, nesta ordem, para dar um rótulo aos itens de uma compreensão.
DEFAULT_ITEM_LABEL_KEYS = (
    "identificador",
    "rotulo",
    "nome",
    "name",
    "titulo",
    "title",
    "codigo",
    "code",
    "id",
)

ItemLabel = Union[None, str, Sequence[str], Callable[[Any], Any]]

_ARITHMETIC = (
    "AddExpression",
    "SubtractExpression",
    "ArithmeticExpression",
    "BitwiseExpression",
    "BitwiseShiftExpression",
)
_COMPARISON = (
    "ComparisonExpression",
    "ArithmeticComparisonExpression",
    "FuzzyComparisonExpression",
)
_ACCESS = ("SymbolExpression", "GetAttributeExpression", "GetItemExpression")

# Precedência usada só para pôr parênteses no texto regerado (maior = liga mais forte).
_PRECEDENCE = {
    "ternario": 1,
    "or": 2,
    "and": 3,
    "nao": 4,
    "comparacao": 5,
    "bw": 6,
    "add": 7,
    "mul": 8,
    "pow": 9,
    "unario": 10,
    "atomo": 11,
}
_PRECEDENCE_BY_OP = {
    "add": "add",
    "sub": "add",
    "mul": "mul",
    "tdiv": "mul",
    "fdiv": "mul",
    "mod": "mul",
    "pow": "pow",
    "bwand": "bw",
    "bwor": "bw",
    "bwxor": "bw",
    "bwlsh": "bw",
    "bwrsh": "bw",
}


def _name(node: Any) -> str:
    return type(node).__name__


# --- Texto regerado a partir do AST --------------------------------------------------------------


def _precedence(node: Any) -> int:
    name = _name(node)
    if name == "TernaryExpression":
        return _PRECEDENCE["ternario"]
    if name == "LogicExpression":
        return _PRECEDENCE["or" if node.type == "or" else "and"]
    if name == "UnaryExpression":
        return _PRECEDENCE["nao" if node.type == "not" else "unario"]
    if name in _COMPARISON or name == "ContainsExpression":
        return _PRECEDENCE["comparacao"]
    if name == "CoalesceExpression":
        return _PRECEDENCE["bw"]
    if name in _ARITHMETIC:
        return _PRECEDENCE[_PRECEDENCE_BY_OP.get(node.type, "mul")]
    return _PRECEDENCE["atomo"]


def _wrapped(child: Any, parent_precedence: int, strict: bool = False) -> str:
    text = unparse(child)
    child_precedence = _precedence(child)
    if child_precedence < parent_precedence or (strict and child_precedence == parent_precedence):
        return f"({text})"
    return text


def _literal_text(node: Any) -> str:
    name, value = _name(node), getattr(node, "value", None)
    if name == "StringExpression":
        return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"
    if name == "BooleanExpression":
        return "true" if value else "false"
    if name == "NullExpression":
        return "null"
    if name == "FloatExpression":
        return str(to_json(value))
    if name == "BytesExpression":
        return repr(bytes(value))
    if name == "DatetimeExpression":
        return f"d'{value.isoformat() if hasattr(value, 'isoformat') else value}'"
    if name == "TimedeltaExpression":
        return f"t'{_iso_duration(value)}'"
    if name == "ArrayExpression":
        return "[" + ", ".join(unparse(v) for v in value) + "]"
    if name == "SetExpression":
        return "{" + ", ".join(sorted(unparse(v) for v in value)) + "}"
    if name == "MappingExpression":
        return "{" + ", ".join(f"{unparse(k)}: {unparse(v)}" for k, v in value) + "}"
    if name == "FunctionExpression":
        return str(getattr(value, "name", None) or getattr(value, "__name__", "função"))
    return str(to_json(value))


def _iso_duration(value: Any) -> str:
    if not isinstance(value, datetime.timedelta):
        return str(value)
    seconds = int(value.total_seconds())
    days, rest = divmod(abs(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    text = "P" + (f"{days}D" if days else "")
    if hours or minutes or secs or not days:
        text += (
            "T"
            + (f"{hours}H" if hours else "")
            + (f"{minutes}M" if minutes else "")
            + (f"{secs}S" if secs or not (hours or minutes) else "")
        )
    return ("-" if seconds < 0 else "") + text


def unparse(node: Any) -> str:
    """Texto de um nó do AST do ``rule_engine``.

    Equivalente ao original, mas não necessariamente idêntico (espaços, parênteses, constantes).
    """
    name = _name(node)
    if name == "LogicExpression":
        precedence = _precedence(node)
        return f"{_wrapped(node.left, precedence)} {node.type} {_wrapped(node.right, precedence)}"
    if name in _COMPARISON:
        precedence = _precedence(node)
        operator = COMPARISON_SYMBOLS.get(node.type, node.type)
        left, right = _wrapped(node.left, precedence, True), _wrapped(node.right, precedence, True)
        return f"{left} {operator} {right}"
    if name in _ARITHMETIC or name == "CoalesceExpression":
        precedence = _precedence(node)
        operator = ARITHMETIC_SYMBOLS.get(getattr(node, "type", "coalesce"), "??")
        return (
            f"{_wrapped(node.left, precedence)} {operator} {_wrapped(node.right, precedence, True)}"
        )
    if name == "ContainsExpression":
        precedence = _precedence(node)
        member = _wrapped(node.member, precedence, True)
        return f"{member} in {_wrapped(node.container, precedence, True)}"
    if name == "UnaryExpression":
        if node.type == "not" and _name(node.right) == "ContainsExpression":
            contains = node.right
            precedence = _precedence(contains)
            member = _wrapped(contains.member, precedence, True)
            return f"{member} not in {_wrapped(contains.container, precedence, True)}"
        if node.type == "not":
            return f"not {_wrapped(node.right, _PRECEDENCE['nao'])}"
        return f"-{_wrapped(node.right, _PRECEDENCE['unario'])}"
    if name == "TernaryExpression":
        precedence = _PRECEDENCE["ternario"]
        condition = _wrapped(node.condition, precedence, True)
        case_true = _wrapped(node.case_true, precedence, True)
        return f"{condition} ? {case_true} : {_wrapped(node.case_false, precedence)}"
    if name == "SymbolExpression":
        return ("$" if getattr(node, "scope", None) else "") + node.name
    if name == "GetAttributeExpression":
        return (
            f"{_wrapped(node.object, _PRECEDENCE['atomo'])}{'&.' if node.safe else '.'}{node.name}"
        )
    if name == "GetItemExpression":
        container = _wrapped(node.container, _PRECEDENCE["atomo"]) + ("&" if node.safe else "")
        return f"{container}[{unparse(node.item)}]"
    if name == "GetSliceExpression":
        start = unparse(node.start) if node.start is not None else ""
        stop = unparse(node.stop) if node.stop is not None else ""
        container = _wrapped(node.container, _PRECEDENCE["atomo"]) + ("&" if node.safe else "")
        return f"{container}[{start}:{stop}]"
    if name == "FunctionCallExpression":
        return f"{unparse(node.function)}({', '.join(unparse(a) for a in node.arguments)})"
    if name == "ComprehensionExpression":
        condition = f" if {unparse(node.condition)}" if node.condition is not None else ""
        return (
            f"[{unparse(node.result)} for {node.variable} in {unparse(node.iterable)}{condition}]"
        )
    if hasattr(node, "value"):
        return _literal_text(node)
    return name


# --- Avaliação nó a nó ---------------------------------------------------------------------------


class _Builder:
    def __init__(self, context: dict, sensitive, max_items: int, item_label: ItemLabel) -> None:
        self.context = context
        self.sensitive = sensitive
        self.max_items = max_items
        self.item_label = item_label

    def evaluate(self, node: Any) -> Tuple[Any, str]:
        try:
            return node.evaluate(self.context), ""
        except Exception as exc:  # noqa: BLE001 - o erro é parte da explicação
            return None, _error_text(exc)

    def mask(self, value: Any) -> Any:
        """Valor em JSON sem as chaves sensíveis de dicionários aninhados."""
        if isinstance(value, dict):
            return {k: None if self.is_sensitive(k) else self.mask(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.mask(v) for v in value]
        return value

    def base(self, node: Any, tipo: str) -> Dict[str, Any]:
        value, error = self.evaluate(node)
        return {
            "tipo": tipo,
            "trecho": unparse(node),
            "valor": self.mask(to_json(value)),
            "atendido": value if isinstance(value, bool) and not error else None,
            "erro": error,
        }

    def is_sensitive(self, text: str) -> bool:
        return bool(self.sensitive and self.sensitive.search(text))

    def build(self, node: Any) -> Dict[str, Any]:
        name = _name(node)
        if name == "LogicExpression":
            out = self.base(node, "logico")
            out["operador"] = node.type
            out["filhos"] = [self.build(child) for child in self._chain(node, node.type)]
            return out
        if (
            name == "UnaryExpression"
            and node.type == "not"
            and _name(node.right) == "ContainsExpression"
        ):
            out = self.base(node, "contem")
            out.update(
                operador="not in",
                esquerda=self.build(node.right.member),
                direita=self.build(node.right.container),
            )
            return out
        if name == "UnaryExpression" and node.type == "not":
            out = self.base(node, "nao")
            out["filho"] = self.build(node.right)
            return out
        if name == "UnaryExpression":
            out = self.base(node, "aritmetica")
            out.update(
                operador=ARITHMETIC_SYMBOLS.get(node.type, node.type),
                direita=self.build(node.right),
            )
            return out
        if name in _COMPARISON:
            out = self.base(node, "comparacao")
            out.update(
                operador=COMPARISON_SYMBOLS.get(node.type, node.type),
                esquerda=self.build(node.left),
                direita=self.build(node.right),
            )
            return out
        if name == "ContainsExpression":
            out = self.base(node, "contem")
            out.update(
                operador="in", esquerda=self.build(node.member), direita=self.build(node.container)
            )
            return out
        if name in _ARITHMETIC or name == "CoalesceExpression":
            out = self.base(node, "aritmetica")
            out.update(
                operador=ARITHMETIC_SYMBOLS.get(getattr(node, "type", "coalesce"), "??"),
                esquerda=self.build(node.left),
                direita=self.build(node.right),
            )
            return out
        if name == "TernaryExpression":
            out = self.base(node, "ternario")
            out.update(
                condicao=self.build(node.condition),
                se_verdadeiro=self.build(node.case_true),
                se_falso=self.build(node.case_false),
            )
            return out
        if name == "FunctionCallExpression":
            out = self.base(node, "funcao")
            out.update(
                nome=unparse(node.function), argumentos=[self.build(arg) for arg in node.arguments]
            )
            return out
        if name == "ComprehensionExpression":
            return self.comprehension(node)
        if name in _ACCESS:
            return self.field(node)
        if isinstance(node, re_ast.LiteralExpressionBase):
            return self.base(node, "literal")
        return self.base(node, "expressao")

    def _chain(self, node: Any, operator: str) -> List[Any]:
        if _name(node) == "LogicExpression" and node.type == operator:
            return self._chain(node.left, operator) + self._chain(node.right, operator)
        return [node]

    def field(self, node: Any) -> Dict[str, Any]:
        text = unparse(node)
        out = self.base(node, "campo")
        out["rotulo"] = field_label(text)
        out["sensivel"] = self.is_sensitive(text)
        if out["sensivel"]:
            out["valor"] = None
        return out

    def label(self, item: Any) -> str:
        if callable(self.item_label):
            try:
                return str(self.item_label(item) or "")
            except Exception:  # noqa: BLE001 - rótulo é só apoio visual
                logger.warning("Erro ao gerar rótulo de item da compreensão", exc_info=True)
                return ""
        if not isinstance(item, dict):
            return "" if isinstance(item, (list, tuple, set)) else str(to_json(item))
        keys = (
            (self.item_label,)
            if isinstance(self.item_label, str)
            else (self.item_label or DEFAULT_ITEM_LABEL_KEYS)
        )
        for key in keys:
            if item.get(key) not in (None, "") and not self.is_sensitive(str(key)):
                return str(to_json(item[key]))
        return ""

    def comprehension(self, node: Any) -> Dict[str, Any]:
        out = self.base(node, "compreensao")
        values, iterable_error = self.evaluate(node.iterable)
        out.update(
            variavel=node.variable,
            lista=self.build(node.iterable),
            filtro=unparse(node.condition) if node.condition is not None else "",
            expressao=unparse(node.result),
            itens=[],
            total=None,
            truncado=False,
            melhor_item=None,
        )
        if iterable_error or values is None:
            return out
        try:
            values = list(values)
        except TypeError:
            return out
        out["lista"]["valor"] = None  # os itens aparecem um a um em "itens"
        out["total"] = len(values)
        out["truncado"] = len(values) > self.max_items
        for index, value in enumerate(values[: self.max_items]):
            with node.context.assignments(re_ast.Assignment(node.variable, value=value)):
                label = "" if out["lista"].get("sensivel") else self.label(value)
                item = {"indice": index, "rotulo": label, "incluido": True, "filtro": None}
                if node.condition is not None:
                    item["filtro"] = self.build(node.condition)
                    item["incluido"] = not item["filtro"]["erro"] and bool(item["filtro"]["valor"])
                item["expressao"] = self.build(node.result)
                item["atendido"] = item["expressao"]["atendido"] if item["incluido"] else None
            out["itens"].append(item)
        out["melhor_item"] = _best_item(out["itens"])
        return out


def _count_matched(node: Any) -> int:
    """Quantas comparações (e campos booleanos) atendidas há na subárvore."""
    if isinstance(node, dict):
        own = (
            1
            if node.get("tipo") in ("comparacao", "contem") and node.get("atendido") is True
            else 0
        )
        return own + sum(
            _count_matched(v) for k, v in node.items() if k not in ("esquerda", "direita")
        )
    if isinstance(node, list):
        return sum(_count_matched(v) for v in node)
    return 0


def _best_item(items: List[Dict[str, Any]]) -> Optional[int]:
    """Índice do item que mais se aproxima de atender (o primeiro atendido, se houver)."""
    included = [item for item in items if item["incluido"]]
    if not included:
        return None
    for item in included:
        if item["atendido"] is True:
            return item["indice"]
    return max(included, key=lambda item: (_count_matched(item["expressao"]), -item["indice"]))[
        "indice"
    ]


def explain_tree(
    rule: str,
    context: Optional[dict] = None,
    *,
    sensitive: SensitiveArg = DEFAULT_SENSITIVE_FIELDS,
    max_items: int = 50,
    item_label: ItemLabel = None,
) -> Dict[str, Any]:
    """Explica a regra em árvore, nó a nó, a partir do AST do ``rule_engine``.

    Args:
        rule: texto da regra do ``rule_engine``.
        context: dados avaliados (o mesmo ``dict`` passado a ``Rule.matches``).
        sensitive: regex (texto ou compilada) dos campos cujo valor não é exibido; ``None`` ou
            ``""`` exibe tudo. Padrão: :data:`django_rule_engine.explain.DEFAULT_SENSITIVE_FIELDS`.
        max_items: máximo de itens detalhados por compreensão (o resto é contado em ``total``).
        item_label: como rotular cada item de uma compreensão: chave (ou lista de chaves) do item,
            função ``item -> texto`` ou ``None`` para tentar :data:`DEFAULT_ITEM_LABEL_KEYS`.

    Returns:
        ``{"regra", "resultado", "atendido", "erro", "raiz"}``, serializável em JSON. ``raiz`` é
        ``None`` quando a regra está vazia ou não compila.
    """
    rule = (rule or "").strip()
    context = context if context is not None else {}
    if not rule:
        return {
            "regra": "",
            "resultado": None,
            "atendido": None,
            "erro": "Regra vazia",
            "raiz": None,
        }
    try:
        compiled = rule_engine.Rule(rule)
    except Exception as exc:  # noqa: BLE001
        return {
            "regra": rule,
            "resultado": None,
            "atendido": None,
            "erro": _error_text(exc),
            "raiz": None,
        }
    builder = _Builder(context, _sensitive_pattern(sensitive), max(0, int(max_items)), item_label)
    root = builder.build(compiled.statement.expression)
    matched, error = None, root["erro"]
    if not error:
        try:
            matched = bool(compiled.matches(context))
        except Exception as exc:  # noqa: BLE001
            error = _error_text(exc)
    return {
        "regra": rule,
        "resultado": root["valor"],
        "atendido": matched,
        "erro": error,
        "raiz": root,
    }
