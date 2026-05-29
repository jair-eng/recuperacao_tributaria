from decimal import Decimal
from app.domain.ecd.ecd_gap_service import carregar_linhas_ecd_com_natureza_real, gerar_diagnostico_gap_ecd_efd, \
    gerar_diagnostico_gap_ecd_efd_por_versao
from app.db.session import SessionLocal
from app.utils.numbers import to_decimal

db = SessionLocal()

linhas_ecd = carregar_linhas_ecd_com_natureza_real(
    db=db,
    empresa_id=1,
    periodo="202211",
)

resultado = gerar_diagnostico_gap_ecd_efd_por_versao(
    db=db,
    versao_id=4,
    periodo="202211",
    linhas_ecd_classificadas=linhas_ecd,
)

print(resultado["resumo"])
print(resultado["comparativo"])

