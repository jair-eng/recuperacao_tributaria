from dataclasses import dataclass
from typing import Optional


@dataclass
class EcdIdentificacao:
    cod_ver: str = ""
    cod_fin: str = ""
    dt_ini: str = ""
    dt_fin: str = ""
    nome: str = ""
    cnpj: str = ""


@dataclass
class EcdContaI050:
    linha: int
    dt_alt: str
    cod_nat: str
    ind_cta: str
    nivel: str
    cod_cta: str
    cod_cta_sup: str
    cta: str


@dataclass
class EcdContaReferencialI051:
    linha: int
    cod_cta: str
    cod_ccus: str
    cod_cta_ref: str


@dataclass
class EcdSaldoI155:
    linha: int
    cod_cta: str
    cod_ccus: str
    vl_sld_ini: str
    ind_dc_ini: str
    vl_deb: str
    vl_cred: str
    vl_sld_fin: str
    ind_dc_fin: str


@dataclass
class EcdDreJ150:
    linha: int
    cod_agl: str
    nivel_agl: str
    descr_cod_agl: str
    vl_cta: str
    ind_vl: str
    cod_cta: Optional[str] = None