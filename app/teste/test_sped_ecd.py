from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.models import EcdResultadoI355Db
from app.db.models.ecd_conta_empresa import EcdContaEmpresa
from app.domain.ecd.ecd_gap_service import carregar_linhas_ecd_elegiveis_reais
from app.db.session import SessionLocal

db = SessionLocal()
dados = carregar_linhas_ecd_elegiveis_reais(
    db=db,
    empresa_id=1,
    periodo="202211",
)

print(f"TOTAL: {len(dados)}")

for d in dados[:20]:
    print(d)

contas = (
    db.query(EcdContaEmpresa)
    .filter(EcdContaEmpresa.empresa_id == 1)
    .filter(EcdContaEmpresa.periodo.like("2022%"))
    .filter(
        or_(
            EcdContaEmpresa.elegivel_credito_sugerido == True,
            EcdContaEmpresa.elegivel_credito_confirmado == True,
        )
    )
    .all()
)

print("CONTAS ELEGIVEIS EMPRESA 1:", len(contas))

for c in contas:
    print(c.cod_cta, c.nome_cta, c.grupo_conta_sugerido)

linha = db.query(EcdResultadoI355Db).first()

if linha:
    print(linha.__dict__)
else:
    print("SEM REGISTROS")