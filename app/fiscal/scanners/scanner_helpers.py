from __future__ import annotations
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple, Union
from collections import defaultdict
from typing import Dict, Any
from app.fiscal.regras.Diagnostico.achado import Achado

Number = Union[int, float, Decimal]

def norm_codigo(c: Optional[str]) -> str:
    return (str(c).strip() if c is not None else "").strip()

def prioridade_por_impacto(impacto) -> Optional[str]:
    if impacto is None:
        return None
    try:
        val = Decimal(str(impacto))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if val <= 0:
        return None
    if val >= Decimal("5000"):
        return "ALTA"
    if val >= Decimal("1000"):
        return "MEDIA"
    return "BAIXA"

def norm_prioridade(p) -> Optional[str]:
    if p is None:
        return None
    p = str(p).strip().upper()
    if p == "MÉDIA":
        p = "MEDIA"
    return p if p in ("ALTA", "MEDIA", "BAIXA") else None

def safe_float(x) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        try:
            return float(str(x).replace(",", "."))
        except Exception:
            return None

def key_apontamento(registro_id: Optional[int], tipo: str, codigo: Optional[str]) -> Tuple[int, str, str]:
    rid = int(registro_id) if registro_id is not None else 0
    return (rid, str(tipo), norm_codigo(codigo))


def consolidar_achados_cfop_sem_credito_v1(result) -> None:
    """
    Consolida C170_CFOP_SEM_CREDITO_V1 para evitar poluição visual:
    - agrupa por (cfop, cst_pis)
    - remove os individuais
    - cria 1 achado consolidado por grupo
    """
    if not getattr(result, "apontamentos", None):
        return

    grupos: Dict[tuple[str, str], Dict[str, Any]] = defaultdict(
        lambda: {
            "qtd": 0,
            "vl_pis_total": Decimal("0"),
            "vl_cofins_total": Decimal("0"),
            "impacto_total": Decimal("0"),
            "registro_id": None,
            "csts_cofins": set(),
        }
    )

    manter = []

    for a in result.apontamentos:
        codigo = norm_codigo(getattr(a, "codigo", None))
        if codigo != "C170_CFOP_SEM_CREDITO_V1":
            manter.append(a)
            continue

        meta = getattr(a, "meta", None) or {}
        if not isinstance(meta, dict):
            meta = {}

        cfop = str(meta.get("cfop") or "").strip()
        cst_pis = str(meta.get("cst_pis") or "").strip()
        cst_cofins = str(meta.get("cst_cofins") or "").strip()

        chave = (cfop, cst_pis)
        g = grupos[chave]

        if g["registro_id"] is None:
            try:
                g["registro_id"] = int(a.registro_id)
            except Exception:
                g["registro_id"] = None

        if cst_cofins:
            g["csts_cofins"].add(cst_cofins)

        try:
            g["vl_pis_total"] += Decimal(str(meta.get("vl_pis") or "0"))
        except Exception:
            pass

        try:
            g["vl_cofins_total"] += Decimal(str(meta.get("vl_cofins") or "0"))
        except Exception:
            pass

        try:
            g["impacto_total"] += Decimal(str(getattr(a, "impacto_financeiro", 0) or "0"))
        except Exception:
            pass

        g["qtd"] += 1

    for (cfop, cst_pis), g in grupos.items():
        if not g["registro_id"]:
            continue

        vl_pis_total = g["vl_pis_total"].quantize(Decimal("0.01"))
        vl_cofins_total = g["vl_cofins_total"].quantize(Decimal("0.01"))
        impacto_total = g["impacto_total"].quantize(Decimal("0.01"))
        csts_cofins = sorted(g["csts_cofins"])

        desc = (
            "CFOP sem direito a crédito com CST creditável. "
            f"CFOP={cfop or '-'} | CST PIS={cst_pis or '-'} | "
            f"{int(g['qtd'])} ocorrência(s). "
            "Favor verificar o CST adequado para operação sem crédito."
        )

        manter.append(
            Achado(
                registro_id=int(g["registro_id"]),
                tipo="ERRO",
                codigo="C170_CFOP_SEM_CREDITO_V1",
                descricao=desc,
                impacto_financeiro=float(impacto_total),
                regra="CFOP sem direito a crédito com CST creditável",
                meta={
                    "cfop": cfop,
                    "cst_pis": cst_pis,
                    "csts_cofins": csts_cofins,
                    "qtd": int(g["qtd"]),
                    "vl_pis_total": str(vl_pis_total),
                    "vl_cofins_total": str(vl_cofins_total),
                    "impacto_total": str(impacto_total),
                    "consolidado": True,
                },
            )
        )


    result.apontamentos = manter