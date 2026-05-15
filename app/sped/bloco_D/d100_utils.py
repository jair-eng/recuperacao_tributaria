
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from app.db.models import NfIcmsBase, NfIcmsItem
from collections import defaultdict
from decimal import Decimal
from copy import deepcopy


def _norm_str(v: Any) -> str:
    return "" if v is None else str(v).strip()

def norm_codigo(c: Optional[str]) -> str:
    return (str(c).strip() if c is not None else "").strip()

def _only_digits(v: Any) -> str:
    return "".join(ch for ch in str(v or "") if ch.isdigit())

def _to_float_br(v) -> float:
    if v is None:
        return 0.0
    s = str(v).strip()
    if not s:
        return 0.0

    # formato brasileiro: 6.504,00
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        # formato já normal: 6504.00
        s = s.replace(",", ".")

    try:
        return float(s)
    except Exception:
        return 0.0


def _norm_decimal_str(v: Any) -> str:
    s = _norm_str(v)
    if not s:
        return ""
    try:
        return f"{float(s.replace('.', '').replace(',', '.')):.2f}"
    except Exception:
        try:
            return f"{float(s):.2f}"
        except Exception:
            return ""

def _to_float_db(v) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _norm_date_yyyymmdd(v: Any) -> str:
    s = _only_digits(v)
    return s[:8] if len(s) >= 8 else ""


def match_d100_icms_contrib(
    d100_icms: dict[str, Any],
    d100_contrib: dict[str, Any],
) -> bool:
    """
    Match entre D100 do ICMS/IPI e D100 do EFD Contribuições.

    Regra:
    1) Match principal por CHV_CTE
    2) Fallback por composição documental:
       NUM_DOC + SER + DT_DOC + VL_SERV/VL_DOC

    Observação:
    - função pensada para ser evoluída no futuro
    - hoje serve como camada única de verdade para o match
    """

    if not isinstance(d100_icms, dict) or not isinstance(d100_contrib, dict):
        return False

    # -------------------------
    # 1) Match principal: CHV_CTE
    # -------------------------
    chv_icms = _only_digits(
        d100_icms.get("chv_cte")
        or d100_icms.get("chave")
        or d100_icms.get("chv_doc")
    )
    chv_contrib = _only_digits(
        d100_contrib.get("chv_cte")
        or d100_contrib.get("chave")
        or d100_contrib.get("chv_doc")
    )

    if chv_icms and chv_contrib and chv_icms == chv_contrib:
        return True

    # -------------------------
    # 2) Fallback documental
    # -------------------------
    num_icms = _norm_str(d100_icms.get("num_doc") or d100_icms.get("numero"))
    num_contrib = _norm_str(d100_contrib.get("num_doc") or d100_contrib.get("numero"))

    ser_icms = _norm_str(d100_icms.get("ser") or d100_icms.get("serie"))
    ser_contrib = _norm_str(d100_contrib.get("ser") or d100_contrib.get("serie"))

    dt_icms = _norm_date_yyyymmdd(d100_icms.get("dt_doc"))
    dt_contrib = _norm_date_yyyymmdd(d100_contrib.get("dt_doc"))

    vl_serv_icms = _norm_decimal_str(d100_icms.get("vl_serv") or d100_icms.get("valor_servico"))
    vl_serv_contrib = _norm_decimal_str(d100_contrib.get("vl_serv") or d100_contrib.get("valor_servico"))

    vl_doc_icms = _norm_decimal_str(d100_icms.get("vl_doc") or d100_icms.get("valor_documento"))
    vl_doc_contrib = _norm_decimal_str(d100_contrib.get("vl_doc") or d100_contrib.get("valor_documento"))

    if num_icms and num_contrib and num_icms == num_contrib:
        ser_ok = (not ser_icms or not ser_contrib or ser_icms == ser_contrib)
        dt_ok = (dt_icms and dt_contrib and dt_icms == dt_contrib)

        valor_ok = False
        if vl_serv_icms and vl_serv_contrib and vl_serv_icms == vl_serv_contrib:
            valor_ok = True
        elif vl_doc_icms and vl_doc_contrib and vl_doc_icms == vl_doc_contrib:
            valor_ok = True

        if ser_ok and dt_ok and valor_ok:
            return True

    return False

