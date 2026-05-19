from typing import List, Dict, Any

from app.db.models import Empresa
from app.Legacy.fiscal.contexto import get_fiscal_db
from app.Legacy.fiscal.dto import RegistroFiscalDTO
from app.sped.bloco_D.d100_helpers import obter_base_d100, calcular_credito_presumido,qualificar_prestador_d100
from app.sped.bloco_D.d100_utils import _to_float_br, _only_digits


def cruzar_d100_icms_com_contribuicoes(
    *,
    dtos_icms: List[Dict[str, Any]],
    versao_id: int,
    empresa_id: int,
    dominio: str,
) -> List[RegistroFiscalDTO]:
    """
    Cruzamento D100 ICMS/IPI vs EFD Contribuições.

    V2:
    - Considera D100 como fonte operacional
    - Detecta oportunidade de crédito presumido não aproveitado
    - Classifica PF / PJ / INDETERMINADO
    - PF => permite braço autocorretivo
    - PJ/INDETERMINADO => revisão manual
    """
    db = get_fiscal_db()
    empresa = db.get(Empresa, int(empresa_id)) if empresa_id else None
    cnpj_empresa = _only_digits(getattr(empresa, "cnpj", None)) if empresa else ""
    resultados: List[RegistroFiscalDTO] = []

    if dominio != "TRANSP":
        return resultados

    for d in dtos_icms:
        if not isinstance(d, dict):
            continue

        # -------------------------
        # filtros mínimos
        # -------------------------
        if str(d.get("reg") or "").upper() != "D100":
            continue

        if str(d.get("cod_mod") or "") != "57":
            continue

        if str(d.get("cod_sit") or "") not in {"00", ""}:
            continue

        # -------------------------
        # valores normalizados
        # -------------------------
        vl_doc = _to_float_br(d.get("vl_doc"))
        vl_serv = _to_float_br(d.get("vl_serv"))
        vl_icms = _to_float_br(d.get("vl_icms"))

        base = obter_base_d100(d)

        if not base or base <= 0:
            continue

        # -------------------------
        # qualificação do prestador
        # -------------------------
        prest = qualificar_prestador_d100(d)

        # se não permite crédito e também não merece revisão manual, ignora
        if not prest.get("permite_credito_presumido", False) and not prest.get("exige_revisao_manual", True):
            continue

        # -------------------------
        # cálculo
        # -------------------------
        cred = calcular_credito_presumido(base)


        # -------------------------
        # montar DTO de oportunidade
        # -------------------------
        dto = RegistroFiscalDTO(
            id=0,
            reg="ICMS_IPI_CRUZAMENTO_D100",
            linha=0,
            dados=[],
            is_pf=(prest.get("tipo") == "PF"),
            versao_id=int(versao_id),
            empresa_id=int(empresa_id),
            meta={

                "tipo_match": "TRANSP_CRED_PRESUMIDO_NAO_APROVEITADO",
                "status": "OPORTUNIDADE",
                "origem": "ICMS_IPI",
                "dominio": dominio,
                "cnpj_empresa": empresa.cnpj,

                # identificação
                "cod_part": d.get("cod_part"),
                "num_doc": d.get("num_doc"),
                "chv_cte": d.get("chv_cte"),
                "dt_doc": d.get("dt_doc"),
                "cod_mod": d.get("cod_mod"),
                "cod_sit": d.get("cod_sit"),
                "cfop": d.get("cfop"),

                # valores
                "vl_doc": vl_doc,
                "vl_serv": vl_serv,
                "vl_icms": vl_icms,
                "base_credito": base,

                # cálculo estimado
                "pis_estimado": cred["pis"],
                "cofins_estimado": cred["cofins"],
                "credito_total_estimado": cred["total"],

                # qualificação do prestador
                "tipo_prestador_detectado": prest.get("tipo"),
                "evidencia_prestador": prest.get("evidencia"),
                "cpf_prestador": prest.get("cpf"),
                "cnpj_prestador": prest.get("cnpj"),
                "nome_prestador": prest.get("nome"),
                "antt_prestador": prest.get("antt"),

                # flags
                "permite_autocorrecao": prest.get("tipo") == "PF",
                "exige_revisao_manual": prest.get("exige_revisao_manual", True),

                # placeholder fiscal
                "cst_sugerido": "CRED_PRESUMIDO_TRANSP",

                # rastreabilidade
                "fonte_base": "icms_ipi_d100",

                "forca_evidencia_pf": prest.get("forca_evidencia_pf"),
                "score_pf": prest.get("score_pf"),
            },
        )

        resultados.append(dto)

    return resultados