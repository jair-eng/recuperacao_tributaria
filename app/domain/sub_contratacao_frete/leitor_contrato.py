from pathlib import Path
from io import BytesIO

from PIL import Image
import pytesseract
import fitz

from app.domain.sub_contratacao_frete.helpers_leitor import normalizar_texto_ocr, extrair_dados_endereco, \
    extrair_municipio_uf, separar_endereco_bruto
from app.domain.sub_contratacao_frete.utils_leitor import encontrar_documentos, classificar_documentos, \
    extrair_secao_contratante, extrair_dados_contratante, extrair_nome_por_documento, extrair_identificadores_operacao, \
    escolher_numero_contrato_f100, extrair_contexto_participante, extrair_dados_frete, extrair_secao_contratado, \
    extrair_IE_RNTRC



# precisa instalar o pymupdf
# Precisou ser dessa forma no projeto C:\Users\jcbn1\AppData\Local\Programs\Python\Python312\python.exe -m pip install PyMuPDF
# ---------------------------------------------------------
# CONFIGURAÇÃO DO TESSERACT
# ---------------------------------------------------------

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


# ---------------------------------------------------------
# PASTAS
# ---------------------------------------------------------

pasta_leitor = Path(
    r"C:\Sped\LEITOR_CONTRATO"
)

pasta_leitor.mkdir(
    parents=True,
    exist_ok=True
)


pasta_texto_bruto = (
    pasta_leitor
    / "texto_bruto"
)

pasta_texto_bruto.mkdir(
    parents=True,
    exist_ok=True
)

pasta_resultado = pasta_leitor / "resultado"

pasta_resultado.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# EXTENSÕES ACEITAS
# ---------------------------------------------------------

EXTENSOES_IMAGEM = {
    ".jpg",
    ".jpeg",
    ".png",
}

EXTENSOES_ACEITAS = (
    EXTENSOES_IMAGEM
    | {".pdf"}
)


# ---------------------------------------------------------
# OCR DE UMA IMAGEM
# ---------------------------------------------------------

def extrair_texto_imagem(caminho_imagem):

    imagem = Image.open(
        caminho_imagem
    )

    largura, altura = imagem.size

    imagem_maior = imagem.resize(
        (
            largura * 3,
            altura * 3
        )
    )

    texto = pytesseract.image_to_string(
        imagem_maior,
        lang="por"
    )

    return texto


# ---------------------------------------------------------
# LEITURA DE PDF
# ---------------------------------------------------------

def extrair_texto_pdf(caminho_pdf):

    documento = fitz.open(
        caminho_pdf
    )

    textos_paginas = []

    for numero_pagina, pagina in enumerate(
        documento,
        start=1
    ):

        # ---------------------------------------------
        # PRIMEIRO:
        # tenta pegar texto existente no próprio PDF
        # ---------------------------------------------

        texto_pagina = pagina.get_text(
            "text"
        )

        # ---------------------------------------------
        # SE NÃO HOUVER TEXTO SUFICIENTE:
        # provavelmente é um PDF escaneado.
        #
        # Então transformamos a página em imagem
        # e fazemos OCR.
        # ---------------------------------------------

        if len(texto_pagina.strip()) < 30:

            pixmap = pagina.get_pixmap(
                matrix=fitz.Matrix(
                    3,
                    3
                )
            )

            imagem = Image.open(
                BytesIO(
                    pixmap.tobytes("png")
                )
            )

            texto_pagina = (
                pytesseract.image_to_string(
                    imagem,
                    lang="por"
                )
            )

        # ---------------------------------------------
        # Guardamos cada página separadamente
        # ---------------------------------------------

        textos_paginas.append(
            f"""
==============================
PÁGINA {numero_pagina}
==============================

{texto_pagina}
"""
        )

    documento.close()

    return "\n".join(
        textos_paginas
    )


# ---------------------------------------------------------
# IDENTIFICA O TIPO DE ARQUIVO
# E DEVOLVE TODO O TEXTO
# ---------------------------------------------------------

def extrair_texto_arquivo(arquivo):

    extensao = (
        arquivo.suffix.lower()
    )

    if extensao in EXTENSOES_IMAGEM:

        return extrair_texto_imagem(
            arquivo
        )

    if extensao == ".pdf":

        return extrair_texto_pdf(
            arquivo
        )

    raise ValueError(
        f"Extensão não suportada: {extensao}"
    )


# ---------------------------------------------------------
# SALVA O TEXTO BRUTO
# ---------------------------------------------------------

def salvar_texto_bruto(
    arquivo_original,
    texto
):

    caminho_txt = (
        pasta_texto_bruto
        / f"{arquivo_original.stem}.txt"
    )

    with open(
        caminho_txt,
        "w",
        encoding="utf-8"
    ) as arquivo_txt:

        arquivo_txt.write(
            texto
        )

    return caminho_txt

