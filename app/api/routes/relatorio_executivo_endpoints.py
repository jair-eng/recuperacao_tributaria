from __future__ import annotations

import tempfile
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.relatorio_executivo.relatorio_executivo_local_service import (
    gerar_relatorio_executivo_local,
)


router = APIRouter(
    prefix="/relatorio-executivo",
    tags=["Relatório Executivo"],
)

PASTA_ECD = Path(r"C:\Sped\ECD")
PASTA_CONTRIB = Path(r"C:\Sped\CONTRIB")

@router.post("/ecd-efd/local")
def gerar_relatorio_ecd_efd_local(
    db: Session = Depends(get_db),
    empresa_id: int | None = None,
    dominio: str = "GERAL"
):
    try:

        PASTA_SAIDA = Path(r"C:\Sped\saida")

        nome_arquivo = f"relatorio_executivo_ecd_efd_local_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        caminho_saida = PASTA_SAIDA / nome_arquivo


        caminho = gerar_relatorio_executivo_local(
            db=db,
            empresa_id=empresa_id,
            dominio=dominio,
            pasta_ecd=PASTA_ECD,
            pasta_contrib=PASTA_CONTRIB,
            caminho_saida=caminho_saida,
        )

        return FileResponse(
            path=str(caminho),
            filename=nome_arquivo,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar relatório executivo local: {e}",
        )