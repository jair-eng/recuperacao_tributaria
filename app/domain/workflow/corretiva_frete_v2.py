from app.db.models import EfdApontamento

from sqlalchemy.orm import Session
from typing import Any, Dict, Optional

from app.domain.fiscal.frete_transp.insercao_frete import inserir_f100s_do_f010_encadeados

def _aplicar_corretiva_frete_v2(
    db: Session,
    *,
    apontamento: EfdApontamento,
    meta: Dict[str, Any],
    cache: dict | None = None,
) -> Dict[str, Any]:
    """
    Aplica a corretiva V2 para contratos de frete ausentes no F100.

    Cenário atualmente suportado:

    - 0140 já existe;
    - 0150 já existe;
    - F010 já existe;
    - F100 do contrato está ausente.

    Cenários que exigem criação de 0140, 0150 ou F010
    serão tratados posteriormente.
    """

    versao_id = int(apontamento.versao_id)

    criar_0140 = bool(meta.get("criar_0140"))
    criar_0150 = bool(meta.get("criar_0150"))
    criar_f010 = bool(meta.get("criar_f010"))
    criar_f100 = bool(meta.get("criar_f100"))

    # ------------------------------------------------------------
    # Validação do cenário atualmente suportado
    # ------------------------------------------------------------
    if criar_0140 or criar_0150 or criar_f010:
        return {
            "ok": False,
            "status": "skip",
            "msg": (
                "Corretiva de frete ainda não suporta criação "
                "de 0140, 0150 ou F010."
            ),
        }

    if not criar_f100:
        return {
            "ok": False,
            "status": "skip",
            "msg": "Apontamento não requer criação de F100.",
        }

    # ------------------------------------------------------------
    # F010 diagnosticado
    # ------------------------------------------------------------
    estabelecimento_f010 = meta.get("estabelecimento_f010") or {}

    registro_id_f010 = estabelecimento_f010.get("registro_id_f010")
    linha_f010 = estabelecimento_f010.get("linha_inicio")

    if not registro_id_f010 or linha_f010 is None:
        return {
            "ok": False,
            "status": "erro",
            "msg": (
                "F010 existente sem registro_id ou linha_inicio "
                "para inserção do F100."
            ),
        }

    # ------------------------------------------------------------
    # Participante diagnosticado
    # ------------------------------------------------------------
    participante = meta.get("participante") or {}
    cod_part = participante.get("cod_part")

    if not cod_part:
        return {
            "ok": False,
            "status": "erro",
            "msg": "Participante existente sem COD_PART.",
        }

    # ------------------------------------------------------------
    # Dados do contrato
    # ------------------------------------------------------------
    contrato = meta.get("contrato") or {}
    frete = contrato.get("frete") or {}
    enq = meta.get("enquadramento") or {}

    numero_f100 = (
        meta.get("numero_f100")
        or contrato.get("numero_f100")
    )

    valor_frete = frete.get("valor_frete")
    data_frete = frete.get("data")

    # ------------------------------------------------------------
    # Enquadramento fiscal
    # ------------------------------------------------------------
    cst_pis = (
        meta.get("cst_pis_destino")
        or enq.get("cst_pis_destino")
    )

    cst_cofins = (
        meta.get("cst_cofins_destino")
        or enq.get("cst_cofins_destino")
    )

    aliq_pis = (
        enq.get("aliq_pis")
        or meta.get("aliq_pis")
    )

    aliq_cofins = (
        enq.get("aliq_cofins")
        or meta.get("aliq_cofins")
    )

    nat_bc_cred = (
        enq.get("nat_bc_cred")
        or enq.get("base_credito_codigo")
        or meta.get("nat_bc_cred")
    )

    cod_cred = (
        meta.get("cod_cred")
        or meta.get("tipo_credito_codigo")
        or meta.get("tipo_credito")
        or enq.get("cod_cred")
        or enq.get("tipo_credito_codigo")
        or enq.get("tipo_credito")
    )

    cod_cta = meta.get("cod_cta")

    # ------------------------------------------------------------
    # Dados necessários para montagem do F100
    # ------------------------------------------------------------
    frete_para_insercao = {
        "numero_f100": str(numero_f100 or "").strip(),
        "cod_part": str(cod_part or "").strip(),
        "data": data_frete,
        "valor_frete": valor_frete,
        "cst_pis": cst_pis,
        "cst_cofins": cst_cofins,
        "aliq_pis": aliq_pis,
        "aliq_cofins": aliq_cofins,
        "nat_bc_cred": nat_bc_cred,
        "cod_cred": cod_cred,
        "cod_cta": cod_cta,
        "periodo": meta.get("periodo"),
    }

    # ------------------------------------------------------------
    # Criar revisão INSERT do F100
    # ------------------------------------------------------------
    resultado_insercao = inserir_f100s_do_f010_encadeados(
        db,
        versao_origem_id=versao_id,
        fretes=[frete_para_insercao],
        registro_id_f010=int(registro_id_f010),
        linha_f010=int(linha_f010),
        apontamento_id=int(apontamento.id),
        motivo_codigo="CORRETIVA_F100_FRETE",
    )

    total_inseridos = int(
        resultado_insercao.get("total_inseridos") or 0
    )

    if total_inseridos <= 0:
        return {
            "ok": False,
            "status": "erro",
            "msg": "Nenhum F100 foi inserido pela corretiva de frete.",
        }

    # ------------------------------------------------------------
    # Resultado
    # ------------------------------------------------------------
    return {
        "ok": True,
        "status": "APLICADO",
        "tipo_corretiva": "INSERIR_F100_FRETE",

        "apontamento_id": int(apontamento.id),
        "versao_id": versao_id,

        "registro_id_f010": int(registro_id_f010),
        "linha_f010": int(linha_f010),

        "cod_part": str(cod_part),
        "numero_f100": str(numero_f100),
        "data_frete": data_frete,
        "valor_frete": valor_frete,

        "cod_cta": cod_cta,
        "cod_cred": cod_cred,
        "nat_bc_cred": nat_bc_cred,

        "cst_pis": cst_pis,
        "aliq_pis": aliq_pis,
        "cst_cofins": cst_cofins,
        "aliq_cofins": aliq_cofins,

        "total_inseridos": total_inseridos,
        "linha_fim_bloco": resultado_insercao.get("linha_fim_bloco"),
        "revisao_fim_bloco_id": resultado_insercao.get(
            "revisao_fim_bloco_id"
        ),
    }
#
# if __name__ == "__main__":
#
#     from app.db.session import SessionLocal
#
#     db = SessionLocal()
#
#     try:
#         apontamento_id_teste = 62594  # contrato 3835
#
#         apontamento = (
#             db.query(EfdApontamento)
#             .filter(EfdApontamento.id == apontamento_id_teste)
#             .first()
#         )
#
#         if not apontamento:
#             raise ValueError(
#                 f"Apontamento {apontamento_id_teste} não encontrado."
#             )
#
#         meta = apontamento.meta_json or {}
#         from app.domain.workflow.corretiva_v2_service import aplicar_corretiva_apontamento_v2
#
#         resultado = aplicar_corretiva_apontamento_v2(
#             db=db,
#             apontamento_id=62594,
#         )
#
#         print("\nRESULTADO CORRETIVA:")
#         print(resultado)
#
#         db.rollback()
#
#     finally:
#         db.close()