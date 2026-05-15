from app.fiscal.regras.Diagnostico.insumos.insumos_base import RegraC170InsumosBase


class RegraC170InsumosCafeV1(RegraC170InsumosBase):
    codigo = "C170_INSUMO_CAFE_V1"
    nome = "Possível crédito por insumo (C170) — café"

    SLUG_CFOP_ENTRADA = "CFOP_ENTRADA_REVENDA"
    SLUG_CST_PIS_ALVO_CRED = "SUP_CST_PIS_CREDITO"
    SLUG_CST_COF_ALVO_CRED = "SUP_CST_COFINS_CREDITO"
    SLUG_CST_PIS_SEM_CRED = "CST_PIS_AQUIS_SEM_CRED"
    SLUG_CST_COF_SEM_CRED = "CST_COFINS_AQUIS_SEM_CRED"

    SLUG_NCM_GRAOS_10 = "NCM_GRAOS_FAMILIA_10"
    SLUG_NCM_GRAOS_12 = "NCM_GRAOS_FAMILIA_12"

    def _definir_prioridade(self, cat, acc: dict, meta0: dict) -> str:
        for ncm in list(acc["base_por_ncm"].keys())[:400]:
            if self.ncm_match(cat, self.SLUG_NCM_GRAOS_10, ncm) or self.ncm_match(cat, self.SLUG_NCM_GRAOS_12, ncm):
                return "MEDIA"
        return "BAIXA"