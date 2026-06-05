from pathlib import Path

from app.db.session import SessionLocal
from app.domain.relatorio_executivo.relatorio_executivo_local_service import (
    gerar_relatorio_executivo_local,
)


def main():
    db = SessionLocal()

    try:
        caminho = gerar_relatorio_executivo_local(
            db=db,
            empresa_id=1,
            pasta_ecd=Path(r"C:\Sped\ECD"),
            pasta_contrib=Path(r"C:\Sped\CONTRIB"),
            caminho_saida=Path(r"C:\Sped\saida\relatorio_executivo_local.xlsx"),
        )

        print("\nOK - Relatório gerado:")
        print(caminho)

    finally:
        db.close()


if __name__ == "__main__":
    main()