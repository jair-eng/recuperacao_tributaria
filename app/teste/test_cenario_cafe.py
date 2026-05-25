# app/teste/test_cenario_cafe.py

from app.db.session import SessionLocal

from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.cenarios.cenario_cafe import cenario_cafe


def testar(titulo, meta, catalogo):

    print("\n" + "=" * 80)
    print(titulo)
    print("=" * 80)

    classificacao = classificar_item_fiscal(
        catalogo=catalogo,
        meta=meta,
    )
    print(classificacao["produto"].keys())
    resultado = cenario_cafe(
        meta,
        classificacao,
    )

    print("META:")
    print(meta)

    print("\nCLASSIFICACAO:")
    print(classificacao)

    print("\nCENARIO CAFE:")
    print(resultado)


def main():

    db = SessionLocal()

    try:
        catalogo = carregar_catalogo_fiscal(db)

        casos = [

            (
                "CAFE TORRADO | ENTRADA CAFE",
                {
                    "dominio": "DOM_CAFE",
                    "cfop": "1101",
                    "ncm": "09012100",
                    "descr_item": "CAFE TORRADO EM GRAO",
                },
            ),

            (
                "CAFE CRU | ENTRADA CAFE",
                {
                    "dominio": "DOM_CAFE",
                    "cfop": "1101",
                    "ncm": "09011110",
                    "descr_item": "CAFE CRU EM GRAO",
                },
            ),

            (
                "CAFE | CFOP FORA",
                {
                    "dominio": "DOM_CAFE",
                    "cfop": "1551",
                    "ncm": "09012100",
                    "descr_item": "CAFE TORRADO",
                },
            ),

            (
                "FERTILIZANTE | DOMINIO CAFE",
                {
                    "dominio": "DOM_CAFE",
                    "cfop": "1101",
                    "ncm": "31021010",
                    "descr_item": "UREIA AGRICOLA",
                },
            ),

            (
                "CAFE | OUTRO DOMINIO",
                {
                    "dominio": "DOM_AGRO",
                    "cfop": "1101",
                    "ncm": "09012100",
                    "descr_item": "CAFE TORRADO",
                },
            ),
        ]

        for titulo, meta in casos:
            testar(titulo, meta, catalogo)

    finally:
        db.close()


if __name__ == "__main__":
    main()