import re


def normalizar_documento(documento):
    return re.sub(r"\D", "", documento)

def normalizar_texto_ocr(texto):
    texto = texto.replace("\r", "\n")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()

def calcular_digito_cpf(parte_cpf, peso):
    soma = 0
    for digito in parte_cpf:
        soma += int(digito) * peso
        peso -= 1
    resto = soma % 11
    if resto < 2:
        return  0
    return 11 - resto

def validar_cpf(cpf):
    cpf = normalizar_documento(cpf)

    if cpf == cpf[0] * 11:
        return False

    if len(cpf) != 11:
        return False

    primeiro_digito = calcular_digito_cpf(cpf[:9],10)

    if primeiro_digito != int(cpf[9]):
        return False

    segundo_digito = calcular_digito_cpf(cpf[:10], 11)

    if segundo_digito != int(cpf[10]):
        return False

    return True

# def descontinuado_validar_cpf(cpf):
#     cpf = normalizar_documento(cpf)
#     if len(cpf) != 11:
#         return False
#     soma = 0
#     peso = 10
#
#     for indice in range(9):
#         soma += int(cpf[indice]) * peso
#         peso -= 1
#     resto = soma % 11
#
#     if resto < 2:
#         primeiro_digito = 0
#
#     else:
#         primeiro_digito = 11 - resto
#
#     if primeiro_digito != int(cpf[9]):
#         return False
#
#     soma = 0
#     peso = 11
#
#     for indice in range(10):
#         soma += int(cpf[indice]) * peso
#         peso -= 1
#     resto = soma % 11
#
#     if resto < 2:
#         segundo_digito = 0
#
#     else:
#         segundo_digito = 11 - resto
#
#     if segundo_digito != int(cpf[10]):
#         return False
#     print(f"Primeiro digito:{primeiro_digito} e Segundo digito:{segundo_digito}")
#     return True

def calcular_digito_cnpj(parte_cnpj):

    pesos = []
    if len(parte_cnpj) == 12:
        pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    elif len(parte_cnpj) == 13:
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    else:
        None

    soma = 0

    for digito, peso in zip(parte_cnpj, pesos):
        soma += int(digito) * peso
    resto = soma % 11
    if resto < 2:
        return 0
    return 11 - resto

def validar_cnpj(cnpj):
    cnpj = normalizar_documento(cnpj)

    if len(cnpj) != 14:
        return False

    if cnpj == cnpj[0] * 14:
        return False

    primeiro_digito = calcular_digito_cnpj(cnpj[:12])

    if primeiro_digito != int(cnpj[12]):
        return False

    segundo_digito = calcular_digito_cnpj(cnpj[:13])

    if segundo_digito != int(cnpj[13]):
        return False

    return True

def extrair_cep(contexto):

    resultado = re.search(
        r"CEP\s*:\s*(\d{5}-?\d{3})",
        contexto,
        flags=re.IGNORECASE
    )

    if resultado:
        return resultado.group(1)

    return None

def extrair_linha_endereco(contexto):

    for linha in contexto.splitlines():

        if "Endereço:" in linha:

            return linha.strip()

    return None

def extrair_dados_endereco(contexto):

    linha = extrair_linha_endereco(contexto)

    if not linha:
        return None

    resultado = re.search(
        r"Endereço:\s*(.*?)\s+CEP\s*:\s*(\d{5}-?\d{3})\s+(.*)",
        linha,
        flags=re.IGNORECASE
    )

    if not resultado:
        return None

    endereco_bruto = resultado.group(1).strip()
    cep = resultado.group(2).strip()
    depois_cep = resultado.group(3).strip()

    return {
        "endereco_bruto": endereco_bruto,
        "cep": cep,
        "depois_cep": depois_cep,
    }

def extrair_municipio_uf(depois_cep):

    texto = depois_cep.strip()

    texto = re.split(
        r"\b(?:IE|PISINSS|PIS/INSS|PIS|INSS)\b\s*:?",
        texto,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0].strip()

    resultado = re.search(
        r"(.+?)\s+([A-Z]{2})$",
        texto,
        flags=re.IGNORECASE
    )

    if not resultado:
        return {
            "municipio": None,
            "uf": None
        }

    municipio = resultado.group(1).strip()
    uf = resultado.group(2).upper()

    return {
        "municipio": municipio,
        "uf": uf
    }

def separar_endereco_bruto(dados_endereco):

    endereco_bruto = dados_endereco["endereco_bruto"]

    dados_endereco["logradouro"] = None
    dados_endereco["numero"] = None
    dados_endereco["complemento"] = None
    dados_endereco["bairro"] = None

    partes = endereco_bruto.split(",", maxsplit=1)

    dados_endereco["logradouro"] = partes[0].strip()

    if len(partes) == 1:
        return dados_endereco

    restante = partes[1].strip()

    resultado_numero = re.match(
        r"(\d+)\s*(.*)",
        restante
    )

    if not resultado_numero:
        return dados_endereco

    dados_endereco["numero"] = resultado_numero.group(1)

    depois_numero = resultado_numero.group(2).strip()

    if depois_numero:

        padrao_complemento = (
            r"^(AP|APT|APTO|CASA|SALA|LOJA|BLOCO)"
            r"\s+(\S+)"
            r"\s+(.*)$"
        )

        resultado_complemento = re.match(
            padrao_complemento,
            depois_numero,
            flags=re.IGNORECASE
        )

        if resultado_complemento:

            marcador = resultado_complemento.group(1)
            valor = resultado_complemento.group(2)
            bairro = resultado_complemento.group(3)

            dados_endereco["complemento"] = (
                    marcador + " " + valor
            )

            dados_endereco["bairro"] = bairro.strip()

        else:
            dados_endereco["bairro"] = depois_numero

    return dados_endereco