# app/teste/test_cenario_insumo_cafe.py

from app.db.session import SessionLocal

from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.cenarios.cenario_insumo_cafe import cenario_insumo_cafe


def testar(titulo, meta, catalogo):

    print("\n" + "=" * 80)
    print(titulo)
    print("=" * 80)

    classificacao = classificar_item_fiscal(
        catalogo=catalogo,
        meta=meta,
    )

    resultado = cenario_insumo_cafe(
        meta,
        classificacao,
    )

    print("META:")
    print(meta)

    print("\nCLASSIFICACAO:")
    print(classificacao)

    print("\nCENARIO INSUMO CAFE:")
    print(resultado)


def main():

    db = SessionLocal()

    try:

        catalogo = carregar_catalogo_fiscal(db)

        casos = [

            (
                "FERTILIZANTE",
                {
                    "dominio": "DOM_CAFE",
                    "cfop": "1102",
                    "ncm": "31021010",
                    "descr_item": "UREIA AGRICOLA",
                },
            ),

            (
                "DIESEL",
                {
                    "dominio": "DOM_CAFE",
                    "cfop": "1102",
                    "ncm": "27101921",
                    "descr_item": "OLEO DIESEL S10",
                },
            ),

            (
                "BIG BAG",
                {
                    "dominio": "DOM_CAFE",
                    "cfop": "1102",
                    "ncm": "63053200",
                    "descr_item": "BIG BAG 1000KG",
                },
            ),

            (
                "CAFE TORRADO",
                {
                    "dominio": "DOM_CAFE",
                    "cfop": "1102",
                    "ncm": "09012100",
                    "descr_item": "CAFE TORRADO",
                },
            ),

            (
                "IMOBILIZADO",
                {
                    "dominio": "DOM_CAFE",
                    "cfop": "1551",
                    "ncm": "27101921",
                    "descr_item": "OLEO DIESEL S10",
                },
            ),

            (
                "OUTRO DOMINIO",
                {
                    "dominio": "DOM_TRANSP",
                    "cfop": "1102",
                    "ncm": "31021010",
                    "descr_item": "UREIA AGRICOLA",
                },
            ),
        ]

        for titulo, meta in casos:
            testar(titulo, meta, catalogo)

    finally:
        db.close()


if __name__ == "__main__":
    main()