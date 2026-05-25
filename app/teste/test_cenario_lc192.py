from app.db.session import SessionLocal

from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.cenarios.cenario_lc192 import cenario_lc192


def testar(titulo, meta, catalogo):

    print("\n" + "=" * 80)
    print(titulo)
    print("=" * 80)

    classificacao = classificar_item_fiscal(
        catalogo=catalogo,
        meta=meta,
    )

    resultado = cenario_lc192(
        meta,
        classificacao,
    )

    print("META:")
    print(meta)

    print("\nCLASSIFICACAO:")
    print(classificacao)

    print("\nCENARIO LC192:")
    print(resultado)


def main():

    db = SessionLocal()

    try:

        catalogo = carregar_catalogo_fiscal(db)

        casos = [

            # -------------------------------------------------
            # TRANSPORTE
            # -------------------------------------------------

            (
                "TRANSPORTADORA DIESEL | DENTRO LC192",
                {
                    "dominio": "DOM_TRANSP",
                    "cfop": "1102",
                    "ncm": "27101921",
                    "descr_item": "OLEO DIESEL S10",
                    "periodo": "202203",
                },
            ),

            (
                "TRANSPORTADORA DIESEL | FORA LC192",
                {
                    "dominio": "DOM_TRANSP",
                    "cfop": "1102",
                    "ncm": "27101921",
                    "descr_item": "OLEO DIESEL S10",
                    "periodo": "202301",
                },
            ),

            (
                "TRANSPORTADORA GASOLINA",
                {
                    "dominio": "DOM_TRANSP",
                    "cfop": "1102",
                    "ncm": "27101259",
                    "descr_item": "GASOLINA",
                    "periodo": "202203",
                },
            ),

            # -------------------------------------------------
            # POSTO
            # -------------------------------------------------

            (
                "POSTO GASOLINA | DENTRO LC192",
                {
                    "dominio": "DOM_POSTO",
                    "cfop": "1102",
                    "ncm": "27101259",
                    "descr_item": "GASOLINA COMUM",
                    "periodo": "202204",
                },
            ),

            (
                "POSTO GASOLINA | FORA LC192",
                {
                    "dominio": "DOM_POSTO",
                    "cfop": "1102",
                    "ncm": "27101259",
                    "descr_item": "GASOLINA COMUM",
                    "periodo": "202401",
                },
            ),

            # -------------------------------------------------
            # REVENDA GÁS
            # -------------------------------------------------

            (
                "REVENDA GAS GLP | DENTRO LC192",
                {
                    "dominio": "DOM_REVENDA_GAS",
                    "cfop": "1102",
                    "ncm": "27111910",
                    "descr_item": "GLP P13",
                    "periodo": "202205",
                },
            ),

            (
                "REVENDA GAS GLP | FORA LC192",
                {
                    "dominio": "DOM_REVENDA_GAS",
                    "cfop": "1102",
                    "ncm": "27111910",
                    "descr_item": "GLP P13",
                    "periodo": "202501",
                },
            ),

            # -------------------------------------------------
            # NÃO ELEGÍVEL
            # -------------------------------------------------

            (
                "FERTILIZANTE",
                {
                    "dominio": "DOM_AGRO",
                    "cfop": "1102",
                    "ncm": "31021010",
                    "descr_item": "UREIA AGRICOLA",
                    "periodo": "202203",
                },
            ),
        ]

        for titulo, meta in casos:
            testar(titulo, meta, catalogo)

    finally:
        db.close()


if __name__ == "__main__":
    main()