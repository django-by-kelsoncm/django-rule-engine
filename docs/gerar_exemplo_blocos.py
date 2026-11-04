"""Gera o exemplo visual da explicação em blocos usado na documentação (dados fictícios).

    python docs/gerar_exemplo_blocos.py

Saída em docs/_static/blocos/: exemplo.html (página completa, base da imagem), fragmento.html
(incluído no Sphinx) e rule_blocks.css (cópia do CSS do pacote).
"""

import pathlib
import shutil
import sys

import django
from django.conf import settings

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
settings.configure()
django.setup()

from django_rule_engine.blocks import render_blocks  # noqa: E402
from django_rule_engine.explain_tree import explain_tree  # noqa: E402

REGRA = (
    "tipo_usuario in ['Aluno'] and $any([m['tipo'] == 'aluno' and m['detalhamento']['ativo'] == true"
    " and m['detalhamento']['modalidade'] in ['Técnico integrado ao ensino médio']"
    " for m in outras_matriculas])"
)
CONTEXTO = {
    "tipo_usuario": "Aluno",
    "outras_matriculas": [
        {
            "identificador": "M-0001",
            "tipo": "aluno",
            "detalhamento": {"ativo": True, "modalidade": "Técnico Integrado"},
        },
        {
            "identificador": "M-0002",
            "tipo": "aluno",
            "detalhamento": {"ativo": True, "modalidade": "FIC"},
        },
    ],
}
REGRA_2 = "idade >= 18 or (campus in ['ZN', 'CNAT'] and not bloqueado) or cpf == '000'"
CONTEXTO_2 = {"idade": 16, "campus": "ZN", "bloqueado": False, "cpf": "123"}

SAIDA = RAIZ / "docs" / "_static" / "blocos"


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    shutil.copy(
        RAIZ / "src/django_rule_engine/static/rule_widget/rule_blocks.css",
        SAIDA / "rule_blocks.css",
    )
    exemplos = [
        (
            "Regra de autoinscrição com <code>$any</code> sobre uma lista",
            REGRA,
            explain_tree(REGRA, CONTEXTO),
        ),
        (
            "<code>or</code>, <code>and</code>, <code>not</code> e campo sensível",
            REGRA_2,
            explain_tree(REGRA_2, CONTEXTO_2),
        ),
    ]
    partes = []
    for titulo, regra, explicacao in exemplos:
        partes.append(
            f'<div class="dre-exemplo"><p class="dre-exemplo-titulo">{titulo}</p>'
            f"<pre class=\"dre-exemplo-regra\">{regra.replace('<', '&lt;')}</pre>{render_blocks(explicacao)}</div>"
        )
    fragmento = (
        '<link rel="stylesheet" href="_static/blocos/rule_blocks.css">\n<style>'
        ".dre-exemplo{margin:0 0 24px}.dre-exemplo-titulo{margin:0 0 4px;font-weight:600}"
        ".dre-exemplo-regra{margin:0 0 6px;padding:6px 8px;font-size:12px;"
        "white-space:pre-wrap;word-break:break-word}</style>\n" + "\n".join(partes) + "\n"
    )
    (SAIDA / "fragmento.html").write_text(fragmento, encoding="utf-8")
    pagina = (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<link rel="stylesheet" href="rule_blocks.css"><style>'
        "body{margin:0;padding:16px;background:#fff;font-family:system-ui,sans-serif;width:760px}"
        ".dre-exemplo{margin-bottom:18px}.dre-exemplo-titulo{margin:0 0 4px;font-weight:600;font-size:14px}"
        ".dre-exemplo-regra{margin:0 0 6px;padding:6px 8px;background:#f5f5f5;border-radius:6px;"
        "font-size:12px;white-space:pre-wrap;word-break:break-word}"
        "</style></head><body>" + "\n".join(partes) + "</body></html>\n"
    )
    (SAIDA / "exemplo.html").write_text(pagina, encoding="utf-8")
    print("ok", SAIDA)


if __name__ == "__main__":
    main()
