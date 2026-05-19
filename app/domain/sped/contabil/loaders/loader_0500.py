from dataclasses import dataclass

from app.db.models.efd_registro import EfdRegistro

from app.domain.sped.contabil.models.conta_0500 import Conta0500
from app.domain.sped.contabil.parsers.parse_0500 import parse_0500
from app.domain.sped.contabil.indexes.indice_0500 import indexar_0500
from app.utils.sped import extrair_dados_sped


@dataclass(frozen=True)
class Contabil0500Context:
    contas: list[Conta0500]
    indice: dict[str, Conta0500]


def carregar_0500(
    registros: list[EfdRegistro],
) -> Contabil0500Context:

    contas: list[Conta0500] = []

    for reg in registros:

        if str(reg.reg or "").strip().upper() != "0500":
            continue

        dados = extrair_dados_sped(reg)

        conta = parse_0500(
            dados=dados,
            linha=int(reg.linha or 0),
        )

        if not conta:
            continue

        contas.append(conta)

    indice = indexar_0500(contas)

    return Contabil0500Context(
        contas=contas,
        indice=indice,
    )