def carregar_d100_icms(
    db: Session,
    *,
    empresa_id: int,
    periodo: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Carrega documentos de transporte (CT-e / modelo 57) do ICMS/IPI
    para alimentar o cruzamento D100 -> Contribuições.

    V1:
    - usa nf_icms_base (ou equivalente)
    - considera modelo 57
    - devolve estrutura mínima para cruzar e calcular crédito presumido
    """

    q = (
        db.query(NfIcmsBase)
        .options(joinedload(NfIcmsBase.items))
        .filter(NfIcmsBase.empresa_id == int(empresa_id))
        .filter(NfIcmsBase.modelo == "57")
    )


    if periodo:
        q = q.filter(NfIcmsBase.periodo == str(periodo))

    rows = q.order_by(NfIcmsBase.dt_doc.asc(), NfIcmsBase.id.asc()).all()

    out: List[Dict[str, Any]] = []

    for nf in rows:
        itens = getattr(nf, "items", []) or []
        cfop = ""
        for it in itens:
            cfop_item = _only_digits(getattr(it, "cfop", None))
            if cfop_item:
                cfop = cfop_item
                break

        chave = _only_digits(getattr(nf, "chave_nfe", None) or getattr(nf, "chave", None))
        num_doc = _norm_str(getattr(nf, "num_doc", None))
        dt_doc = getattr(nf, "dt_doc", None)

        # cod_part geralmente não vem pronto no nf_icms_base;
        # se você tiver esse vínculo, ótimo. Senão deixa vazio nesta v1.
        cod_part = _norm_str(getattr(nf, "cod_part", None))

        # mesmo raciocínio para série / cfop / municípios
        ser = _norm_str(getattr(nf, "serie", None))

        cod_mun_orig = _norm_str(getattr(nf, "cod_mun_orig", None))
        cod_mun_dest = _norm_str(getattr(nf, "cod_mun_dest", None))

        vl_doc_raw = getattr(nf, "vl_doc", None)
        vl_doc = _to_float_db(vl_doc_raw)

        # no CT-e tomado, na falta de vl_serv separado, usa vl_doc
        vl_serv_raw = getattr(nf, "vl_serv", None) or vl_doc_raw
        vl_serv = _to_float_db(vl_serv_raw)

        out.append(
            {
                "reg": "D100",
                "cod_mod": "57",
                "cod_sit": _norm_str(getattr(nf, "cod_sit", None) or "00"),
                "cod_part": cod_part,
                "ser": ser,
                "num_doc": num_doc,
                "chv_cte": chave,
                "dt_doc": dt_doc.strftime("%d%m%Y") if dt_doc else "",
                "vl_doc": vl_doc,
                "vl_serv": vl_serv,
                "cfop": cfop,
                "cod_mun_orig": cod_mun_orig,
                "cod_mun_dest": cod_mun_dest,
                "nf_icms_base_id": int(getattr(nf, "id")),
                "empresa_id": int(getattr(nf, "empresa_id")),
                "periodo": _norm_str(getattr(nf, "periodo", None)),
                "fonte_base": "nf_icms_base",
                "codigos_0460": list(getattr(nf, "codigos_0460_json", None) or []),
                "evidencias_0460": list(getattr(nf, "evidencias_0460_json", None) or []),
            }
        )

    return out

def consolidar_achados_transp_cred_pres_v1(result) -> None:
    aps = list(result.apontamentos or [])
    if not aps:
        return

    manter = []
    grupos = defaultdict(lambda: {
        "aps": [],
        "impacto": Decimal("0"),
        "base": Decimal("0"),
        "pis": Decimal("0"),
        "cofins": Decimal("0"),
        "qtd": 0,
        "repr": None,
        "docs": [],
        "cpfs_distintos": set(),
        "forcas_pf": [],
        "scores_pf": [],
        "exige_revisao_manual": False,
        "permite_autocorrecao_all": True,
    })

    for a in aps:
        codigo = norm_codigo(getattr(a, "codigo", None))
        if codigo != "TRANSP_CRED_PRES_V1":
            manter.append(a)
            continue

        meta = getattr(a, "meta_json", None) or getattr(a, "meta", None) or {}
        tipo_prestador = str(meta.get("tipo_prestador_detectado") or "").upper()

        # por enquanto agrupa só PF
        if tipo_prestador != "PF":
            manter.append(a)
            continue

        chave = ("TRANSP_CRED_PRES_V1", tipo_prestador)

        g = grupos[chave]
        g["aps"].append(a)
        g["qtd"] += 1
        g["impacto"] += Decimal(str(getattr(a, "impacto_financeiro", 0) or 0))
        g["base"] += Decimal(str(meta.get("base_credito") or 0))
        g["pis"] += Decimal(str(meta.get("pis_estimado") or 0))
        g["cofins"] += Decimal(str(meta.get("cofins_estimado") or 0))
        if g["repr"] is None:
            g["repr"] = a
        cpf = str(meta.get("cpf_prestador") or "").strip()
        if cpf:
            g["cpfs_distintos"].add(cpf)

        forca_pf = str(meta.get("forca_evidencia_pf") or "").strip()
        if forca_pf:
            g["forcas_pf"].append(forca_pf)

        score_pf = meta.get("score_pf")
        if score_pf is not None:
            try:
                g["scores_pf"].append(int(score_pf))
            except Exception:
                pass

        if bool(meta.get("exige_revisao_manual")):
            g["exige_revisao_manual"] = True

        if not bool(meta.get("permite_autocorrecao")):
            g["permite_autocorrecao_all"] = False

        if len(g["docs"]) < 10:
            g["docs"].append({
                "num_doc": meta.get("num_doc"),
                "chv_cte": meta.get("chv_cte"),
                "dt_doc": meta.get("dt_doc"),
                "cfop": meta.get("cfop"),
                "base_credito": str(meta.get("base_credito") or 0),
                "credito_total_estimado": str(meta.get("credito_total_estimado") or 0),
                "cpf_prestador": meta.get("cpf_prestador"),
                "forca_evidencia_pf": meta.get("forca_evidencia_pf"),
                "score_pf": meta.get("score_pf"),
            })

    for (_, tipo_prestador), g in grupos.items():
        if not g["repr"]:
            continue

        base_ap = g["repr"]
        meta_base = deepcopy(getattr(base_ap, "meta_json", None) or getattr(base_ap, "meta", None) or {})

        forca_pf_agregada = None
        if "PF_EVIDENCIA_FRACA" in g["forcas_pf"]:
            forca_pf_agregada = "PF_EVIDENCIA_FRACA"
        elif "PF_EVIDENCIA_MEDIA" in g["forcas_pf"]:
            forca_pf_agregada = "PF_EVIDENCIA_MEDIA"
        elif "PF_EVIDENCIA_FORTE" in g["forcas_pf"]:
            forca_pf_agregada = "PF_EVIDENCIA_FORTE"

        score_pf_agregado = min(g["scores_pf"]) if g["scores_pf"] else None

        meta_base.update({
            "agrupado": True,
            "qtd_docs": g["qtd"],
            "base_total": str(g["base"]),
            "pis_total": str(g["pis"]),
            "cofins_total": str(g["cofins"]),
            "credito_total_estimado": str(g["impacto"]),
            "docs_resumo": g["docs"],
            "tipo_prestador_detectado": tipo_prestador,

            # novos
            "cpfs_distintos": sorted(g["cpfs_distintos"]),
            "qtd_cpfs_distintos": len(g["cpfs_distintos"]),
            "forca_evidencia_pf": forca_pf_agregada,
            "score_pf": score_pf_agregado,
            "exige_revisao_manual": g["exige_revisao_manual"],
            "permite_autocorrecao": g["permite_autocorrecao_all"],
        })

        desc = (
            f"Possível crédito presumido de transporte não aproveitado ({tipo_prestador}). "
            f"{g['qtd']} CT-es | base total {g['base']} | crédito estimado total {g['impacto']}"
        )

        novo = deepcopy(base_ap)
        novo.codigo = "TRANSP_CRED_PRES_AGR_V1"
        novo.descricao = desc
        novo.impacto_financeiro = float(g["impacto"])
        if hasattr(novo, "meta_json"):
            novo.meta_json = meta_base
        elif hasattr(novo, "meta"):
            novo.meta = meta_base

        manter.append(novo)

    result.apontamentos = manter