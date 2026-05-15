from decimal import Decimal
import logging
import json
from app.fiscal.contexto import get_fiscal_db
from app.fiscal.dto import RegistroFiscalDTO
from app.fiscal.regras.Diagnostico.achado import Achado
from app.fiscal.regras.Diagnostico.base_regras import RegraBase
from app.icms_ipi.icms_helpers import _norm
from app.sped.bloco_D.d100_helpers import resolver_ancora_transp

logger = logging.getLogger(__name__)


class RegraTranspCredPresumidoNaoAproveitadoV1(RegraBase):
    codigo = "TRANSP_CRED_PRES_V1"
    tipo = "OPORTUNIDADE"
    alvo = "ICMS_IPI_CRUZAMENTO_D100"

    def aplicar(self, dto: RegistroFiscalDTO):
        try:
            if not isinstance(dto, RegistroFiscalDTO):
                return None

            if _norm(dto.reg) != "ICMS_IPI_CRUZAMENTO_D100":
                return None

            meta = dto.meta or {}
            versao_id = meta.get("versao_id") or getattr(dto, "versao_id", None)
            db = get_fiscal_db()

            logger.debug(
                "[TRANSP_CRED_PRESUMIDO] entrada | dto_id=%s dto_reg=%s tipo_match=%s status=%s "
                "num_doc=%s chv_cte=%s tipo_prestador=%s base=%s credito=%s",
                getattr(dto, "id", None),
                getattr(dto, "reg", None),
                meta.get("tipo_match"),
                meta.get("status"),
                meta.get("num_doc"),
                meta.get("chv_cte"),
                meta.get("tipo_prestador_detectado"),
                meta.get("base_credito"),
                meta.get("credito_total_estimado"),
            )

            if _norm(meta.get("tipo_match")) != "TRANSP_CRED_PRESUMIDO_NAO_APROVEITADO":
                return None

            if _norm(meta.get("status")) != "OPORTUNIDADE":
                return None

            base = Decimal(str(meta.get("base_credito") or "0"))
            credito_total = Decimal(str(meta.get("credito_total_estimado") or "0"))
            tipo_prestador = _norm(meta.get("tipo_prestador_detectado"))
            exige_revisao_manual = bool(meta.get("exige_revisao_manual"))

            if base <= 0:
                logger.debug("[TRANSP_CRED_PRESUMIDO] bloqueio | motivo=base_invalida")
                return None

            forca_pf = str(meta.get("forca_evidencia_pf") or "").strip().upper()
            score_pf = meta.get("score_pf")
            antt_prestador = str(meta.get("antt_prestador") or "").strip()

            if tipo_prestador == "PF":
                prioridade = "ALTA"
                permite_autocorrecao = not exige_revisao_manual

            elif tipo_prestador == "PJ":
                prioridade = "MEDIA"
                permite_autocorrecao = False

            else:
                prioridade = "BAIXA"
                permite_autocorrecao = False

            num_doc = str(meta.get("num_doc") or "").strip()
            chv_cte = str(meta.get("chv_cte") or "").strip()
            cod_part = str(meta.get("cod_part") or "").strip()
            evidencia = str(meta.get("evidencia_prestador") or "").strip()
            nome_prestador = str(meta.get("nome_prestador") or "").strip()
            cpf_prestador = str(meta.get("cpf_prestador") or "").strip()
            cfop = str(meta.get("cfop") or "").strip()

            descricao = (
                f"Possível crédito presumido de transporte não aproveitado. "
                f"CT-e {num_doc or '-'} | chave {chv_cte or '-'} | "
                f"base {base} | crédito estimado {credito_total} | "
                f"prestador {tipo_prestador or '-'} | evidência {evidencia or '-'}"
            )

            rid = int(meta.get("registro_id_ancora") or 0)
            reg_ancora = str(meta.get("reg_ancora") or "").strip().upper()
            linha_ancora = meta.get("linha_ancora")

            # 🔥 se não veio do meta, resolve no banco
            if rid <= 0:
                rid, reg_ancora, linha_ancora = resolver_ancora_transp(db, versao_id)

            # 🔒 valida final
            if rid <= 0:
                logger.debug("[TRANSP_CRED] bloqueio | motivo=sem_ancora_resolvida")
                return None

            achado = Achado(
                registro_id=rid,
                tipo=self.tipo,
                codigo=self.codigo,
                descricao=descricao,
                impacto_financeiro=float(credito_total),
                regra="Cruzamento ICMS/IPI D100 x crédito presumido transporte",
                meta={
                    **meta,
                    "registro_id_ancora": rid,
                    "reg_ancora": reg_ancora,
                    "linha_ancora": linha_ancora,
                    "fonte_base": "icms_ipi_d100",
                    "origem": "ICMS_IPI_CRUZAMENTO_D100",
                    "num_doc": num_doc,
                    "chv_cte": chv_cte,
                    "cod_part": cod_part,
                    "cfop": cfop,
                    "tipo_prestador_detectado": tipo_prestador,
                    "evidencia_prestador": evidencia,
                    "nome_prestador": nome_prestador,
                    "cpf_prestador": cpf_prestador,
                    "base_credito": str(base),
                    "credito_total_estimado": str(credito_total),
                    "permite_autocorrecao": permite_autocorrecao,
                    "exige_revisao_manual": exige_revisao_manual,
                    "prioridade_sugerida": prioridade,
                    "forca_evidencia_pf": meta.get("forca_evidencia_pf"),
                    "score_pf": meta.get("score_pf"),
                },
            )


            logger.debug(
                "[TRANSP_CRED_PRESUMIDO] achado_gerado | codigo=%s num_doc=%s chv_cte=%s impacto=%s tipo_prestador=%s",
                achado.codigo,
                num_doc,
                chv_cte,
                achado.impacto_financeiro,
                tipo_prestador,
            )

            return achado

        except Exception as e:
            logger.exception("[ERRO REGRA TRANSP_CRED_PRESUMIDO_NAO_APROVEITADO_V1] %r", e)
            raise