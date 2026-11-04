"""Testes de django_rule_engine.explain."""

import datetime
import json
import re
from decimal import Decimal

import pytest

from django_rule_engine.explain import (
    DEFAULT_SENSITIVE_FIELDS,
    explain,
    field_label,
    parse_comprehension,
    split_comparison,
    split_conditions,
    to_json,
)

REGRA_IFRN = (
    "tipo_usuario in ['Aluno'] and $any([m['tipo'] == 'aluno'"
    " and m['detalhamento']['ativo'] == true"
    " and m['detalhamento']['modalidade'] in ['Técnico integrado ao ensino médio']"
    " for m in outras_matriculas])"
)


def _matricula(tipo, ativo, modalidade):
    return {"tipo": tipo, "detalhamento": {"ativo": ativo, "modalidade": modalidade}}


# --- split_conditions --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "regra, partes",
    [
        ("a == 1 and b == 2", ["a == 1", "b == 2"]),
        ("a == 1 or b == 2 or c", ["a == 1", "b == 2", "c"]),
        ("(a == 1 and b == 2)", ["a == 1", "b == 2"]),
        ("((a == 1) and (b or c))", ["(a == 1)", "(b or c)"]),
        ("x == 'cats and dogs' and y", ["x == 'cats and dogs'", "y"]),
        ('x == "a or b" or y', ['x == "a or b"', "y"]),
        ("x in ['and', 'or'] and y", ["x in ['and', 'or']", "y"]),
        ("brand == 1 and ordem == 2", ["brand == 1", "ordem == 2"]),
        ("x == 'it\\'s and' and y", ["x == 'it\\'s and'", "y"]),
    ],
)
def test_split_conditions_divide_no_nivel_superior(regra, partes):
    assert split_conditions(regra) == partes


@pytest.mark.parametrize(
    "regra",
    [
        "a == 1",
        "a and b or c",  # operadores misturados: sem divisão confiável
        "(a and b)  or c and d",
        "$any([x and y for x in l])",
        "",
    ],
)
def test_split_conditions_sem_divisao(regra):
    assert split_conditions(regra) == []


# --- split_comparison --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "atomo, esperado",
    [
        ("idade >= 18", ("idade", ">=", "18")),
        ("idade <= 18", ("idade", "<=", "18")),
        ("idade > 18", ("idade", ">", "18")),
        ("idade < 18", ("idade", "<", "18")),
        ("a == 'x'", ("a", "==", "'x'")),
        ("a != 'x'", ("a", "!=", "'x'")),
        ("email =~ '.*@ifrn'", ("email", "=~", "'.*@ifrn'")),
        ("email =~~ 'ifrn'", ("email", "=~~", "'ifrn'")),
        ("email !~ 'x'", ("email", "!~", "'x'")),
        ("email !~~ 'x'", ("email", "!~~", "'x'")),
        ("tipo in ['Aluno']", ("tipo", "in", "['Aluno']")),
        ("tipo not in ['Aluno']", ("tipo", "not in", "['Aluno']")),
        ("tipo not   in ['A']", ("tipo", "not in", "['A']")),
        ("m['a'] == 'x == y'", ("m['a']", "==", "'x == y'")),
        ("'@ifrn' in email", ("'@ifrn'", "in", "email")),
        ("f(a == b) == true", ("f(a == b)", "==", "true")),
        ("index == 1", ("index", "==", "1")),
    ],
)
def test_split_comparison(atomo, esperado):
    assert split_comparison(atomo) == esperado


@pytest.mark.parametrize("atomo", ["ativo", "not ativo", "$any([x == 1 for x in l])", "insc"])
def test_split_comparison_sem_operador(atomo):
    assert split_comparison(atomo) is None


# --- parse_comprehension -----------------------------------------------------------------------


