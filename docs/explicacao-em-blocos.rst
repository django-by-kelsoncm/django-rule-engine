Explicação em árvore e desenho em blocos
========================================

``explain_tree()`` explica **por que** uma regra é (ou não) atendida, nó a nó, para qualquer
regra do ``rule-engine``: ``and``/``or`` misturados, ``not``, compreensões dentro de compreensões,
ternários, funções e aritmética. O resultado pode ser desenhado como **blocos encaixados**, no
estilo Scratch: verde para o que foi atendido, vermelho para o que não foi e cinza para o que
ficou indefinido (erro, valor que não é booleano).

Dois exemplos desenhados pelo template tag (o HTML abaixo é real, não uma imagem):

.. raw:: html
   :file: _static/blocos/fragmento.html

Os dados dos exemplos são fictícios. O fragmento e a imagem usada no README são gerados por
``python docs/gerar_exemplo_blocos.py``.

Explicar a regra
----------------

.. code-block:: python

   from django_rule_engine.explain_tree import explain_tree

   explicacao = explain_tree(
       "tipo_usuario in ['Aluno'] and $any([m['tipo'] == 'aluno' and m['ativo'] == true"
       " for m in matriculas])",
       {"tipo_usuario": "Aluno", "matriculas": [{"identificador": "M-0001", "tipo": "aluno", "ativo": False}]},
   )
   explicacao["atendido"]          # False
   explicacao["raiz"]["tipo"]      # "logico"

A árvore é montada a partir do AST do próprio ``rule_engine`` e cada nó é avaliado com o
``evaluate()`` da biblioteca, sem interpretador paralelo. Funciona com ``rule-engine`` 4.5.3 ou
mais novo.

Parâmetros:

``sensitive``
   Regex (texto ou compilada) dos campos cujo valor não é exibido. Padrão:
   ``DEFAULT_SENSITIVE_FIELDS`` (CPF, RG, e-mail, telefone, senha, token...). Chaves sensíveis
   dentro de dicionários também são ocultadas. ``None`` ou ``""`` exibe tudo.
``max_items``
   Máximo de itens detalhados por compreensão (padrão 50). O resto é contado em ``total`` e o
   nó recebe ``truncado: true``.
``item_label``
   Como rotular cada item de uma compreensão: uma chave (``"nome"``), uma lista de chaves ou uma
   função ``item -> texto``. Padrão: a primeira chave presente entre ``identificador``,
   ``rotulo``, ``nome``, ``name``, ``titulo``, ``title``, ``codigo``, ``code`` e ``id``.

Formato
-------

.. code-block:: text

   {"regra": str, "resultado": Any, "atendido": bool | None, "erro": str, "raiz": nó | None}

Todo nó traz ``tipo``, ``trecho`` (texto do nó, regerado a partir do AST), ``valor`` (resultado
da avaliação, serializável em JSON), ``atendido`` (``true``/``false`` quando o valor é booleano,
senão ``null``) e ``erro`` (vazio quando a avaliação deu certo).

.. list-table::
   :header-rows: 1
   :widths: 18 30 52

   * - ``tipo``
     - Regra
     - Campos próprios
   * - ``logico``
     - ``a and b``, ``a or b``
     - ``operador``; ``filhos`` (cadeias do mesmo operador viram um só nó)
   * - ``nao``
     - ``not a``
     - ``filho``
   * - ``comparacao``
     - ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``, ``=~``, ``=~~``, ``!~``, ``!~~``
     - ``operador``, ``esquerda``, ``direita``
   * - ``contem``
     - ``a in b``, ``a not in b``
     - ``operador``, ``esquerda`` (membro), ``direita`` (contêiner)
   * - ``funcao``
     - ``$any(...)``, ``$len(...)``
     - ``nome``, ``argumentos``
   * - ``compreensao``
     - ``[expr for v in lista if filtro]``
     - ``variavel``, ``lista``, ``filtro``, ``expressao``, ``itens``, ``total``, ``truncado``,
       ``melhor_item``
   * - ``ternario``
     - ``c ? a : b``
     - ``condicao``, ``se_verdadeiro``, ``se_falso``
   * - ``aritmetica``
     - ``+``, ``-``, ``*``, ``/``, ``//``, ``%``, ``**``, bit a bit, ``??``
     - ``operador``, ``esquerda``, ``direita`` (``-x`` só ``direita``)
   * - ``campo``
     - ``idade``, ``m.x``, ``m['x'][0]``
     - ``rotulo`` (``m.x[0]``), ``sensivel``
   * - ``literal``
     - ``18``, ``'ZN'``, ``['a', 'b']``
     - —
   * - ``expressao``
     - fatias (``s[1:2]``) e outros nós
     - —

