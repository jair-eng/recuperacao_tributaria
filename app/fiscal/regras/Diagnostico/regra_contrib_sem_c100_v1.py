from app.db.models import EfdArquivo, EfdVersao
from app.fiscal.constants import DOM_GERAL
from app.fiscal.contexto import get_fiscal_context, get_fiscal_db
from app.fiscal.dto import RegistroFiscalDTO
from app.fiscal.ent_cat_fiscal import carregar_catalogo_fiscal
from app.fiscal.regras.Diagnostico.achado import Achado
from app.fiscal.regras.Diagnostico.base_regras import RegraBase
from app.fiscal.regras.Diagnostico.insumos.lc192_helpers import elegivel_lc192_combustivel
from app.fiscal.regras.helpers.elegibilidade_dominio import item_cruzamento_elegivel_por_dominio
from app.icms_ipi.icms_helpers import _item_ncm, _item_cfop, _item_dominio_ok, _norm

import logging

logger = logging.getLogger(__name__)


class RegraContribSemC100V1(RegraBase):
    codigo = "CONTRIB_SEM_C100_V1"
    tipo = "OPORTUNIDADE"
    alvo = "ICMS_IPI_CRUZAMENTO_NF"

    def aplicar(self, dto: RegistroFiscalDTO):

        db = get_fiscal_db()
        if db is None:
            raise RuntimeError("DB não disponível no contexto fiscal.")

        meta = dto.meta or {}

        if str(getattr(dto, "reg", "")).upper() != "ICMS_IPI_CRUZAMENTO_NF":
            return None

        #  BLOQUEIO DE D100 (CT-e)
        if str(meta.get("cod_mod") or "") != "55":
            return None

        versao_id = meta.get("versao_id") or getattr(dto, "versao_id", None)
        empresa_id = meta.get("empresa_id") or getattr(dto, "empresa_id", None)
        catalogo = carregar_catalogo_fiscal(db, empresa_id=empresa_id)

        try:
            if not isinstance(dto, RegistroFiscalDTO):
                logger.debug("[CONTRIB_SEM_C100] bloqueio | motivo=nao_dto")
                return None

            if _norm(dto.reg) != "ICMS_IPI_CRUZAMENTO_NF":
                logger.debug(
                    "[CONTRIB_SEM_C100] bloqueio | motivo=reg_invalido reg=%s",
                    getattr(dto, "reg", None),
                )
                return None

            meta = dto.meta or {}

            print(
                "[CONTRIB_SEM_C100] entrada",
                "dto_id=", getattr(dto, "id", None),
                "reg=", getattr(dto, "reg", None),
                "tipo_match=", meta.get("tipo_match"),
                "status=", meta.get("status"),
                "nota_elegivel=", meta.get("nota_elegivel_para_insercao"),
                "itens_contexto=", len(list(meta.get("itens_contexto") or [])),
                "dominio=", meta.get("dominio_aplicado") or meta.get("dominio") or meta.get("dominio_versao"),
                "chave=", meta.get("chave_nfe"),
                "numero=", meta.get("numero_nf"),
                flush=True,
            )
            if _norm(meta.get("tipo_match")) != "CONTRIB_SEM_C100":
                logger.debug(
                    "[CONTRIB_SEM_C100] bloqueio | motivo=tipo_match tipo_match=%s",

                    meta.get("tipo_match"),

                )
                print("[CONTRIB_SEM_C100] bloqueio | motivo=tipo_match", meta.get("tipo_match"), flush=True)
                return None

            if _norm(meta.get("status")) != "NAO_ESCRITURADO":
                print("[CONTRIB_SEM_C100] bloqueio | motivo=status", meta.get("status"), flush=True)
                logger.debug(
                    "[CONTRIB_SEM_C100] bloqueio | motivo=status status=%s",
                    meta.get("status"),

                )
                return None

            if not bool(meta.get("nota_elegivel_para_insercao")):
                print("[CONTRIB_SEM_C100] bloqueio | motivo=nota_elegivel_false", flush=True)
                logger.debug(
                    "[CONTRIB_SEM_C100] bloqueio | motivo=nota_elegivel_false chave=%s numero=%s",
                    meta.get("chave_nfe"),
                    meta.get("numero_nf"),

                )
                return None

            if bool(meta.get("contrib_tem_c100")):
                print(
                    "[CONTRIB_SEM_C100] bloqueio | motivo=contrib_tem_c100",
                    meta.get("chave_nfe"),
                    flush=True,
                )
                return None

            if bool(meta.get("nota_parcial")):
                print(
                    "[CONTRIB_SEM_C100] bloqueio | motivo=nota_parcial",
                    meta.get("chave_nfe"),
                    flush=True,
                )
                return None

            itens_contexto = list(meta.get("itens_contexto") or [])
            if not itens_contexto:
                print("[CONTRIB_SEM_C100] bloqueio | motivo=itens_contexto_vazio", flush=True)
                logger.debug(
                    "[CONTRIB_SEM_C100] bloqueio | motivo=itens_contexto_vazio chave=%s numero=%s",
                    meta.get("chave_nfe"),
                    meta.get("numero_nf"),

                )
                return None

            dominio = (
                    meta.get("dominio_aplicado")
                    or meta.get("dominio")
                    or meta.get("dominio_versao")
                    or DOM_GERAL
            )
            dominio = str(dominio or DOM_GERAL).strip().upper()
            itens_validos = []

            for it in itens_contexto:
                ok_dom = _item_dominio_ok(it, dominio,catalogo=catalogo)
                ok_eleg = item_cruzamento_elegivel_por_dominio({**it, "dominio": dominio},catalogo=catalogo)

                print(
                    "[CONTRIB_SEM_C100] item",
                    "cod_item=", it.get("cod_item"),
                    "cfop=", it.get("cfop"),
                    "ncm=", it.get("ncm"),
                    "descricao=", it.get("descricao") or it.get("descricao_item"),
                    "ok_dom=", ok_dom,
                    "ok_eleg=", ok_eleg,
                    flush=True,
                )

                if ok_dom and ok_eleg:
                    itens_validos.append(it)

            if not itens_validos:
                logger.debug(
                    "[CONTRIB_SEM_C100] bloqueio | motivo=sem_itens_validos chave=%s numero=%s dominio=%s",
                    meta.get("chave_nfe"),
                    meta.get("numero_nf"),
                    dominio,

                )
                print("[CONTRIB_SEM_C100] bloqueio | motivo=sem_itens_validos dominio=", dominio, flush=True)
                return None

            itens_lc192 = []
            # pegando periodo e regime para lc192
            periodo_lc192 = (
                    str(meta.get("periodo") or "").strip()
                    or str(meta.get("periodo_arquivo") or "").strip()
            )

            if not periodo_lc192:
                dt_doc = str(meta.get("dt_doc") or "").strip()
                # dt_doc vem "2022-08-08"
                if len(dt_doc) >= 7:
                    periodo_lc192 = dt_doc[:7].replace("-", "")

            regime_lc192 = str(
                meta.get("regime_apuracao")
                or meta.get("cod_inc_trib")
                or "1"
            ).strip()

            for it in itens_validos:
                ncm_it = _item_ncm(it)
                no_catalogo_lc192 = catalogo.ncm_match("COMB_LC192_NCM", ncm_it)

                if elegivel_lc192_combustivel(
                        meta={**meta, **it},
                        periodo=periodo_lc192,
                        regime=regime_lc192,
                        ncm=ncm_it,
                        no_catalogo_lc192=no_catalogo_lc192,
                ):
                    itens_lc192.append({
                        **it,
                        "lc192": True,
                        "novo_cst_pis": "61",
                        "novo_cst_cofins": "61",
                        "natureza_credito_m": "206",
                        "recalcular_c170": True,
                        "recalcular_c100": True,
                        "segregar_m": True,
                        "contexto_correcao": "LC192",
                        "modo_correcao": "AUTO_C100_C170_LC192",
                        "tipo_correcao": "C100_C170_REPROCESSAMENTO_LC192",
                    })

            logger.debug(
                "[CONTRIB_SEM_C100] achado_gerado | chave=%s numero=%s itens_validos=%s",
                meta.get("chave_nfe"),
                meta.get("numero_nf"),
                len(itens_validos),
            )
            print("[CONTRIB_SEM_C100] REGRA CHAMADA", getattr(dto, "reg", None), flush=True)

            chave = str(meta.get("chave_nfe") or "")
            numero = str(meta.get("numero_nf") or "")
            participante = str(meta.get("participante_nome") or "")

            cfops = sorted({
                _item_cfop(it)
                for it in itens_validos
                if _item_cfop(it)
            })

            ncms = sorted({
                _item_ncm(it)
                for it in itens_validos
                if _item_ncm(it)
            })

            return Achado(
                registro_id=int(getattr(dto, "id", 0) or 0),
                tipo=self.tipo,
                codigo=self.codigo,
                descricao=(
                    f"Nota presente no ICMS/IPI e ausente no C100 da EFD Contribuições. "
                    f"NF-e {chave or '-'} | número {numero or '-'} | "
                    f"participante {participante or '-'} | "
                    f"CFOPs {', '.join(cfops) if cfops else '-'} | "
                    f"NCMs {', '.join(ncms) if ncms else '-'}"
                ),
                impacto_financeiro=0,
                regra="Cruzamento ICMS/IPI x EFD Contribuições",
                meta={
                    **meta,
                    "fonte_base": "icms_ipi_cruzamento",
                    "dominio_aplicado": dominio,
                    # contexto geral
                    "qtd_itens_contexto_total": len(itens_contexto),
                    "qtd_itens_dominio_ok": len(itens_validos),
                    "qtd_itens_elegiveis_dominio": len(itens_validos),
                    # controle da nota
                    "nota_parcial": len(itens_validos) < len(itens_contexto),
                    "possui_itens_nao_elegiveis": len(itens_validos) < len(itens_contexto),
                    # mantém o original intacto
                    "itens_contexto": itens_contexto,
                    # lista filtrada para inserção/correção
                    "itens_contexto_filtrados": itens_validos,
                    # resumos úteis
                    "cfops_elegiveis_dominio": cfops,
                    "ncms_elegiveis_dominio": ncms,
                    "lc192": bool(itens_lc192),
                    "qtd_itens_lc192": len(itens_lc192),
                    "itens_lc192": itens_lc192,
                    "possui_lc192": bool(itens_lc192),
                    "acao_sugerida_lc192": "INSERIR_C100_C170_LC192" if itens_lc192 else None,
                    "novo_cst_pis": "61" if itens_lc192 else None,
                    "novo_cst_cofins": "61" if itens_lc192 else None,
                    "natureza_credito_m": "206" if itens_lc192 else None,
                    "recalcular_c100": bool(itens_lc192),
                    "recalcular_c170": bool(itens_lc192),
                    "segregar_m": bool(itens_lc192),
                    "periodo_lc192": periodo_lc192,
                    "regime_lc192": regime_lc192,
                },
            )
        except Exception as e:
            logger.exception("[ERRO REGRA CONTRIB_SEM_C100_V1] %r", e)
            raise