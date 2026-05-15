from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional, Dict, Any

from app.fiscal.constants import DOM_AGRO, DOM_CAFE
from app.fiscal.dto import RegistroFiscalDTO
from app.fiscal.regras.Diagnostico.base_regras import RegraBase

logger = logging.getLogger(__name__)


class RegraC170CfopSemCreditoV1(RegraBase):
    """
    Regra geral:
    - Se CFOP estiver em grupo sem direito a crédito
    - E CST PIS/COFINS estiver em grupo de CST creditável
    => gera apontamento

    Mensagem:
      "CFOP sem direito a crédito com CST creditável.
       Favor verificar o CST adequado para operação sem crédito."
    """

    codigo = "C170_CFOP_SEM_CREDITO_V1"
    tipo = "ERRO"
    prioridade = "ALTA"
    nome = "CFOP sem direito a crédito com CST creditável"

    CAT_CFOP_SEM_CREDITO = "CFOP_SEM_DIREITO_CREDITO"
    CAT_CST_CREDITO_NCUM = "CST_PIS_CREDITO_NCUM"
    CAT_CST_CREDITO_PRES = "CST_PIS_CREDITO_PRESUMIDO"

    def aplicar(self, registro: RegistroFiscalDTO) -> Optional[Dict[str, Any]]:
        try:
            if getattr(registro, "is_pf", False):
                return None

            meta = registro.meta if isinstance(registro.meta, dict) else {}
            dom = (meta.get("dominio") or "").strip().upper()

            if dom not in {DOM_CAFE, DOM_AGRO}:
                return None

            if (registro.reg or "").strip().upper() != "C170":
                return None

            dados = registro.dados or []
            if not isinstance(dados, list) or not dados:
                return None

            # Layout C170 do projeto
            num_item = str(dados[0]).strip() if len(dados) > 0 else ""
            cod_item = str(dados[1]).strip() if len(dados) > 1 else ""
            descricao = str(dados[2]).strip() if len(dados) > 2 else ""
            cfop = str(dados[9]).strip() if len(dados) > 9 else ""

            cst_pis = str(dados[23]).strip() if len(dados) > 23 else ""
            vl_bc_pis = self.dec_br(dados[24]) if len(dados) > 24 else Decimal("0")
            vl_pis = self.dec_br(dados[27]) if len(dados) > 27 else Decimal("0")

            cst_cofins = str(dados[29]).strip() if len(dados) > 29 else ""
            vl_bc_cofins = self.dec_br(dados[30]) if len(dados) > 30 else Decimal("0")
            vl_cofins = self.dec_br(dados[33]) if len(dados) > 33 else Decimal("0")

            vl_item = self.dec_br(dados[5]) if len(dados) > 5 else Decimal("0")

            if not cfop:
                return None

            try:
                cat = self.get_catalogo(registro)
            except Exception:
                logger.exception("C170_CFOP_SEM_CREDITO_V1: falha ao carregar catálogo")
                return None

            if not cat:
                return None

            cfop_sem_credito = self.cfop_match(cat, self.CAT_CFOP_SEM_CREDITO, cfop)
            if not cfop_sem_credito:
                return None

            cst_pis_creditavel = (
                self.cst_match(cat, self.CAT_CST_CREDITO_NCUM, cst_pis)
                or self.cst_match(cat, self.CAT_CST_CREDITO_PRES, cst_pis)
            ) if cst_pis else False

            cst_cofins_creditavel = (
                self.cst_match(cat, self.CAT_CST_CREDITO_NCUM, cst_cofins)
                or self.cst_match(cat, self.CAT_CST_CREDITO_PRES, cst_cofins)
            ) if cst_cofins else False

            if not (cst_pis_creditavel or cst_cofins_creditavel):
                return None

            rid = int(getattr(registro, "id", 0) or 0)
            anchor_rid = (registro.meta or {}).get("anchor_registro_id") if isinstance(registro.meta, dict) else None
            try:
                anchor_rid = int(anchor_rid) if anchor_rid is not None else None
            except Exception:
                anchor_rid = None

            registro_id_final = rid if rid > 0 else (anchor_rid or 0)
            if not registro_id_final:
                return None

            impacto = (vl_pis or Decimal("0")) + (vl_cofins or Decimal("0"))

            desc = (
                "CFOP sem direito a crédito com CST creditável. "
                "Favor verificar o CST adequado para operação sem crédito."
            )

            meta: Dict[str, Any] = dict(registro.meta or {}) if isinstance(registro.meta, dict) else {}
            meta.update({
                "fonte_base": "C170",
                "cfop": cfop,
                "num_item": num_item,
                "cod_item": cod_item,
                "descricao_item": descricao,
                "cst_pis": cst_pis,
                "cst_cofins": cst_cofins,
                "cst_pis_creditavel": bool(cst_pis_creditavel),
                "cst_cofins_creditavel": bool(cst_cofins_creditavel),
                "vl_item": str(vl_item),
                "vl_bc_pis": str(vl_bc_pis or Decimal("0")),
                "vl_pis": str(vl_pis or Decimal("0")),
                "vl_bc_cofins": str(vl_bc_cofins or Decimal("0")),
                "vl_cofins": str(vl_cofins or Decimal("0")),
                "cat_cfop_sem_credito": self.CAT_CFOP_SEM_CREDITO,
                "cat_cst_credito_ncum": self.CAT_CST_CREDITO_NCUM,
                "cat_cst_credito_pres": self.CAT_CST_CREDITO_PRES,
            })

            return {
                "registro_id": int(registro_id_final),
                "tipo": self.tipo,
                "codigo": self.codigo,
                "descricao": desc,
                "impacto_financeiro": impacto,
                "prioridade": self.prioridade,
                "meta": meta,
                "regra": self.nome,
            }

        except Exception:
            logger.exception("Erro na regra %s", getattr(self, "codigo", "C170_CFOP_SEM_CREDITO_V1"))
            return None