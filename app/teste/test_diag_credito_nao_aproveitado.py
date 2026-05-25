# app/teste/test_diag_credito_nao_aproveitado_v2.py
from app.db.models import ItemFiscalConsolidado
from app.db.session import SessionLocal
from sqlalchemy import or_
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal

from app.domain.fiscal.cenarios.cenario_posto_cred_normal import (
    cenario_posto_credito_normal,
)

from app.domain.fiscal.cenarios.cenario_enriquecimento import (
    enriquecer_cenario_com_enquadramento,
)
from app.domain.fiscal.diagnostico.diag_credito_nao_aproveitado import diagnosticar_credito_nao_aproveitado
from app.domain.fiscal.meta.meta_item_fiscal import meta_from_item_fiscal


def main():

    db = SessionLocal()

    try:

        catalogo = carregar_catalogo_fiscal(db)

        total = db.query(ItemFiscalConsolidado).count()
        print("TOTAL ItemFiscalConsolidado:", total)

        item = (
            db.query(ItemFiscalConsolidado)
            .filter(ItemFiscalConsolidado.dominio == "POSTO")
            .filter(ItemFiscalConsolidado.cfop == "1556")
            .filter(ItemFiscalConsolidado.cst_pis == "70")
            .first()
        )

        if not item:
            print("Nenhum item POSTO/1652/lubrificante com crédito zerado encontrado.")
            return


        if not item:
            print("Nenhum item fiscal consolidado encontrado para teste.")
            return

        meta = meta_from_item_fiscal(item)

        print("\n" + "=" * 80)
        print("META")
        print("=" * 80)
        print(meta)

        classificacao = classificar_item_fiscal(
            meta=meta,
            catalogo=catalogo,
        )

        print(classificacao)

        print("\n" + "=" * 80)
        print("CENARIO")
        print("=" * 80)

        cenario = cenario_posto_credito_normal(
            meta,
            classificacao,
        )

        print(cenario)

        print("\n" + "=" * 80)
        print("CENARIO ENRIQUECIDO")
        print("=" * 80)

        cenario = enriquecer_cenario_com_enquadramento(
            db,
            cenario,
        )

        print(cenario)

        print("\n" + "=" * 80)
        print("DIAGNOSTICA")
        print("=" * 80)

        diag = diagnosticar_credito_nao_aproveitado(
            meta=meta,
            classificacao=classificacao,
            cenario=cenario,
        )

        print(diag)

    finally:
        db.close()


if __name__ == "__main__":
    main()