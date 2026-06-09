

from sqlalchemy import Column, Integer, String, Text, Boolean, Enum
from app.db.models import Base


class FiscalGrupo(Base):
    __tablename__ = "fiscal_grupo"

    id = Column(Integer, primary_key=True, index=True)

    slug = Column(String(80), nullable=False, unique=True, index=True)
    descricao = Column(String(255), nullable=False)

    tipo = Column(
        Enum("CFOP", "CST_PIS", "CST_COFINS", "CST_ICMS", "NCM", "DESC"),
        nullable=True,
    )

    ativo = Column(Boolean, nullable=False, default=True)
    ordem = Column(Integer, nullable=True, default=0)