from sqlalchemy import Column, Integer, String, ForeignKey, Numeric, Boolean, JSON, DateTime, func
from sqlalchemy import BigInteger
from sqlalchemy.orm import relationship

from app.db.models.base import Base


class ItemFiscalConsolidado(Base):
    __tablename__ = "item_fiscal_consolidado"

    id = Column(Integer, primary_key=True, index=True)

    contexto_id = Column(Integer, ForeignKey("contexto_fiscal_versao.id"), nullable=False, index=True)

    empresa_id = Column(Integer, ForeignKey("empresa.id"), nullable=False, index=True)
    versao_id = Column(Integer, ForeignKey("efd_versao.id"), nullable=False, index=True)

    periodo = Column(String(6), nullable=True, index=True)

    registro_id_c100 = Column(BigInteger, ForeignKey("efd_registro.id"), nullable=True, index=True)
    registro_id_c170 = Column(BigInteger, ForeignKey("efd_registro.id"), nullable=True, index=True)
    nf_icms_base_id = Column(BigInteger, ForeignKey("nf_icms_base.id"), nullable=True, index=True)
    nf_icms_item_id = Column(BigInteger, ForeignKey("nf_icms_item.id"), nullable=True, index=True)

    chave_nfe = Column(String(60), nullable=True, index=True)
    cod_mod = Column(String(5), nullable=True, index=True)
    num_doc = Column(String(30), nullable=True, index=True)
    serie = Column(String(20), nullable=True)
    dt_doc = Column(String(20), nullable=True)

    cod_part = Column(String(100), nullable=True, index=True)
    participante_nome = Column(String(255), nullable=True)
    participante_doc = Column(String(20), nullable=True, index=True)
    participante_tipo_doc = Column(String(10), nullable=True, index=True)

    num_item = Column(String(20), nullable=True)
    cod_item = Column(String(100), nullable=True, index=True)
    descr_item = Column(String(500), nullable=True)
    qtd = Column(Numeric(18, 4), nullable=True)
    unidade = Column(String(20), nullable=True)
    ncm = Column(String(20), nullable=True, index=True)

    cfop = Column(String(10), nullable=True, index=True)
    cst_pis = Column(String(5), nullable=True, index=True)
    cst_cofins = Column(String(5), nullable=True, index=True)
    cst_icms = Column(String(5), nullable=True, index=True)
    cod_cta = Column(String(100), nullable=True, index=True)

    vl_item = Column(Numeric(18, 2), nullable=True)
    vl_desc = Column(Numeric(18, 2), nullable=True)
    vl_icms = Column(Numeric(18, 2), nullable=True)
    vl_ipi = Column(Numeric(18, 2), nullable=True)
    vl_bc_pis = Column(Numeric(18, 2), nullable=True)
    vl_pis = Column(Numeric(18, 2), nullable=True)
    vl_bc_cofins = Column(Numeric(18, 2), nullable=True)
    vl_cofins = Column(Numeric(18, 2), nullable=True)

    tem_no_contrib = Column(Boolean, nullable=False, default=False, index=True)
    tem_no_icms = Column(Boolean, nullable=False, default=False, index=True)
    status_cruzamento = Column(String(50), nullable=True, index=True)
    tipo_match = Column(String(50), nullable=True)

    dominio = Column(String(50), nullable=True, index=True)
    regime = Column(String(50), nullable=True, index=True)

    categoria_catalogo = Column(String(100), nullable=True, index=True)
    familias_catalogo = Column(JSON, nullable=True)

    conta_nome = Column(String(255), nullable=True)
    conta_grupo = Column(String(100), nullable=True)
    categoria_ecd = Column(String(100), nullable=True)

    meta = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    contexto = relationship("ContextoFiscalVersao")
    empresa = relationship("Empresa")
    versao = relationship("EfdVersao")