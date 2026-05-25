from dataclasses import dataclass

from app.domain.ecd.ecd_models import EcdParseResult


@dataclass
class EcdIndexes:
    contas_por_cod_cta: dict
    saldos_por_cod_cta: dict
    dre_por_cod_agl: dict
    vinculos_agl_por_cod_cta: dict

    def build_ecd_indexes(
            parsed: EcdParseResult,
    ) -> EcdIndexes: