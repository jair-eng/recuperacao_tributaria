
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from app.db.models.base import Base

class FiscalGrupoItem(Base):
    __tablename__ = "fiscal_grupo_item"

    id = Column(Integer, primary_key=True, index=True)

    grupo_id = Column(
        Integer,
        ForeignKey("fiscal_grupo.id"),
        nullable=False,
        index=True,
    )

    codigo = Column(String(10), nullable=False, index=True)
    descricao = Column(String(255))

    ativo = Column(Boolean, nullable=False, default=True)

    empresa_id = Column(Integer, nullable=True, index=True)

    peso = Column(Integer, default=0)

    vig_ini = Column(Date, nullable=True)
    vig_fim = Column(Date, nullable=True)

    grupo = relationship("FiscalGrupo")