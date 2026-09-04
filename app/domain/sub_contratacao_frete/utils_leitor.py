import re
from tkinter.messagebox import IGNORE

from app.domain.sub_contratacao_frete.helpers_leitor import validar_cnpj, validar_cpf


def identificar_tipo_documento(secao_contratado):
    resultado_cpf = re.search(r"\d{3}[.\s]?\d{3}[.\s]?\d{3}-?\d{2}", secao_contratado)
    resultado_cnpj = re.search(r"\d{2}[.\s]?\d{3}[.\s]?\d{3}/?\d{4}-?\d{2}", secao_contratado)

    if resultado_cnpj:
        documento = resultado_cnpj.group()

        return {"tipo": "PJ",
                "documento": documento,
                "valido": validar_cnpj(documento)
                }

    if resultado_cpf:
        documento = resultado_cpf.group()

        return {"tipo": "PF",
                "documento": documento,
                "valido": validar_cpf(documento)}

    return None

def encontrar_documentos(texto):

    candidatos = []

    padrao_cnpj = (
        r"(?<!\d)"
        r"\d{2}[.\s]?\d{3}[.\s]?\d{3}/?\d{4}-?\d{2}"
        r"(?!\d)"
    )

    padrao_cpf = (
        r"(?<!\d)"
        r"(?:"
        r"\d{3}[.\s]\d{3}[.\s]\d{3}-?\d{2}"
        r"|"
        r"\d{11}"
        r")"
        r"(?![\d/])"
    )

    for resultado in re.finditer(padrao_cnpj, texto):

        documento = resultado.group()

        inicio = max(0, resultado.start() - 80)
        fim = min(len(texto), resultado.end() + 80)

        contexto = texto[inicio:fim]

        candidatos.append({
            "tipo": "PJ",
            "documento": documento,
            "valido": validar_cnpj(documento),
            "posicao": resultado.start(),
            "contexto": contexto,
        })

    for resultado in re.finditer(padrao_cpf, texto):

        documento = resultado.group()

        inicio = max(0, resultado.start() - 80)
        fim = min(len(texto), resultado.end() + 80)

        contexto = texto[inicio:fim]

        candidatos.append({
            "tipo": "PF",
            "documento": documento,
            "valido": validar_cpf(documento),
            "posicao": resultado.start(),
            "contexto": contexto,
        })

    candidatos.sort(
        key=lambda item: item["posicao"]
    )

    return candidatos

def classificar_documentos(texto, candidatos):

    dados = {
        "contratante": None,
        "contratado": None,
        "motorista": None,
    }

    texto_lower = texto.lower()

    posicao_contratado = texto_lower.find("contratado")
    posicao_motorista = texto_lower.find("motorista")

    # ---------------------------
    # CONTRATANTE
    # ---------------------------

    for candidato in candidatos:

        if candidato["tipo"] != "PJ":
            continue

        if (
            posicao_contratado == -1
            or candidato["posicao"] < posicao_contratado
        ):
            dados["contratante"] = candidato
            break

    # ---------------------------
    # CONTRATADO
    # ---------------------------

    if posicao_contratado != -1:

        for candidato in candidatos:

            if candidato["posicao"] <= posicao_contratado:
                continue

            if (
                posicao_motorista != -1
                and candidato["posicao"] >= posicao_motorista
            ):
                break

            dados["contratado"] = candidato
            break

    # ---------------------------
    # MOTORISTA
    # ---------------------------

    if posicao_motorista != -1:

        for candidato in candidatos:

            if candidato["posicao"] <= posicao_motorista:
                continue

            if candidato["tipo"] != "PF":
                continue

            dados["motorista"] = candidato
            break

    return dados

def extrair_nome_por_documento(texto, documento):

    posicao_documento = texto.find(documento)

    if posicao_documento == -1:
        return None

    inicio = max(
        0,
        posicao_documento - 250
    )

    trecho = texto[
        inicio:posicao_documento
    ]

    linhas = [
        linha.strip()
        for linha in trecho.splitlines()
        if linha.strip()
    ]

    # tenta primeiro encontrar Nome/CPF ou Nome/CNPJ
    for indice in range(len(linhas) - 1, -1, -1):

        linha = linhas[indice]

        if "Nome/CPF" in linha or "Nome/CNPJ" in linha:

            nome = linha

            nome = nome.replace("Nome/CPF:", "")
            nome = nome.replace("Nome/CNPJ:", "")
            nome = nome.replace("|", "")
            nome = nome.replace("/", "")
            nome = nome.strip()

            # se o nome estiver na mesma linha
            if nome:
                return nome

            # se o rótulo estiver sozinho,
            # tenta a próxima linha
            if indice + 1 < len(linhas):

                nome = linhas[indice + 1]

                nome = nome.replace("|", "")
                nome = nome.replace("/", "")
                nome = nome.strip()

                if nome:
                    return nome

    # tenta localizar uma razão social
    for linha in reversed(linhas):

        linha_upper = linha.upper()

        if (
            "LTDA" in linha_upper
            or "S/A" in linha_upper
            or "EIRELI" in linha_upper
            or "MEI" in linha_upper
        ):

            # remove Nº 23, Nº33, N° 10 etc.
            linha = re.sub(
                r"\s+N[º°]?\s*\d+\s*$",
                "",
                linha,
                flags=re.IGNORECASE
            )

            return linha.strip()

    return None

