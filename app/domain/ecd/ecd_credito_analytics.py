from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional
from app.utils.sped import reg_linha_sped
from app.utils.numbers import dec_any

from app.utils.dates import normalizar_periodo
from app.utils.numbers import to_decimal




def somar_despesa_ecd_potencial_por_mes_natureza(
    linhas_ecd: Iterable[Dict[str, Any]],
) -> Dict[str, Dict[str, Dict[str, Any]]]:

    acumulado: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(
            lambda: {
                "valor_ecd_elegivel": Decimal("0"),
                "qtd_linhas": 0,
                "codigos_cta": set(),
                "origens": set(),
                "categorias": set(),
                "grupos": set(),
                "fundamentos": set(),
                "naturezas_esperadas": set(),
            }
        )
    )

    for linha in linhas_ecd:
        if not linha:
            continue

        if not bool(linha.get("potencial_credito")):
            continue

        periodo = (
            linha.get("periodo")
            or linha.get("competencia")
            or linha.get("periodo_competencia")
        )
        periodo = normalizar_periodo(periodo)

        nat_bc_cred = (
            linha.get("nat_bc_cred")
            or linha.get("natureza_credito")
            or linha.get("codigo_natureza")
        )

        if not periodo or not nat_bc_cred:
            continue

        nat_bc_cred = str(nat_bc_cred).strip().zfill(2)

        valor = to_decimal(
            linha.get("valor")
            or linha.get("vl_lcto")
            or linha.get("valor_despesa")
            or linha.get("saldo")
        )

        if valor <= 0:
            continue

        item = acumulado[periodo][nat_bc_cred]
        item["valor_ecd_elegivel"] += valor
        item["qtd_linhas"] += 1

        cod_cta = linha.get("cod_cta")
        if cod_cta:
            item["codigos_cta"].add(str(cod_cta))

        origem = linha.get("origem")
        if origem:
            item["origens"].add(str(origem))

        categoria = linha.get("categoria")
        if categoria:
            item["categorias"].add(str(categoria))

        grupo = linha.get("grupo")
        if grupo:
            item["grupos"].add(str(grupo))

        fundamento = linha.get("fundamento")
        if fundamento:
            item["fundamentos"].add(str(fundamento))

        for nat_esp in linha.get("naturezas_esperadas") or []:
            if nat_esp:
                item["naturezas_esperadas"].add(str(nat_esp).strip().zfill(2))

    resultado: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for periodo, por_nat in acumulado.items():
        resultado[periodo] = {}

        for nat, dados in por_nat.items():
            resultado[periodo][nat] = {
                "valor_ecd_elegivel": dados["valor_ecd_elegivel"],
                "qtd_linhas": dados["qtd_linhas"],
                "codigos_cta": sorted(dados["codigos_cta"]),
                "origens": sorted(dados["origens"]),
                "categorias": sorted(dados["categorias"]),
                "grupos": sorted(dados["grupos"]),
                "fundamentos": sorted(dados["fundamentos"]),
                "naturezas_esperadas": sorted(dados["naturezas_esperadas"]),
            }

    return resultado

