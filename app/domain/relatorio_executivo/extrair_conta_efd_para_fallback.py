from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable
from typing import Any

import logging

from app.utils.strings import only_digits

logger = logging.getLogger(__name__)


def _ordem_data_0500(valor: str | None) -> datetime:
    """
    Converte DT_ALT do 0500 (DDMMAAAA) para comparação.
    Datas inválidas ficam como as mais antigas.
    """
    texto = str(valor or "").strip()

    try:
        return datetime.strptime(texto, "%d%m%Y")
    except ValueError:
        return datetime.min


def gerar_catalogo_0500_local(
    *,
    arquivos_contrib: Iterable[Path],
    caminho_saida: Path,
) -> dict:
    """
    Varre os arquivos EFD Contribuições já localizados pelo relatório,
    extrai os registros 0500 e gera um catálogo JSON consolidado.

    Deduplicação:
        CNPJ da empresa + COD_CTA

    Quando o mesmo COD_CTA aparece mais de uma vez, preserva o registro
    com a DT_ALT mais recente.
    """

    caminho_saida = Path(caminho_saida)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    arquivos = [Path(p) for p in arquivos_contrib]

    catalogo: dict[str, dict[str, dict]] = {}

    arquivos_lidos = 0
    arquivos_com_erro = 0
    linhas_0500 = 0
    registros_substituidos = 0

    for arquivo in arquivos:
        try:
            with arquivo.open(
                "r",
                encoding="latin-1",
                errors="ignore",
            ) as f:
                linhas = f.readlines()

            arquivos_lidos += 1

        except OSError as exc:
            arquivos_com_erro += 1
            print(
                f"[CATALOGO 0500] erro ao ler arquivo={arquivo} erro={exc}",
                flush=True,
            )
            continue

        # ---------------------------------------------------------
        # 1. Descobre o CNPJ do próprio SPED pelo registro 0000
        # ---------------------------------------------------------
        cnpj_arquivo = ""

        for linha in linhas:
            texto = str(linha or "").strip()

            if not texto.startswith("|0000|"):
                continue

            campos_0000 = texto.split("|")

            # |0000|COD_VER|TIPO_ESCRIT|IND_SIT_ESP|NUM_REC_ANTERIOR|
            # DT_INI|DT_FIN|NOME|CNPJ|...
            if len(campos_0000) > 9:
                cnpj_arquivo = "".join(
                    c for c in str(campos_0000[9] or "") if c.isdigit()
                )

            break

        chave_empresa = cnpj_arquivo or "SEM_CNPJ"
        contas_empresa = catalogo.setdefault(chave_empresa, {})

        # ---------------------------------------------------------
        # 2. Extrai os registros 0500
        # ---------------------------------------------------------
        for numero_linha, linha in enumerate(linhas, start=1):
            texto = str(linha or "").strip()

            if not texto.startswith("|0500|"):
                continue

            campos = texto.split("|")

            # |0500|DT_ALT|COD_NAT_CC|IND_CTA|NIVEL|
            # COD_CTA|NOME_CTA|COD_CTA_REF|CNPJ_EST|
            if len(campos) < 8:
                continue

            cod_cta = str(campos[6] or "").strip()

            if not cod_cta:
                continue

            linhas_0500 += 1

            cnpj_est = ""
            if len(campos) > 9:
                cnpj_est = "".join(
                    c for c in str(campos[9] or "") if c.isdigit()
                )

            registro = {
                "dt_alt": str(campos[2] or "").strip(),
                "cod_nat_cc": str(campos[3] or "").strip(),
                "ind_cta": str(campos[4] or "").strip(),
                "nivel": str(campos[5] or "").strip(),
                "cod_cta": cod_cta,
                "nome_cta": str(campos[7] or "").strip(),
                "cod_cta_ref": (
                    str(campos[8] or "").strip()
                    if len(campos) > 8
                    else ""
                ),
                "cnpj_est": cnpj_est,
                "cnpj_arquivo": cnpj_arquivo,
                "arquivo": arquivo.name,
                "linha": numero_linha,
                "linha_original": texto,
            }

            anterior = contas_empresa.get(cod_cta)

            if anterior is None:
                contas_empresa[cod_cta] = registro
                continue

            # Mesmo código em vários períodos:
            # preserva a definição mais recente do 0500.
            if _ordem_data_0500(registro["dt_alt"]) > _ordem_data_0500(
                anterior.get("dt_alt")
            ):
                contas_empresa[cod_cta] = registro
                registros_substituidos += 1

    total_empresas = len(catalogo)
    contas_unicas = sum(len(contas) for contas in catalogo.values())

    saida = {
        "resumo": {
            "arquivos_encontrados": len(arquivos),
            "arquivos_lidos": arquivos_lidos,
            "arquivos_com_erro": arquivos_com_erro,
            "linhas_0500": linhas_0500,
            "contas_unicas": contas_unicas,
            "empresas": total_empresas,
            "registros_substituidos": registros_substituidos,
        },
        "empresas": catalogo,
    }

    # Gravação segura: primeiro temporário, depois substitui o destino.
    caminho_temporario = caminho_saida.with_suffix(
        caminho_saida.suffix + ".tmp"
    )

    caminho_temporario.write_text(
        json.dumps(
            saida,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    caminho_temporario.replace(caminho_saida)

    return {
        **saida["resumo"],
        "arquivo_saida": str(caminho_saida),
    }


def carregar_contas_0500_local(
    *,
    caminho_catalogo: Path,
    cnpj_empresa: str,
) -> list[dict[str, Any]]:
    caminho_catalogo = Path(caminho_catalogo)
    cnpj_empresa = only_digits(cnpj_empresa)

    if not caminho_catalogo.exists():
        logger.warning(
            "[CATALOGO_0500] arquivo não encontrado | caminho=%s",
            caminho_catalogo,
        )
        return []

    try:
        dados = json.loads(
            caminho_catalogo.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "[CATALOGO_0500] erro ao carregar | caminho=%s erro=%s",
            caminho_catalogo,
            exc,
        )
        return []

    contas_por_codigo = (
        dados.get("empresas", {})
        .get(cnpj_empresa, {})
    )

    contas = list(contas_por_codigo.values())

    logger.warning(
        "[CATALOGO_0500] cnpj=%s contas=%s caminho=%s",
        cnpj_empresa,
        len(contas),
        caminho_catalogo,
    )

    return contas