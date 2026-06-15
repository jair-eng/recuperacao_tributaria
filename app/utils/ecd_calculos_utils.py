from app.utils.numbers import to_decimal

from decimal import Decimal
from typing import Any


def somar_ecd_por_categorias(
    linhas_ecd: list[dict[str, Any]],
    categorias_ecd: list[str],
) -> tuple[Decimal, list[dict[str, Any]]]:
    contas_encontradas = []
    valor_total = Decimal("0.00")
    categorias_set = set(categorias_ecd or [])

    for item in linhas_ecd:
        categoria = str(item.get("categoria") or "")

        if categoria not in categorias_set:
            continue

        valor = to_decimal(item.get("valor"))
        valor_total += valor

        contas_encontradas.append(
            {
                "cod_cta": item.get("cod_cta"),
                "nome_cta": item.get("nome_cta"),
                "valor": valor,
                "categoria": categoria,
                "nat_bc_cred": str(item.get("nat_bc_cred") or "00").zfill(2),
                "naturezas_esperadas": [
                    str(n).zfill(2)
                    for n in (item.get("naturezas_esperadas") or [])
                ],
            }
        )

    return valor_total, contas_encontradas




def calcular_metricas_gap_ecd_efd(
    *,
    base_ecd: Any,
    base_efd: Any,
) -> dict[str, Decimal]:
    ecd = to_decimal(base_ecd)
    efd = to_decimal(base_efd)

    gap = ecd - efd
    if gap < 0:
        gap = Decimal("0.00")

    cobertura_pct = Decimal("0.00")
    if ecd > 0:
        cobertura_pct = (efd / ecd) * Decimal("100")

    return {
        "base_ecd": ecd,
        "base_efd": efd,
        "ecd_elegivel": ecd,
        "efd_declarada": efd,
        "gap": gap,
        "cobertura_pct": cobertura_pct,
    }
def extrair_naturezas_de_contas(contas_ecd: list[dict[str, Any]]) -> set[str]:
    naturezas = set()

    for conta in contas_ecd:
        nat = str(conta.get("nat_bc_cred") or "00").zfill(2)
        if nat != "00":
            naturezas.add(nat)

        for n in conta.get("naturezas_esperadas") or []:
            nat_esp = str(n or "00").zfill(2)
            if nat_esp != "00":
                naturezas.add(nat_esp)

    return naturezas

def nat_list(item: dict[str, Any]) -> list[str]:
    nats = [
        str(n or "00").zfill(2)
        for n in (item.get("naturezas_esperadas") or [])
    ]
    return [n for n in sorted(set(nats)) if n != "00"]