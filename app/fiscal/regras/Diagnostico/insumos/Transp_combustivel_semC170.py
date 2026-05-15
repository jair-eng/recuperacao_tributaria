from app.fiscal.constants import DOM_GERAL
from app.fiscal.contexto import get_fiscal_db
from app.fiscal.dto import RegistroFiscalDTO
from app.fiscal.ent_cat_fiscal import carregar_catalogo_fiscal
from app.fiscal.regras.Diagnostico.achado import Achado
from app.fiscal.regras.Diagnostico.base_regras import RegraBase
from app.fiscal.regras.Diagnostico.insumos.transp_combustivel_helper import \
    item_candidato_fluxo_manual_combustivel_transp, modo_execucao_combustivel_transp_por_meta, \
    bypassar_combustivel_manual_por_lc192


class RegraTranspCombustivelSemC170V1(RegraBase):
    codigo = "TRANSP_COMBUSTIVEL_SEM_C170_V1"
    tipo = "OPORTUNIDADE"
    alvo = "ICMS_IPI_CRUZAMENTO_ITEM"

    def aplicar(self, dto: RegistroFiscalDTO):
        db = get_fiscal_db()
        if db is None:
            raise RuntimeError("DB não disponível no contexto fiscal.")

        if str(getattr(dto, "reg", "")).upper() != "ICMS_IPI_CRUZAMENTO_ITEM":
            return None

        meta = dto.meta or {}

        if str(meta.get("tipo_match") or "").upper() != "CONTRIB_SEM_C170":
            return None

        if str(meta.get("status") or "").upper() != "NAO_ESCRITURADO":
            return None

        if not bool(meta.get("contrib_tem_c100")):
            return None

        empresa_id = meta.get("empresa_id") or getattr(dto, "empresa_id", None)
        catalogo = carregar_catalogo_fiscal(db, empresa_id=empresa_id)

        cand = item_candidato_fluxo_manual_combustivel_transp(
            catalogo,
            item=meta,
            nome_participante=str(meta.get("participante_nome") or ""),
            periodo=str(meta.get("periodo") or ""),
            origem_dados="ICMS_IPI",
        )
        if not cand:
            return None

        #Bypass do periodo pandemia
        if bypassar_combustivel_manual_por_lc192(
                meta=meta,
                item=cand,
                catalogo=catalogo,
        ):
            return None

        bucket = str(cand.get("bucket") or "")
        subbucket = str(cand.get("subbucket") or "")
        descricao_item = str(cand.get("descricao") or "")
        chave = str(meta.get("chave_nfe") or "")
        num_item = str(meta.get("num_item") or "")
        cfop = str(cand.get("cfop") or "")
        ncm = str(cand.get("ncm") or "")
        nf_icms_item_id = meta.get("nf_icms_item_id")
        registro_id_ancora = meta.get("registro_id_ancora")
        linha_ancora = meta.get("linha_ancora")

        return Achado(
            registro_id=int(getattr(dto, "id", 0) or 0),
            tipo=self.tipo,
            codigo=self.codigo,
            descricao=(
                f"Item de combustível sensível ausente no C170 da EFD Contribuições. "
                f"NF-e {chave or '-'} | item {num_item or '-'} | "
                f"{bucket}/{subbucket or '-'} | "
                f"descrição {descricao_item or '-'} | "
                f"CFOP {cfop or '-'} | NCM {ncm or '-'}"
            ),
            impacto_financeiro=0,
            regra="Fluxo manual de combustível - item faltante",
            meta={
                **meta,
                **cand,
                "executor_fluxo": "COMBUSTIVEL_MANUAL",
                "origem_execucao": modo_execucao_combustivel_transp_por_meta(meta),
                "fonte_base": "icms_ipi_cruzamento",
                "permite_autocorrecao": False,
                "permite_acao_manual": True,
                "exige_revisao_manual": True,
                "modo_correcao": "MANUAL_ONLY",
                "acao_manual_sugerida": "APLICAR_CORRECAO_COMBUSTIVEL",
                "risco_fiscal": "ALTO",
                "nf_icms_item_id": nf_icms_item_id,
                "registro_id_ancora": registro_id_ancora,
                "linha_ancora": linha_ancora,
                "contrib_tem_c100": bool(meta.get("contrib_tem_c100")),
            },
        )