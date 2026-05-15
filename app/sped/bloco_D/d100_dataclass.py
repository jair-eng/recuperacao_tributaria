from dataclasses import dataclass, field


@dataclass
class EvidenciasPrestadorD100:
    cpfs: list[str] = field(default_factory=list)
    cnpjs: list[str] = field(default_factory=list)
    placas: list[str] = field(default_factory=list)
    antts: list[str] = field(default_factory=list)
    nomes_textuais: list[str] = field(default_factory=list)
    textos_fonte: list[str] = field(default_factory=list)

    has_pf_keywords: bool = False
    has_pj_keywords: bool = False
    has_autonomo_keywords: bool = False
    has_subcontratacao_keywords: bool = False