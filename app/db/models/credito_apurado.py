from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, func, DECIMAL, CHAR

from app.db.models.base import Base

class CreditoApurado(Base):
    __tablename__ = "credito_apurado"

    id = Column(Integer, primary_key=True)

    empresa_id = Column(Integer, ForeignKey("empresa.id"), nullable=False)
    versao_id = Column(Integer, ForeignKey("efd_versao.id"), nullable=False)

    periodo = Column(CHAR(6), index=True)

    tipo_credito = Column(String(50), index=True)

    natureza_credito = Column(String(10))
    cst_pis = Column(String(5))
    cst_cofins = Column(String(5))

    valor_base = Column(DECIMAL(15, 2))
    valor_pis = Column(DECIMAL(15, 2))
    valor_cofins = Column(DECIMAL(15, 2))
    valor_total = Column(DECIMAL(15, 2))

    origem = Column(String(100))

    meta = Column(JSON)

    data_calculo = Column(DateTime, default=datetime.utcnow)
