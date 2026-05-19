from types import SimpleNamespace

from app.domain.sped.contextos.contexto_competencia import montar_contexto_competencia
from app.domain.sped.services.contabil.resolver_cod_cta_service import resolver_cod_cta_v2


registros = [
    SimpleNamespace(
        reg="0500",
        linha=10,
        dados=[
            "01012024",
            "04",
            "A",
            "5",
            "523",
            "PRESTA O DE SERVICOS DE TRANSPORTE",
            "3.01.01.01.01.06",
            "",
        ],
    ),
    SimpleNamespace(
        reg="0500",
        linha=11,
        dados=[
            "01012024",
            "04",
            "A",
            "5",
            "25666",
            "Mercadorias",
            "",
            "",
        ],
    ),
]

ctx = montar_contexto_competencia(registros=registros)

print("=== CONTEXTO 0500 ===")
print("qtd contas:", len(ctx.contabil_0500.contas))
print("indice:", list(ctx.contabil_0500.indice.keys()))

print("\n=== C170 COM COD_CTA EXISTENTE ===")
print(
    resolver_cod_cta_v2(
        cod_cta_original="523",
        contabil_0500=ctx.contabil_0500,
    )
)

print("\n=== C170 COM COD_CTA EXISTENTE 2 ===")
print(
    resolver_cod_cta_v2(
        cod_cta_original="25666",
        contabil_0500=ctx.contabil_0500,
    )
)

print("\n=== C170 COM COD_CTA INEXISTENTE NO 0500 ===")
print(
    resolver_cod_cta_v2(
        cod_cta_original="99999",
        contabil_0500=ctx.contabil_0500,
    )
)

print("\n=== C170 SEM COD_CTA + MESMA NATUREZA ===")
print(
    resolver_cod_cta_v2(
        cod_cta_original="",
        contabil_0500=ctx.contabil_0500,
        candidatos_mesma_natureza=[
            (5, "523"),
            (7, "25666"),
            (7, "25666"),
        ],
    )
)

print("\n=== C170 SEM COD_CTA E SEM CANDIDATO ===")
print(
    resolver_cod_cta_v2(
        cod_cta_original="",
        contabil_0500=ctx.contabil_0500,
    )
)