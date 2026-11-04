# Examples 

Complete usage examples of RuleField demonstrating different ways to use RuleField in your Django models.


```python
from django.db import models
from django_rule_engine.fields import RuleField


class Exemplo1_Basico(models.Model):
    """Basic example - simple field without additional configuration."""
    
    nome = models.CharField(max_length=100)
    regra = RuleField(
        verbose_name="Simple Rule",
        help_text="Enter a rule-engine rule"
    )
    
    class Meta:
        verbose_name = "Example 1: Basic Usage"


class Exemplo2_ComDadosExemplo(models.Model):
    """Example with pre-configured sample data."""
    
    nome = models.CharField(max_length=100)
    regra_validacao = RuleField(
        verbose_name="Validation Rule",
        example_data={
            "idade": 25,
            "status": "ativo",
            "nivel": "avancado"
        },
        help_text="Use: idade, status, nivel"
    )
    
    class Meta:
        verbose_name = "Example 2: With Sample Data"


class Exemplo3_ValidacaoUsuario(models.Model):
    """Real example: user validation."""
    
    nome_grupo = models.CharField(max_length=200)
    regra_acesso = RuleField(
        verbose_name="Access Rule",
        blank=True,
        null=True,
        example_data={
            "username": "joao.silva",
            "email": "joao@ifrn.edu.br",
            "is_staff": True,
            "is_active": True,
            "age": 30,
            "department": "TI"
        },
        help_text=(
            "Defines who can access this group. "
            "Available variables: username, email, is_staff, "
            "is_active, age, department"
        )
    )
    
    def user_can_access(self, user_data):
        """Checks if the user can access the group."""
        if not self.regra_acesso:
            return True
        
        import rule_engine
        try:
            rule = rule_engine.Rule(self.regra_acesso)
            return rule.matches(user_data)
        except Exception as e:
            print(f"Error evaluating rule: {e}")
            return False
    
    class Meta:
        verbose_name = "Example 3: User Validation"


class Exemplo4_RegraDesconto(models.Model):
    """Real example: discount rule for products."""
    
    nome_campanha = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    
    regra_desconto = RuleField(
        verbose_name="Discount Rule",
        example_data={
            "preco": 150.00,
            "quantidade": 3,
            "tipo_cliente": "premium",
            "primeira_compra": False,
            "total_compras_ano": 5
        },
        help_text=(
            "Defines when the discount applies. "
            "Example: preco > 100 and quantidade >= 2"
        )
    )
    
    percentual_desconto = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Discount percentage (0-100)"
    )
    
    def calcular_desconto(self, pedido):
        """Calculates the discount based on the rule."""
        if not self.regra_desconto:
            return 0
        
        import rule_engine
        try:
            rule = rule_engine.Rule(self.regra_desconto)
            
            # Prepare order data
            dados = {
                "preco": float(pedido.preco),
                "quantidade": pedido.quantidade,
                "tipo_cliente": pedido.cliente.tipo,
                "primeira_compra": pedido.cliente.primeira_compra,
                "total_compras_ano": pedido.cliente.total_compras_ano
            }
            
            if rule.matches(dados):
                return float(self.percentual_desconto)
            return 0
        except Exception as e:
            print(f"Error calculating discount: {e}")
            return 0
    
    class Meta:
        verbose_name = "Example 4: Discount Rule"


class Exemplo5_MultiplaRegras(models.Model):
    """Example with multiple rules in the same model."""
    
    nome = models.CharField(max_length=200)
    
    # Eligibility rule
    regra_elegibilidade = RuleField(
        verbose_name="Eligibility Rule",
        example_data={
            "idade": 25,
            "formacao": "superior",
            "experiencia_anos": 3
        },
        help_text="Defines if the person is eligible"
    )
    
    # Priority rule
    regra_prioridade = RuleField(
        verbose_name="Priority Rule",
        example_data={
            "pontuacao": 85,
            "tempo_espera_dias": 30,
            "situacao": "regular"
        },
        help_text="Defines the priority in the process"
    )
    
    # Classification rule
    regra_classificacao = RuleField(
        verbose_name="Classification Rule",
        example_data={
            "nota_prova": 8.5,
            "nota_titulos": 7.0,
            "nota_experiencia": 9.0
        },
        help_text="Defines the final classification"
    )
    
    def avaliar_candidato(self, dados_candidato):
        """Evaluates the candidate against all rules."""
        import rule_engine
        
        resultados = {
            "elegivel": False,
            "prioridade": False,
            "classificacao": False
        }
        
        # Evaluate eligibility
        if self.regra_elegibilidade:
            try:
                rule = rule_engine.Rule(self.regra_elegibilidade)
                resultados["elegivel"] = rule.matches(dados_candidato)
            except Exception as e:
                print(f"Error evaluating eligibility: {e}")
        
        # Evaluate priority (only if eligible)
        if resultados["elegivel"] and self.regra_prioridade:
            try:
                rule = rule_engine.Rule(self.regra_prioridade)
                resultados["prioridade"] = rule.matches(dados_candidato)
            except Exception as e:
                print(f"Error evaluating priority: {e}")
        
        # Evaluate classification (only if eligible)
        if resultados["elegivel"] and self.regra_classificacao:
            try:
                rule = rule_engine.Rule(self.regra_classificacao)
                resultados["classificacao"] = rule.matches(dados_candidato)
            except Exception as e:
                print(f"Error evaluating classification: {e}")
        
        return resultados
    
    class Meta:
        verbose_name = "Example 5: Multiple Rules"
```

