from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    ForeignKey,
    Numeric,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from app.db.models.base import Base



class EcdArquivo(Base):
    __tablename__ = "ecd_arquivo"

    id = Column(Integer, primary_key=True, autoincrement=True)

    empresa_id = Column(Integer, ForeignKey("empresa.id"), nullable=False, index=True)
    periodo_inicio = Column(String(8), nullable=True)
    periodo_fim = Column(String(8), nullable=True)
    ano = Column(String(4), nullable=True, index=True)

    nome_arquivo = Column(String(255), nullable=True)
    cnpj = Column(String(20), nullable=True, index=True)
    nome_empresa = Column(String(255), nullable=True)

    total_linhas = Column(Integer, nullable=False, default=0)
    criado_em = Column(DateTime, server_default=func.now())

    contas = relationship("EcdContaI050Db", cascade="all, delete-orphan")
    vinculos = relationship("EcdVinculoI052Db", cascade="all, delete-orphan")
    saldos = relationship("EcdSaldoI155Db", cascade="all, delete-orphan")
    resultados = relationship("EcdResultadoI355Db", cascade="all, delete-orphan")
    dres = relationship("EcdDreJ150Db", cascade="all, delete-orphan")


class EcdContaI050Db(Base):
    __tablename__ = "ecd_conta_i050"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ecd_arquivo_id = Column(Integer, ForeignKey("ecd_arquivo.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresa.id"), nullable=False, index=True)

    linha = Column(Integer, nullable=False)
    dt_alt = Column(String(8), nullable=True)
    cod_nat = Column(String(10), nullable=True)
    ind_cta = Column(String(5), nullable=True)
    nivel = Column(String(10), nullable=True)
    cod_cta = Column(String(60), nullable=False, index=True)
    cod_cta_sup = Column(String(60), nullable=True)
    cta = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_ecd_i050_empresa_cod_cta", "empresa_id", "cod_cta"),
    )


class EcdVinculoI052Db(Base):
    __tablename__ = "ecd_vinculo_i052"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ecd_arquivo_id = Column(Integer, ForeignKey("ecd_arquivo.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresa.id"), nullable=False, index=True)

    linha = Column(Integer, nullable=False)
    cod_cta_i050 = Column(String(60), nullable=False, index=True)
    cod_ccus = Column(String(60), nullable=True)
    cod_agl = Column(String(60), nullable=True, index=True)


class EcdSaldoI155Db(Base):
    __tablename__ = "ecd_saldo_i155"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ecd_arquivo_id = Column(Integer, ForeignKey("ecd_arquivo.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresa.id"), nullable=False, index=True)

    linha = Column(Integer, nullable=False)
    dt_ini = Column(String(8), nullable=True, index=True)
    dt_fin = Column(String(8), nullable=True, index=True)
    cod_cta = Column(String(60), nullable=False, index=True)
    cod_ccus = Column(String(60), nullable=True)

    vl_sld_ini = Column(Numeric(18, 2), nullable=True)
    ind_dc_ini = Column(String(1), nullable=True)
    vl_deb = Column(Numeric(18, 2), nullable=True)
    vl_cred = Column(Numeric(18, 2), nullable=True)
    vl_sld_fin = Column(Numeric(18, 2), nullable=True)
    ind_dc_fin = Column(String(1), nullable=True)

    __table_args__ = (
        Index("ix_ecd_i155_empresa_periodo_conta", "empresa_id", "dt_ini", "dt_fin", "cod_cta"),
    )


class EcdResultadoI355Db(Base):
    __tablename__ = "ecd_resultado_i355"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ecd_arquivo_id = Column(Integer, ForeignKey("ecd_arquivo.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresa.id"), nullable=False, index=True)

    linha = Column(Integer, nullable=False)
    dt_res = Column(String(8), nullable=True, index=True)
    cod_cta = Column(String(60), nullable=False, index=True)
    cod_ccus = Column(String(60), nullable=True)
    vl_cta = Column(Numeric(18, 2), nullable=True)
    ind_dc = Column(String(1), nullable=True)


class EcdDreJ150Db(Base):
    __tablename__ = "ecd_dre_j150"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ecd_arquivo_id = Column(Integer, ForeignKey("ecd_arquivo.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresa.id"), nullable=False, index=True)

    linha = Column(Integer, nullable=False)
    dt_ini = Column(String(8), nullable=True, index=True)
    dt_fin = Column(String(8), nullable=True, index=True)

    nu_ordem = Column(String(30), nullable=True)
    cod_agl = Column(String(60), nullable=True, index=True)
    ind_cod_agl = Column(String(5), nullable=True)
    nivel_agl = Column(String(10), nullable=True)
    cod_agl_sup = Column(String(60), nullable=True)
    descr_cod_agl = Column(String(255), nullable=True)

    vl_cta = Column(Numeric(18, 2), nullable=True)
    ind_vl = Column(String(1), nullable=True)
    vl_cta_ult_dre = Column(Numeric(18, 2), nullable=True)
    ind_vl_ult_dre = Column(String(1), nullable=True)
    ind_grp_dre = Column(String(5), nullable=True)
    nota_exp_ref = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_ecd_j150_empresa_periodo_agl", "empresa_id", "dt_ini", "dt_fin", "cod_agl"),
    )