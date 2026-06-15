from __future__ import annotations

from app.utils.dates import buscar_bloco_m_trimestre, agregar_trimestral
from app.utils.numbers import to_decimal
from app.utils.strings import norm_str
from collections import defaultdict
from decimal import Decimal
from typing import Any

def get(partes: list[str], idx: int, default=None):
    return partes[idx] if len(partes) > idx else default

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

def classificar_alerta_natureza(item: dict) -> str | None:
    nat = str(item["nat_bc_cred"]).zfill(2)

    if nat == "00":
        return None

    valor_ecd = to_decimal(item["valor_ecd"])
    total_documentado = to_decimal(item["total_documentado"])
    valor_bloco_m = to_decimal(item["valor_bloco_m"])
    gap_ecd = to_decimal(item["gap_ecd"])
    cobertura = to_decimal(item["cobertura_documental_pct"])

    if valor_ecd <= 0:
        return None

    if total_documentado == 0 and valor_bloco_m == 0:
        return "ECD_SEM_DOCUMENTACAO_NEM_ESCRITURACAO"

    if total_documentado == 0 and valor_bloco_m > 0:
        return "ECD_SEM_DOCUMENTACAO_IDENTIFICADA"

    if cobertura < Decimal("0.30"):
        return "BAIXA_COBERTURA_DOCUMENTAL"

    if cobertura < Decimal("0.80"):
        return "COBERTURA_DOCUMENTAL_PARCIAL"

    return None


def descricao_alerta_natureza(tipo: str) -> str:
    descricoes = {
        "ECD_SEM_DOCUMENTACAO_NEM_ESCRITURACAO": (
            "Existe despesa elegível na ECD sem documentação identificada e sem escrituração no Bloco M."
        ),
        "ECD_SEM_DOCUMENTACAO_IDENTIFICADA": (
            "Existe valor escriturado no Bloco M, porém não foi possível identificar documentação correspondente na análise."
        ),
        "BAIXA_COBERTURA_DOCUMENTAL": (
            "A documentação identificada cobre menos de 30% da despesa elegível registrada na ECD."
        ),
        "COBERTURA_DOCUMENTAL_PARCIAL": (
            "A documentação identificada cobre parcialmente a despesa elegível registrada na ECD."
        ),
    }

    return descricoes.get(tipo, "")

def iter_items(valor):
    if isinstance(valor, dict):
        return valor.values()

    if isinstance(valor, list):
        return valor

    return []

def ordem_categoria(item):
    categoria, dados = item
    elegivel = dados["elegivel"]

    # elegíveis primeiro; investigar/não classificado no final
    return (
        elegivel <= 0,
        categoria == "NaoClassificado",
        -dados["despesa"],
    )

def eh_categoria_frete(categoria: str) -> bool:
    c = norm_str(categoria)
    return (
        "FRETE" in c
        or "SUBCONTRATACAO" in c
        or "CARRETO" in c
    )

def naturezas_linha_ecd(linha: dict) -> list[str]:
    naturezas = [
        str(n).zfill(2)
        for n in (linha.get("naturezas_esperadas") or [])
        if str(n).zfill(2) != "00"
    ]

    if naturezas:
        return sorted(set(naturezas))

    nat = str(linha.get("nat_bc_cred") or "00").zfill(2)
    if nat != "00":
        return [nat]

    return []



def resolver_modo_recuperacao(
    *,
    tem_c170: bool,
    tem_f100: bool,
    tem_credito: bool,
) -> str:
    if tem_c170:
        return "AUTOMATICA"

    if tem_f100:
        return "ASSISTIDA"

    return "INVESTIGAR"

def resolver_status_recuperacao(
    *,
    valor_ecd: Decimal,
    valor_creditado_total: Decimal,
    tem_c170: bool,
    tem_f100: bool,
) -> str:
    if valor_creditado_total <= 0 and tem_c170:
        return "C170_SEM_CREDITO_APROVEITADO"

    if valor_creditado_total <= 0 and tem_f100:
        return "F100_SEM_CREDITO_APROVEITADO"

    if valor_creditado_total <= 0:
        return "ECD_SEM_CREDITO_IDENTIFICADO"

    if valor_creditado_total < valor_ecd:
        return "CREDITO_PARCIAL"

    return "CREDITO_COBERTO"


