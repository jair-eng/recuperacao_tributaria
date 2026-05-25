# app/teste/test_insumo_transportadora.py

from app.db.session import SessionLocal

from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.cenarios.cenario_insumo_transportadora import cenario_insumo_transportadora


def testar(titulo, meta, catalogo):

    print("\n" + "=" * 80)
    print(titulo)
    print("=" * 80)

    classificacao = classificar_item_fiscal(
        catalogo=catalogo,
        meta=meta,
    )

    resultado = cenario_insumo_transportadora(
        meta,
        classificacao,
    )

    print("META:")
    print(meta)

    print("\nCLASSIFICACAO:")
    print(classificacao)

    print("\nCENARIO INSUMO TRANSPORTADORA:")
    print(resultado)


def main():

    db = SessionLocal()

    try:
        catalogo = carregar_catalogo_fiscal(db)

        casos = [
            (
                "DIESEL TRANSPORTADORA",
                {
                    "dominio": "DOM_TRANSP",
                    "cfop": "1102",
                    "ncm": "27101921",
                    "descr_item": "OLEO DIESEL S10",
                },
            ),
            (
                "GASOLINA TRANSPORTADORA | NAO ENTRA POR ENQUANTO",
                {
                    "dominio": "DOM_TRANSP",
                    "cfop": "1102",
                    "ncm": "27101259",
                    "descr_item": "GASOLINA COMUM",
                },
            ),
            (
                "LUBRIFICANTE TRANSPORTADORA",
                {
                    "dominio": "DOM_TRANSP",
                    "cfop": "1102",
                    "ncm": "27101932",
                    "descr_item": "OLEO LUBRIFICANTE 15W40",
                },
            ),
            (
                "PNEU TRANSPORTADORA",
                {
                    "dominio": "DOM_TRANSP",
                    "cfop": "1102",
                    "ncm": "40112090",
                    "descr_item": "PNEU CAMINHAO",
                },
            ),
            (
                "ARLA TRANSPORTADORA",
                {
                    "dominio": "DOM_TRANSP",
                    "cfop": "1102",
                    "ncm": "31021010",
                    "descr_item": "ARLA 32",
                },
            ),
            (
                "OUTRO DOMINIO",
                {
                    "dominio": "DOM_CAFE",
                    "cfop": "1102",
                    "ncm": "27101921",
                    "descr_item": "OLEO DIESEL S10",
                },
            ),
        ]

        for titulo, meta in casos:
            testar(titulo, meta, catalogo)

    finally:
        db.close()


if __name__ == "__main__":
    main()