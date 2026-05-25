
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EcdIdentificacao0000:
    cod_ver: str = ""
    dt_ini: str = ""
    dt_fin: str = ""
    nome: str = ""
    cnpj: str = ""
    uf: str = ""
    ie: str = ""
    cod_mun: str = ""


@dataclass
class EcdI010:
    ind_esc: str = ""
    cod_ver_lc: str = ""


@dataclass
class EcdI030:
    dnrc_abert: str = ""
    num_ord: str = ""
    nat_livr: str = ""
    qtd_lin: str = ""
    nome: str = ""
    nire: str = ""
    cnpj: str = ""
    dt_arq: str = ""
    desc_mun: str = ""
    dt_ex_social: str = ""


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
class EcdVinculoI052:
    linha: int
    cod_cta_i050: str
    cod_ccus: str
    cod_agl: str


@dataclass
class EcdPeriodoI150:
    linha: int
    dt_ini: str
    dt_fin: str


@dataclass
class EcdSaldoI155:
    linha: int
    dt_ini: str
    dt_fin: str
    cod_cta: str
    cod_ccus: str
    vl_sld_ini: str
    ind_dc_ini: str
    vl_deb: str
    vl_cred: str
    vl_sld_fin: str
    ind_dc_fin: str


@dataclass
class EcdPeriodoResultadoI350:
    linha: int
    dt_res: str


@dataclass
class EcdResultadoI355:
    linha: int
    dt_res: str
    cod_cta: str
    cod_ccus: str
    vl_cta: str
    ind_dc: str


@dataclass
class EcdDemonstracaoJ005:
    linha: int
    dt_ini: str
    dt_fin: str
    id_dem: str
    cab_dem: str


@dataclass
class EcdBalancoJ100:
    linha: int
    dt_ini: str
    dt_fin: str
    cod_agl: str
    ind_cod_agl: str
    nivel_agl: str
    cod_agl_sup: str
    ind_grp_bal: str
    descr_cod_agl: str
    vl_cta: str
    ind_dc_bal: str
    vl_cta_ini: str
    ind_dc_bal_ini: str
    nota_exp_ref: str


@dataclass
class EcdDreJ150:
    linha: int
    dt_ini: str
    dt_fin: str
    nu_ordem: str
    cod_agl: str
    ind_cod_agl: str
    nivel_agl: str
    cod_agl_sup: str
    descr_cod_agl: str
    vl_cta: str
    ind_vl: str
    vl_cta_ult_dre: str
    ind_vl_ult_dre: str
    ind_grp_dre: str
    nota_exp_ref: str


@dataclass
class EcdTermoEncerramentoJ900:
    linha: int
    dnrc_encer: str
    num_ord: str
    nat_livr: str
    nome: str
    qtd_lin: str
    dt_ini_escr: str
    dt_fin_escr: str


@dataclass
class EcdSignatarioJ930:
    linha: int
    ident_nom: str
    ident_cpf_cnpj: str
    ident_qualif: str
    cod_assin: str
    ind_crc: str
    email: str
    fone: str
    uf_crc: str


@dataclass
class EcdParseResult:
    identificacao: Optional[EcdIdentificacao0000] = None
    i010: Optional[EcdI010] = None
    i030: Optional[EcdI030] = None

    contas_i050: List[EcdContaI050] = field(default_factory=list)
    vinculos_i052: List[EcdVinculoI052] = field(default_factory=list)

    periodos_i150: List[EcdPeriodoI150] = field(default_factory=list)
    saldos_i155: List[EcdSaldoI155] = field(default_factory=list)

    periodos_i350: List[EcdPeriodoResultadoI350] = field(default_factory=list)
    resultados_i355: List[EcdResultadoI355] = field(default_factory=list)

    demonstracoes_j005: List[EcdDemonstracaoJ005] = field(default_factory=list)
    balancos_j100: List[EcdBalancoJ100] = field(default_factory=list)
    dres_j150: List[EcdDreJ150] = field(default_factory=list)

    encerramentos_j900: List[EcdTermoEncerramentoJ900] = field(default_factory=list)
    signatarios_j930: List[EcdSignatarioJ930] = field(default_factory=list)

    contagem_por_registro: Dict[str, int] = field(default_factory=dict)
    registros_ignorados: Dict[str, int] = field(default_factory=dict)