def ajustar_sinal_anulacao_ecd(linhas_ecd: list[dict]) -> list[dict]:
    for item in linhas_ecd:
        nome = (item.get("nome_cta") or "").upper().strip()

        if nome.startswith("(-)") or "ANULACAO" in nome or "ANULAÇÃO" in nome:
            valor = to_decimal(item.get("valor"))
            item["valor"] = valor * Decimal("-1")
            item["eh_anulacao"] = True

    return linhas_ecd

def resolver_nat_categoria(item: dict) -> str:
    nat = (
        item.get("nat_bc_cred_esperada")
        or item.get("natureza_esperada")
        or item.get("nat_esperada")
        or item.get("nat_bc_cred")
        or "00"
    )
    return str(nat).zfill(2)

def pct(numerador: Decimal, denominador: Decimal) -> Decimal:
    if denominador <= 0:
        return Decimal("0.00")
    return numerador / denominador

def montar_base_por_natureza_trimestral(ctx: dict) -> dict[str, dict]:
    agregado_cat = agregar_trimestral(ctx)
    agregado_nat = {}

    for item in agregado_cat.values():
        trimestre = item["trimestre"]
        nat = item["nat_bc_cred"]
        chave = f"{trimestre}|{nat}"

        if chave not in agregado_nat:
            agregado_nat[chave] = {
                "trimestre": trimestre,
                "nat_bc_cred": nat,
                "valor_ecd": Decimal("0.00"),
                "valor_creditado_c170": Decimal("0.00"),
                "valor_oportunidade_c170": Decimal("0.00"),
                "valor_creditado_f100": Decimal("0.00"),
                "valor_creditado_a170": Decimal("0.00"),
                "valor_sem_credito_a170": Decimal("0.00"),
                "qtd_contas": 0,
                "qtd_c170": 0,
                "qtd_f100": 0,
                "qtd_a170": 0,
            }

        agg = agregado_nat[chave]

        for campo in [
            "valor_ecd",
            "valor_creditado_c170",
            "valor_oportunidade_c170",
            "valor_creditado_f100",
            "valor_creditado_a170",
            "valor_sem_credito_a170",
        ]:
            agg[campo] += to_decimal(item.get(campo))

        agg["qtd_contas"] += int(item.get("qtd_contas") or 0)
        agg["qtd_c170"] += int(item.get("qtd_c170") or 0)
        agg["qtd_f100"] += int(item.get("qtd_f100") or 0)
        agg["qtd_a170"] += int(item.get("qtd_a170") or 0)

    for item in agregado_nat.values():
        trimestre = item["trimestre"]
        nat = item["nat_bc_cred"]

        valor_ecd = to_decimal(item.get("valor_ecd"))
        valor_c170 = to_decimal(item.get("valor_creditado_c170"))
        valor_oportunidade_c170 = to_decimal(item.get("valor_oportunidade_c170"))
        valor_f100 = to_decimal(item.get("valor_creditado_f100"))
        valor_a170 = to_decimal(item.get("valor_creditado_a170"))
        valor_sem_credito_a170 = to_decimal(item.get("valor_sem_credito_a170"))

        total_creditado = valor_c170 + valor_f100 + valor_a170
        total_documentado = total_creditado + valor_sem_credito_a170

        valor_bloco_m = buscar_bloco_m_trimestre(
            ctx=ctx,
            periodo_trim=trimestre,
            nat=nat,
        )

        gap_ecd = max(Decimal("0.00"), valor_ecd - total_documentado)
        dif_documentado_m = total_documentado - valor_bloco_m
        cobertura = pct(total_documentado, valor_ecd)

        item["total_creditado"] = total_creditado
        item["total_documentado"] = total_documentado
        item["valor_bloco_m"] = valor_bloco_m
        item["gap_ecd"] = gap_ecd
        item["dif_documentado_m"] = dif_documentado_m
        item["cobertura_documental_pct"] = cobertura

        if valor_ecd > 0 and total_documentado == 0 and valor_bloco_m == 0:
            item["status"] = "SEM_DOCUMENTO_E_SEM_BLOCO_M"
        elif valor_ecd > 0 and total_documentado == 0:
            item["status"] = "SEM_DOCUMENTO"
        elif total_documentado > 0 and valor_bloco_m == 0:
            item["status"] = "DOCUMENTADO_SEM_BLOCO_M"
        elif gap_ecd > 0:
            item["status"] = "PARCIAL"
        else:
            item["status"] = "COBERTO"

    return agregado_nat
