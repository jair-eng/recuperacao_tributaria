from __future__ import annotations

from pathlib import Path

from app.db.session import SessionLocal
from app.domain.relatorio_executivo.exportar_relatorio_ecd_efd import exportar_relatorio_executivo_ecd_efd


def main() -> None:
    empresa_id = 1
    versao_id = 4
    periodo = "202211"

    caminho_saida = Path("tmp") / f"relatorio_executivo_ecd_efd_{empresa_id}_{versao_id}_{periodo}.xlsx"

    db = SessionLocal()
    try:
        arquivo = exportar_relatorio_executivo_ecd_efd(
            db,
            empresa_id=empresa_id,
            versao_id=versao_id,
            periodo=periodo,
            caminho_saida=caminho_saida,
            incluir_correcoes_automaticas=True,
            correcoes_automaticas=[],
        )

        print("=" * 80)
        print("RELATÓRIO EXECUTIVO ECD x EFD GERADO")
        print("=" * 80)
        print(f"Empresa ID: {empresa_id}")
        print(f"Versão ID: {versao_id}")
        print(f"Período: {periodo}")
        print(f"Arquivo: {arquivo.resolve()}")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    main()