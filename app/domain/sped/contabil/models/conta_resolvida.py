from dataclasses import dataclass


@dataclass(frozen=True)
class ContaResolvida:
    cod_cta: str
    origem: str
    confianca: int
    justificativa: str = ""