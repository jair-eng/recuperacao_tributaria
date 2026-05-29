from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, UniqueConstraint, func

from app.db.models.base import Base


class EcdContaEmpresa(Base):
    __tablename__ = "ecd_conta_empresa"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    empresa_id = Column(BigInteger, nullable=False, index=True)
    arquivo_id = Column(BigInteger, nullable=True, index=True)

    periodo = Column(String(6), nullable=True, index=True)

    linha = Column(BigInteger, nullable=True)
    cod_cta = Column(String(100), nullable=False)
    nome_cta = Column(String(255), nullable=True)

    cod_nat = Column(String(20), nullable=True)
    ind_cta = Column(String(20), nullable=True)
    nivel = Column(String(20), nullable=True)
    cod_cta_sup = Column(String(100), nullable=True)

    categoria_sugerida = Column(String(100), nullable=True)
    grupo_conta_sugerido = Column(String(100), nullable=True)
    elegivel_credito_sugerido = Column(Boolean, nullable=True)

    categoria_confirmada = Column(String(100), nullable=True)
    grupo_conta_confirmado = Column(String(100), nullable=True)
    elegivel_credito_confirmado = Column(Boolean, nullable=True)

    origem = Column(String(30), nullable=False, default="ECD_I050")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "periodo",
            "cod_cta",
            name="uq_ecd_conta_empresa_periodo_cod_cta",
        ),
    )