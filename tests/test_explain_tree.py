"""Testes da explicação em árvore (django_rule_engine.explain_tree)."""

import datetime

import pytest

import rule_engine
from django_rule_engine.explain_tree import explain_tree, unparse

# ``??``, bytes e operações bit a bit sobre símbolos sem tipo só existem no rule-engine 5.
REQUER_RULE_ENGINE_5 = pytest.mark.skipif(
    int(rule_engine.__version__.split(".")[0]) < 5, reason="recurso da gramática do rule-engine 5"
)

REGRA_MATRICULA = (
    "tipo_usuario in ['Aluno'] and $any([m['tipo'] == 'aluno' and m['detalhamento']['ativo'] == true"
    " and m['detalhamento']['modalidade'] in ['Técnico integrado ao ensino médio']"
    " for m in outras_matriculas])"
)
CONTEXTO_MATRICULA = {
    "tipo_usuario": "Aluno",
    "outras_matriculas": [
        {
            "identificador": "M-0001",
            "tipo": "aluno",
            "cpf": "000.000.000-00",
            "detalhamento": {"ativo": True, "modalidade": "Técnico Integrado"},
        },
        {
            "identificador": "M-0002",
            "tipo": "aluno",
            "detalhamento": {"ativo": False, "modalidade": "FIC"},
        },
    ],
}


def _filhos(no):
    return no["filhos"]


def test_regra_vazia_e_regra_invalida():
    assert explain_tree("")["erro"] == "Regra vazia"
    invalida = explain_tree("idade >=")
    assert invalida["raiz"] is None
    assert invalida["atendido"] is None
    assert invalida["erro"].startswith("RuleSyntaxError")


def test_cadeia_de_and_vira_um_no_com_varios_filhos():
    exp = explain_tree("a == 1 and b == 2 and c == 3", {"a": 1, "b": 0, "c": 3})
    raiz = exp["raiz"]
    assert exp["atendido"] is False
    assert raiz["tipo"] == "logico" and raiz["operador"] == "and"
    assert [f["atendido"] for f in _filhos(raiz)] == [True, False, True]
    esquerda, direita = _filhos(raiz)[1]["esquerda"], _filhos(raiz)[1]["direita"]
    assert (esquerda["tipo"], esquerda["rotulo"], esquerda["valor"]) == ("campo", "b", 0)
    assert (direita["tipo"], direita["valor"]) == ("literal", 2)


def test_and_e_or_misturados_e_not_em_qualquer_profundidade():
    exp = explain_tree(
        "a and not (b or c > 2) and (d ? e : f)",
        {"a": True, "b": False, "c": 1, "d": False, "e": False, "f": True},
    )
    raiz = exp["raiz"]
    assert exp["atendido"] is True
    a, nao, ternario = _filhos(raiz)
    assert a["tipo"] == "campo" and a["atendido"] is True
    assert nao["tipo"] == "nao" and nao["atendido"] is True
    ou = nao["filho"]
    assert ou["operador"] == "or" and ou["atendido"] is False
    assert [f["atendido"] for f in _filhos(ou)] == [False, False]
    assert ternario["tipo"] == "ternario"
    assert ternario["condicao"]["valor"] is False
    assert ternario["se_falso"]["valor"] is True


def test_compreensao_detalha_cada_item_e_aponta_o_melhor():
    exp = explain_tree(REGRA_MATRICULA, CONTEXTO_MATRICULA)
    assert exp["atendido"] is False
    contem, funcao = _filhos(exp["raiz"])
    assert contem["tipo"] == "contem" and contem["atendido"] is True
    assert funcao["tipo"] == "funcao" and funcao["nome"] == "$any"
    comp = funcao["argumentos"][0]
    assert comp["tipo"] == "compreensao"
    assert (comp["variavel"], comp["total"], comp["truncado"]) == ("m", 2, False)
    assert comp["lista"]["valor"] is None  # os itens aparecem em "itens"
    primeiro, segundo = comp["itens"]
    assert (primeiro["rotulo"], segundo["rotulo"]) == ("M-0001", "M-0002")
    assert [f["atendido"] for f in _filhos(primeiro["expressao"])] == [True, True, False]
    assert [f["atendido"] for f in _filhos(segundo["expressao"])] == [True, False, False]
    assert comp["melhor_item"] == 0
    modalidade = _filhos(primeiro["expressao"])[2]
    assert modalidade["esquerda"]["rotulo"] == "m.detalhamento.modalidade"
    assert modalidade["esquerda"]["valor"] == "Técnico Integrado"
    assert modalidade["direita"]["valor"] == ["Técnico integrado ao ensino médio"]


def test_melhor_item_e_o_primeiro_que_atende():
    exp = explain_tree("$any([v > 2 for v in vs])", {"vs": [1, 3, 5]})
    comp = exp["raiz"]["argumentos"][0]
    assert exp["atendido"] is True
    assert comp["melhor_item"] == 1


def test_compreensao_com_filtro_marca_itens_fora_do_filtro():
    exp = explain_tree("$all([v > 0 for v in vs if v != 0])", {"vs": [0, 2]})
    comp = exp["raiz"]["argumentos"][0]
    assert comp["filtro"] == "v != 0"
    fora, dentro = comp["itens"]
    assert fora["incluido"] is False and fora["atendido"] is None
    assert dentro["incluido"] is True and dentro["atendido"] is True
    assert comp["melhor_item"] == 1


