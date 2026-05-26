from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.ecd import EcdArquivo
from app.domain.ecd.ecd_importer import importar_ecd_arquivo

router = APIRouter(prefix="/ecd", tags=["ECD"])

UPLOAD_DIR = Path("uploads/ecd")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/importar")
async def importar_ecd(
    empresa_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    nome_arquivo = file.filename or "ecd.txt"

    destino = UPLOAD_DIR / nome_arquivo

    with destino.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = importar_ecd_arquivo(
        db,
        empresa_id=empresa_id,
        caminho_arquivo=str(destino),
        nome_arquivo=nome_arquivo,
        sobrescrever=True,
    )

    return result

@router.get("/empresa/{empresa_id}/arquivos")
def listar_arquivos_ecd(
    empresa_id: int,
    db: Session = Depends(get_db),
):
    rows = (
        db.query(EcdArquivo)
        .filter(EcdArquivo.empresa_id == empresa_id)
        .order_by(EcdArquivo.id.desc())
        .all()
    )

    return [
        {
            "id": x.id,
            "empresa_id": x.empresa_id,
            "ano": x.ano,
            "cnpj": x.cnpj,
            "nome_empresa": x.nome_empresa,
            "periodo_inicio": x.periodo_inicio,
            "periodo_fim": x.periodo_fim,
            "nome_arquivo": x.nome_arquivo,
            "total_linhas": x.total_linhas,
            "criado_em": x.criado_em,
        }
        for x in rows
    ]

@router.get("/arquivo/{ecd_arquivo_id}/resumo")
def resumo_ecd(
    ecd_arquivo_id: int,
    db: Session = Depends(get_db),
):
    row = (
        db.query(EcdArquivo)
        .filter(EcdArquivo.id == ecd_arquivo_id)
        .first()
    )

    if not row:
        return {
            "ok": False,
            "erro": "ECD não encontrada",
        }

    return {
        "ok": True,
        "id": row.id,
        "empresa_id": row.empresa_id,
        "ano": row.ano,
        "cnpj": row.cnpj,
        "nome_empresa": row.nome_empresa,
        "periodo_inicio": row.periodo_inicio,
        "periodo_fim": row.periodo_fim,
        "nome_arquivo": row.nome_arquivo,
        "total_linhas": row.total_linhas,
        "criado_em": row.criado_em,
    }