from app.db.session import SessionLocal

from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.cenarios.cenario_posto_cred_normal import cenario_posto_credito_normal


def rodar(titulo,meta,catalogo):
    print("\n" + "=" * 80)
    print(titulo)
    print("=" * 80)

    classificacao = classificar_item_fiscal(meta=meta,catalogo=catalogo)

    print("META:")
    print(meta)

    print("\nCLASSIFICACAO:")
    print(classificacao)

    resultado = cenario_posto_credito_normal(meta, classificacao)

    print("\nCENARIO POSTO CREDITO NORMAL:")
    print(resultado)


def main():
    db = SessionLocal()

    try:
        catalogo = carregar_catalogo_fiscal(db)
        casos = [
            (
                "LUBRIFICANTE POSTO",
                {
                    "dominio": "DOM_POSTO",
                    "cfop": "1102",
                    "ncm": "27101932",
                    "descr_item": "OLEO LUBRIFICANTE 15W40",
                },
            ),
            (
                "FILTRO POSTO",
                {
                    "dominio": "DOM_POSTO",
                    "cfop": "1102",
                    "ncm": "84212300",
                    "descr_item": "FILTRO DE OLEO",
                },
            ),
            (
                "ARLA POSTO",
                {
                    "dominio": "DOM_POSTO",
                    "cfop": "1102",
                    "ncm": "31021010",
                    "descr_item": "ARLA 32",
                },
            ),
            (
                "PNEU POSTO",
                {
                    "dominio": "DOM_POSTO",
                    "cfop": "1102",
                    "ncm": "40112090",
                    "descr_item": "PNEU CAMINHAO",
                },
            ),
            (
                "POSTO GERAL | SHAMPOO AUTOMOTIVO",
                {
                    "dominio": "DOM_POSTO",
                    "cfop": "1102",
                    "ncm": "34029090",
                    "descr_item": "SHAMPOO AUTOMOTIVO",
                },
            ),
            (
                "POSTO GERAL | SILICONE AUTOMOTIVO",
                {
                    "dominio": "DOM_POSTO",
                    "cfop": "1102",
                    "ncm": "39100012",
                    "descr_item": "SILICONE AUTOMOTIVO",
                },
            ),
            (
                "GASOLINA POSTO | DEVE BLOQUEAR",
                {
                    "dominio": "DOM_POSTO",
                    "cfop": "1102",
                    "ncm": "27101259",
                    "descr_item": "GASOLINA COMUM",
                },
            ),
            (
                "DIESEL POSTO | DEVE BLOQUEAR",
                {
                    "dominio": "DOM_POSTO",
                    "cfop": "1102",
                    "ncm": "27101921",
                    "descr_item": "OLEO DIESEL S10",
                },
            ),
            (
                "LUBRIFICANTE OUTRO DOMINIO | DEVE BLOQUEAR",
                {
                    "dominio": "DOM_TRANSP",
                    "cfop": "1102",
                    "ncm": "27101932",
                    "descr_item": "OLEO LUBRIFICANTE 15W40",
                },
            ),
        ]

        for titulo, meta in casos:
            rodar(titulo, meta,catalogo)

    finally:
        db.close()
if __name__ == "__main__":
    main()