def comparar_ecd_elegivel_vs_efd_declarada(
    ecd_por_mes_nat: Dict[str, Dict[str, Dict[str, Any]]],
    efd_por_mes_nat: Dict[str, Dict[str, Dict[str, Any]]],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Compara despesa elegível ECD x base declarada EFD por período/natureza.

    Entrada esperada:

    ecd_por_mes_nat:
    {
        "202401": {
            "03": {"valor_ecd_elegivel": Decimal("1500.00")}
        }
    }

    efd_por_mes_nat:
    {
        "202401": {
            "03": {"base_efd_declarada": Decimal("1000.00")}
        }
    }
    """

    resultado: Dict[str, Dict[str, Dict[str, Any]]] = {}

    periodos = sorted(set(ecd_por_mes_nat.keys()) | set(efd_por_mes_nat.keys()))

    for periodo in periodos:
        resultado[periodo] = {}

        naturezas = sorted(
            set((ecd_por_mes_nat.get(periodo) or {}).keys())
            | set((efd_por_mes_nat.get(periodo) or {}).keys())
        )

        for nat in naturezas:
            dados_ecd = (ecd_por_mes_nat.get(periodo) or {}).get(nat) or {}
            dados_efd = (efd_por_mes_nat.get(periodo) or {}).get(nat) or {}

            valor_ecd = dados_ecd.get("valor_ecd_elegivel") or Decimal("0")
            base_efd = dados_efd.get("base_efd_declarada") or Decimal("0")

            if not isinstance(valor_ecd, Decimal):
                valor_ecd = Decimal(str(valor_ecd or "0"))

            if not isinstance(base_efd, Decimal):
                base_efd = Decimal(str(base_efd or "0"))

            gap_base = valor_ecd - base_efd

            if valor_ecd > 0:
                cobertura_pct = ((base_efd / valor_ecd) * Decimal("100")).quantize(
                    Decimal("0.01")
                )
            else:
                cobertura_pct = Decimal("0.00")

            if valor_ecd <= 0 and base_efd > 0:
                status = "SEM_ECD"
            elif valor_ecd > 0 and base_efd <= 0:
                status = "SEM_EFD"
            elif base_efd < valor_ecd:
                status = "PARCIAL"
            elif base_efd == valor_ecd:
                status = "COBERTO"
            else:
                status = "EXCEDENTE_EFD"

            categorias = dados_ecd.get("categorias") or []
            grupos = dados_ecd.get("grupos") or []
            fundamentos = dados_ecd.get("fundamentos") or []
            naturezas_esperadas = dados_ecd.get("naturezas_esperadas") or []

            resultado[periodo][nat] = {
                "periodo": periodo,
                "nat_bc_cred": nat,
                "valor_ecd_elegivel": valor_ecd.quantize(Decimal("0.01")),
                "base_efd_declarada": base_efd.quantize(Decimal("0.01")),
                "gap_base": gap_base.quantize(Decimal("0.01")),
                "cobertura_pct": cobertura_pct,
                "status": status,

                # Enriquecimento ECD / catálogo
                "categorias": categorias,
                "grupos": grupos,
                "fundamentos": fundamentos,
                "naturezas_esperadas": naturezas_esperadas,

                "ecd": dados_ecd,
                "efd": dados_efd,
            }

    return resultado



def montar_efd_declarada_por_mes_natureza(
    linhas_bloco_m: Iterable[str],
    *,
    periodo: str,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Lê o Bloco M declarado e agrega base por período/natureza.

    Usa:
    - M100/M500 para identificar COD_CRED atual
    - M105/M505 para identificar NAT_BC_CRED, CST e base declarada

    Saída:
    {
        "202401": {
            "03": {
                "base_efd_declarada": Decimal("1000.00"),
                "qtd_linhas": 2,
                "cod_creds": ["201"],
                "csts": ["50"],
            }
        }
    }
    """

    periodo_norm = normalizar_periodo(periodo)
    if not periodo_norm:
        raise ValueError(f"Período inválido para Bloco M: {periodo}")

    resultado: Dict[str, Dict[str, Dict[str, Any]]] = {
        periodo_norm: {}
    }

    cod_cred_atual_pis: Optional[str] = None
    cod_cred_atual_cofins: Optional[str] = None

    for linha in linhas_bloco_m or []:
        linha = (linha or "").strip()
        if not linha:
            continue

        if not linha.startswith("|"):
            linha = "|" + linha
        if not linha.endswith("|"):
            linha = linha + "|"

        campos: List[str] = linha.split("|")
        reg = reg_linha_sped(linha)

        if reg == "M100":
            # |M100|COD_CRED|IND_CRED_ORI|VL_BC_PIS|...
            cod_cred_atual_pis = campos[2].strip() if len(campos) > 2 else None
            continue

        if reg == "M500":
            # |M500|COD_CRED|IND_CRED_ORI|VL_BC_COFINS|...
            cod_cred_atual_cofins = campos[2].strip() if len(campos) > 2 else None
            continue

        if reg not in ("M105", "M505"):
            continue

        # Estrutura usada no seu próprio gerador:
        # |M105|NAT_BC_CRED|CST_PIS|VL_BC_PIS_TOT|...|
        # |M505|NAT_BC_CRED|CST_COFINS|VL_BC_COFINS_TOT|...|
        nat = campos[2].strip().zfill(2) if len(campos) > 2 else ""
        cst = campos[3].strip().zfill(2) if len(campos) > 3 else ""
        base = dec_any(campos[4] if len(campos) > 4 else "0")

        if not nat or base <= 0:
            continue

        cod_cred = cod_cred_atual_pis if reg == "M105" else cod_cred_atual_cofins

        por_nat = resultado[periodo_norm].setdefault(
            nat,
            {
                "base_efd_declarada": Decimal("0.00"),
                "base_cofins_declarada": Decimal("0.00"),
                "base_pis_declarada": Decimal("0.00"),
                "qtd_linhas": 0,
                "cod_creds": set(),
                "csts": set(),
                "regs": set(),
            },
        )

        if reg == "M105":
            por_nat["base_pis_declarada"] += base

        if reg == "M505":
            por_nat["base_cofins_declarada"] += base
        por_nat["qtd_linhas"] += 1
        por_nat["regs"].add(reg)

        if cod_cred:
            por_nat["cod_creds"].add(cod_cred)

        if cst:
            por_nat["csts"].add(cst)

    # converter sets para listas
    for nat, dados in resultado[periodo_norm].items():
        pis = dados["base_pis_declarada"].quantize(Decimal("0.01"))
        cofins = dados["base_cofins_declarada"].quantize(Decimal("0.01"))

        dados["base_pis_declarada"] = pis
        dados["base_cofins_declarada"] = cofins

        # base principal usada no comparador
        dados["base_efd_declarada"] = max(pis, cofins)

        dados["cod_creds"] = sorted(dados["cod_creds"])
        dados["csts"] = sorted(dados["csts"])
        dados["regs"] = sorted(dados["regs"])

    return resultado