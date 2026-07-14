from collections import Counter

from typing import Any, Iterable, Optional, List
from app.Legacy.fiscal.regras.Diagnostico.insumos.insumos_helpers import _extrair_chaves_c170, _score_natureza, _norm_str,_get_dados_list, _somente_digitos

import re
from typing import Any

_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


def resolver_cod_cta_para_insert_c170(
    *,
    alvo: Any,
    linhas_base: Iterable[Any],
    cod_cta_padrao_0500: str | None = None,
    dados_c170_novo: Optional[List[Any]] = None,
    ncm_novo: str | None = None,
) -> str:
    """
    Resolve COD_CTA para C170 inserido.

    Prioridade:
    1) C170 do mesmo documento
    2) C170 de mesma natureza (CFOP/NCM/descrição)
    3) fallback 0500
    4) vazio

    ⚠️ NÃO inventa conta fixa
    """

    alvo_reg = _norm_str(getattr(alvo, "reg", "")).upper()
    alvo_rid = int(getattr(alvo, "registro_id", 0) or 0)
    alvo_pai = int(getattr(alvo, "pai_id", 0) or 0)

    # Descobre C100
    c100_id = 0
    if alvo_reg == "C100" and alvo_rid > 0:
        c100_id = alvo_rid
    elif alvo_pai > 0:
        c100_id = alvo_pai

    # =========================
    # 1) MESMO DOCUMENTO
    # =========================
    if c100_id > 0:
        for ln in linhas_base or []:
            reg = _norm_str(getattr(ln, "reg", "")).upper()
            if reg != "C170":
                continue

            pai_id = int(getattr(ln, "pai_id", 0) or 0)
            if pai_id != c100_id:
                continue

            dados = _get_dados_list(getattr(ln, "dados", None))
            if len(dados) >= 36:
                cod_cta = _norm_str(dados[35])
                if cod_cta:
                    return cod_cta

    # =========================
    # 2) MESMA NATUREZA
    # =========================
    alvo_desc = ""
    alvo_cfop = ""
    alvo_ncm = _somente_digitos(ncm_novo)

    if dados_c170_novo:
        ch = _extrair_chaves_c170(dados_c170_novo)
        alvo_desc = ch["descricao"]
        alvo_cfop = ch["cfop"]

    candidatos: list[tuple[int, str]] = []

    for ln in linhas_base or []:
        reg = _norm_str(getattr(ln, "reg", "")).upper()
        if reg != "C170":
            continue

        dados = _get_dados_list(getattr(ln, "dados", None))
        if len(dados) < 36:
            continue

        ch = _extrair_chaves_c170(dados)
        cod_cta = ch["cod_cta"]

        if not cod_cta:
            continue

        score = _score_natureza(
            alvo_desc=alvo_desc,
            alvo_cfop=alvo_cfop,
            alvo_ncm=alvo_ncm,
            cand_desc=ch["descricao"],
            cand_cfop=ch["cfop"],
            cand_ncm="",  # pode evoluir depois
        )

        if score >= 5:
            candidatos.append((score, cod_cta))

    if candidatos:
        melhor_score = max(s for s, _ in candidatos)
        melhores = [c for s, c in candidatos if s == melhor_score]
        return Counter(melhores).most_common(1)[0][0]

    # =========================
    # 3) FALLBACK 0500
    # =========================
    if cod_cta_padrao_0500:
        return _norm_str(cod_cta_padrao_0500)

    # =========================
    # 4) VAZIO
    # =========================
    return ""

def resolver_cod_cta_padrao_0500(linhas_base: Iterable[Any]) -> str:
    """
    Mantém o comportamento conservador atual:
    retorna o primeiro COD_CTA disponível no 0500.
    """
    for ln in linhas_base or []:
        reg = str(getattr(ln, "reg", "") or "").strip().upper()
        if reg != "0500":
            continue

        dados = list(getattr(ln, "dados", None) or [])
        if len(dados) > 4:
            cod_cta = str(dados[4] or "").strip()
            if cod_cta:
                return cod_cta
    return ""

def resolver_tipo_conta_por_cenario(
    *,
    dominio: str,
    categoria: str,
    fundamentos: str | list[str] | None,
) -> str:

    dominio = str(dominio or "").strip().upper()
    categoria = str(categoria or "").strip()

    if isinstance(fundamentos, str):
        fundamentos = [fundamentos]

    fundamentos = {
        str(f or "").strip().upper()
        for f in (fundamentos or [])
        if str(f or "").strip()
    }

    if dominio == "TRANSP":
        if categoria == "CombustiveisLubrificantes":
            return "COMBUSTIVEL"

        if fundamentos & {
            "TRANSP_INSUMO_DIESEL",
            "TRANSP_INSUMO_GASOLINA",
            "TRANSP_INSUMO_ETANOL",
            "TRANSP_INSUMO_LUBRIFICANTE",
            "TRANSP_INSUMO_ARLA32",
        }:
            return "COMBUSTIVEL"

        return "INSUMOS"

    if dominio == "CAFE":
        if "CAFE_OPERACAO_PRINCIPAL" in fundamentos:
            return "MERCADORIA_REVENDA"

        return "INSUMOS"

    return "INSUMOS"

