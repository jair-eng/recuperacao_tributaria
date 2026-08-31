from app.utils.normalizacao_utils import normalizar_valor, normalizar_data, normalizar_documento

from pathlib import Path
import re


def extrair_campo(secao, campo):

    resultado = re.search(
        rf"^{re.escape(campo)}:\s*(.*)$",
        secao,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    if resultado:

        valor = resultado.group(1).strip()

        if valor == "None":
            return None

        return valor

    return None

def extrair_contrato_do_bloco(bloco):

    contrato = {
        "numero_f100": None,

        "contratante": {
            "nome": None,
            "documento": None,
            "ie": None,
            "logradouro": None,
            "numero": None,
            "bairro": None,
            "cep": None,
            "municipio": None,
            "uf": None,
        },

        "contratado": {
            "nome": None,
            "documento": None,
            "ie": None,
            "rntrc": None,
            "logradouro": None,
            "numero": None,
            "complemento": None,
            "bairro": None,
            "cep": None,
            "municipio": None,
            "uf": None,
        },

        "motorista": {
            "nome": None,
            "documento": None,
        },

        "operacao": {
            "numero_interno": None,
            "ciot": None,
            "contrato_completo": None,
            "numero_contrato": None,
        },

        "frete": {
            "cte": None,
            "data": None,
            "valor_frete": None,
            "valor_liquido": None,
        },
    }

    # -----------------------------------------
    # NÚMERO F100
    # -----------------------------------------

    contrato["numero_f100"] = extrair_campo(
        bloco,
        "Número F100"
    )

    # -----------------------------------------
    # CONTRATANTE
    # -----------------------------------------

    resultado = re.search(
        r"CONTRATANTE\s*(.*?)(?=\nCONTRATADO)",
        bloco,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if resultado:

        secao = resultado.group(1)

        contrato["contratante"]["nome"] = extrair_campo(
            secao,
            "Nome"
        )

        contrato["contratante"]["documento"] = extrair_campo(
            secao,
            "Documento"
        )

        contrato["contratante"]["ie"] = extrair_campo(
            secao,
            "IE"
        )

        contrato["contratante"]["logradouro"] = extrair_campo(
            secao,
            "Logradouro"
        )

        contrato["contratante"]["numero"] = extrair_campo(
            secao,
            "Número"
        )

        contrato["contratante"]["bairro"] = extrair_campo(
            secao,
            "Bairro"
        )

        contrato["contratante"]["cep"] = extrair_campo(
            secao,
            "CEP"
        )

        contrato["contratante"]["municipio"] = extrair_campo(
            secao,
            "Município"
        )

        contrato["contratante"]["uf"] = extrair_campo(
            secao,
            "UF"
        )

    # -----------------------------------------
    # CONTRATADO
    # -----------------------------------------

    resultado = re.search(
        r"CONTRATADO\s*(.*?)(?=\nMOTORISTA)",
        bloco,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if resultado:

        secao = resultado.group(1)

        contrato["contratado"]["nome"] = extrair_campo(
            secao,
            "Nome"
        )

        contrato["contratado"]["documento"] = extrair_campo(
            secao,
            "Documento"
        )

        contrato["contratado"]["ie"] = extrair_campo(
            secao,
            "IE"
        )

        contrato["contratado"]["rntrc"] = extrair_campo(
            secao,
            "RNTRC"
        )

        contrato["contratado"]["logradouro"] = extrair_campo(
            secao,
            "Logradouro"
        )

        contrato["contratado"]["numero"] = extrair_campo(
            secao,
            "Número"
        )

        contrato["contratado"]["complemento"] = extrair_campo(
            secao,
            "Complemento"
        )

        contrato["contratado"]["bairro"] = extrair_campo(
            secao,
            "Bairro"
        )

        contrato["contratado"]["cep"] = extrair_campo(
            secao,
            "CEP"
        )

        contrato["contratado"]["municipio"] = extrair_campo(
            secao,
            "Município"
        )

        contrato["contratado"]["uf"] = extrair_campo(
            secao,
            "UF"
        )

    # -----------------------------------------
    # MOTORISTA
    # -----------------------------------------

    resultado = re.search(
        r"MOTORISTA\s*(.*?)(?=\nOPERAÇÃO)",
        bloco,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if resultado:

        secao = resultado.group(1)

        contrato["motorista"]["nome"] = extrair_campo(
            secao,
            "Nome"
        )

        contrato["motorista"]["documento"] = extrair_campo(
            secao,
            "Documento"
        )

    # -----------------------------------------
    # OPERAÇÃO
    # -----------------------------------------

    resultado = re.search(
        r"OPERAÇÃO\s*(.*?)(?=\nFRETE)",
        bloco,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if resultado:

        secao = resultado.group(1)

        contrato["operacao"]["numero_interno"] = extrair_campo(
            secao,
            "Número Ct Interno"
        )

        contrato["operacao"]["ciot"] = extrair_campo(
            secao,
            "CIOT"
        )

        contrato["operacao"]["contrato_completo"] = extrair_campo(
            secao,
            "Contrato Completo"
        )

        contrato["operacao"]["numero_contrato"] = extrair_campo(
            secao,
            "Número Contrato"
        )

    # -----------------------------------------
    # FRETE
    # -----------------------------------------

    resultado = re.search(
        r"FRETE\s*(.*)",
        bloco,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if resultado:

        secao = resultado.group(1)

        contrato["frete"]["cte"] = extrair_campo(
            secao,
            "CTE"
        )

        contrato["frete"]["data"] = extrair_campo(
            secao,
            "Data"
        )

        contrato["frete"]["valor_frete"] = extrair_campo(
            secao,
            "Valor Frete"
        )

        contrato["frete"]["valor_liquido"] = extrair_campo(
            secao,
            "Valor Líquido"
        )

    return contrato


def carregar_contratos_extraidos(
    pasta_resultado: Path,
    ano: str,
    mes: str,
):

    caminho = (
        Path(pasta_resultado)
        / ano
        / mes
        / "contratos.txt"
    )

    if not caminho.exists():
        return []

    texto = caminho.read_text(
        encoding="utf-8"
    )

    # -------------------------------------------------
    # SEPARA CADA CONTRATO PELO INÍCIO DO REGISTRO
    # -------------------------------------------------

    blocos = re.split(
        r"(?=^Número F100:\s*)",
        texto,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    contratos = []

    for bloco in blocos:

        # Ignora cabeçalho e qualquer trecho
        # que não represente um contrato.
        if not re.search(
            r"^Número F100:\s*",
            bloco,
            flags=re.IGNORECASE | re.MULTILINE,
        ):
            continue

        contrato = extrair_contrato_do_bloco(
            bloco
        )

        contrato["periodo"] = ano + mes

        contratos.append(
            contrato
        )

    return contratos

def contrato_existe_no_f100(
    contrato,
    registros_f100
):

    documento_contrato = normalizar_documento(
        contrato["contratado"]["documento"]
    )
    periodo_contrato = str(
        contrato.get("periodo") or ""
    )

    data_contrato = normalizar_data(
        contrato["frete"]["data"]
    )

    valor_contrato = normalizar_valor(
        contrato["frete"]["valor_frete"]
    )

    numero_f100 = str(
        contrato["numero_f100"] or ""
    )

    for f100 in registros_f100:

        documento_f100 = normalizar_documento(
            f100.get("participante_cpf")
            or f100.get("participante_cnpj")
        )

        data_f100 = str(
            f100.get("dt_oper") or ""
        )

        valor_f100 = f100.get("vl_oper")

        descricao = str(
            f100.get("desc_doc_oper") or ""
        )

        if documento_f100 != documento_contrato:
            continue

        if data_f100 != data_contrato:
            continue

        if valor_f100 != valor_contrato:
            continue

        if numero_f100 not in descricao:
            continue

        periodo_f100 = str(
            f100.get("periodo") or ""
        )

        if periodo_f100 != periodo_contrato:
            continue

        return True

    return False



def listar_contratos_nao_encontrados(
    contratos_extraidos,
    registros_f100
):

    nao_encontrados = []

    for contrato in contratos_extraidos:

        existe = contrato_existe_no_f100(
            contrato,
            registros_f100
        )

        if not existe:
            nao_encontrados.append(
                contrato
            )

    return nao_encontrados



def salvar_contratos_nao_encontrados(
    contratos,
    pasta_resultado,
    periodo,
):

    ano = periodo[:4]
    mes = periodo[4:6]

    pasta_competencia = (
        Path(pasta_resultado)
        / ano
        / mes
    )

    pasta_competencia.mkdir(
        parents=True,
        exist_ok=True
    )

    caminho_saida = (
        pasta_competencia
        / "nao_encontrados.txt"
    )

    linhas = [
        "CONTRATOS NÃO ENCONTRADOS NO EFD-CONTRIBUIÇÕES",
        "=" * 50,
        "",
    ]

    if not contratos:
        linhas.append(
            "Nenhum contrato pendente."
        )

    for contrato in contratos:
        linhas.append(
            f"Número F100: {contrato['numero_f100']}"
        )

        linhas.append("")
        linhas.append("CONTRATANTE")
        linhas.append(f"Nome: {contrato['contratante']['nome']}")
        linhas.append(f"Documento: {contrato['contratante']['documento']}")
        linhas.append(f"IE: {contrato['contratante']['ie']}")
        linhas.append(f"Logradouro: {contrato['contratante']['logradouro']}")
        linhas.append(f"Número: {contrato['contratante']['numero']}")
        linhas.append(f"Bairro: {contrato['contratante']['bairro']}")
        linhas.append(f"CEP: {contrato['contratante']['cep']}")
        linhas.append(f"Município: {contrato['contratante']['municipio']}")
        linhas.append(f"UF: {contrato['contratante']['uf']}")
        linhas.append("")

        linhas.append("CONTRATADO")
        linhas.append(f"Nome: {contrato['contratado']['nome']}")
        linhas.append(f"Documento: {contrato['contratado']['documento']}")
        linhas.append(f"IE: {contrato['contratado']['ie']}")
        linhas.append(f"RNTRC: {contrato['contratado']['rntrc']}")
        linhas.append(f"Logradouro: {contrato['contratado']['logradouro']}")
        linhas.append(f"Número: {contrato['contratado']['numero']}")
        linhas.append(f"Complemento: {contrato['contratado']['complemento']}")
        linhas.append(f"Bairro: {contrato['contratado']['bairro']}")
        linhas.append(f"CEP: {contrato['contratado']['cep']}")
        linhas.append(f"Município: {contrato['contratado']['municipio']}")
        linhas.append(f"UF: {contrato['contratado']['uf']}")
        linhas.append("")

        linhas.append(f"MOTORISTA")
        linhas.append(f"Nome: {contrato['motorista']['nome']}")
        linhas.append(f"Documento: {contrato['motorista']['documento']}")
        linhas.append("")

        linhas.append(f"OPERAÇÃO")
        linhas.append(f"Número Ct Interno: {contrato['operacao']['numero_interno']}")
        linhas.append(f"CIOT: {contrato['operacao']['ciot']}")
        linhas.append(f"Contrato Completo: {contrato['operacao']['contrato_completo']}")
        linhas.append(f"Número Contrato: {contrato['operacao']['numero_contrato']}")
        linhas.append("")

        linhas.append(f"FRETE")
        linhas.append(f"CTE: {contrato['frete']['cte']}")
        linhas.append(f"Data: {contrato['frete']['data']}")
        linhas.append(f"Valor Frete: {contrato['frete']['valor_frete']}")
        linhas.append(f"Valor Líquido: {contrato['frete']['valor_liquido']}")

        linhas.append("")
        linhas.append("-" * 50)
        linhas.append("")

    caminho_saida.write_text(
        "\n".join(linhas),
        encoding="utf-8",
    )

    return caminho_saida