def montar_texto_estruturado(dados_contrato):

    linhas = []

    linhas.append("CONTRATO")
    linhas.append("=" * 50)
    linhas.append("")

    linhas.append(
        f"Número F100: {dados_contrato['numero_f100']}"
    )

    linhas.append("")
    linhas.append("CONTRATANTE")
    linhas.append(f"Nome: {dados_contrato['contratante']['nome']}")
    linhas.append(f"Documento: {dados_contrato['contratante']['documento']}")
    linhas.append(f"IE: {dados_contrato['contratante']['ie']}")
    linhas.append(f"Logradouro: {dados_contrato['contratante']['logradouro']}")
    linhas.append(f"Número: {dados_contrato['contratante']['numero']}")
    linhas.append(f"Bairro: {dados_contrato['contratante']['bairro']}")
    linhas.append(f"CEP: {dados_contrato['contratante']['cep']}")
    linhas.append(f"Município: {dados_contrato['contratante']['municipio']}")
    linhas.append(f"UF: {dados_contrato['contratante']['uf']}")
    linhas.append("")

    linhas.append("CONTRATADO")
    linhas.append(f"Nome: {dados_contrato['contratado']['nome']}")
    linhas.append(f"Documento: {dados_contrato['contratado']['documento']}")
    linhas.append(f"IE: {dados_contrato['contratado']['ie']}")
    linhas.append(f"RNTRC: {dados_contrato['contratado']['rntrc']}")
    linhas.append(f"Logradouro: {dados_contrato['contratado']['logradouro']}")
    linhas.append(f"Número: {dados_contrato['contratado']['numero']}")
    linhas.append(f"Complemento: {dados_contrato['contratado']['complemento']}")
    linhas.append(f"Bairro: {dados_contrato['contratado']['bairro']}")
    linhas.append(f"CEP: {dados_contrato['contratado']['cep']}")
    linhas.append(f"Município: {dados_contrato['contratado']['municipio']}")
    linhas.append(f"UF: {dados_contrato['contratado']['uf']}")
    linhas.append("")

    linhas.append(f"MOTORISTA")
    linhas.append(f"Nome: {dados_contrato['motorista']['nome']}")
    linhas.append(f"Documento: {dados_contrato['motorista']['documento']}")
    linhas.append("")

    linhas.append(f"OPERAÇÃO")
    linhas.append(f"Número Ct Interno: {dados_contrato['operacao']['numero_interno']}")
    linhas.append(f"CIOT: {dados_contrato['operacao']['ciot']}")
    linhas.append(f"Contrato Completo: {dados_contrato['operacao']['contrato_completo']}")
    linhas.append(f"Número Contrato: {dados_contrato['operacao']['numero_contrato']}")
    linhas.append("")

    linhas.append(f"FRETE")
    linhas.append(f"CTE: {dados_contrato['frete']['cte']}")
    linhas.append(f"Data: {dados_contrato['frete']['data']}")
    linhas.append(f"Valor Frete: {dados_contrato['frete']['valor_frete']}")
    linhas.append(f"Valor Líquido: {dados_contrato['frete']['valor_liquido']}")

    return "\n".join(linhas)

def salvar_texto_estruturado(
    dados_contrato
):

    data = dados_contrato["frete"]["data"]

    dia, mes, ano = data.split("/")

    pasta_competencia = (
        pasta_resultado
        / ano
        / mes
    )

    pasta_competencia.mkdir(
        parents=True,
        exist_ok=True
    )

    caminho_txt = (
        pasta_competencia
        / "contratos.txt"
    )

    texto = montar_texto_estruturado(
        dados_contrato
    )

    with open(
        caminho_txt,
        "a",
        encoding="utf-8"
    ) as arquivo_txt:

        arquivo_txt.write(
            texto
        )

        arquivo_txt.write(
            "\n\n" + "=" * 70 + "\n\n"
        )

    return caminho_txt


# ---------------------------------------------------------
# LÊ O TXT
# ---------------------------------------------------------

def ler_texto_bruto(
    caminho_txt
):

    with open(
        caminho_txt,
        "r",
        encoding="utf-8"
    ) as arquivo_txt:

        return arquivo_txt.read()