def _normalizar_nome_conta(valor: str | None) -> str:
    texto = str(valor or "").strip().upper()

    substituicoes = {
        "Á": "A", "À": "A", "Â": "A", "Ã": "A",
        "É": "E", "Ê": "E",
        "Í": "I",
        "Ó": "O", "Ô": "O", "Õ": "O",
        "Ú": "U",
        "Ç": "C",
    }

    for origem, destino in substituicoes.items():
        texto = texto.replace(origem, destino)

    return " ".join(texto.split())


def _tipo_conta_0500(nome_cta: str | None) -> str | None:
    nome = _normalizar_nome_conta(nome_cta)

    if not nome:
        return None

    if "COMBUST" in nome or "LUBRIFIC" in nome:
        return "COMBUSTIVEL"

    termos_insumo = (
        "INSUMO",
        "PRESTACAO DE SERVICO",
        "PREST SERVICO",
        "MATERIAL APLICADO",
        "MATERIAL DE CONSUMO",
    )

    if any(termo in nome for termo in termos_insumo):
        return "INSUMOS"

    return None


def _unidade_conta_0500(nome_cta: str | None) -> tuple[str, str | None]:
    """
    Retorna:
        ("FILIAL", "RJ")
        ("MATRIZ", None)
        ("GENERICO", None)
    """
    nome = _normalizar_nome_conta(nome_cta)

    if any(termo in nome for termo in ("MATRIZ", "MTZ")):
        return "MATRIZ", None

    for uf in _UFS:
        padroes = (
            rf"\bFL\s*[- ]?\s*{uf}\b",
            rf"\bFILIAL\s*[- ]?\s*{uf}\b",
            rf"\b{uf}\b",
        )

        if any(re.search(padrao, nome) for padrao in padroes):
            return "FILIAL", uf

    return "GENERICO", None


def resolver_cod_cta_por_catalogo_0500(
    *,
    categoria: str | None,
    tipo_conta: str,
    contas_0500: list[dict[str, Any]],
    uf_filial: str | None = None,
) -> dict[str, Any]:
    """
    Regras:

    CombustiveisLubrificantes:
        combustível da filial
        combustível da matriz
        combustível genérico

    Demais categorias da corretiva:
        insumos da filial
        insumos da matriz
        insumos genérico

    Sem correspondência:
        cod_cta = 0000
    """
    categoria = str(categoria or "").strip()
    uf_filial = str(uf_filial or "").strip().upper() or None

    categoria = str(categoria or "").strip()
    tipo_desejado = str(tipo_conta or "").strip().upper()

    candidatos: list[dict[str, Any]] = []

    for conta in contas_0500:
        nome_cta = str(conta.get("nome_cta") or "").strip()
        cod_cta = str(conta.get("cod_cta") or "").strip()

        if not cod_cta or not nome_cta:
            continue

        tipo_conta_encontrado = _tipo_conta_0500(nome_cta)

        if tipo_conta_encontrado != tipo_desejado:
            continue

        tipo_unidade, uf_conta = _unidade_conta_0500(nome_cta)

        candidato = {
            **conta,
            "tipo_conta": tipo_conta_encontrado,
            "tipo_unidade": tipo_unidade,
            "uf_conta": uf_conta,
        }

        candidatos.append(candidato)

    if uf_filial:
        conta_filial = next(
            (
                conta
                for conta in candidatos
                if conta["tipo_unidade"] == "FILIAL"
                and conta["uf_conta"] == uf_filial
            ),
            None,
        )

        if conta_filial:
            return {
                **conta_filial,
                "origem_resolucao": "FILIAL",
            }

    conta_matriz = next(
        (
            conta
            for conta in candidatos
            if conta["tipo_unidade"] == "MATRIZ"
        ),
        None,
    )

    if conta_matriz:
        return {
            **conta_matriz,
            "origem_resolucao": "MATRIZ",
        }

    conta_generica = next(
        (
            conta
            for conta in candidatos
            if conta["tipo_unidade"] == "GENERICO"
        ),
        None,
    )

    if conta_generica:
        return {
            **conta_generica,
            "origem_resolucao": "GENERICO",
        }

    return {
        "cod_cta": "0000",
        "nome_cta": "CONTA NAO RESOLVIDA",
        "categoria": categoria,
        "tipo_conta": tipo_desejado,
        "origem_resolucao": "NAO_RESOLVIDO",
    }