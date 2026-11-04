"""Template tags do desenho em blocos da explicação de regras.

Uso::

    {% load static rule_blocks %}
    <link rel="stylesheet" href="{% static 'rule_widget/rule_blocks.css' %}">
    {% regra_em_blocos explicacao %}

``explicacao`` é o ``dict`` devolvido por ``django_rule_engine.explain_tree.explain_tree``.
"""

from django import template

from django_rule_engine.blocks import render_blocks

register = template.Library()


@register.simple_tag
def regra_em_blocos(explicacao):
    """HTML dos blocos (texto escapado) da explicação em árvore."""
    return render_blocks(explicacao)
