# app/teste/test_enquadramento_repository.py

from app.db.session import SessionLocal
from app.domain.fiscal.enquadramento.enquadramento_repository import (
    buscar_enquadramento_por_cenario,
)


def testar(codigo_cenario: str):
    db = SessionLocal()
    try:
        print("\n" + "=" * 80)
        print(codigo_cenario)
        print("=" * 80)

        enq = buscar_enquadramento_por_cenario(db, codigo_cenario)

        print("RESULTADO:")
        print(enq)

    finally:
        db.close()


def main():
    casos = [
        "POSTO_CREDITO_NORMAL_GERAL",
        "POSTO_CREDITO_NORMAL_LUBRIFICANTE",
        "TRANSP_INSUMO_DIESEL",
        "REVENDA_GAS_INSUMO_COMBUSTIVEL",
        "LC192_2022",
        "CENARIO_INEXISTENTE",
    ]

    for codigo in casos:
        testar(codigo)


if __name__ == "__main__":
    main()