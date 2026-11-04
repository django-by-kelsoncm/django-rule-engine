# Version History

## 1.1.0

### 🔍 Rule explanation (`django_rule_engine.explain`)

- New public module `django_rule_engine.explain` with `explain(rule, context, *, sensitive=...)`:
  splits the rule on top-level `and`/`or` (only when all are the same operator, respecting quotes,
  parentheses and brackets), splits each atom into field / operator / expected value
  (`==`, `!=`, `>=`, `<=`, `>`, `<`, `=~`, `=~~`, `!~`, `!~~`, `in`, `not in`; an atom without a
  comparison expects "verdadeiro") and evaluates everything with `rule_engine` itself.
- `$any`/`$all` over comprehensions (`[EXPR for x in LIST if FILTER]`, any list) are detailed per item.
- `atendido` is `True`/`False`/`None` (error); values are JSON-safe (Decimal, tuples, dates, sets).
- Sensitive fields are hidden by a configurable regex (`DEFAULT_SENSITIVE_FIELDS`,
  `RULE_ENGINE_EXPLAIN_SENSITIVE_FIELDS`).
- New endpoint `POST /api/explain-rule/`; `POST /api/validate-rule/` accepts `"explain": true`.
- Widget: colored rule (green / red / yellow) and "Campo | Esperado | Valor" table, one column per
  item in `$any`/`$all` (`static/rule_widget/rule_explain.js`).
- Tests now run with pytest-django (`pytest`) and `node --test "tests/js/*.test.js"`, also in CI.
- `django_rule_engine.__version__` now matches the package version.

## 1.0.1

### 🎯 New Method: `matches()`

Version 1.0.1 introduces the `matches()` method on `RuleField`, enabling programmatic validation of data against a stored rule.

#### Description

The `matches()` method provides a simple and intuitive way to evaluate whether a set of data meets the criteria defined in a rule-engine rule. It encapsulates all the logic for compiling and evaluating the rule, handling exceptions, and simplifying application code.

#### Signature

```python
def matches(self, data: Union[None, bool, int, float, str, List, Dict]) -> bool
```

#### Parameters

- **data** (Union[None, bool, int, float, str, List, Dict]): The data to be validated against the rule. Supports any JSON-compatible type:
  - `None`
  - Primitives: `bool`, `int`, `float`, `str`
  - Structures: `list`, `dict`

#### Return Value

- **bool**: `True` if the data meets the rule, `False` otherwise

#### Exception Handling

- **ValidationError**: Raised if the rule has invalid syntax
- **Exception**: Raised if there's an error during rule evaluation

#### Usage Examples

##### Example 1: Simple Validation

```python
from myapp.models import AccessRule

# Get the rule from the database
rule = AccessRule.objects.get(name="min_age")
rule.rule  # "age >= 18"

# Validate data
user_data = {"age": 25}
if rule.rule_field.matches(user_data):
    print("User can access")
else:
    print("User cannot access")
```

##### Example 2: Complex Dict Validation

```python
rule_field = RuleField(default='user["status"] == "active" and user["age"] >= 18')

data = {
    "user": {
        "status": "active",
        "age": 30
    }
}

result = rule_field.matches(data)  # True
```

##### Example 3: Business Logic Usage

```python
class DiscountRule(models.Model):
    name = models.CharField(max_length=200)
    rule = RuleField(
        example_data={
            "total": 100.00,
            "customer_type": "premium",
            "first_purchase": False
        }
    )
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    
    def get_discount(self, order_data):
        """Calculate the discount if the rule is met"""
        try:
            if self.rule.matches(order_data):
                return float(self.discount_percentage)
            return 0.0
        except Exception as e:
            # Log and return no discount on error
            print(f"Error evaluating discount: {e}")
            return 0.0
```

##### Example 4: With Error Handling

```python
from django.core.exceptions import ValidationError

rule_field = RuleField(default="invalid rule syntax")

try:
    result = rule_field.matches({"data": "test"})
except ValidationError as e:
    print(f"Invalid rule: {e.message}")
```

#### Benefits

✅ **Simplicity**: A single method call to validate data  
✅ **Security**: Encapsulates exception handling  
✅ **Readability**: Cleaner and more expressive code  
✅ **Flexibility**: Supports any JSON-compatible data structure  
✅ **Integration**: Works seamlessly with Django models  

#### Use Cases

- **Access Control**: Validate permissions based on dynamic rules
- **Eligibility**: Check if a candidate meets specific criteria
- **Discount Calculation**: Apply discounts based on business rules
- **Data Validation**: Verify compliance with complex criteria
- **Automation**: Execute actions based on stored rules

### 📝 Notes

- The method always returns `True` if the rule is empty
- Type hints were added for better IDE support
- Compatible with all operations supported by rule-engine


## 1.0.0

We're excited to announce the first stable release of **django-rule-engine**! 🚀

### ✨ Key Features

#### 🎨 Visual Rule Editor
- **Syntax highlighting** for better readability
- **Real-time validation** with immediate feedback
- **Auto-formatting** for JSON example data
- **Keyboard shortcuts** (Ctrl+Enter to validate)
- **Dark mode support** with modern UI

#### 🔌 Easy Integration
```python
from django_rule_engine.fields import RuleField

class MyModel(models.Model):
    access_rule = RuleField(
        verbose_name="Access Rule",
        example_data={
            "age": 25,
            "status": "active",
            "role": "admin"
        }
    )
```

#### ⚡ REST API
Built-in validation endpoint for frontend validation:
```
POST /api/validate-rule/
```

#### 🎯 Django Admin Integration
Seamlessly integrates with Django Admin - just add the field and the editor appears automatically!

### 📦 Installation

```bash
pip install django-rule-engine
```

Add to your `INSTALLED_APPS`:
```python
INSTALLED_APPS = [
    # ...
    'django_rule_engine',
]
```

Include URLs:
```python
urlpatterns = [
    path('', include('django_rule_engine.urls')),
]
```

### 💡 Use Cases

- ✅ **Access Control**: Define who can access resources
- ✅ **Business Rules**: Implement complex discount/pricing logic
- ✅ **Validation**: Create dynamic validation rules
- ✅ **Eligibility**: Determine program/service eligibility
- ✅ **Classification**: Classify entities based on criteria
- ✅ **Filtering**: Advanced data filtering and queries

### 🎓 Quick Example

```python
from django.db import models
from django_rule_engine.fields import RuleField

class DiscountCampaign(models.Model):
    name = models.CharField(max_length=200)
    
    rule = RuleField(
        verbose_name="Discount Rule",
        example_data={
            "price": 150.00,
            "quantity": 3,
            "customer_type": "premium",
            "first_purchase": False
        },
        help_text="Example: price > 100 and quantity >= 2"
    )
    
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)

    def calculate_discount(self, order_data):
        """Calculate discount based on the rule."""
        if not self.rule:
            return 0
        
        import rule_engine
        rule = rule_engine.Rule(self.rule)
        
        if rule.matches(order_data):
            return float(self.discount_percentage)
        return 0
```

### 🔧 Requirements

- Python >= 3.10
- Django >= 4.2
- rule-engine >= 4.5.3
- django-json-widget >= 2.0

### 🎯 Tested On

- Python: 3.10, 3.11, 3.12, 3.13, 3.14
- Django: 4.2, 5.0, 5.1, 5.2
- Modern browsers (Chrome, Firefox, Safari, Edge)
