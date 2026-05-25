from app.db.session import SessionLocal

from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal


def testar(titulo, meta, catalogo):

    print("\n" + "=" * 80)
    print(titulo)
    print("=" * 80)

    print("META:")
    print(meta)

    resultado = classificar_item_fiscal(
        catalogo=catalogo,
        meta=meta,
    )

    print("\nRESULTADO:")
    print(resultado)


def main():

    db = SessionLocal()

    try:

        catalogo = carregar_catalogo_fiscal(db)

        casos = [

            (
                "COMPRA DIESEL TRANSPORTADORA",
                {
                    "cfop": "1102",
                    "ncm": "27101921",
                    "cst_pis": "50",
                    "cst_cofins": "50",
                    "descr_item": "OLEO DIESEL S10",
                },
            ),

            (
                "VENDA GLP",
                {
                    "cfop": "5102",
                    "ncm": "27111910",
                    "cst_pis": "01",
                    "cst_cofins": "01",
                    "descr_item": "GLP P13",
                },
            ),

            (
                "FERTILIZANTE POR DESCRICAO",
                {
                    "cfop": "1102",
                    "ncm": "",
                    "cst_pis": "50",
                    "cst_cofins": "50",
                    "descr_item": "ADUBO NPK 20-05-20",
                },
            ),
        ]

        for titulo, meta in casos:
            testar(titulo, meta, catalogo)

    finally:
        db.close()


if __name__ == "__main__":
    main()