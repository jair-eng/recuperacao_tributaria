from __future__ import annotations


from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, func
from sqlalchemy.orm import relationship

from app.db.models.base import Base


class ContextoFiscalVersao(Base):
    __tablename__ = "contexto_fiscal_versao"

    id = Column(Integer, primary_key=True, index=True)

    empresa_id = Column(Integer, ForeignKey("empresa.id"), nullable=False, index=True)
    versao_id = Column(Integer, ForeignKey("efd_versao.id"), nullable=False, index=True)

    periodo = Column(String(6), nullable=True, index=True)  # MMAAAA ou AAAAMM, decidimos depois

    dominio = Column(String(50), nullable=True, index=True)
    regime = Column(String(50), nullable=True, index=True)

    status = Column(String(30), nullable=False, default="GERADO")

    meta = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    empresa = relationship("Empresa")
    versao = relationship("EfdVersao")