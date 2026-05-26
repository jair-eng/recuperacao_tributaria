from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

from app.domain.ecd.ecd_models import (
    EcdParseResult,
    EcdContaI050,
    EcdSaldoI155,
    EcdDreJ150,
    EcdVinculoI052,
)


@dataclass
class EcdIndexes:
    contas_por_cod_cta: Dict[str, EcdContaI050]
    saldos_por_cod_cta: Dict[str, List[EcdSaldoI155]]
    dre_por_cod_agl: Dict[str, List[EcdDreJ150]]
    vinculos_agl_por_cod_cta: Dict[str, List[EcdVinculoI052]]


def build_ecd_indexes(parsed: EcdParseResult) -> EcdIndexes:
    contas_por_cod_cta = {
        c.cod_cta: c
        for c in parsed.contas_i050
        if c.cod_cta
    }

    saldos_por_cod_cta = defaultdict(list)
    for saldo in parsed.saldos_i155:
        if saldo.cod_cta:
            saldos_por_cod_cta[saldo.cod_cta].append(saldo)

    dre_por_cod_agl = defaultdict(list)
    for dre in parsed.dres_j150:
        if dre.cod_agl:
            dre_por_cod_agl[dre.cod_agl].append(dre)

    vinculos_agl_por_cod_cta = defaultdict(list)
    for vinculo in parsed.vinculos_i052:
        if vinculo.cod_cta_i050:
            vinculos_agl_por_cod_cta[vinculo.cod_cta_i050].append(vinculo)

    return EcdIndexes(
        contas_por_cod_cta=dict(contas_por_cod_cta),
        saldos_por_cod_cta=dict(saldos_por_cod_cta),
        dre_por_cod_agl=dict(dre_por_cod_agl),
        vinculos_agl_por_cod_cta=dict(vinculos_agl_por_cod_cta),
    )