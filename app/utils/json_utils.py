def campos_json(conteudo_json) -> list:
    if not conteudo_json:
        return []

    if isinstance(conteudo_json, dict):
        return conteudo_json.get("dados") or conteudo_json.get("campos") or []

    if isinstance(conteudo_json, list):
        return conteudo_json

    return []