def test_parse_comprehension_qualquer_lista():
    comp = parse_comprehension("$all([v['ok'] == true for v in dados['vinculos']])")
    assert comp == {
        "funcao": "all",
        "expressao": "v['ok'] == true",
        "variavel": "v",
        "lista": "dados['vinculos']",
        "filtro": "",
    }


def test_parse_comprehension_com_filtro_e_parenteses():
    comp = parse_comprehension("($any([x > 1 for x in itens if x != 'for x in y']))")
    assert comp["lista"] == "itens"
    assert comp["filtro"] == "x != 'for x in y'"
    assert comp["expressao"] == "x > 1"


@pytest.mark.parametrize(
    "texto",
    [
        "$any(lista)",
        "$any([x for x in a]) and $all([y for y in b])",
        "$len([x for x in a])",
        "[x for x in a]",
    ],
)
def test_parse_comprehension_nao_reconhece(texto):
    assert parse_comprehension(texto) is None


def test_field_label():
    assert field_label("m['detalhamento']['modalidade']", "m") == "detalhamento.modalidade"
    assert field_label('m["tipo"]', "m") == "tipo"
    assert field_label("m.tipo", "m") == "tipo"
    assert field_label("usuario['nome']") == "usuario.nome"


# --- to_json -----------------------------------------------------------------------------------


def test_to_json_converte_tipos_do_rule_engine():
    valor = {
        "inteiro": Decimal("2"),
        "real": Decimal("1.5"),
        "tupla": (Decimal("1"), "a"),
        "data": datetime.date(2026, 11, 4),
        "conjunto": frozenset({"b", "a"}),
        "bytes": b"x",
        1: None,
    }
    convertido = to_json(valor)
    assert convertido == {
        "inteiro": 2,
        "real": 1.5,
        "tupla": [1, "a"],
        "data": "2026-11-04",
        "conjunto": ["a", "b"],
        "bytes": "x",
        "1": None,
    }
    json.dumps(convertido)


# --- explain: regras simples -------------------------------------------------------------------


def test_explain_simples_atendido_e_nao_atendido():
    exp = explain("idade >= 18 and status == 'ativo'", {"idade": 16, "status": "ativo"})
    assert exp["atendido"] is False and exp["resultado"] is False and exp["erro"] == ""
    assert exp["operador"] == "and"
    idade, status = exp["condicoes"]
    assert idade["atendido"] is False
    linha = idade["detalhes"]["linhas"][0]
    assert (linha["campo"], linha["operador"], linha["esperado"], linha["valor"]) == (
        "idade",
        ">=",
        "18",
        16,
    )
    assert status["atendido"] is True
    assert status["detalhes"]["linhas"][0]["valor"] == "ativo"
    json.dumps(exp)


def test_explain_regra_sem_divisao_tem_uma_condicao():
    exp = explain("idade >= 18", {"idade": 20})
    assert exp["operador"] == ""
    assert [c["condicao"] for c in exp["condicoes"]] == ["idade >= 18"]
    assert exp["atendido"] is True


def test_explain_atomo_sem_comparacao_espera_verdadeiro():
    exp = explain("ativo or admin", {"ativo": False, "admin": True})
    assert exp["operador"] == "or" and exp["atendido"] is True
    linha = exp["condicoes"][0]["detalhes"]["linhas"][0]
    assert (linha["operador"], linha["esperado"], linha["valor"]) == ("", "verdadeiro", False)


def test_explain_condicao_entre_parenteses_detalha_cada_comparacao():
    exp = explain("idade >= 18 and (a == 1 or b == 2)", {"idade": 20, "a": 0, "b": 2})
    detalhes = exp["condicoes"][1]["detalhes"]
    assert [linha["atomo"] for linha in detalhes["linhas"]] == ["a == 1", "b == 2"]
    assert [linha["atendido"] for linha in detalhes["linhas"]] == [False, True]
    assert exp["condicoes"][1]["atendido"] is True


