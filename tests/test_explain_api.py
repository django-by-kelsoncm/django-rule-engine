"""Testes dos endpoints de explicação (explain-rule e validate-rule com explain)."""

import json

import pytest
from django.urls import reverse


def _post(client, nome, corpo, bruto=None):
    return client.post(
        reverse(nome),
        data=bruto if bruto is not None else json.dumps(corpo),
        content_type="application/json",
    )


def test_explain_rule_devolve_explicacao(client):
    resposta = _post(
        client,
        "explain_rule",
        {"rule": "idade >= 18 and cpf == '1'", "data": {"idade": 15, "cpf": "1"}},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["valid"] is True
    exp = corpo["explanation"]
    assert exp["atendido"] is False
    idade, cpf = exp["condicoes"]
    assert idade["detalhes"]["linhas"][0]["valor"] == 15
    assert cpf["detalhes"]["linhas"][0]["valor"] is None  # sensível por padrão


def test_explain_rule_respeita_setting_de_sensiveis(client, settings):
    settings.RULE_ENGINE_EXPLAIN_SENSITIVE_FIELDS = r"idade"
    resposta = _post(
        client,
        "explain_rule",
        {"rule": "idade >= 18 and cpf == '1'", "data": {"idade": 15, "cpf": "1"}},
    )
    idade, cpf = resposta.json()["explanation"]["condicoes"]
    assert idade["detalhes"]["linhas"][0]["valor"] is None
    assert cpf["detalhes"]["linhas"][0]["valor"] == "1"


@pytest.mark.parametrize(
    "corpo, bruto, mensagem",
    [
        (None, "{nao json", "JSON inválido"),
        (None, "[1, 2]", "JSON inválido"),
        ({"rule": "", "data": {}}, None, "Regra não pode ser vazia"),
        ({"rule": "a == 1", "data": [1]}, None, "Dados de exemplo devem ser um objeto JSON"),
        ({"rule": "a >>= 1", "data": {}}, None, "Erro ao compilar regra"),
    ],
)
def test_explain_rule_erros(client, corpo, bruto, mensagem):
    resposta = _post(client, "explain_rule", corpo, bruto)
    assert resposta.status_code == 400
    assert resposta.json() == {"valid": False, "error": mensagem}


def test_explain_rule_so_aceita_post(client):
    assert client.get(reverse("explain_rule")).status_code == 405


def test_validate_rule_com_explain(client):
    resposta = _post(
        client,
        "validate_rule",
        {"rule": "a == 1 or b == 2", "data": {"a": 0, "b": 2}, "explain": True},
    )
    corpo = resposta.json()
    assert corpo["matches"] is True
    assert [c["atendido"] for c in corpo["explanation"]["condicoes"]] == [False, True]


def test_validate_rule_sem_explain_nao_muda_resposta(client):
    resposta = _post(client, "validate_rule", {"rule": "a == 1", "data": {"a": 1}})
    assert "explanation" not in resposta.json()


def test_explain_rule_com_arvore(client):
    resposta = _post(
        client,
        "explain_rule",
        {"rule": "idade >= 18 or cpf == '1'", "data": {"idade": 15, "cpf": "1"}, "tree": True},
    )
    corpo = resposta.json()
    assert corpo["valid"] is True
    arvore = corpo["tree"]
    assert arvore["atendido"] is True
    idade, cpf = arvore["raiz"]["filhos"]
    assert idade["esquerda"]["valor"] == 15
    assert cpf["esquerda"]["valor"] is None  # sensível por padrão


def test_explain_rule_sem_arvore_por_padrao(client):
    corpo = _post(client, "explain_rule", {"rule": "a == 1", "data": {"a": 1}}).json()
    assert "tree" not in corpo


def test_validate_rule_com_explain_tree(client, settings):
    settings.RULE_ENGINE_EXPLAIN_SENSITIVE_FIELDS = ""
    corpo = _post(
        client,
        "validate_rule",
        {"rule": "cpf == '1'", "data": {"cpf": "1"}, "explain_tree": True},
    ).json()
    assert corpo["valid"] is True
    assert corpo["explanation_tree"]["raiz"]["esquerda"]["valor"] == "1"
    assert "explanation" not in corpo
