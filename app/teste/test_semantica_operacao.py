from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.catalogo.semantica_operacao import (
    eh_entrada,
    eh_saida,
    eh_revenda,
    eh_exportacao,
    eh_transferencia,
    eh_imobilizado,
    eh_sem_credito,
    eh_servico,
    classificar_operacao_fiscal,
)

from app.db.session import SessionLocal


def print_result(titulo, meta, catalogo):
    print("\n" + "=" * 80)
    print(titulo)
    print("=" * 80)

    print("META:")
    print(meta)

    print("\nGRUPOS CFOP:")
    print(catalogo.grupos_cfop(meta.get("cfop")))

    print("\nCLASSIFICACAO:")
    print(classificar_operacao_fiscal(meta, catalogo))

    print("\nFLAGS:")
    print("eh_entrada      =", eh_entrada(meta, catalogo))
    print("eh_saida        =", eh_saida(meta, catalogo))
    print("eh_revenda      =", eh_revenda(meta, catalogo))
    print("eh_exportacao   =", eh_exportacao(meta, catalogo))
    print("eh_transferencia=", eh_transferencia(meta, catalogo))
    print("eh_imobilizado  =", eh_imobilizado(meta, catalogo))
    print("eh_servico      =", eh_servico(meta, catalogo))
    print("eh_sem_credito  =", eh_sem_credito(meta, catalogo))


def main():

    db = SessionLocal()

    catalogo = carregar_catalogo_fiscal(db)

    # ---------------------------------------------------------
    # ENTRADA REVENDA
    # ---------------------------------------------------------

    meta_entrada = {
        "cfop": "1102",
        "cst_pis": "50",
        "cst_cofins": "50",
    }

    print_result(
        "TESTE ENTRADA REVENDA",
        meta_entrada,
        catalogo,
    )

    # ---------------------------------------------------------
    # SAIDA REVENDA
    # ---------------------------------------------------------

    meta_saida = {
        "cfop": "5102",
        "cst_pis": "01",
        "cst_cofins": "01",
    }

    print_result(
        "TESTE SAIDA REVENDA",
        meta_saida,
        catalogo,
    )

    # ---------------------------------------------------------
    # EXPORTACAO
    # ---------------------------------------------------------

    meta_exportacao = {
        "cfop": "7501",
        "cst_pis": "08",
        "cst_cofins": "08",
    }

    print_result(
        "TESTE EXPORTACAO",
        meta_exportacao,
        catalogo,
    )

    # ---------------------------------------------------------
    # TRANSFERENCIA
    # ---------------------------------------------------------

    meta_transferencia = {
        "cfop": "5152",
        "cst_pis": "49",
        "cst_cofins": "49",
    }

    print_result(
        "TESTE TRANSFERENCIA",
        meta_transferencia,
        catalogo,
    )

    # ---------------------------------------------------------
    # IMOBILIZADO
    # ---------------------------------------------------------

    meta_imobilizado = {
        "cfop": "1551",
        "cst_pis": "50",
        "cst_cofins": "50",
    }

    print_result(
        "TESTE IMOBILIZADO",
        meta_imobilizado,
        catalogo,
    )

    # ---------------------------------------------------------
    # SEM CREDITO
    # ---------------------------------------------------------

    meta_sem_credito = {
        "cfop": "1102",
        "cst_pis": "70",
        "cst_cofins": "70",
    }

    print_result(
        "TESTE SEM CREDITO",
        meta_sem_credito,
        catalogo,
    )


if __name__ == "__main__":
    main()