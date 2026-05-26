from dataclasses import dataclass


@dataclass
class ScoreFiscalResult:
    score: int
    confianca: str
    justificativas: list[str]


def calcular_score_fiscal_contabil(item) -> ScoreFiscalResult:

    score = 0
    justificativas = []

    # =========================================================
    # DRE / CONTÁBIL
    # =========================================================

    if item.ecd_dre_descr:
        score += 20
        justificativas.append("Conta vinculada à DRE.")

    if item.ecd_confianca == "ALTA":
        score += 20
        justificativas.append("ECD com alta confiança.")

    # =========================================================
    # DOMÍNIO / OPERACIONAL
    # =========================================================

    dominio = str(item.dominio or "").upper()

    if dominio in {
        "TRANSP",
        "POSTO",
        "REVENDA_GAS",
        "CAFE",
        "AGRO",
    }:
        score += 15
        justificativas.append("Domínio operacional reconhecido.")

    # =========================================================
    # CONTA CONTÁBIL
    # =========================================================

    conta_nome = str(item.ecd_conta_nome or "").upper()

    if any(
        termo in conta_nome
        for termo in [
            "COMBUST",
            "CMV",
            "CUSTO",
            "INSUMO",
        ]
    ):
        score += 25
        justificativas.append("Conta contábil compatível com operação.")

    if any(
        termo in conta_nome
        for termo in [
            "ADMINISTRAT",
            "ESCRITORIO",
            "PATRIMONIAL",
        ]
    ):
        score -= 30
        justificativas.append("Conta contábil pouco compatível.")

    # =========================================================
    # MOVIMENTAÇÃO
    # =========================================================

    debito = float(item.ecd_debito or 0)
    credito = float(item.ecd_credito or 0)

    if debito > 0 or credito > 0:
        score += 10
        justificativas.append("Conta possui movimentação contábil.")

    # =========================================================
    # MATCH ICMS X CONTRIBUICAO
    # =========================================================

    status = str(item.status_cruzamento or "").upper()

    if status == "MATCH":
        score += 20
        justificativas.append("Item conciliado entre ICMS/IPI e Contribuições.")

    elif status == "SO_ICMS":
        score += 10
        justificativas.append("Item encontrado apenas no ICMS/IPI.")

    # =========================================================
    # LIMITES
    # =========================================================

    score = max(0, min(score, 100))

    # =========================================================
    # CONFIANÇA
    # =========================================================

    if score >= 70:
        confianca = "ALTA"
    elif score >= 40:
        confianca = "MEDIA"
    else:
        confianca = "BAIXA"

    return ScoreFiscalResult(
        score=score,
        confianca=confianca,
        justificativas=justificativas,
    )