from collections import Counter
from typing import Optional

from app.domain.sped.contabil.models.conta_resolvida import ContaResolvida
from app.domain.sped.contabil.loaders.loader_0500 import Contabil0500Context


ORIGEM_C170_ORIGINAL = "C170_ORIGINAL"
ORIGEM_C170_SEM_0500 = "C170_SEM_0500"
ORIGEM_MESMA_NATUREZA = "MESMA_NATUREZA"
ORIGEM_NAO_RESOLVIDO = "NAO_RESOLVIDO"


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