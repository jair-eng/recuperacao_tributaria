from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.workflow.preparar_revisao_service import preparar_revisao

router = APIRouter(prefix="/workflow", tags=["Workflow"])


@router.post("/workflow/{versao_id}/preparar-revisao")
def preparar_revisao_endpoint(
    versao_id: int,
    db: Session = Depends(get_db),
):
    print("[ROTA_PREPARAR_REVISAO] entrou | versao_id=", versao_id, flush=True)
    try:
        return preparar_revisao(
            db=db,
            versao_id=versao_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print("[PREPARAR_REVISAO][ERRO]", repr(e), flush=True)
        raise HTTPException(
            status_code=500,
            detail="Erro ao preparar revisão fiscal.",
        )