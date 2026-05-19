from collections import Counter

from typing import Any, Iterable, Optional, List
from app.Legacy.fiscal.regras.Diagnostico.insumos.insumos_helpers import _extrair_chaves_c170, _score_natureza, _norm_str,_get_dados_list, _somente_digitos





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