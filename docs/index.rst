Django Rule Engine
==================

.. image:: https://badge.fury.io/py/django-rule-engine.svg
   :target: https://badge.fury.io/py/django-rule-engine
   :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/django-rule-engine.svg
   :target: https://pypi.org/project/django-rule-engine/
   :alt: Python Versions

.. image:: https://img.shields.io/badge/django-4.2%20%7C%205.0%20%7C%205.1%20%7C%205.2-blue.svg
   :target: https://www.djangoproject.com/
   :alt: Django Versions

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License: MIT

Um pacote Django completo que integra a biblioteca `rule-engine <https://github.com/zeroSteiner/rule-engine>`_
ao Django com editor visual interativo, validação em tempo real, API REST e suporte nativo ao Django Admin.

Perfeito para construir regras de negócios flexíveis, controle de acesso, políticas de desconto, regras de elegibilidade
e qualquer lógica dinâmica configurável pelo usuário.

.. toctree::
   :maxdepth: 2
   :caption: Conteúdo:

   start-guide
   explicacao-em-blocos
   contribute
   publishing

📋 Sobre o Projeto
------------------

O **django-rule-engine** fornece um campo Django customizado (``RuleField``) e um widget especializado
para a criação e avaliação de expressões lógicas baseadas em ``rule-engine``.

✨ Recursos Principais
----------------------

🎨 Editor Visual de Regras
^^^^^^^^^^^^^^^^^^^^^^^^^^

* **Destaque de sintaxe**: Leitura e edição intuitivas.
* **Validação em tempo real**: Feedback instantâneo sobre erros de sintaxe ou avaliação.
* **Formatador de JSON**: Para validar regras diretamente contra payloads de exemplo.
* **Atalhos de teclado**: Pressione ``Ctrl+Enter`` para validar a regra rapidamente.
* **Suporte a Dark Mode**: Compatível com o tema nativo do Django Admin.

🔌 Integração Simples
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from django.db import models
   from django_rule_engine.fields import RuleField

   class RegraAcesso(models.Model):
       nome = models.CharField(max_length=100)
       regra = RuleField(
           verbose_name="Regra de Permissão",
           example_data={
               "idade": 25,
               "status": "ativo",
               "funcao": "admin"
           }
       )

⚡ API REST Embutida
^^^^^^^^^^^^^^^^^^^^

Endpoint para validação via frontend ou integrações externas:

.. code-block:: text

   POST /api/validate-rule/
   POST /api/explain-rule/

Payload de requisição:

.. code-block:: json

   {
     "rule": "idade >= 18 and status == 'ativo'",
     "example_data": {"idade": 20, "status": "ativo"}
   }

🎯 Método `matches()` de Conveniência
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Valide dados diretamente a partir do objeto ou do campo:

.. code-block:: python

   # Validação simples
   dados = {"idade": 25, "status": "ativo"}
   if objeto.regra_field.matches(dados):
       # Regra válida
       pass

🚀 Instalação Rápida
--------------------

Via PyPI:

.. code-block:: bash

   pip install django-rule-engine

No ``settings.py``:

.. code-block:: python

   INSTALLED_APPS = [
       # ...
       'django_rule_engine',
   ]

No ``urls.py``:

.. code-block:: python

   from django.urls import path, include

   urlpatterns = [
       # ...
       path('', include('django_rule_engine.urls')),
   ]

💡 Casos de Uso
---------------

* ✅ **Controle de Acesso**: Defina dinamicamente permissões de acesso a recursos.
* ✅ **Políticas de Desconto**: Implemente regras de preços e campanhas promocionais.
* ✅ **Elegibilidade**: Determine se um cliente/aluno atende aos critérios do programa.
* ✅ **Validação Dinâmica**: Crie regras de validação sem alterar o código-fonte.

👥 Contribuindo
---------------

Contribuições são bem-vindas! Consulte o :doc:`Guia de Contribuição <contribute>`
para detalhes de setup local e execução de testes.


📝 Licença
----------

Este projeto está licenciado sob a Licença MIT - veja o arquivo ``LICENSE`` para detalhes.

📧 Contato
----------

Kelson da Costa Medeiros

* Email: kelsoncm@gmail.com
* GitHub: `@kelsoncm <https://github.com/kelsoncm>`_
