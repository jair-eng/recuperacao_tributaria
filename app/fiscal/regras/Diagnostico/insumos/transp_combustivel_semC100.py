from app.fiscal.contexto import get_fiscal_db
from app.fiscal.dto import RegistroFiscalDTO
from app.fiscal.ent_cat_fiscal import carregar_catalogo_fiscal
from app.fiscal.regras.Diagnostico.achado import Achado
from app.fiscal.regras.Diagnostico.base_regras import RegraBase
from app.fiscal.regras.Diagnostico.insumos.transp_combustivel_helper import \
    filtrar_itens_fluxo_manual_combustivel_transp, resumir_itens_fluxo_manual_combustivel_transp, \
    bypassar_combustivel_manual_por_lc192


class RegraTranspCombustivelSemC100V1(RegraBase):
    codigo = "TRANSP_COMBUSTIVEL_SEM_C100_V1"
    tipo = "OPORTUNIDADE"
    alvo = "ICMS_IPI_CRUZAMENTO_NF"

    def aplicar(self, dto: RegistroFiscalDTO):
        db = get_fiscal_db()
        if db is None:
            raise RuntimeError("DB não disponível no contexto fiscal.")

        if str(getattr(dto, "reg", "")).upper() != "ICMS_IPI_CRUZAMENTO_NF":
            return None
        meta = dto.meta or {}
        if str(meta.get("cod_mod") or "") != "55":
            return None
        if str(meta.get("tipo_match") or "").upper() != "CONTRIB_SEM_C100":
            return None
        if str(meta.get("status") or "").upper() != "NAO_ESCRITURADO":
            return None
        if not bool(meta.get("nota_elegivel_para_insercao")):
            return None
        itens_contexto = list(meta.get("itens_contexto") or [])
        if not itens_contexto:
            return None
        empresa_id = meta.get("empresa_id") or getattr(dto, "empresa_id", None)
        catalogo = carregar_catalogo_fiscal(db, empresa_id=empresa_id)

        itens_comb = filtrar_itens_fluxo_manual_combustivel_transp(
            catalogo,
            itens=itens_contexto,
            nome_participante=str(meta.get("participante_nome") or ""),
            periodo=str(meta.get("periodo") or ""),
            origem_dados="ICMS_IPI",
        )
        if not itens_comb:
            return None

        # Bypass do periodo pandemia
        itens_comb = [
            it for it in itens_comb
            if not bypassar_combustivel_manual_por_lc192(
                meta=meta,
                item=it,
                catalogo=catalogo,
            )
        ]

        if not itens_comb:
            return None

        resumo = resumir_itens_fluxo_manual_combustivel_transp(itens_comb)

        chave = str(meta.get("chave_nfe") or "")
        numero = str(meta.get("numero_nf") or "")
        participante = str(meta.get("participante_nome") or "")

        cfops = sorted({str(it.get("cfop") or "") for it in itens_comb if str(it.get("cfop") or "")})
        ncms = sorted({str(it.get("ncm") or "") for it in itens_comb if str(it.get("ncm") or "")})

        meta_out = {
            **meta,
            "executor_fluxo": "COMBUSTIVEL_MANUAL",
            "origem_execucao": "C100_FALTANTE",
            "fonte_base": "icms_ipi_cruzamento",
            "permite_autocorrecao": False,
            "permite_acao_manual": True,
            "exige_revisao_manual": True,
            "modo_correcao": "MANUAL_ONLY",
            "acao_manual_sugerida": "APLICAR_CORRECAO_COMBUSTIVEL",
            "risco_fiscal": "ALTO",
            "itens_contexto_filtrados": itens_comb,
            "qtd_itens_elegiveis": resumo["qtd_itens"],
            "qtd_combustivel": resumo["qtd_combustivel"],
            "qtd_arla32": resumo["qtd_arla32"],
            "score_total": resumo["score_total"],
            "teses_aplicaveis": resumo["teses_aplicaveis"],
            "cfops_elegiveis_dominio": cfops,
            "ncms_elegiveis_dominio": ncms,
            "contrib_tem_c100": bool(meta.get("contrib_tem_c100")),

        }

        meta_out.pop("registro_id_ancora", None)
        meta_out.pop("linha_ancora", None)
        meta_out.pop("reg_ancora", None)
        if meta.get("contrib_tem_c100"):
            return None

        return Achado(
            registro_id=int(getattr(dto, "id", 0) or 0),
            tipo=self.tipo,
            codigo=self.codigo,
            descricao=(
                f"Nota com combustíveis/ARLA sensíveis ausente no C100 da EFD Contribuições. "
                f"NF-e {chave or '-'} | número {numero or '-'} | "
                f"participante {participante or '-'} | "
                f"CFOPs {', '.join(cfops) if cfops else '-'} | "
                f"NCMs {', '.join(ncms) if ncms else '-'}"
            ),
            impacto_financeiro=0,
            regra="Fluxo manual de combustível - nota faltante",
            meta=meta_out,
        )