from __future__ import annotations
from sqlalchemy.orm import Session
from app.services.upload_preview_service import UploadPreviewService
from app.services.upload_confirm_service import UploadConfirmService

class UploadService:
    """
    Orquestra upload:
      preview -> confirm

    Transação:
      - UploadConfirmService NÃO comita
      - UploadService comita 1 vez no final
    """

    @staticmethod
    def preview(upload_file) -> dict:
        return UploadPreviewService.processar_preview(upload_file)

    @staticmethod
    def confirm(db: Session, payload: dict) -> dict:
        temp_id = payload.get("temp_id")
        if not temp_id:
            raise ValueError("temp_id é obrigatório")

        nome_arquivo = payload.get("nome_arquivo")
        dominio = payload.get("dominio")

        try:
            resultado = UploadConfirmService.confirmar_upload(
                db=db,
                temp_id=temp_id,
                nome_arquivo=nome_arquivo,
                dominio=dominio,
            )

            resultado["apontamentos_gerados"] = 0
            resultado["erros_regras"] = []
            resultado["pipeline"] = "V2_PREPARAR_REVISAO_MANUAL"

            db.commit()
            return resultado

        except Exception:
            db.rollback()
            raise