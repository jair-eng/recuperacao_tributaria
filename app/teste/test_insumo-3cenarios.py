# app/teste/test_cenarios_insumos_dominios.py
from app.db.session import SessionLocal
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.cenarios.cenario_insumo_transportadora import cenario_insumo_transportadora
from app.domain.fiscal.cenarios.cenario_posto_cred_normal import cenario_posto_credito_normal
from app.domain.fiscal.cenarios.cenario_insumo_revenda_gas import cenario_insumo_revenda_gas


def rodar(titulo: str, meta: dict, catalogo):
    print("\n" + "=" * 80)
    print(titulo)
    print("=" * 80)

    classificacao = classificar_item_fiscal(meta=meta, catalogo=catalogo)

    print("META:")
    print(meta)

    print("\nCLASSIFICACAO:")
    print(classificacao)

    print("\nTRANSPORTADORA:")
    print(cenario_insumo_transportadora(meta, classificacao))

    print("\nPOSTO CREDITO NORMAL:")
    print(cenario_posto_credito_normal(meta, classificacao))

    print("\nREVENDA GAS:")
    print(cenario_insumo_revenda_gas(meta, classificacao))


def main():
    db = SessionLocal()

    try:
        catalogo = carregar_catalogo_fiscal(db)

        casos = [
            ("TRANSP | DIESEL", {"dominio": "DOM_TRANSP", "cfop": "1102", "ncm": "27101921", "descr_item": "OLEO DIESEL S10"}),
            ("TRANSP | LUBRIFICANTE", {"dominio": "DOM_TRANSP", "cfop": "1102", "ncm": "27101932", "descr_item": "OLEO LUBRIFICANTE 15W40"}),
            ("TRANSP | PNEU", {"dominio": "DOM_TRANSP", "cfop": "1102", "ncm": "40112090", "descr_item": "PNEU CAMINHAO"}),
            ("TRANSP | ARLA", {"dominio": "DOM_TRANSP", "cfop": "1102", "ncm": "31021010", "descr_item": "ARLA 32"}),

            ("POSTO | LUBRIFICANTE", {"dominio": "DOM_POSTO", "cfop": "1102", "ncm": "27101932", "descr_item": "OLEO LUBRIFICANTE 15W40"}),
            ("POSTO | FILTRO", {"dominio": "DOM_POSTO", "cfop": "1102", "ncm": "84212300", "descr_item": "FILTRO DE OLEO"}),
            ("POSTO | PNEU", {"dominio": "DOM_POSTO", "cfop": "1102", "ncm": "40112090", "descr_item": "PNEU CAMINHAO"}),
            ("POSTO | GERAL SHAMPOO", {"dominio": "DOM_POSTO", "cfop": "1102", "ncm": "34029090", "descr_item": "SHAMPOO AUTOMOTIVO"}),
            ("POSTO | DIESEL BLOQUEADO", {"dominio": "DOM_POSTO", "cfop": "1102", "ncm": "27101921", "descr_item": "OLEO DIESEL S10"}),

            ("REVENDA GAS | DIESEL", {"dominio": "DOM_REVENDA_GAS", "cfop": "1102", "ncm": "27101921", "descr_item": "OLEO DIESEL S10"}),
            ("REVENDA GAS | GASOLINA", {"dominio": "DOM_REVENDA_GAS", "cfop": "1102", "ncm": "27101259", "descr_item": "GASOLINA COMUM"}),
            ("REVENDA GAS | PNEU", {"dominio": "DOM_REVENDA_GAS", "cfop": "1102", "ncm": "40112090", "descr_item": "PNEU CAMINHAO"}),
            ("REVENDA GAS | ARLA", {"dominio": "DOM_REVENDA_GAS", "cfop": "1102", "ncm": "31021010", "descr_item": "ARLA 32"}),
            ("REVENDA GAS | GLP BLOQUEADO", {"dominio": "DOM_REVENDA_GAS", "cfop": "1102", "ncm": "27111910", "descr_item": "GLP GAS LIQUEFEITO"}),
        ]

        for titulo, meta in casos:
            rodar(titulo, meta, catalogo)

    finally:
        db.close()
if __name__ == "__main__":
    main()