
from app.db.session import SessionLocal
from app.domain.ecd.ecd_gap_service import gerar_diagnostico_gap_ecd_efd_por_versao


db = SessionLocal()

try:
    resultado = gerar_diagnostico_gap_ecd_efd_por_versao(
        db,
        versao_id=4,
        periodo="202203",
        linhas_ecd_classificadas=[
            {
                "periodo": "202203",
                "nat_bc_cred": "03",
                "valor": "1500,00",
                "elegivel_credito": True,
                "cod_cta": "5001",
            },
            {
                "periodo": "202203",
                "nat_bc_cred": "04",
                "valor": "200,00",
                "elegivel_credito": True,
                "cod_cta": "6001",
            },
        ],
    )

    print("Diagnóstico GAP ECD x EFD")
    print(resultado)

finally:
    db.close()