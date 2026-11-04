"""API views for rule validation."""

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

import rule_engine

from ..explain import DEFAULT_SENSITIVE_FIELDS, explain
from ..explain_tree import explain_tree

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
@ensure_csrf_cookie
def validate_rule(request):
    """
    Valida uma regra do rule-engine com dados de exemplo.

    POST /api/validate-rule/
    Body: {
        "rule": "age >= 18 and status == 'active'",
        "data": {"age": 25, "status": "active"}
    }

    Response: {
        "valid": true,
        "result": true,
        "matches": true
    }

    Ou em caso de erro:
    {
        "valid": false,
        "error": "mensagem de erro"
    }
    """
    print(f"DEBUG: validate_rule chamado - Method: {request.method}")
    print(f"DEBUG: Path: {request.path}")
    print(f"DEBUG: Body: {request.body}")

    try:
        # Parse request body
        body = json.loads(request.body)
        rule_text = body.get("rule", "")
        data = body.get("data", {})

        if not rule_text:
            return JsonResponse({"valid": False, "error": "Regra não pode ser vazia"}, status=400)

        # Compila a regra
        try:
            rule = rule_engine.Rule(rule_text)
        except Exception:
            logger.exception("Erro ao compilar regra")
            return JsonResponse({"valid": False, "error": "Erro ao compilar regra"}, status=400)

        # Avalia a regra com os dados fornecidos
        try:
            result = rule.matches(data)

            payload = {
                "valid": True,
                "result": result,
                "matches": result,
                "rule": rule_text,
                "data": data,
            }
            if body.get("explain"):
                payload["explanation"] = _explain(rule_text, data)
            if body.get("explain_tree"):
                payload["explanation_tree"] = _explain_tree(rule_text, data)
            return JsonResponse(payload)
        except Exception:
            logger.exception("Erro ao avaliar regra")
            return JsonResponse({"valid": False, "error": "Erro ao avaliar regra"}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"valid": False, "error": "JSON inválido"}, status=400)
    except Exception:
        logger.exception("Erro interno ao validar regra")
        return JsonResponse({"valid": False, "error": "Erro interno"}, status=500)


def _sensitive_fields():
    """Regex dos campos ocultados na explicação (``RULE_ENGINE_EXPLAIN_SENSITIVE_FIELDS``)."""
    return getattr(settings, "RULE_ENGINE_EXPLAIN_SENSITIVE_FIELDS", DEFAULT_SENSITIVE_FIELDS)


def _explain(rule_text, data):
    return explain(rule_text, data, sensitive=_sensitive_fields())


def _explain_tree(rule_text, data):
    return explain_tree(rule_text, data, sensitive=_sensitive_fields())


@require_http_methods(["POST"])
@ensure_csrf_cookie
def explain_rule(request):
    """
    Explica, trecho a trecho, por que a regra é (ou não) atendida pelos dados.

    POST /api/explain-rule/
    Body: {"rule": "age >= 18 and status == 'active'", "data": {"age": 15, "status": "active"},
           "tree": true}

    Response (200): {"valid": true, "explanation": {...}}  (ver ``django_rule_engine.explain``),
    mais ``"tree": {...}`` (ver ``django_rule_engine.explain_tree``) quando ``"tree": true``.
    Erros (400): {"valid": false, "error": "..."} para JSON inválido, regra vazia ou que não compila.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"valid": False, "error": "JSON inválido"}, status=400)
    if not isinstance(body, dict):
        return JsonResponse({"valid": False, "error": "JSON inválido"}, status=400)

    rule_text = body.get("rule") or ""
    data = body.get("data") or {}
    if not isinstance(rule_text, str) or not rule_text.strip():
        return JsonResponse({"valid": False, "error": "Regra não pode ser vazia"}, status=400)
    if not isinstance(data, dict):
        return JsonResponse(
            {"valid": False, "error": "Dados de exemplo devem ser um objeto JSON"}, status=400
        )

    try:
        rule_engine.Rule(rule_text)
    except Exception:
        logger.info("Regra não compila", exc_info=True)
        return JsonResponse({"valid": False, "error": "Erro ao compilar regra"}, status=400)

    try:
        payload = {"valid": True, "explanation": _explain(rule_text, data)}
        if body.get("tree"):
            payload["tree"] = _explain_tree(rule_text, data)
    except Exception:
        logger.exception("Erro interno ao explicar regra")
        return JsonResponse({"valid": False, "error": "Erro interno"}, status=500)
    return JsonResponse(payload)
