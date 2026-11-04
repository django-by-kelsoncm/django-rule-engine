"""Desenho em blocos (estilo Scratch) da explicação em árvore de uma regra.

Gera o mesmo modelo de elementos que ``static/rule_widget/rule_blocks.js`` (``RuleBlocks.modelo``),
então o HTML do servidor (template tag ``regra_em_blocos``) e o do navegador são iguais.

Exemplo::

    from django_rule_engine.blocks import render_blocks
    from django_rule_engine.explain_tree import explain_tree

    html = render_blocks(explain_tree(regra, contexto))  # SafeString, texto escapado

Inclua ``rule_widget/rule_blocks.css`` na página para as cores e o encaixe dos blocos.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

__all__ = [
    "OPERATOR_LABELS",
    "BLOCKS_CSS",
    "BLOCKS_JS",
    "model",
    "render_blocks",
    "state",
    "format_value",
]

#: Arquivos estáticos do desenho em blocos.
BLOCKS_CSS = "rule_widget/rule_blocks.css"
BLOCKS_JS = "rule_widget/rule_blocks.js"

#: Texto exibido para cada operador de comparação.
OPERATOR_LABELS = {
    "==": "=",
    "!=": "≠",
    "<": "<",
    "<=": "≤",
    ">": ">",
    ">=": "≥",
    "=~": "casa com",
    "=~~": "contém o padrão",
    "!~": "não casa com",
    "!~~": "não contém o padrão",
    "in": "está em",
    "not in": "não está em",
}
_LOGIC = {"and": "todas estas condições", "or": "alguma destas condições"}
_FUNCTIONS = {"$any": "pelo menos um é verdadeiro", "$all": "todos são verdadeiros"}
_ICONS = {"sim": "✓", "nao": "✗", "indef": "?"}
_TITLES = {"sim": "Atendido", "nao": "Não atendido", "indef": "Indefinido"}
_COMPOUND = ("logico", "nao", "funcao", "compreensao", "ternario")

Model = Dict[str, Any]


def state(matched: Any) -> str:
    """``sim``, ``nao`` ou ``indef``."""
    if matched is True:
        return "sim"
    if matched is False:
        return "nao"
    return "indef"


def format_value(value: Any) -> str:
    """Valor como texto, igual a ``RuleBlocks.formatarValor``."""
    if value is None:
        return "nulo"
    if value is True:
        return "verdadeiro"
    if value is False:
        return "falso"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, list):
        return "[" + ", ".join(format_value(v) for v in value) + "]"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def count_comparisons(node: Any) -> Dict[str, int]:
    """Comparações atendidas e totais da subárvore (sem descer nos lados das comparações)."""
    count = {"atendidas": 0, "total": 0}

    def visit(n: Any) -> None:
        if isinstance(n, list):
            for v in n:
                visit(v)
            return
        if not isinstance(n, dict):
            return
        if n.get("tipo") in ("comparacao", "contem"):
            count["total"] += 1
            if n.get("atendido") is True:
                count["atendidas"] += 1
            return
        for v in n.values():
            visit(v)

    visit(node)
    return count


def _e(
    tag: str, classe: str = "", texto: Optional[str] = None, filhos=None, atributos=None
) -> Model:
    return {
        "tag": tag,
        "classe": classe,
        "texto": texto,
        "atributos": atributos or {},
        "filhos": filhos or [],
    }


def _icon(matched: Any) -> Model:
    st = state(matched)
    return _e(
        "span", "dre-icone", _ICONS[st], [], {"title": _TITLES[st], "aria-label": _TITLES[st]}
    )


def _value(node: Dict[str, Any]) -> Model:
    if node.get("sensivel"):
        return _e(
            "span",
            "dre-valor dre-oculto",
            "oculto",
            [],
            {"title": "Campo sensível: valor não exibido"},
        )
    return _e("span", "dre-valor", format_value(node.get("valor")))


def _term(node: Dict[str, Any]) -> List[Model]:
    if node["tipo"] == "campo":
        return [_e("span", "dre-rotulo", node["rotulo"]), _value(node)]
    if node["tipo"] == "literal":
        return [_value(node)]
    return [_e("code", "dre-trecho", node["trecho"]), _value(node)]


def _block(
    node: Dict[str, Any], head: List[Model], children: Optional[List[Model]] = None
) -> Model:
    classe = f"dre-bloco dre-tipo-{node['tipo']} dre-{state(node.get('atendido'))}"
    parts = [_e("div", "dre-cabeca", None, [_icon(node.get("atendido"))] + head)]
    if node.get("erro"):
        parts.append(_e("div", "dre-erro", node["erro"]))
    if children:
        parts.append(_e("div", "dre-filhos", None, children))
    return _e("div", classe, None, parts)


def _branch(title: str, node: Optional[Dict[str, Any]]) -> Model:
    return _e("div", "dre-ramo", None, [_e("span", "dre-titulo", title), _node(node)])


def _item(node: Dict[str, Any], it: Dict[str, Any]) -> Model:
    summary = [_icon(it.get("atendido")), _e("span", "dre-titulo", f"item {it['indice']}")]
    if it.get("rotulo"):
        summary.append(_e("span", "dre-rotulo", it["rotulo"]))
    if not it.get("incluido"):
        summary.append(_e("span", "dre-meta", "fora do filtro"))
    else:
        count = count_comparisons(it.get("expressao"))
        if count["total"]:
            summary.append(_e("span", "dre-meta", f"{count['atendidas']} de {count['total']}"))
    best = it["indice"] == node.get("melhor_item")
    if best:
        summary.append(
            _e(
                "span",
                "dre-meta dre-destaque",
                "atende" if it.get("atendido") is True else "mais perto",
            )
        )
    body = []
    if it.get("filtro"):
        body.append(_branch("se", it["filtro"]))
    body.append(_node(it.get("expressao")))
    return _e(
        "details",
        f"dre-bloco dre-tipo-item dre-{state(it.get('atendido'))}",
        None,
        [_e("summary", "dre-cabeca", None, summary), _e("div", "dre-filhos", None, body)],
        {"open": ""} if best else {},
    )


def _node(node: Optional[Dict[str, Any]]) -> Model:
    if not node:
        return _e("div", "dre-bloco dre-tipo-expressao dre-indef")
    tipo = node["tipo"]
    if tipo == "logico":
        head = [_e("span", "dre-titulo", _LOGIC.get(node["operador"], node["operador"]))]
        return _block(node, head, [_node(n) for n in node["filhos"]])
    if tipo == "nao":
        return _block(node, [_e("span", "dre-titulo", "não é verdade que")], [_node(node["filho"])])
    if tipo in ("comparacao", "contem"):
        head = (
            _term(node["esquerda"])
            + [_e("span", "dre-op", OPERATOR_LABELS.get(node["operador"], node["operador"]))]
            + _term(node["direita"])
        )
        children = [_node(n) for n in (node["esquerda"], node["direita"]) if n["tipo"] in _COMPOUND]
        return _block(node, head, children)
    if tipo == "funcao":
        title = _FUNCTIONS.get(node["nome"], f"{node['nome']}(…)")
        return _block(
            node,
            [_e("span", "dre-titulo", title), _value(node)],
            [_node(a) for a in node["argumentos"]],
        )
    if tipo == "compreensao":
        head = [
            _e("span", "dre-titulo", f"para cada {node['variavel']} em"),
            _e("span", "dre-rotulo", node["lista"].get("rotulo") or node["lista"]["trecho"]),
        ]
        if node.get("total") is not None:
            head.append(
                _e(
                    "span",
                    "dre-meta",
                    f"{node['total']} {'item' if node['total'] == 1 else 'itens'}",
                )
            )
        if node.get("filtro"):
            head += [_e("span", "dre-meta", "se"), _e("code", "dre-trecho", node["filtro"])]
        children = [_item(node, it) for it in node["itens"]]
        if node.get("truncado"):
            hidden = node["total"] - len(node["itens"])
            children.append(_e("div", "dre-meta", f"mais {hidden} itens não exibidos"))
        return _block(node, head, children)
    if tipo == "ternario":
        return _block(
            node,
            [_e("span", "dre-titulo", "se… então… senão"), _value(node)],
            [
                _branch("se", node["condicao"]),
                _branch("então", node["se_verdadeiro"]),
                _branch("senão", node["se_falso"]),
            ],
        )
    if tipo == "campo":
        return _block(node, _term(node))
    return _block(node, [_e("code", "dre-trecho", node["trecho"]), _value(node)])


def model(explanation: Optional[Dict[str, Any]]) -> Model:
    """Modelo de elementos (igual a ``RuleBlocks.modelo``) da explicação de ``explain_tree``."""
    explanation = explanation or {}
    children = []
    if explanation.get("raiz"):
        children.append(_node(explanation["raiz"]))
    elif explanation.get("erro"):
        children.append(_e("div", "dre-erro", explanation["erro"]))
    return _e("div", f"dre-blocos dre-{state(explanation.get('atendido'))}", None, children)


def _html(m: Model) -> str:
    attrs = ""
    if m["classe"]:
        attrs += f' class="{escape(m["classe"])}"'
    for key, value in m["atributos"].items():
        attrs += f' {escape(key)}="{escape(value)}"'
    inner = escape(m["texto"]) if m["texto"] is not None else ""
    inner += "".join(_html(f) for f in m["filhos"])
    return f"<{m['tag']}{attrs}>{inner}</{m['tag']}>"


def render_blocks(explanation: Optional[Dict[str, Any]]) -> SafeString:
    """HTML dos blocos da explicação de :func:`django_rule_engine.explain_tree.explain_tree`."""
    return mark_safe(_html(model(explanation)))  # nosec B703 B308 - todo texto passa por escape()
