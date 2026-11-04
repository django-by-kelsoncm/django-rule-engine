"""Gera tests/fixtures/blocos.json: explicações em árvore e o modelo de blocos esperado.

O mesmo arquivo é usado pelo teste Python (blocks.model) e pelo teste JS (RuleBlocks.modelo),
garantindo que servidor e navegador desenhem o mesmo HTML. Regerar após mudar o desenho:

    python tests/gerar_fixture_blocos.py
"""

import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "src"), str(RAIZ)]

from django_rule_engine.blocks import model  # noqa: E402
from django_rule_engine.explain_tree import explain_tree  # noqa: E402
from tests.test_explain_tree import CONTEXTO_MATRICULA, REGRA_MATRICULA  # noqa: E402

CASOS = [
    ("matriculas", REGRA_MATRICULA, CONTEXTO_MATRICULA, {}),
    (
        "misturado",
        "idade >= 18 or (campus in ['ZN', 'CNAT'] and not bloqueado) or cpf == '1'",
        {"idade": 16, "campus": "ZN", "bloqueado": False, "cpf": "1"},
        {},
    ),
    ("ternario", "(a ? b : c) and x =~ '^a'", {"a": False, "b": True, "c": True, "x": "abc"}, {}),
    ("filtro", "$all([v > 0 for v in vs if v != 0])", {"vs": [0, 2, -1]}, {}),
    ("truncado", "$any([v == 9 for v in vs])", {"vs": [1, 2, 3, 4]}, {"max_items": 2}),
    ("comparacao_com_compreensao", "[v for v in vs if v > 1] == [2]", {"vs": [1, 2]}, {}),
    ("erro", "a == 1 or b['x'] == 2.5", {"a": 2, "b": None}, {}),
    ("invalida", "idade >=", {}, {}),
]


def main() -> None:
    saida = []
    for nome, regra, contexto, opcoes in CASOS:
        explicacao = explain_tree(regra, contexto, **opcoes)
        saida.append({"nome": nome, "explicacao": explicacao, "modelo": model(explicacao)})
    destino = pathlib.Path(__file__).parent / "fixtures" / "blocos.json"
    destino.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(saida)} casos em {destino}")


if __name__ == "__main__":
    main()
