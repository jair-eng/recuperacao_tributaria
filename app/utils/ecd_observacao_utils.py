from __future__ import annotations

import re

from app.utils.ecd_gap_utils import diagnostico_texto


SIGLAS_MANTER = {
    "pf": "PF",
    "pj": "PJ",
    "fl": "filial",
    "mtz": "matriz",
    "pis": "PIS",
    "cofins": "COFINS",
}


def padronizar_descricao_conta(texto: str | None) -> str:
    texto = (texto or "").strip()
    if not texto:
        return ""

    texto = re.sub(r"\s+", " ", texto)
    texto = texto.lower()

    partes = []
    for parte in texto.split(" "):
        limpo = parte.strip(".,;:-")
        pontuacao_ini = parte[: len(parte) - len(parte.lstrip(".,;:-"))]
        pontuacao_fim = parte[len(parte.rstrip(".,;:-")) :]

        if limpo in SIGLAS_MANTER:
            partes.append(f"{pontuacao_ini}{SIGLAS_MANTER[limpo]}{pontuacao_fim}")
        else:
            partes.append(parte)

    resultado = " ".join(partes)

    if resultado:
        resultado = resultado[0].upper() + resultado[1:]

    return resultado


def montar_observacao_detalhe(
    *,
    item: dict,
    status: str | None,
) -> str:
    categoria = item.get("categoria") or ""
    fundamento = item.get("fundamento") or ""
    confianca = item.get("confianca")
    nome_cta = item.get("nome_cta")

    observacao_catalogo = item.get("observacao") or item.get("observacao_catalogo")
    observacao_match = item.get("observacao_match")

    if observacao_match:
        return str(observacao_match)

    if observacao_catalogo:
        return str(observacao_catalogo)

    if fundamento == "CreditoPresumido75":
        return "Crédito presumido com base reduzida a 75%."

    if categoria == "CombustiveisLubrificantes":
        return "Insumo motriz."

    if str(confianca).replace(",", ".") in {"100", "100.0", "100.00"} and nome_cta:
        return padronizar_descricao_conta(nome_cta)

    return diagnostico_texto(status)

def montar_observacao(status: str, modo_recuperacao: str) -> str:
    if modo_recuperacao == "AUTOMATICA":
        return "Conta possui vínculo com C170 da EFD Contribuições. Pode ser confrontada futuramente com ICMS/IPI para correção automatizável."

    if modo_recuperacao == "ASSISTIDA":
        return "Conta possui vínculo com F100. Recuperação depende de revisão documental e validação do suporte da operação."

    return "Conta elegível na ECD sem vínculo suficiente em C170/F100. Exige investigação documental."