from app.db.session import SessionLocal
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.catalogo.semantica_produto import classificar_produto_fiscal


def testar(titulo, ncm,descricao, catalogo):
    meta = {"ncm": ncm,  "descr_item": descricao}

    print("\n" + "=" * 80)
    print(titulo)
    print("=" * 80)
    print("NCM:", ncm)
    print("DESCR:", descricao)
    print("GRUPOS:", catalogo.grupos_ncm(ncm))
    print("CLASSIFICACAO:", classificar_produto_fiscal(meta, catalogo))


def main():
    db = SessionLocal()

    try:
        catalogo = carregar_catalogo_fiscal(db)

        casos = [
            ("DIESEL", "27101921", None),
            ("GASOLINA", "27101259", None),
            ("ETANOL", "22071090", None),
            ("GLP", "27111910", None),
            ("LUBRIFICANTE", "27101932", None),
            ("FILTRO", "84212300", None),
            ("ARLA32", "31021010", None),
            ("PNEU CAMINHAO", "40112010", None),
            ("PNEU MOTO", "40114000", None),
            ("MANUTENCAO VEICULAR", "87089990", None),

            # novos cenários
            ("PECA MOTO", "87141000", None),
            ("AGUA MINERAL", "22011000", None),
            ("VASILHAME GAS", "73110000", None),
            ("ACESSORIO GAS - REGULADOR", "84811000", None),
            ("ACESSORIO GAS - MANGUEIRA", "39173100", None),
            ("MAQUININHA CARTAO", "84705010", None),
            ("FERTILIZANTE NCM", "31021010", None),
            ("FERTILIZANTE DESC NPK", "", "ADUBO NPK 20-05-20"),
            ("FERTILIZANTE DESC UREIA", "", "UREIA AGRICOLA"),
        ]

        for titulo, ncm, descricao in casos:
            testar(titulo, ncm, descricao, catalogo)

    finally:
        db.close()


if __name__ == "__main__":
    main()