def test_explain_decimal_vira_numero():
    exp = explain("nota > 7", {"nota": 7.5})
    assert exp["condicoes"][0]["detalhes"]["linhas"][0]["valor"] == 7.5


# --- explain: erros ----------------------------------------------------------------------------


def test_explain_campo_inexistente_atendido_null():
    exp = explain("idade >= 18 and curso == 'x'", {"idade": 20})
    assert exp["atendido"] is None
    assert "SymbolResolutionError" in exp["erro"]
    idade, curso = exp["condicoes"]
    assert idade["atendido"] is True
    assert curso["atendido"] is None
    linha = curso["detalhes"]["linhas"][0]
    assert linha["atendido"] is None and "curso" in linha["erro"]


def test_explain_regra_que_nao_compila():
    exp = explain("idade >>= 18", {"idade": 20})
    assert exp["atendido"] is None
    assert exp["erro"]
    json.dumps(exp)


def test_explain_regra_vazia():
    exp = explain("   ", {})
    assert exp["erro"] == "Regra vazia" and exp["condicoes"] == []


def test_explain_tipo_incompativel():
    exp = explain("idade > 'x'", {"idade": 1})
    assert exp["atendido"] is None
    assert exp["condicoes"][0]["detalhes"]["linhas"][0]["valor"] == 1


# --- explain: compreensões ---------------------------------------------------------------------


def test_explain_compreensao_any_regra_real():
    contexto = {
        "tipo_usuario": "Aluno",
        "outras_matriculas": [
            _matricula("aluno", True, "Subsequente"),
            _matricula("aluno", False, "Técnico integrado ao ensino médio"),
        ],
    }
    exp = explain(REGRA_IFRN, contexto)
    assert exp["atendido"] is False
    tipo, compreensao = exp["condicoes"]
    assert tipo["atendido"] is True
    assert compreensao["atendido"] is False
    detalhes = compreensao["detalhes"]
    assert detalhes["tipo"] == "por_item"
    assert (detalhes["funcao"], detalhes["variavel"], detalhes["lista"], detalhes["itens"]) == (
        "any",
        "m",
        "outras_matriculas",
        2,
    )
    rotulos = [linha["rotulo"] for linha in detalhes["linhas"]]
    assert rotulos == ["tipo", "detalhamento.ativo", "detalhamento.modalidade"]
    ativo = detalhes["linhas"][1]
    assert ativo["valores"] == [True, False]
    assert ativo["resultados"] == [True, False]
    assert ativo["atendido"] is True  # algum item atende este trecho
    modalidade = detalhes["linhas"][2]
    assert modalidade["valores"] == ["Subsequente", "Técnico integrado ao ensino médio"]
    assert modalidade["resultados"] == [False, True]


def test_explain_compreensao_all_lista_qualquer():
    contexto = {"pedido": {"itens": [{"qtd": 2}, {"qtd": 0}]}}
    exp = explain("$all([i['qtd'] > 0 for i in pedido['itens']])", contexto)
    assert exp["atendido"] is False
    detalhes = exp["condicoes"][0]["detalhes"]
    assert detalhes["lista"] == "pedido['itens']" and detalhes["funcao"] == "all"
    linha = detalhes["linhas"][0]
    assert linha["rotulo"] == "qtd"
    assert linha["valores"] == [2, 0]
    assert linha["resultados"] == [True, False]
    assert linha["atendido"] is False


def test_explain_compreensao_com_filtro():
    contexto = {"notas": [{"n": 9, "ok": True}, {"n": 3, "ok": False}]}
    exp = explain("$all([x['n'] >= 6 for x in notas if x['ok']])", contexto)
    assert exp["atendido"] is True
    detalhes = exp["condicoes"][0]["detalhes"]
    assert detalhes["filtro"] == "x['ok']" and detalhes["itens"] == 1
    assert detalhes["linhas"][0]["valores"] == [9]


