"""Testes do desenho em blocos (django_rule_engine.blocks e template tag regra_em_blocos)."""

import json
import pathlib

import pytest
from django.template import Context, Template

from django_rule_engine.blocks import count_comparisons, format_value, model, render_blocks, state
from django_rule_engine.explain_tree import explain_tree

CASOS = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "blocos.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("caso", CASOS, ids=[c["nome"] for c in CASOS])
def test_modelo_igual_ao_da_fixture_compartilhada_com_o_js(caso):
    # Se falhar após mudar o desenho, regere com: python tests/gerar_fixture_blocos.py
    assert model(caso["explicacao"]) == caso["modelo"]


def test_estado_e_formatacao_de_valores():
    assert [state(True), state(False), state(None)] == ["sim", "nao", "indef"]
    assert format_value(None) == "nulo"
    assert format_value(True) == "verdadeiro"
    assert format_value(False) == "falso"
    assert format_value(2.0) == "2"
    assert format_value(1.5) == "1.5"
    assert format_value(["a", 1, None]) == "[a, 1, nulo]"
    assert format_value({"a": "é", "b": [1]}) == '{"a":"é","b":[1]}'


def test_contagem_de_comparacoes_nao_desce_nos_lados():
    exp = explain_tree("a == 1 and (b == 2 or c in [3])", {"a": 1, "b": 0, "c": 3})
    assert count_comparisons(exp["raiz"]) == {"atendidas": 2, "total": 3}


def test_html_escapa_texto_e_marca_estados():
    exp = explain_tree("nome == '<b>x</b>' and cpf == '1'", {"nome": "<script>", "cpf": "1"})
    html = render_blocks(exp)
    assert html.startswith('<div class="dre-blocos dre-nao">')
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert 'class="dre-valor dre-oculto"' in html
    assert 'class="dre-bloco dre-tipo-logico dre-nao"' in html
    assert "todas estas condições" in html


def test_item_mais_perto_vem_aberto():
    exp = explain_tree("$any([v > 5 for v in vs])", {"vs": [1, 4]})
    html = render_blocks(exp)
    assert html.count("<details") == 2
    assert html.count(' open=""') == 1
    assert "mais perto" in html


def test_explicacao_vazia_ou_com_erro():
    assert render_blocks(None) == '<div class="dre-blocos dre-indef"></div>'
    html = render_blocks(explain_tree("idade >="))
    assert 'class="dre-erro"' in html and "RuleSyntaxError" in html


def test_template_tag():
    exp = explain_tree("idade >= 18", {"idade": 20})
    html = Template("{% load rule_blocks %}{% regra_em_blocos explicacao %}").render(
        Context({"explicacao": exp})
    )
    assert html == render_blocks(exp)
    assert 'class="dre-blocos dre-sim"' in html
