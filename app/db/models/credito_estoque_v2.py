from __future__ import annotations
from sqlalchemy import UniqueConstraint
from datetime import datetime
from decimal import Decimal
from app.db.models.base import Base
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    CHAR,
    Numeric,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship




class CreditoEstoqueV2(Base):
    __tablename__ = "credito_estoque_v2"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresa.id"),
        nullable=False,
        index=True,
    )

    versao_exportada_id: Mapped[int] = mapped_column(
        ForeignKey("efd_versao.id"),
        nullable=False,
        index=True,
    )

    # competência onde nasceu o crédito (YYYYMM)
    periodo_origem: Mapped[str] = mapped_column(
        CHAR(6),
        nullable=False,
        index=True,
    )

    # primeiro mês em que começa a aparecer no 1100/1500
    periodo_escrituracao: Mapped[str] = mapped_column(
        CHAR(6),
        nullable=False,
        index=True,
    )

    # último mês já processado pelo motor (futuro)
    ultimo_periodo_processado: Mapped[str | None] = mapped_column(
        CHAR(6),
        nullable=True,
    )

    cod_cred: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="101",
        index=True,
    )

    orig_cred: Mapped[str] = mapped_column(
        CHAR(2),
        nullable=False,
        default="01",
    )

    valor_original_pis: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    valor_original_cofins: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    valor_utilizado_pis: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    valor_utilizado_cofins: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    saldo_pis: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    saldo_cofins: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ABERTO",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    empresa = relationship("Empresa")
    versao_exportada = relationship("EfdVersao")

    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "periodo_origem",
            "cod_cred",
            name="uq_credito_v2",
        ),
    )