def extrair_contexto_participante(texto, documento, tamanho=500):

    posicao = texto.find(documento)

    if posicao == -1:
        return None

    inicio = max(0, posicao - tamanho)
    fim = min(len(texto), posicao + tamanho)

    return texto[inicio:fim]

def extrair_identificadores_operacao(texto):

    dados = {"numero_interno": None,
             "ciot": None,
             "contrato_completo": None,
             "numero_contrato": None,
             }
    resultado_numero = re.search(
        r"N[º°]?\s*(\d+)",
        texto,
        flags= re.IGNORECASE
    )
    if resultado_numero:
        dados["numero_interno"] = resultado_numero.group(1)

    resultado_ciot = re.search(
        r"CIOT\s*[:\-]?\s*(\d+\s*/\s*\d+)",
        texto,
        flags=re.IGNORECASE
    )
    if resultado_ciot:
        ciot = resultado_ciot.group(1)
        ciot = re.sub(r"\s+", "", ciot)

        dados["ciot"] = ciot

    resultado_contrato = re.search(
        r"Contrato\s*[:\-]?\s*(\d+\s*/\s*\d+)",
        texto,
        flags=re.IGNORECASE
    )
    if resultado_contrato:
        contrato = resultado_contrato.group(1)
        contrato = re.sub(r"\s", "", contrato)

        dados["contrato_completo"] = contrato
        dados["numero_contrato"] = contrato.split("/")[-1]

    return dados

def escolher_numero_contrato_f100(dados_operacao):

    if dados_operacao["numero_contrato"]:
        return dados_operacao["numero_contrato"]

    return dados_operacao["numero_interno"]

def extrair_dados_frete(texto):

    dados = {"cte": None,
             "data": None,
             "valor_frete": None,
             "valor_liquido": None}

    resultado_cte = re.search(r"CT-e\s*/?\s*(\d+)",
                              texto,
                              flags= re.IGNORECASE)
    if resultado_cte:
        dados["cte"] = resultado_cte.group(1)

    resultado_data = re.search(r"CT[\s\-]*E[^\n]*?(\d{2}/\d{2}/\d{4})",
                               texto,
                               flags= re.IGNORECASE)
    if resultado_data:
        dados["data"] = resultado_data.group(1)

    resultado_valor_frete = re.search(r"Frete\s*(?:=)?\s*(?:R\$)?\s*([\d.,]+)",
                                      texto,
                                      flags= re.IGNORECASE)
    if resultado_valor_frete:
        dados["valor_frete"] = resultado_valor_frete.group(1)

    resultado_valor_liquido = re.search(r"L[ií]quido\s*(?:=)?\s*(?:R\$)?\s*([\d.,]+)",
                                      texto,
                                      flags=re.IGNORECASE)
    if resultado_valor_liquido:
        dados["valor_liquido"] = resultado_valor_liquido.group(1)

    return dados

def extrair_secao_contratado(texto):

    resultado = re.search(
        r"Contratado(.*?)Motorista",
        texto,
        flags=re.IGNORECASE | re.DOTALL
    )

    if resultado:
        return resultado.group(1)

    return ""

def extrair_secao_contratante(texto):

    resultado = re.search(
        r"^(.*?)Contratado",
        texto,
        flags=re.IGNORECASE | re.DOTALL
    )

    if resultado:
        return resultado.group(1)

    return ""

def extrair_IE_RNTRC(texto):

    dados = {"IE": None,
             "RNTRC": None}

    resultado_IE = re.search(r"IE\s*:\s*([\d.\-]+)",
                             texto,
                             flags= re.IGNORECASE)
    if resultado_IE:
        dados["IE"] = resultado_IE.group(1)

    resultado_RNTRC = re.search(r"RNTRC\s*:\s*(\d+)",
                                texto,
                                flags= re.IGNORECASE)
    if resultado_RNTRC:
        dados["RNTRC"] = resultado_RNTRC.group(1)

    return dados

def extrair_dados_contratante(texto):

    dados = {
        "ie": None,
        "cep": None,
        "municipio": None,
        "uf": None,
        "logradouro": None,
        "numero": None,
        "bairro": None,
    }

    resultado_ie = re.search(
        r"IE\s*:\s*([\d.\-]+)",
        texto,
        flags=re.IGNORECASE
    )

    if resultado_ie:
        dados["ie"] = resultado_ie.group(1)


    resultado_cep = re.search(
        r"CEP\s*:\s*(\d{5}-\d{3})",
        texto,
        flags=re.IGNORECASE
    )

    if resultado_cep:
        dados["cep"] = resultado_cep.group(1)


    resultado_municipio_uf = re.search(
        r"CEP\s*:\s*\d{5}-\d{3}\s*,?\s*"
        r"([A-ZÀ-Ú\s]+?)\s*-\s*([A-Z]{2})",
        texto,
        flags=re.IGNORECASE
    )

    if resultado_municipio_uf:
        dados["municipio"] = resultado_municipio_uf.group(1).strip()
        dados["uf"] = resultado_municipio_uf.group(2).upper()


    resultado_endereco = re.search(
        r"(?:AV|RUA|R|ROD|RODOVIA)\.?\s+"
        r"([^,\n]+)"
        r",\s*(\d+)"
        r"\s*-\s*([^\n]+)",
        texto,
        flags=re.IGNORECASE
    )

    if resultado_endereco:
        dados["logradouro"] = resultado_endereco.group(1).strip()
        dados["numero"] = resultado_endereco.group(2).strip()
        dados["bairro"] = resultado_endereco.group(3).strip()

    return dados
