from app.db.session import SessionLocal
from app.domain.ecd.ecd_services import obter_contexto_contabil_por_cod_cta

db = SessionLocal()

try:
    ctx = obter_contexto_contabil_por_cod_cta(
        db,
        empresa_id=3,
        periodo="202203",
        cod_cta="470",
    )
    print(ctx)

finally:
    db.close()