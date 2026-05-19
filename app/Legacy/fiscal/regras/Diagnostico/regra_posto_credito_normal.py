from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional
from collections import defaultdict

from app.Legacy.fiscal.constants import DOM_POSTO
from app.Legacy.fiscal.contexto import get_fiscal_db
from app.Legacy.fiscal.dto import RegistroFiscalDTO
from app.Legacy.fiscal.ent_cat_fiscal import carregar_catalogo_fiscal
from app.Legacy.fiscal.regras.Diagnostico.base_regras import RegraBase
from app.Legacy.fiscal.regras.helpers.elegibilidade_dominio import (
    resolver_dominio_meta,
    item_elegivel_posto_credito_normal,
)
from app.Legacy.fiscal.settings_fiscais import CSTS_TRIB_NCUM, CFOPS_POSTO_COMBUSTIVEL


class RegraPostoCreditoNormalV1(RegraBase):
    codigo = "POSTO_CREDITO_NORMAL_V1"
    nome = "Possível crédito normal de PIS/COFINS em posto"
    tipo = "OPORTUNIDADE"

    # pega C170 existente, igual transportadora insumos
    alvo = "C170_INSUMO_AGG"

    CONTEXTO = "POSTO_CREDITO_NORMAL"
    MODO_CORRECAO = "C170_EXISTENTE_AUTOFIX"
    PERMITE_AUTOCORRECAO = True
    PERMITE_ACAO_MANUAL = False
    EXIGE_REVISAO_MANUAL = False

    ALIQ_PIS = Decimal("0.0165")
    ALIQ_COFINS = Decimal("0.0760")

    def aplicar(self, registro: RegistroFiscalDTO) -> Optional[Dict[str, Any]]:
        if (registro.reg or "").strip() != self.alvo:
            return None

        meta = registro.meta or {}
        dados = registro.dados or []

        dominio = resolver_dominio_meta(meta)

        if dominio != DOM_POSTO:
            return None
        if not dados or not isinstance(dados, list):
            return None

        itens = dados[1:]
        if not itens:
            return None

        db = get_fiscal_db()
        if db is None:
            return None

        empresa_id = meta.get("empresa_id") or getattr(registro, "empresa_id", None)
        catalogo = carregar_catalogo_fiscal(db, empresa_id=empresa_id)
        if not catalogo:
            return None

        itens_evidenciados = []
        base_total = Decimal("0")
        pis_total = Decimal("0")
        cofins_total = Decimal("0")

        resumo_por_ncm = defaultdict(lambda: Decimal("0"))
        resumo_por_situacao = defaultdict(lambda: Decimal("0"))

        for it in itens:
            if not isinstance(it, dict):
                continue

            ncm = str(it.get("ncm") or "").strip()
            cfop = str(it.get("cfop") or "").strip()
            cod_item = str(it.get("cod_item") or "").strip()
            descricao = str(it.get("descricao") or it.get("descr_item") or "").strip()

            cst_pis = str(it.get("cst_pis") or "").strip()
            cst_cofins = str(it.get("cst_cofins") or "").strip()

            vl_item = self.dec_br(it.get("vl_item")) or Decimal("0")
            vl_desc = self.dec_br(it.get("vl_desc")) or Decimal("0")
            vl_icms = self.dec_br(it.get("vl_icms")) or Decimal("0")

            vl_bc_pis = self.dec_br(it.get("vl_bc_pis")) or Decimal("0")
            vl_pis = self.dec_br(it.get("vl_pis")) or Decimal("0")
            vl_bc_cofins = self.dec_br(it.get("vl_bc_cofins")) or Decimal("0")
            vl_cofins = self.dec_br(it.get("vl_cofins")) or Decimal("0")

            base_credito = vl_item - vl_desc - vl_icms
            if base_credito <= 0:
                continue

            if cod_item in {"71", "302"}:
                print("[DBG POSTO ITEM]", {
                    "cod_item": cod_item,
                    "ncm": ncm,
                    "cfop": cfop,
                    "cst_pis": cst_pis,
                    "cst_cofins": cst_cofins,
                    "vl_item": str(vl_item),
                    "vl_bc_pis": str(vl_bc_pis),
                    "vl_pis": str(vl_pis),
                    "vl_bc_cofins": str(vl_bc_cofins),
                    "vl_cofins": str(vl_cofins),
                    "elegivel": item_elegivel_posto_credito_normal(it, catalogo=catalogo),
                }, flush=True)

            if not item_elegivel_posto_credito_normal(it, catalogo=catalogo):
                continue

            if cfop not in CFOPS_POSTO_COMBUSTIVEL:
                continue

            situacoes_credito = []

            cst_creditavel = (
                    cst_pis in CSTS_TRIB_NCUM
                    and cst_cofins in CSTS_TRIB_NCUM
            )

            if not cst_creditavel:
                situacoes_credito.append("CST_NAO_CREDITAVEL")
            elif vl_bc_pis <= 0 or vl_bc_cofins <= 0:
                situacoes_credito.append("BASE_ZERADA")
            elif vl_pis <= 0 or vl_cofins <= 0:
                situacoes_credito.append("CREDITO_NAO_APROVEITADO")
            if not situacoes_credito:
                continue

            pis_estimado = (base_credito * self.ALIQ_PIS).quantize(Decimal("0.01"))
            cofins_estimado = (base_credito * self.ALIQ_COFINS).quantize(Decimal("0.01"))
            impacto_item = pis_estimado + cofins_estimado

            base_total += base_credito
            pis_total += pis_estimado
            cofins_total += cofins_estimado

            resumo_por_ncm[ncm or "SEM_NCM"] += base_credito
            resumo_por_situacao[situacoes_credito[0]] += base_credito

            registro_id_c170 = int(it.get("registro_id") or 0)
            registro_id_c100 = int(it.get("pai_id") or 0)

            itens_evidenciados.append({
                "registro_id": registro_id_c170,
                "registro_id_c170": registro_id_c170,
                "registro_id_c100": registro_id_c100,
                "pai_id": registro_id_c100,
                "linha": it.get("linha"),

                "cod_item": cod_item,
                "ncm": ncm,
                "cfop": cfop,
                "descricao": descricao[:120],

                "cst_pis_atual": cst_pis,
                "cst_cofins_atual": cst_cofins,
                "cst_pis_sugerido": "50",
                "cst_cofins_sugerido": "50",

                "vl_item": str(vl_item),
                "vl_desc": str(vl_desc),
                "vl_icms": str(vl_icms),
                "vl_bc_pis_atual": str(vl_bc_pis),
                "vl_pis_atual": str(vl_pis),
                "vl_bc_cofins_atual": str(vl_bc_cofins),
                "vl_cofins_atual": str(vl_cofins),

                "base_credito_sugerida": str(base_credito),
                "aliq_pis_sugerida": "1,65",
                "aliq_cofins_sugerida": "7,60",
                "pis_estimado": str(pis_estimado),
                "cofins_estimado": str(cofins_estimado),
                "impacto_estimado": str(impacto_item),

                "situacao_credito": situacoes_credito,
                "situacao_credito_principal": situacoes_credito[0],
                "contexto": self.CONTEXTO,

                # pronto para autofix futuro
                "permite_editar_c170_existente": True,
                "permite_inserir_c170": False,
                "permite_inserir_c100": False,
            })

        if not itens_evidenciados or base_total <= 0:
            return None

        impacto_total = pis_total + cofins_total
        prioridade = "ALTA" if impacto_total >= Decimal("1000") else "MEDIA"

        desc = (
            f"Itens de posto com possível crédito normal de PIS/COFINS não aproveitado: "
            f"{len(itens_evidenciados)} item(ns). "
            f"Base estimada: R$ {self.fmt_br(base_total)}. "
            f"Crédito estimado: R$ {self.fmt_br(impacto_total)}."
        )


        return {
            "tipo": self.tipo,
            "codigo": self.codigo,
            "regra": self.nome,
            "descricao": desc,
            "impacto_financeiro": float(impacto_total),
            "prioridade": prioridade,
            "registro_id": itens_evidenciados[0]["registro_id_c170"],
            "meta": {
                "contexto": self.CONTEXTO,
                "executor_fluxo": "POSTO_CREDITO_NORMAL",
                "executor_contexto": {
                    "origem_execucao": "C170_EXISTENTE",
                    "permite_editar_c170_existente": True,
                    "permite_inserir_c170": False,
                    "permite_inserir_c100": False,
                },

                "qtd_itens": len(itens_evidenciados),
                "base_total": str(base_total),
                "pis_estimado": str(pis_total),
                "cofins_estimado": str(cofins_total),
                "impacto_estimado": str(impacto_total),

                "cst_pis_sugerido": "50",
                "cst_cofins_sugerido": "50",
                "aliq_pis_sugerida": "1.65",
                "aliq_cofins_sugerida": "7.60",

                "itens": itens_evidenciados[:50],
                "resumo_por_ncm": {
                    k: str(v.quantize(Decimal("0.01")))
                    for k, v in resumo_por_ncm.items()
                },
                "resumo_por_situacao": {
                    k: str(v.quantize(Decimal("0.01")))
                    for k, v in resumo_por_situacao.items()
                },

                "permite_acao_manual": False,
                "permite_correcao_c170": True,
                "permite_autocorrecao": self.PERMITE_AUTOCORRECAO,
                "permite_auto_fix": self.PERMITE_AUTOCORRECAO,
                "exige_revisao_manual": False,
                "modo_correcao": "C170_EXISTENTE_AUTOFIX",
                "fonte_base": "C170_INSUMO_AGG",
            },
        }