## Rule.matches() Method

The `matches()` method validates if a rule matches a given data structure. It accepts any JSON-compatible data type.

### Method Signature

```python
rule.matches(data: Any) -> bool
```

### Parameters

- **data** (Any): The data to validate against the rule. Can be:
  - `None`
  - JSON primitives: `str`, `int`, `float`, `bool`
  - `list`: List of any supported types
  - `dict`: Dictionary with string keys and any supported values

### Return Value

- **bool**: `True` if the data matches the rule, `False` otherwise

### Usage Examples

```python
from rule_engine import Rule

# Simple rule with primitive
rule = Rule("age >= 18")
result = rule.matches({"age": 25})  # True
result = rule.matches({"age": 15})  # False

# Rule with None
rule = Rule("value is None")
result = rule.matches(None)  # True

# Rule with list
rule = Rule("len(items) > 2")
result = rule.matches({"items": [1, 2, 3]})  # True
result = rule.matches({"items": [1]})  # False

# Complex nested data
rule = Rule('user["status"] == "ativo" and user["age"] >= 18')
result = rule.matches({
    "user": {
        "status": "ativo",
        "age": 25
    }
})  # True

# Rule with string operations
rule = Rule('email.endswith("@ifrn.edu.br")')
result = rule.matches({"email": "joao@ifrn.edu.br"})  # True
result = rule.matches({"email": "joao@gmail.com"})  # False

# Multiple conditions
rule = Rule('(price > 100 or quantity >= 5) and category == "premium"')
result = rule.matches({
    "price": 150,
    "quantity": 3,
    "category": "premium"
})  # True

# Rule with None handling
rule = Rule('value is not None and value > 0')
result = rule.matches({"value": None})  # False
result = rule.matches({"value": 10})  # True
result = rule.matches({"value": -5})  # False
```

### Exception Handling

The `matches()` method may raise exceptions if:
- The rule syntax is invalid
- The data structure doesn't provide required fields
- Type mismatches occur during evaluation

Always wrap in try-except for production code:

```python
rule = Rule(rule_string)
try:
    if rule.matches(data):
        # Rule matched
        pass
except Exception as e:
    print(f"Error evaluating rule: {e}")
    # Handle error appropriately
```

## Explaining a rule

```python
from django_rule_engine.explain import explain

rule = (
    "tipo_usuario in ['Aluno'] and $any([m['tipo'] == 'aluno' and m['detalhamento']['ativo'] == true"
    " for m in outras_matriculas])"
)
context = {
    "tipo_usuario": "Aluno",
    "cpf": "000.000.000-00",
    "outras_matriculas": [
        {"tipo": "aluno", "detalhamento": {"ativo": False}},
        {"tipo": "servidor", "detalhamento": {"ativo": True}},
    ],
}
result = explain(rule, context)
result["atendido"]                       # False
comp = result["condicoes"][1]["detalhes"]
comp["tipo"], comp["funcao"], comp["itens"]  # ("por_item", "any", 2)
[(l["rotulo"], l["valores"], l["resultados"]) for l in comp["linhas"]]
# [("tipo", ["aluno", "servidor"], [True, False]),
#  ("detalhamento.ativo", [False, True], [False, True])]
# No item matches both pieces at the same time, so $any(...) is False.

explain("cpf == '1'", context)["condicoes"][0]["detalhes"]["linhas"][0]["valor"]  # None (sensitive)
explain("cpf == '1'", context, sensitive=None)  # shows every value
```

Over HTTP:

```bash
curl -X POST http://localhost:8000/api/explain-rule/ -H 'Content-Type: application/json'   -d '{"rule": "age >= 18 and status == 'active'", "data": {"age": 16, "status": "active"}}'
```

## Examples of common rules you can use:

> RULE EXAMPLES:

1. Age Validation:
   - age >= 18
   - age >= 18 and age <= 65
   - age < 18 or age > 65

2. Email Validation:
   - "@ifrn.edu.br" in email
   - email.endswith("@edu.br")
   - not ("@gmail.com" in email)

3. Status Validation:
   - status == "ativo"
   - status in ["ativo", "pendente"]
   - status != "inativo"

4. Composite Rules:
   - age >= 18 and status == "ativo"
   - (price > 100 or quantity >= 5) and customer_type == "premium"
   - level >= 5 and (points > 1000 or vip == true)

5. Mathematical Operations:
   - price * quantity > 1000
   - (total - discount) >= 100
   - abs(balance) < 50

6. Functions:
   - len(name) > 3
   - max(value1, value2) > 100
   - min(price1, price2) < 50

7. Strings:
   - name.startswith("IFRN")
   - code.endswith("2024")
   - "palavra" in description

8. Booleans:
   - is_active and not is_suspended
   - has_permission or is_admin
   - approved and verified