def processar_arquivo(arquivo):
    print("=" * 60)
    print(f"Processando: {arquivo.name}")
    # =====================================================
    # ETAPA 1
    #
    # ARQUIVO ORIGINAL
    #       ↓
    # LEITURA / OCR
    #       ↓
    # TXT BRUTO
    # =====================================================

    texto_bruto = extrair_texto_arquivo(
        arquivo
    )

    caminho_txt = salvar_texto_bruto(
        arquivo,
        texto_bruto
    )

    print(
        "TXT bruto criado:",
        caminho_txt
    )


    # =====================================================
    # ETAPA 2
    #
    # DAQUI PARA BAIXO A EXTRAÇÃO NÃO CONHECE MAIS
    # JPG, JPEG, PNG OU PDF.
    #
    # ELA RECEBE SOMENTE TEXTO.
    # =====================================================

    texto = ler_texto_bruto(
        caminho_txt
    )

    texto_normalizado = (
        normalizar_texto_ocr(
            texto
        )
    )


    # -----------------------------------------------------
    # LOCALIZA DOCUMENTOS
    # -----------------------------------------------------

    documentos = encontrar_documentos(
        texto_normalizado
    )


    # -----------------------------------------------------
    # CLASSIFICA:
    #
    # contratante
    # contratado
    # motorista
    # -----------------------------------------------------

    classificacao = (
        classificar_documentos(
            texto_normalizado,
            documentos
        )
    )


    contratante = (
        classificacao.get(
            "contratante"
        )
    )

    contratado = (
        classificacao.get(
            "contratado"
        )
    )

    motorista = (
        classificacao.get(
            "motorista"
        )
    )

    secao_contratante = extrair_secao_contratante(
        texto_normalizado
    )

    dados_contratante = extrair_dados_contratante(
        secao_contratante
    )


    # -----------------------------------------------------
    # CONTRATANTE
    # -----------------------------------------------------

    if contratante:

        nome_contratante = (
            extrair_nome_por_documento(
                texto_normalizado,
                contratante["documento"]
            )
        )

    else:

        nome_contratante = None


    # -----------------------------------------------------
    # CONTRATADO
    # -----------------------------------------------------

    if contratado:

        nome_contratado = (
            extrair_nome_por_documento(
                texto_normalizado,
                contratado["documento"]
            )
        )

    else:

        nome_contratado = None


    # -----------------------------------------------------
    # MOTORISTA
    # -----------------------------------------------------

    if motorista:

        nome_motorista = (
            extrair_nome_por_documento(
                texto_normalizado,
                motorista["documento"]
            )
        )

    else:

        nome_motorista = None
    # Dados do contrato
    dados_operacao = extrair_identificadores_operacao(
        texto_normalizado
    )

    numero_f100 = escolher_numero_contrato_f100(
        dados_operacao
    )

    # -----------------------------------------------------
    # ENDEREÇO DO CONTRATADO
    # -----------------------------------------------------

    dados_endereco = {}

    if contratado:

        contexto_contratado = (
            extrair_contexto_participante(
                texto_normalizado,
                contratado["documento"]
            )
        )

        dados_endereco = (
            extrair_dados_endereco(
                contexto_contratado
            )
        )

        municipio_uf = (
            extrair_municipio_uf(
                dados_endereco["depois_cep"]
            )
        )

        dados_endereco.update(
            municipio_uf
        )

        dados_endereco = (
            separar_endereco_bruto(
                dados_endereco
            )
        )




    # Dados Frete
    dados_frete = extrair_dados_frete(texto_normalizado)

    #RNTRC e IE

    secao_contratado = extrair_secao_contratado(texto_normalizado)

    dados_ie_rntrc = extrair_IE_RNTRC(
        secao_contratado
    )

    dados_contrato = {
        "numero_f100": numero_f100,

        "contratante": {
            "nome": nome_contratante,
            "documento": contratante["documento"] if contratante else None,
            **dados_contratante,
        },

        "contratado": {
            "nome": nome_contratado,
            "documento": contratado["documento"] if contratado else None,
            "ie": dados_ie_rntrc["IE"],
            "rntrc": dados_ie_rntrc["RNTRC"],
            **dados_endereco,
        },

        "motorista": {
            "nome": nome_motorista,
            "documento": motorista["documento"] if motorista else None,
        },

        "operacao": dados_operacao,
        "frete": dados_frete,
    }

    return dados_contrato


# =========================================================
# PROCESSAMENTO DOS ARQUIVOS
# =========================================================

contratos = []
for arquivo in pasta_leitor.iterdir():

    # -----------------------------------------------------
    # Ignora pastas
    # -----------------------------------------------------

    if not arquivo.is_file():
        continue


    # -----------------------------------------------------
    # Ignora arquivos que não interessam
    # -----------------------------------------------------

    if arquivo.suffix.lower() not in EXTENSOES_ACEITAS:
        continue

    dados_contrato = processar_arquivo(arquivo)
    contratos.append(dados_contrato)


    caminho_txt = salvar_texto_estruturado(
        dados_contrato
    )

    print(
        "TXT Estrutura criado:",
        caminho_txt
    )


