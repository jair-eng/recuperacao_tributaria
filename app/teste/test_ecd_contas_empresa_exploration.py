from app.db.session import SessionLocal
from app.db.models.ecd_conta_empresa import EcdContaEmpresa


EMPRESA_ID = 1
PERIODO = "202201"


db = SessionLocal()

try:
    contas = (
        db.query(EcdContaEmpresa)
        .filter(EcdContaEmpresa.empresa_id == EMPRESA_ID)
        .filter(EcdContaEmpresa.periodo == PERIODO)
        .filter(EcdContaEmpresa.elegivel_credito_sugerido == True)
        .order_by(EcdContaEmpresa.cod_cta.asc())
        .all()
    )

    print("TOTAL AMOSTRA:", len(contas))
    print("=" * 120)

    for c in contas:
        elegivel = (
            c.elegivel_credito_confirmado
            if c.elegivel_credito_confirmado is not None
            else c.elegivel_credito_sugerido
        )

        categoria = c.categoria_confirmada or c.categoria_sugerida
        grupo = c.grupo_conta_confirmado or c.grupo_conta_sugerido

        print("ID:", c.id)
        print("PERIODO:", c.periodo)
        print("COD_CTA:", c.cod_cta)
        print("NOME:", c.nome_cta)
        print("CATEGORIA:", categoria)
        print("GRUPO:", grupo)
        print("ELEGIVEL:", elegivel)
        print("SUG:", c.categoria_sugerida, "|", c.grupo_conta_sugerido, "|", c.elegivel_credito_sugerido)
        print("CONF:", c.categoria_confirmada, "|", c.grupo_conta_confirmado, "|", c.elegivel_credito_confirmado)
        print("-" * 120)

finally:
    db.close()