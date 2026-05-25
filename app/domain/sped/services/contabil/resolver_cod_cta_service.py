from collections import Counter
from typing import Optional

from app.domain.sped.contabil.models.conta_resolvida import ContaResolvida
from app.domain.sped.contabil.loaders.loader_0500 import Contabil0500Context
from app.utils.strings import norm_str

ORIGEM_C170_ORIGINAL = "C170_ORIGINAL"
ORIGEM_C170_SEM_0500 = "C170_SEM_0500"
ORIGEM_MESMA_NATUREZA = "MESMA_NATUREZA"
ORIGEM_NAO_RESOLVIDO = "NAO_RESOLVIDO"


def _descricao_tokens(desc: str) -> set[str]:
    base = norm_str(desc).lower()
    tokens = {
        t for t in base.replace("-", " ").replace("/", " ").split()
        if len(t) >= 4
    }
    stop = {"para", "com", "de", "da", "das", "dos", "item", "tipo"}
    return {t for t in tokens if t not in stop}


def _score_natureza_contabil(
    *,
    alvo_desc: str,
    alvo_cfop: str,
    alvo_ncm: str,
    cand_desc: str,
    cand_cfop: str,
    cand_ncm: str,
) -> int:
    score = 0

    if alvo_cfop and cand_cfop and alvo_cfop == cand_cfop:
        score += 4
    elif alvo_cfop and cand_cfop and alvo_cfop[:3] == cand_cfop[:3]:
        score += 2

    if alvo_ncm and cand_ncm and alvo_ncm == cand_ncm:
        score += 4
    elif alvo_ncm and cand_ncm and alvo_ncm[:4] == cand_ncm[:4]:
        score += 2

    ta = _descricao_tokens(alvo_desc)
    tc = _descricao_tokens(cand_desc)
    inter = ta & tc

    if len(inter) >= 2:
        score += 3
    elif len(inter) == 1:
        score += 1

    desc_a = norm_str(alvo_desc).lower()
    desc_c = norm_str(cand_desc).lower()

    grupos = [
        {"diesel", "combustivel", "combustível"},
        {"pneu", "recap"},
        {"filtro", "oleo", "óleo", "lubrificante"},
        {"freio", "lona", "rolamento", "peca", "peça"},
    ]

    for g in grupos:
        if any(x in desc_a for x in g) and any(x in desc_c for x in g):
            score += 2
            break

    return score

def montar_candidatos_mesma_natureza(
    *,
    alvo,
    itens_referencia: list,
) -> list[tuple[int, str]]:
    candidatos: list[tuple[int, str]] = []

    for cand in itens_referencia:
        cod_cta = str(getattr(cand, "cod_cta", "") or "").strip()
        origem = str(getattr(cand, "cod_cta_origem", "") or "").strip()

        if not cod_cta:
            continue

        if origem in {ORIGEM_NAO_RESOLVIDO, "NAO_APLICAVEL_SO_ICMS"}:
            continue

        score = _score_natureza_contabil(
            alvo_desc=str(getattr(alvo, "descr_item", "") or ""),
            alvo_cfop=str(getattr(alvo, "cfop", "") or ""),
            alvo_ncm=str(getattr(alvo, "ncm", "") or ""),
            cand_desc=str(getattr(cand, "descr_item", "") or ""),
            cand_cfop=str(getattr(cand, "cfop", "") or ""),
            cand_ncm=str(getattr(cand, "ncm", "") or ""),
        )

        if score >= 5:
            candidatos.append((score, cod_cta))

    return candidatos

def resolver_cod_cta_v2(
    *,
    cod_cta_original: Optional[str],
    contabil_0500: Contabil0500Context,
    candidatos_mesma_natureza: Optional[list[tuple[int, str]]] = None,
) -> ContaResolvida:
    cod_cta = str(cod_cta_original or "").strip()

    if cod_cta and cod_cta in contabil_0500.indice:
        conta = contabil_0500.indice[cod_cta]
        return ContaResolvida(
            cod_cta=cod_cta,
            origem=ORIGEM_C170_ORIGINAL,
            confianca=100,
            justificativa=f"COD_CTA informado no C170 e encontrado no 0500: {conta.nome_cta}",
        )

    if cod_cta:
        return ContaResolvida(
            cod_cta=cod_cta,
            origem=ORIGEM_C170_SEM_0500,
            confianca=60,
            justificativa="COD_CTA informado no C170, mas não encontrado no 0500.",
        )

    candidatos_validos = [
        (score, str(c or "").strip())
        for score, c in (candidatos_mesma_natureza or [])
        if score > 0 and str(c or "").strip()
    ]

    if candidatos_validos:
        melhor_score = max(score for score, _ in candidatos_validos)
        melhores = [c for score, c in candidatos_validos if score == melhor_score]
        cod_cta_inferido = Counter(melhores).most_common(1)[0][0]

        return ContaResolvida(
            cod_cta=cod_cta_inferido,
            origem=ORIGEM_MESMA_NATUREZA,
            confianca=min(80, max(40, melhor_score * 10)),
            justificativa=f"COD_CTA inferido por mesma natureza fiscal. Score={melhor_score}.",
        )

    return ContaResolvida(
        cod_cta="",
        origem=ORIGEM_NAO_RESOLVIDO,
        confianca=0,
        justificativa="C170 sem COD_CTA informado e sem candidato confiável por natureza.",
    )