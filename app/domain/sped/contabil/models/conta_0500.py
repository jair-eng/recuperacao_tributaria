from dataclasses import dataclass
from typing import Any

from app.domain.sped.maps.reg0500_map import IDX_0500
from app.utils.sped import get_sped_str
from app.utils.strings import limpar_texto_sped


@dataclass(frozen=True)
class Conta0500:
    linha: int
    cod_cta: str
    nome_cta: str
    dt_alt: str = ""
    cod_nat_cc: str = ""
    ind_cta: str = ""
    nivel: int | None = None
    cod_cta_ref: str = ""
    cnpj_est: str = ""



def parse_0500_dados(dados: list[Any], linha: int) -> Conta0500 | None:
    cod_cta = get_sped_str(dados, IDX_0500, "cod_cta")
    if not cod_cta:
        return None

    nivel_raw = get_sped_str(dados, IDX_0500, "nivel")
    try:
        nivel = int(nivel_raw) if nivel_raw else None
    except ValueError:
        nivel = None

    return Conta0500(
        linha=linha,
        dt_alt=get_sped_str(dados, IDX_0500, "dt_alt"),
        cod_nat_cc=get_sped_str(dados, IDX_0500, "cod_nat_cc"),
        ind_cta=get_sped_str(dados, IDX_0500, "ind_cta"),
        nivel=nivel,
        cod_cta=cod_cta,
        nome_cta=limpar_texto_sped(get_sped_str(dados, IDX_0500, "nome_cta")),
        cod_cta_ref=get_sped_str(dados, IDX_0500, "cod_cta_ref"),
        cnpj_est=get_sped_str(dados, IDX_0500, "cnpj_est"),
    )