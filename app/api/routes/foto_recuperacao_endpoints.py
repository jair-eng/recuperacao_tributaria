from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse


router = APIRouter(prefix="/foto-recuperacao", tags=["Foto Recuperação"])

PASTA_ICMS = Path(r"C:\Sped\ICMS_IPI")
PASTA_CONTRIB = Path(r"C:\Sped\CONTRIB")

@router.post("/executar")
def executar_foto_recuperacao():
    """
       Gera a Foto Recuperação Tributária da empresa.
       """
    raise HTTPException(
        status_code=410,
        detail={
            "ok": False,
            "status": "descontinuado",
            "mensagem": "Foto Recuperação legado foi descontinuado. Use o novo relatório executivo ECD x EFD.",
            "novo_endpoint": "/relatorio-executivo/ecd-efd",
        },
    )