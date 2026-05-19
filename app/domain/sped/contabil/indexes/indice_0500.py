from app.domain.sped.contabil.models.conta_0500 import Conta0500


def indexar_0500(
    contas: list[Conta0500],
) -> dict[str, Conta0500]:

    out: dict[str, Conta0500] = {}

    for conta in contas:
        if not conta.cod_cta:
            continue

        out[conta.cod_cta] = conta

    return out