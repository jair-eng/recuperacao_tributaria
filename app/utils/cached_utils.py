from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ItemFiscalConsolidado
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.cenarios.avaliador_cenarios import avaliar_cenarios
from app.domain.fiscal.cenarios.cenario_enriquecimento import (
    enriquecer_cenario_com_enquadramento,
)
from app.domain.fiscal.score_fiscal_services import calcular_score_fiscal_contabil


class FiscalRuntimeCache:
    def __init__(self, *, catalogo: Any):
        self.catalogo = catalogo
        self.classif_cache = {}
        self.cenario_cache = {}
        self.enquadramento_cache = {}
        self.score_cache = {}

    def classificar(self, meta: dict):
        key = self._meta_key(meta)

        if key not in self.classif_cache:
            self.classif_cache[key] = classificar_item_fiscal(
                meta=meta,
                catalogo=self.catalogo,
            )

        return self.classif_cache[key]

    def avaliar_cenario(self, meta: dict, classificacao: dict):
        key = (
            self._meta_key(meta),
            str((classificacao or {}).get("categoria") or ""),
            str((classificacao or {}).get("grupo") or ""),
            str((classificacao or {}).get("fundamento") or ""),
            str((classificacao or {}).get("nat_bc_cred") or ""),
        )

        if key not in self.cenario_cache:
            self.cenario_cache[key] = avaliar_cenarios(meta, classificacao)

        return self.cenario_cache[key]

    def enriquecer_cenario(self, db: Session, cenario: dict):
        if not cenario:
            return None

        key = self._cenario_cache_key(cenario)

        if key not in self.enquadramento_cache:
            self.enquadramento_cache[key] = enriquecer_cenario_com_enquadramento(
                db,
                cenario,
            )

        return self.enquadramento_cache[key]

    def score(self, item: ItemFiscalConsolidado):
        key = (
            str(getattr(item, "status_cruzamento", "") or ""),
            str(getattr(item, "cod_cta", "") or ""),
            str(getattr(item, "cod_cta_origem", "") or ""),
            str(getattr(item, "cfop", "") or ""),
            str(getattr(item, "ncm", "") or ""),
            str(getattr(item, "cst_pis", "") or ""),
            str(getattr(item, "cst_cofins", "") or ""),
            str(getattr(item, "dominio", "") or ""),
        )

        if key not in self.score_cache:
            self.score_cache[key] = calcular_score_fiscal_contabil(item)

        return self.score_cache[key]

    def stats(self) -> dict:
        return {
            "cache_classif": len(self.classif_cache),
            "cache_cenario": len(self.cenario_cache),
            "cache_enquadramento": len(self.enquadramento_cache),
            "cache_score": len(self.score_cache),
        }

    @staticmethod
    def _meta_key(meta: dict) -> tuple:
        return (
            str(meta.get("dominio") or ""),
            str(meta.get("origem") or ""),
            str(meta.get("status_cruzamento") or ""),
            str(meta.get("tipo_normalizacao") or ""),
            str(meta.get("cfop") or ""),
            str(meta.get("ncm") or ""),
            str(meta.get("cst_pis") or ""),
            str(meta.get("cst_cofins") or ""),
            str(meta.get("cod_item") or ""),
            str(meta.get("cod_cta") or ""),
        )

    @staticmethod
    def _cenario_cache_key(cenario: dict) -> tuple:
        fundamento0 = ""

        fundamentos = cenario.get("fundamento_legal") or []
        if fundamentos:
            fundamento0 = str(fundamentos[0] or "").strip()

        codigo = (
            cenario.get("codigo")
            or cenario.get("codigo_cenario")
            or fundamento0
            or cenario.get("cenario")
            or ""
        )

        return (
            str(codigo),
            str(cenario.get("tipo_credito") or ""),
            str(cenario.get("base_credito") or ""),
            str(cenario.get("cst_destino") or ""),
        )