from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.config.settings import ALIQUOTA_PIS, ALIQUOTA_COFINS
from app.Legacy.fiscal.settings_fiscais import CSTS_NAO_CREDITAVEIS
from app.Legacy.fiscal.constants import DOMINIOS_LC192, DOM_REVENDA_GAS
from app.Legacy.fiscal.contexto import get_fiscal_db
from app.Legacy.fiscal.dto import RegistroFiscalDTO
from app.Legacy.fiscal.ent_cat_fiscal import carregar_catalogo_fiscal
from app.Legacy.fiscal.regras.Diagnostico.achado import Achado
from app.Legacy.fiscal.regras.Diagnostico.base_regras import RegraBase
from app.Legacy.fiscal.regras.Diagnostico.insumos.insumos_helpers import classificar_item_transp
from app.Legacy.fiscal.regras.Diagnostico.insumos.lc192_helpers import elegivel_lc192_combustivel
from app.Legacy.fiscal.regras.helpers.elegibilidade_dominio import item_cruzamento_elegivel_por_dominio
from app.services.dominio_service import resolver_dominio_por_versao
from app.sped.utils_geral import q2


CODIGO = "COMB_LC192_V1"


class RegraCombLC192V1(RegraBase):
    codigo = CODIGO
    tipo = "OPORTUNIDADE"
    alvo = "C170"

    def aplicar(self, registro: RegistroFiscalDTO) -> Optional[Achado]:
        cfops_uso_consumo = {"1407", "2407", "3407"}
        db = get_fiscal_db()

        if db is None:
            raise RuntimeError("DB não disponível no contexto fiscal.")

        if (registro.reg or "").strip() != self.alvo:
            return None

        campos = registro.dados or []
        if not campos:
            return None

        meta = registro.meta or {}
        dominio = str(
            meta.get("dominio_aplicado")
            or meta.get("dominio")
            or meta.get("dominio_versao")
            or ""
        ).strip().upper()

        if not dominio:
            versao_id = meta.get("versao_id") or getattr(registro, "versao_id", None)
            if versao_id:
                dominio = str(resolver_dominio_por_versao(db, int(versao_id)) or "").strip().upper()

        if dominio not in DOMINIOS_LC192:

            return None

        empresa_id = meta.get("empresa_id") or getattr(registro, "empresa_id", None)
        catalogo = carregar_catalogo_fiscal(db, empresa_id=empresa_id)

        periodo = meta.get("periodo")
        regime = meta.get("regime_apuracao") or meta.get("cod_inc_trib")


        if not periodo or not regime:
            return None
        # ---------------------------
        # CAMPOS C170
        # ---------------------------
        try:
            cfop = str(campos[9] or "").strip()
        except Exception:
            return None
        if cfop.startswith(("5", "6", "7")):
            return None

        vl_item = self.dec_any(campos[5])
        vl_desc = self.dec_any(campos[6])

        # ICMS no C170 geralmente índice 13
        vl_icms = Decimal("0")
        try:
            vl_icms = self.dec_any(campos[13])
        except Exception:
            vl_icms = Decimal("0")

        # CSTs atuais
        cst_pis_atual = str(campos[23] or "").strip() if len(campos) > 23 else ""
        cst_cofins_atual = str(campos[29] or "").strip() if len(campos) > 29 else ""

        cst_pis_atual = cst_pis_atual.zfill(2) if cst_pis_atual else "00"
        cst_cofins_atual = cst_cofins_atual.zfill(2) if cst_cofins_atual else "00"

        # Evita duplicar apontamento se o item já estiver tratado como LC192
        if (
                cst_pis_atual not in CSTS_NAO_CREDITAVEIS
                or cst_cofins_atual not in CSTS_NAO_CREDITAVEIS
        ):
            return None

        # ---------------------------
        # DADOS ENRIQUECIDOS
        # ---------------------------
        ncm = meta.get("ncm")
        descricao = meta.get("descricao") or meta.get("descr_item")

        if not ncm:
            return None

        # ---------------------------
        # CLASSIFICAÇÃO
        # ---------------------------
        cls = classificar_item_transp(
            catalogo,
            ncm=ncm,
            desc_item=descricao,
            nome_part=meta.get("nome_participante"),
            cod_cta=meta.get("cod_cta"),
            origem_cod_cta=meta.get("origem_cod_cta"),
            cst_pis=cst_pis_atual,
            cst_cofins=cst_cofins_atual,
            cfop=cfop,
            periodo=periodo,
        )

        bucket = cls.get("bucket")


        if dominio == DOM_REVENDA_GAS:
            if not catalogo.ncm_match("REVENDA_GAS_LC192_NCM", ncm):
                return None
            bucket = "GLP"
        else:
            # LC192: somente combustível. Não tratar ARLA/lubrificante aqui.
            if bucket != "COMBUSTIVEL":
                return None

        meta_dom = {
            **meta,
            "ncm": ncm,
            "cfop": cfop,
            "descricao": descricao,
            "descricao_item": descricao,
            "dominio_aplicado": dominio,
        }

        if not item_cruzamento_elegivel_por_dominio(meta_dom, catalogo=catalogo):
            return None

        # ---------------------------
        # CATÁLOGO LC192
        # ---------------------------
        if dominio == DOM_REVENDA_GAS:
            grupo_lc192 = "REVENDA_GAS_LC192_NCM"

        else:
            grupo_lc192 = "COMB_LC192_NCM"

        no_catalogo_lc192 = catalogo.ncm_match(grupo_lc192, ncm)

        ok_lc192 = elegivel_lc192_combustivel(
            meta=meta,
            periodo=periodo,
            regime=regime,
            ncm=ncm,
            no_catalogo_lc192=no_catalogo_lc192,
        )

        if not ok_lc192:
            return None

        base_estimada = max(Decimal("0"), vl_item - vl_desc - vl_icms)

        if base_estimada <= 0:
            return None

        pis_estimado = q2(base_estimada * ALIQUOTA_PIS)
        cofins_estimado = q2(base_estimada * ALIQUOTA_COFINS)
        total_estimado = q2(pis_estimado + cofins_estimado)

        if total_estimado <= 0:
            return None
        cfop_sensivel = cfop in cfops_uso_consumo
        # ---------------------------
        # META
        # ---------------------------
        meta_out = {
            **meta,
            "fonte_base": self.alvo,
            "dominio_aplicado": dominio,
            "dominio_lc192": dominio,
            "regra": CODIGO,
            "lc192": True,
            "periodo": periodo,
            "regime_apuracao": regime,
            "grupo_catalogo": grupo_lc192,
            "ncm": ncm,
            "cfop": cfop,
            "descricao_item": descricao,

            # dados atuais
            "cst_pis_atual": cst_pis_atual,
            "cst_cofins_atual": cst_cofins_atual,

            # decisão de correção
            "acao_sugerida": "CORRIGIR_C170_LC192",
            "tipo_correcao": "C170_REPROCESSAMENTO_LC192",
            "modo_correcao": "AUTO_C170_LC192",
            "permite_correcao_automatica": True,

            # nova política decidida
            "novo_cst_pis": "61",
            "novo_cst_cofins": "61",
            "recalcular_c170": True,
            "recalcular_c100": True,
            "segregar_m": True,
            "natureza_credito_m": "206",

            # estimativa
            "vl_item": str(q2(vl_item)),
            "vl_desc": str(q2(vl_desc)),
            "vl_icms": str(q2(vl_icms)),
            "base_calculo_estimada": str(q2(base_estimada)),
            "aliq_pis": "1.65",
            "aliq_cofins": "7.60",
            "valor_pis_estimado": str(pis_estimado),
            "valor_cofins_estimado": str(cofins_estimado),
            "credito_total_estimado": str(total_estimado),
            "cfop_sensivel" : cfop_sensivel,
            "tipo_operacao_lc192": "USO_CONSUMO" if cfop_sensivel else "NORMAL",
            "bucket": bucket,
        }
        return Achado(
            registro_id=int(getattr(registro, "id", 0) or 0),
            tipo=self.tipo,
            codigo=self.codigo,
            descricao=(
                "Possível crédito de PIS/COFINS sobre combustível na janela da "
                f"LC 192/2022. NCM {ncm} | CFOP {cfop} | "
                f"CST atual {cst_pis_atual}/{cst_cofins_atual} → 61/61 | "
                f"crédito estimado R$ {str(total_estimado)}."
            ),
            impacto_financeiro=float(total_estimado),
            regra="Crédito combustível LC 192/2022",
            prioridade="ALTA",
            meta=meta_out,
        )