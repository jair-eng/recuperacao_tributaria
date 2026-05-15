def get_safe(lista: list, idx: int, default=None):
    try:
        return lista[idx]
    except Exception:
        return default