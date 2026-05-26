from app.db.session import SessionLocal
from app.domain.workflow.corretiva_v2_service import aplicar_corretiva_apontamento_v2


APONTAMENTO_ID = 53


def main():
    db = SessionLocal()
    try:
        res = aplicar_corretiva_apontamento_v2(
            db=db,
            apontamento_id=APONTAMENTO_ID,
        )

        db.commit()

        print("RESULTADO CORRETIVA V2:")
        print(res)

    except Exception as e:
        db.rollback()
        print("ERRO:")
        print(repr(e))
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()