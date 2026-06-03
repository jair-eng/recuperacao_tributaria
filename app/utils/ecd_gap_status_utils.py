from __future__ import annotations


def diagnostico_texto(status: str | None) -> str:
    status = (status or "").upper()

    if status == "SEM_EFD":
        return "Despesa elegível identificada na ECD, mas sem base correspondente declarada na EFD."

    if status == "SEM_ECD":
        return "Base declarada na EFD sem despesa elegível correspondente identificada na ECD."

    if status == "PARCIAL":
        return "Base declarada parcialmente em relação ao potencial identificado na ECD."

    if status == "COBERTO":
        return "Base declarada compatível com o potencial identificado na ECD."

    if status == "EXCEDENTE_EFD":
        return "Base declarada na EFD superior ao lastro identificado na ECD."

    return "Status não classificado."


def prioridade_por_status(status: str | None) -> str:
    status = (status or "").upper()

    if status == "SEM_EFD":
        return "ALTA"

    if status in {"PARCIAL", "SEM_ECD", "EXCEDENTE_EFD"}:
        return "MEDIA"

    if status == "COBERTO":
        return "BAIXA"

    return "INDEFINIDA"


def classificar_alerta(item: dict) -> str:
    ecd = item.get("ecd_elegivel") or 0
    efd = item.get("efd_declarada") or 0
    cobertura = item.get("cobertura_pct") or 0

    if ecd > 0 and efd == 0:
        return "EFD_ZERADA_COM_DESPESA_ECD"

    if ecd > 0 and efd > 0 and cobertura < 70:
        return "EFD_COM_BAIXA_COBERTURA"

    return ""


def descricao_alerta(tipo: str) -> str:
    if tipo == "EFD_ZERADA_COM_DESPESA_ECD":
        return "Existe despesa elegível na ECD, mas nenhuma base correspondente foi declarada na EFD."

    if tipo == "EFD_COM_BAIXA_COBERTURA":
        return "A empresa declarou parte das bases, mas a cobertura está abaixo do limite definido."

    return ""

def iter_items(valor):
    if isinstance(valor, dict):
        return valor.values()

    if isinstance(valor, list):
        return valor

    return []

def categoria_diagnostico(item: dict) -> str:
    categoria = item.get("categoria")
    if categoria:
        return categoria

    nat = item.get("nat_bc_cred")
    status = item.get("status")

    if status == "SEM_ECD" and nat:
        return f"EFD NAT {nat} - sem categoria ECD"

    return "SEM CATEGORIA"
