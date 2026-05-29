
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from app.db.models.base import Base


class EcdContaNaturezaEsperada(Base):
    __tablename__ = "ecd_conta_natureza_esperada"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    empresa_id = Column(BigInteger, nullable=False, index=True)
    ecd_conta_empresa_id = Column(
        BigInteger,
        ForeignKey("ecd_conta_empresa.id"),
        nullable=False,
        index=True,
    )

    cod_cta = Column(String(100), nullable=False, index=True)

    categoria_sugerida = Column(String(100), nullable=True)
    grupo_conta_sugerido = Column(String(100), nullable=True)

    natureza_codigo = Column(String(10), nullable=False)
    natureza_descricao = Column(String(255), nullable=True)

    fundamento_sugerido = Column(String(100), nullable=True)

    origem = Column(String(30), nullable=False, default="CLASSIFICADOR_ECD")
    ativo = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "ecd_conta_empresa_id",
            "natureza_codigo",
            name="uq_ecd_conta_natureza",
        ),
    )