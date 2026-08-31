from decimal import Decimal

import re
from app.sped.blocoC.c100_utils import patch_c100_totais_imposto
from app.utils.sped import split_linha_sped, dec_sped_safe, reg_linha_sped


def normalizar_c100_c170_exportado(linhas: list[str]) -> list[str]:
    """
    Pós-processamento estrutural do Bloco C após overlay/revisões.

    Executa sobre o arquivo final já consolidado:
      - renumera NUM_ITEM dos C170;
      - recalcula VL_PIS/VL_COFINS do C100;
      - preserva a ordem das linhas.
    """
    if not linhas:
        return linhas

    novas = list(linhas)

    idx_c100_atual: int | None = None
    idxs_c170_do_c100: list[int] = []

    def fechar_c100() -> None:
        nonlocal idx_c100_atual, idxs_c170_do_c100, novas

        if idx_c100_atual is None:
            return

        total_pis = Decimal("0.00")
        total_cofins = Decimal("0.00")

        # Renumera e soma
        for seq, idx_c170 in enumerate(idxs_c170_do_c100, start=1):

            partes170 = split_linha_sped(novas[idx_c170])

            if not partes170 or partes170[0].upper() != "C170":
                continue

            dados170 = partes170[1:]

            if len(dados170) < 36:
                dados170.extend([""] * (36 - len(dados170)))
            elif len(dados170) > 36:
                dados170 = dados170[:36]

            # NUM_ITEM
            dados170[0] = str(seq)

            # VL_PIS
            if len(dados170) > 28:
                total_pis += dec_sped_safe(dados170[28])

            # VL_COFINS
            if len(dados170) > 34:
                total_cofins += dec_sped_safe(dados170[34])

            novas[idx_c170] = "|" + "|".join(["C170"] + dados170) + "|"

        # Atualiza o C100
        partes100 = split_linha_sped(novas[idx_c100_atual])

        if partes100 and partes100[0].upper() == "C100":

            dados100 = partes100[1:]

            cod_sit = str(dados100[4] if len(dados100) > 4 else "").strip()

            # Para documento cancelado, cancelado extemporâneo, denegado ou inutilizado,
            # não preencher valores/totais.
            if cod_sit not in {"02", "03", "04", "05"}:
                dados100 = patch_c100_totais_imposto(
                    dados100,
                    total_pis,
                    total_cofins,
                )

                novas[idx_c100_atual] = "|" + "|".join(["C100"] + dados100) + "|"

        idx_c100_atual = None
        idxs_c170_do_c100 = []

    for i, linha in enumerate(novas):

        reg = reg_linha_sped(linha).upper()

        # Encontrou outro C100 → fecha o anterior
        if reg == "C100":
            fechar_c100()
            idx_c100_atual = i
            idxs_c170_do_c100 = []
            continue

        # Acumula apenas os C170 pertencentes ao C100 atual
        if reg == "C170" and idx_c100_atual is not None:
            idxs_c170_do_c100.append(i)



    # Fecha o último documento
    fechar_c100()

    return novas






def normalizar_documento(documento):

    if not documento:
        return ""

    return re.sub(
        r"\D",
        "",
        str(documento)
    )


def normalizar_valor(valor):

    if valor is None:
        return Decimal("0.00")

    valor = str(valor)

    valor = valor.replace(".", "")
    valor = valor.replace(",", ".")

    return Decimal(valor)


def normalizar_data(data):

    if not data:
        return ""

    return data.replace("/", "")