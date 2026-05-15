def only_digits(valor):
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def norm_str(valor):
    return str(valor or "").strip().upper()