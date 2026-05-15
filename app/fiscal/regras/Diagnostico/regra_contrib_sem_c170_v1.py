from decimal import Decimal
import logging

from app.fiscal.constants import DOM_GERAL
from app.fiscal.contexto import get_fiscal_context, get_fiscal_db
from app.fiscal.dto import RegistroFiscalDTO
from app.fiscal.ent_cat_fiscal import carregar_catalogo_fiscal
from app.fiscal.regras.Diagnostico.achado import Achado
from app.fiscal.regras.Diagnostico.base_regras import RegraBase
from app.fiscal.regras.Diagnostico.insumos.lc192_helpers import elegivel_lc192_combustivel
from app.fiscal.regras.helpers.elegibilidade_dominio import item_cruzamento_elegivel_por_dominio
from app.icms_ipi.icms_helpers import _item_dominio_ok, _norm, _only_digits
from app.services.dominio_service import resolver_dominio_por_versao

logger = logging.getLogger(__name__)


class RegraContribSemC170V1(RegraBase):
    codigo = "CONTRIB_SEM_C170_V1"
    tipo = "OPORTUNIDADE"
    alvo = "ICMS_IPI_CRUZAMENTO_ITEM"


    def aplicar(self, dto: RegistroFiscalDTO):

        db = get_fiscal_db()
        if db is None:
            raise RuntimeError("DB não disponível no contexto fiscal.")

        meta = dto.meta or {}
        versao_id = meta.get("versao_id") or getattr(dto, "versao_id", None)
        empresa_id = meta.get("empresa_id") or getattr(dto, "empresa_id", None)
        catalogo = carregar_catalogo_fiscal(db, empresa_id=empresa_id)

        try:
            if not isinstance(dto, RegistroFiscalDTO):
                return None

            if _norm(dto.reg) != "ICMS_IPI_CRUZAMENTO_ITEM":
                return None

            meta = dto.meta or {}

            if _norm(meta.get("tipo_match")) != "CONTRIB_SEM_C170":
                return None

            if _norm(meta.get("status")) != "NAO_ESCRITURADO":
                return None

            # se o pai já for C100 faltante, não deixa virar C170 faltante
            if _norm(meta.get("tipo_match_pai")) == "CONTRIB_SEM_C100":
                logger.debug("[CONTRIB_SEM_C170] bloqueio | motivo=pai_CONTRIB_SEM_C100")
                return None

            dominio = (
                    meta.get("dominio_aplicado")
                    or meta.get("dominio")
                    or meta.get("dominio_versao")
                    or ""
            )
            if not dominio:

                versao_id = meta.get("versao_id") or getattr(dto, "versao_id", None)
                if versao_id:
                    dominio = resolver_dominio_por_versao(db, int(versao_id))

            dominio = str(dominio or DOM_GERAL).strip().upper()

            # 1) aderência ao domínio
            if not _item_dominio_ok(meta, dominio, catalogo=catalogo):
                logger.debug(
                    "[CONTRIB_SEM_C170] bloqueio | motivo=item_dominio_ok_false dominio=%s chave_nfe=%s cod_item=%s",
                    dominio,
                    meta.get("chave_nfe"),
                    meta.get("cod_item"),
                )
                return None

            # 2) elegibilidade fiscal para inserção por domínio
            if not item_cruzamento_elegivel_por_dominio({
                **meta,
                "dominio": dominio}
                ,catalogo=catalogo,):

                logger.debug(
                    "[CONTRIB_SEM_C170] bloqueio | motivo=item_cruzamento_elegivel_false dominio=%s chave_nfe=%s cod_item=%s ncm=%s cfop=%s",
                    dominio,
                    meta.get("chave_nfe"),
                    meta.get("cod_item"),
                    meta.get("ncm"),
                    meta.get("cfop"),
                )
                return None

            # precisa existir C100 correspondente no Contribuições
            contrib_tem_c100 = meta.get("contrib_tem_c100")
            if contrib_tem_c100 is False:
                logger.debug("[CONTRIB_SEM_C170] bloqueio | motivo=contrib_tem_c100_false")
                return None

            reg_ancora = str(meta.get("reg_ancora") or "").strip().upper()

            rid_meta = meta.get("registro_id_ancora")
            rid_dto = getattr(dto, "id", None)

            logger.debug(
                "[CONTRIB_SEM_C170] rid | rid_meta=%s rid_dto=%s reg_ancora=%s",
                rid_meta,
                rid_dto,
                reg_ancora,
            )

            # mantém o comportamento atual, priorizando o dto.id
            rid = int(rid_meta or rid_dto or 0)

            logger.debug(
                "[CONTRIB_SEM_C170] rid_final | rid_final=%s origem=%s",
                rid,
                "dto.id" if rid_dto else ("meta.registro_id_ancora" if rid_meta else "nenhuma"),
            )

            if rid <= 0:
                logger.debug("[CONTRIB_SEM_C170] bloqueio | motivo=rid_invalido")
                return None

            # mantém a regra atual de âncora C100
            if reg_ancora and reg_ancora != "C100":
                logger.debug(
                    "[CONTRIB_SEM_C170] bloqueio | motivo=reg_ancora_nao_c100 reg_ancora=%s rid_final=%s",
                    reg_ancora,
                    rid,
                )
                return None

            nf_icms_item_id = meta.get("nf_icms_item_id")
            if not nf_icms_item_id:
                logger.debug("[CONTRIB_SEM_C170] bloqueio | motivo=nf_icms_item_id_ausente")
                return None

            chave_nfe = str(meta.get("chave_nfe") or "").strip()
            descricao_item = str(meta.get("descricao") or meta.get("descricao_item") or "").strip()
            cod_item = str(meta.get("cod_item") or "").strip()
            num_item = str(meta.get("num_item") or "").strip()
            cfop = _only_digits(meta.get("cfop"))
            ncm = _only_digits(meta.get("ncm"))
            no_catalogo_lc192 = catalogo.ncm_match("COMB_LC192_NCM", ncm)

            periodo_lc192 = str(meta.get("periodo") or "").strip()

            if not periodo_lc192:
                dt_doc = str(meta.get("dt_doc") or meta.get("data_doc") or "").strip()
                if len(dt_doc) >= 7:
                    periodo_lc192 = dt_doc[:7].replace("-", "")
            if not periodo_lc192:
                chave = str(meta.get("chave_nfe") or "").strip()
                if len(chave) >= 6:
                    aamm = chave[2:6]  # ex: 2208
                    if aamm.isdigit():
                        periodo_lc192 = "20" + aamm

            regime_lc192 = str(
                meta.get("regime_apuracao")
                or meta.get("cod_inc_trib")
                or "1"
            ).strip()

            eh_lc192 = elegivel_lc192_combustivel(
                meta=meta,
                periodo=periodo_lc192,
                regime=regime_lc192,
                ncm=ncm,
                no_catalogo_lc192=no_catalogo_lc192,
            )

            if not cod_item and not descricao_item and not num_item:
                logger.debug("[CONTRIB_SEM_C170] bloqueio | motivo=identificacao_minima_ausente")
                return None

            try:
                impacto = Decimal(str(meta.get("credito_total_estimado") or "0"))
            except Exception:
                impacto = Decimal("0")

            achado = Achado(
                registro_id=rid,
                tipo=self.tipo,
                codigo=self.codigo,
                descricao=(
                    f"Item presente no ICMS/IPI e ausente no C170 da EFD Contribuições. "
                    f"NF-e {chave_nfe or '-'} | item {num_item or '-'} | "
                    f"cod_item {cod_item or '-'} | CFOP {cfop or '-'} | "
                    f"{descricao_item or '-'}"
                ),
                impacto_financeiro=float(impacto),
                regra="Cruzamento ICMS/IPI x EFD Contribuições",
                meta={
                    **meta,
                    "periodo_lc192": periodo_lc192,
                    "regime_lc192": regime_lc192,
                    "fonte_base": "icms_ipi_cruzamento",
                    "origem": "ICMS_IPI_CRUZAMENTO",
                    "dominio_aplicado": dominio,
                    "chave_nfe": chave_nfe,
                    "num_item": num_item,
                    "cod_item": cod_item,
                    "cfop": cfop,
                    "ncm": ncm,
                    "descricao_item": descricao_item,
                    "nf_icms_item_id": nf_icms_item_id,
                    "valor_item_icms": str(meta.get("valor_item_icms") or "0"),
                    "valor_icms_icms": str(meta.get("valor_icms_icms") or "0"),
                    "valor_ipi_icms": str(meta.get("valor_ipi_icms") or "0"),
                    "registro_id_ancora": rid,
                    "linha_ancora": meta.get("linha_ancora"),
                    "reg_ancora": reg_ancora,
                    "contrib_tem_c100": contrib_tem_c100,
                    "lc192": eh_lc192,
                    "possui_lc192": eh_lc192,
                    "acao_sugerida_lc192": "INSERIR_C170_LC192" if eh_lc192 else None,
                    "novo_cst_pis": "61" if eh_lc192 else None,
                    "novo_cst_cofins": "61" if eh_lc192 else None,
                    "natureza_credito_m": "206" if eh_lc192 else None,
                    "recalcular_c170": eh_lc192,
                    "recalcular_c100": eh_lc192,
                    "segregar_m": eh_lc192,
                    "contexto_correcao": "LC192" if eh_lc192 else None,
                    "modo_correcao": "AUTO_C170_LC192" if eh_lc192 else None,
                    "tipo_correcao": "C170_REPROCESSAMENTO_LC192" if eh_lc192 else None,
                },
            )

            logger.debug(
                "[CONTRIB_SEM_C170] achado_gerado | registro_id=%s codigo=%s chave_nfe=%s num_item=%s cod_item=%s",
                achado.registro_id,
                achado.codigo,
                chave_nfe,
                num_item,
                cod_item,
            )

            return achado

        except Exception as e:
            logger.exception("[ERRO REGRA CONTRIB_SEM_C170_V1] %r", e)
            raise