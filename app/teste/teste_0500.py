from app.db.session import SessionLocal
from app.db.models import ItemFiscalConsolidado
from app.domain.sped.services.contexto_fiscal.materializar_contexto_fiscal import (
    materializar_contexto_fiscal,
)


VERSOES = [1, 2, 3, 6, 7, 8, 9, 10]


def contar(db, versao_id, campo):
    rows = (
        db.query(campo, ItemFiscalConsolidado.id)
        .filter(ItemFiscalConsolidado.versao_id == versao_id)
        .all()
    )

    out = {}
    for valor, _ in rows:
        chave = str(valor or "NULL")
        out[chave] = out.get(chave, 0) + 1
    return out


db = SessionLocal()

try:
    for versao_id in VERSOES:
        print("\n" + "=" * 80)
        print(f"VERSAO {versao_id}")
        print("=" * 80)

        try:
            materializar_contexto_fiscal(db, versao_id=versao_id)

            total = (
                db.query(ItemFiscalConsolidado)
                .filter(ItemFiscalConsolidado.versao_id == versao_id)
                .count()
            )

            print("TOTAL ITENS:", total)

            print("\nSTATUS CRUZAMENTO:")
            print(contar(db, versao_id, ItemFiscalConsolidado.status_cruzamento))

            print("\nORIGEM COD_CTA:")
            print(contar(db, versao_id, ItemFiscalConsolidado.cod_cta_origem))

            print("\nDOMINIO:")
            print(contar(db, versao_id, ItemFiscalConsolidado.dominio))

            print("\nCFOP TOP 20:")
            cfops = (
                db.query(ItemFiscalConsolidado.cfop, ItemFiscalConsolidado.id)
                .filter(ItemFiscalConsolidado.versao_id == versao_id)
                .all()
            )
            cont_cfop = {}
            for cfop, _ in cfops:
                chave = str(cfop or "NULL")
                cont_cfop[chave] = cont_cfop.get(chave, 0) + 1

            for cfop, qtd in sorted(cont_cfop.items(), key=lambda x: x[1], reverse=True)[:20]:
                print(cfop, qtd)

            print("\nAMOSTRA PROBLEMAS:")
            problemas = (
                db.query(ItemFiscalConsolidado)
                .filter(ItemFiscalConsolidado.versao_id == versao_id)
                .filter(
                    ItemFiscalConsolidado.status_cruzamento.in_(
                        ["SO_ICMS", "SO_CONTRIB", "DIVERGENTE"]
                    )
                )
                .limit(15)
                .all()
            )

            for item in problemas:
                print(
                    "status=", item.status_cruzamento,
                    "| cod_item=", item.cod_item,
                    "| descr=", item.descr_item,
                    "| cfop=", item.cfop,
                    "| ncm=", item.ncm,
                    "| cod_cta=", item.cod_cta,
                    "| origem_cta=", item.cod_cta_origem,
                    "| conf=", item.cod_cta_confianca,
                    "| meta=", item.meta,
                )

        except Exception as e:
            db.rollback()
            print("ERRO:", e)

finally:
    db.close()