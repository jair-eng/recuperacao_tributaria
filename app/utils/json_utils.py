from decimal import Decimal
from datetime import date, datetime


def json_safe(value):

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            k: json_safe(v)
            for k, v in value.items()
        }

    if isinstance(value, list):
        return [
            json_safe(v)
            for v in value
        ]

    return value

def campos_json(conteudo_json) -> list:
    if not conteudo_json:
        return []

    if isinstance(conteudo_json, dict):
        return conteudo_json.get("dados") or conteudo_json.get("campos") or []

    if isinstance(conteudo_json, list):
        return conteudo_json

    return []