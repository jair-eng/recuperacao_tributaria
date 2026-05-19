from types import SimpleNamespace

from app.db.session import SessionLocal
from app.db.models import ItemFiscalConsolidado

from app.domain.sped.contextos.contexto_competencia import montar_contexto_competencia
from app.domain.sped.services.contabil.resolver_cod_cta_service import resolver_cod_cta_v2
from app.domain.sped.services.contexto_fiscal.materializar_contexto_fiscal import materializar_contexto_fiscal


def teste_0500_vazio():
    print("\n=== TESTE 1: 0500 vazio ===")

    ctx = montar_contexto_competencia(registros=[])

    print("qtd contas:", len(ctx.contabil_0500.contas))
    print("indice:", ctx.contabil_0500.indice)

    res = resolver_cod_cta_v2(
        cod_cta_original="123",
        contabil_0500=ctx.contabil_0500,
    )

    print(res)


def teste_cod_cta_existente():
    print("\n=== TESTE 2: COD_CTA existente no 0500 ===")

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
        )
    ]

    ctx = montar_contexto_competencia(registros=registros)

    res = resolver_cod_cta_v2(
        cod_cta_original="523",
        contabil_0500=ctx.contabil_0500,
    )

    print(res)


def teste_mesma_natureza():
    print("\n=== TESTE 3: Mesma natureza ===")

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
                "TRANSPORTE",
                "",
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
                "MERCADORIAS",
                "",
                "",
            ],
        ),
    ]

    ctx = montar_contexto_competencia(registros=registros)

    res = resolver_cod_cta_v2(
        cod_cta_original="",
        contabil_0500=ctx.contabil_0500,
        candidatos_mesma_natureza=[
            (5, "523"),
            (7, "25666"),
            (7, "25666"),
        ],
    )

    print(res)


def teste_materializar_duas_vezes():
    print("\n=== TESTE 4: Materializar duas vezes ===")

    VERSAO_ID = 1
    db = SessionLocal()

    try:
        materializar_contexto_fiscal(db, versao_id=VERSAO_ID)
        materializar_contexto_fiscal(db, versao_id=VERSAO_ID)

        itens = (
            db.query(ItemFiscalConsolidado)
            .filter(ItemFiscalConsolidado.versao_id == VERSAO_ID)
            .limit(20)
            .all()
        )

        print("qtd exibida:", len(itens))

        for item in itens:
            print(
                "id=", item.id,
                "| cod_item=", item.cod_item,
                "| cod_cta=", item.cod_cta,
                "| origem=", item.cod_cta_origem,
                "| conf=", item.cod_cta_confianca,
                "| just=", item.cod_cta_justificativa,
            )

    finally:
        db.close()


if __name__ == "__main__":
    teste_0500_vazio()
    teste_cod_cta_existente()
    teste_mesma_natureza()
    teste_materializar_duas_vezes()