def test_explain_compreensao_lista_vazia():
    exp = explain(
        "$any([m['tipo'] == 'aluno' for m in outras_matriculas])", {"outras_matriculas": []}
    )
    assert exp["atendido"] is False
    detalhes = exp["condicoes"][0]["detalhes"]
    assert detalhes["itens"] == 0
    assert detalhes["linhas"][0]["valores"] == []
    assert detalhes["linhas"][0]["atendido"] is False


def test_explain_compreensao_lista_inexistente():
    exp = explain("$any([m['tipo'] == 'aluno' for m in outras_matriculas])", {})
    assert exp["atendido"] is None
    detalhes = exp["condicoes"][0]["detalhes"]
    assert detalhes["itens"] is None and "outras_matriculas" in detalhes["erro"]
    assert detalhes["linhas"][0]["atendido"] is None


def test_explain_compreensao_chave_ausente_em_um_item():
    contexto = {"ms": [{"tipo": "aluno"}, {}]}
    exp = explain("$any([m['tipo'] == 'aluno' for m in ms])", contexto)
    linha = exp["condicoes"][0]["detalhes"]["linhas"][0]
    assert linha["atendido"] is None and linha["erro"]


# --- explain: campos sensíveis -----------------------------------------------------------------


def test_explain_oculta_campos_sensiveis_por_padrao():
    contexto = {"cpf": "123", "email": "a@b.c", "ms": [{"email": "x@y"}]}
    exp = explain(
        "cpf == '123' and email =~ '.*@b.c' and $any([m['email'] != '' for m in ms])", contexto
    )
    cpf, email, comp = exp["condicoes"]
    linha_cpf = cpf["detalhes"]["linhas"][0]
    assert linha_cpf["sensivel"] is True and linha_cpf["valor"] is None
    assert linha_cpf["atendido"] is True  # o resultado da comparação continua visível
    assert email["detalhes"]["linhas"][0]["valor"] is None
    linha_comp = comp["detalhes"]["linhas"][0]
    assert linha_comp["valores"] is None and linha_comp["resultados"] == [True]
    texto = json.dumps(exp)
    assert 'a@b.c"' not in texto.replace("'.*@b.c'", "")
    assert "x@y" not in texto
    assert '"123"' not in texto


def test_explain_sensiveis_configuravel():
    contexto = {"cpf": "123", "salario": 10}
    exp = explain("cpf == '123' and salario > 5", contexto, sensitive=r"salario")
    cpf, salario = exp["condicoes"]
    assert cpf["detalhes"]["linhas"][0]["valor"] == "123"
    assert salario["detalhes"]["linhas"][0]["valor"] is None

    exp = explain("cpf == '123'", contexto, sensitive=None)
    assert exp["condicoes"][0]["detalhes"]["linhas"][0]["valor"] == "123"

    exp = explain("CPF_aluno == 1", {"CPF_aluno": 1}, sensitive=re.compile("cpf"))
    assert exp["condicoes"][0]["detalhes"]["linhas"][0]["sensivel"] is False


def test_padrao_sensivel_ignora_maiusculas():
    exp = explain("Email_Pessoal == 'x'", {"Email_Pessoal": "x"})
    assert exp["condicoes"][0]["detalhes"]["linhas"][0]["sensivel"] is True
    assert "email" in DEFAULT_SENSITIVE_FIELDS


def test_explain_nao_expoe_mensagem_de_erro_inesperado(monkeypatch):
    from django_rule_engine import explain as modulo

    class Quebrado:
        def evaluate(self, contexto):
            raise RuntimeError("detalhe interno secreto")

        matches = evaluate

    monkeypatch.setattr(modulo, "_compiled", lambda expressao: Quebrado())
    exp = modulo.explain("a == 1", {"a": 1})
    assert exp["erro"] == modulo.UNEXPECTED_ERROR
    assert exp["atendido"] is None
    assert "secreto" not in json.dumps(exp)