Cada item de ``itens`` traz ``indice``, ``rotulo``, ``incluido`` (passou no filtro), ``filtro``
(nó ou ``null``), ``expressao`` (nó avaliado com a variável apontando para o item) e
``atendido``. ``melhor_item`` é o índice do primeiro item que atende ou, se nenhum atende, do que
tem mais comparações atendidas.

O ``rule_engine`` simplifica constantes ao compilar (``1 + 1`` vira ``2``), então o ``trecho`` é
equivalente ao texto original, mas não necessariamente idêntico.

Desenhar os blocos
------------------

No servidor, com o template tag:

.. code-block:: html+django

   {% load static rule_blocks %}
   <link rel="stylesheet" href="{% static 'rule_widget/rule_blocks.css' %}">
   {% regra_em_blocos explicacao %}

Em Python: ``django_rule_engine.blocks.render_blocks(explicacao)`` devolve o mesmo HTML.

No navegador, com a explicação vinda de uma API:

.. code-block:: html

   <link rel="stylesheet" href="/static/rule_widget/rule_blocks.css">
   <script src="/static/rule_widget/rule_blocks.js"></script>
   <div id="explicacao"></div>
   <script>
     RuleBlocks.render(document.getElementById('explicacao'), explicacao);
   </script>

Servidor e navegador geram o mesmo HTML: os dois partem do mesmo modelo de elementos
(``django_rule_engine.blocks.model`` e ``RuleBlocks.modelo``), e os testes comparam os dois com
uma fixture comum. Todo texto é escapado (template tag) ou inserido com ``textContent`` (JS).

Cada item de compreensão é um ``<details>``: abre e fecha sem JavaScript, e o item mais perto de
atender já vem aberto.

API e widget
------------

- ``POST /api/explain-rule/`` com ``"tree": true`` devolve também ``"tree"`` (a explicação em
  árvore).
- ``POST /api/validate-rule/`` com ``"explain_tree": true`` devolve ``"explanation_tree"``.
- O widget do ``RuleField`` desenha os blocos ao testar a regra com os dados de exemplo.

Os campos sensíveis seguem a configuração ``RULE_ENGINE_EXPLAIN_SENSITIVE_FIELDS``.

Personalizar o visual
---------------------

As cores e medidas são variáveis CSS em ``.dre-blocos``. Redefina-as no seu tema:

.. code-block:: css

   .dre-blocos {
       --dre-tamanho: 14px;
       --dre-sim-fundo: #e6f4ea;
       --dre-nao-fundo: #fdecea;
       --dre-grupo-fundo: #f3f0ff;   /* e / ou / não / se */
       --dre-laco-fundo: #fff4e5;    /* funções e compreensões */
   }

O modo escuro segue ``prefers-color-scheme``. Classes úteis para ajustes: ``dre-bloco``,
``dre-tipo-<tipo>``, ``dre-sim``/``dre-nao``/``dre-indef``, ``dre-cabeca``, ``dre-filhos``,
``dre-rotulo``, ``dre-valor``, ``dre-op``, ``dre-meta`` e ``dre-erro``.