def test_compreensao_aninhada():
    exp = explain_tree(
        "$any([$all([n > 5 for n in g['notas']]) for g in grupos])",
        {"grupos": [{"nome": "A", "notas": [6, 4]}, {"nome": "B", "notas": [7, 8]}]},
    )
    comp = exp["raiz"]["argumentos"][0]
    assert exp["atendido"] is True
    assert [i["rotulo"] for i in comp["itens"]] == ["A", "B"]
    interna = comp["itens"][0]["expressao"]["argumentos"][0]
    assert [i["atendido"] for i in interna["itens"]] == [True, False]


def test_compreensao_truncada():
    exp = explain_tree("$any([v == 99 for v in vs])", {"vs": list(range(10))}, max_items=3)
    comp = exp["raiz"]["argumentos"][0]
    assert (len(comp["itens"]), comp["total"], comp["truncado"]) == (3, 10, True)


@pytest.mark.parametrize(
    "item_label,esperado",
    [
        ("nome", ["Ana", "Bia"]),
        (("x", "nome"), ["Ana", "Bia"]),
        (lambda item: item["nome"].upper(), ["ANA", "BIA"]),
        (lambda item: 1 / 0, ["", ""]),
    ],
)
def test_rotulo_dos_itens(item_label, esperado):
    exp = explain_tree(
        "$any([p['idade'] > 1 for p in pessoas])",
        {"pessoas": [{"nome": "Ana", "idade": 1}, {"nome": "Bia", "idade": 2}]},
        item_label=item_label,
    )
    assert [i["rotulo"] for i in exp["raiz"]["argumentos"][0]["itens"]] == esperado


def test_rotulo_de_item_escalar_e_lista_sensivel():
    escalar = explain_tree("$any([v > 1 for v in vs])", {"vs": [1, 2]})
    assert [i["rotulo"] for i in escalar["raiz"]["argumentos"][0]["itens"]] == ["1", "2"]
    sensivel = explain_tree("$any([e =~ '.*@x' for e in emails])", {"emails": ["a@x"]})
    assert sensivel["raiz"]["argumentos"][0]["itens"][0]["rotulo"] == ""


def test_campos_sensiveis_sao_mascarados_inclusive_aninhados():
    exp = explain_tree(
        "cpf == '1' and pessoa['nome'] == 'Ana' and pessoa != null",
        {"cpf": "1", "pessoa": {"nome": "Ana", "email": "a@x"}},
    )
    cpf, nome, pessoa = _filhos(exp["raiz"])
    assert cpf["esquerda"]["sensivel"] is True and cpf["esquerda"]["valor"] is None
    assert cpf["atendido"] is True  # o resultado continua sendo informado
    assert nome["esquerda"]["valor"] == "Ana"
    assert pessoa["esquerda"]["valor"] == {"nome": "Ana", "email": None}
    tudo = explain_tree("cpf == '1'", {"cpf": "1"}, sensitive=None)
    assert tudo["raiz"]["esquerda"]["valor"] == "1"


def test_erro_de_avaliacao_fica_no_no():
    exp = explain_tree("a == 1 or b['x'] == 2", {"a": 1, "b": None})
    raiz = exp["raiz"]
    assert exp["atendido"] is True
    _, b = _filhos(raiz)
    assert b["atendido"] is None
    assert b["erro"]


def test_simbolo_inexistente():
    exp = explain_tree("x > 1", {})
    assert exp["atendido"] is None
    assert exp["erro"].startswith("SymbolResolutionError")
    assert exp["raiz"]["esquerda"]["erro"]


@REQUER_RULE_ENGINE_5
def test_aritmetica_contem_e_expressao():
    exp = explain_tree(
        "-a + b * 2 > 1 and 'x' not in nomes and s[0:2] == 'ab' and (c ?? 3) == 3",
        {"a": 1, "b": 2, "nomes": ["y"], "s": "abc", "c": None},
    )
    soma, contem, fatia, coalesce = _filhos(exp["raiz"])
    assert soma["esquerda"]["tipo"] == "aritmetica" and soma["esquerda"]["valor"] == 3
    assert (
        contem["tipo"] == "contem" and contem["operador"] == "not in" and contem["atendido"] is True
    )
    assert fatia["esquerda"]["tipo"] == "expressao" and fatia["esquerda"]["valor"] == "ab"
    assert coalesce["atendido"] is True
    assert exp["atendido"] is True


@pytest.mark.parametrize(
    "regra",
    [
        "a == 1 and (b == 2 or c == 3)",
        "not (a in [1, 2.5, 'x', true, null])",
        "a.b&.c == m['k'][0] and s&[1:] =~ 'x' and t !~~ 'y'",
        pytest.param(
            "(a + b) * c ** 2 // 3 % 2 - -d >= 1 and e & 1 | f ^ 2 << 1 >> 1 == 0",
            marks=REQUER_RULE_ENGINE_5,
        ),
        "[v * 2 for v in vs if v > 1] == [4] and {'k': 1}['k'] == k and {1, 2} == s",
        "a ? b : c ? d : e",
        pytest.param(
            "x =~~ 'a\\'b' and d > d'2024-01-02T03:04:05' and t > t'P1DT2H' and b == b'ab'",
            marks=REQUER_RULE_ENGINE_5,
        ),
    ],
)
def test_unparse_gera_regra_equivalente(regra):
    original = rule_engine.Rule(regra)
    regerada = unparse(original.statement.expression)
    assert unparse(rule_engine.Rule(regerada).statement.expression) == regerada


def test_unparse_de_valores_literais():
    exp = explain_tree("x == 1.5 and y == null and z == false", {"x": 1.5, "y": None, "z": False})
    assert exp["raiz"]["trecho"] == "x == 1.5 and y == null and z == false"
    assert (
        explain_tree(
            "d < d'2024-01-01'", {"d": datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc)}
        )["atendido"]
        is True
    )
