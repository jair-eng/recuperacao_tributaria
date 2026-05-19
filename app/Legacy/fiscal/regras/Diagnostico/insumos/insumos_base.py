from __future__ import annotations
from typing import Optional, Any, Dict
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import logging

from app.Legacy.fiscal.dto import RegistroFiscalDTO
from app.Legacy.fiscal.regras.Diagnostico.base_regras import RegraBase

logger = logging.getLogger(__name__)


class RegraC170InsumosBase(RegraBase):
    nome = "Possível crédito por insumo (C170) — base"
    tipo = "OPORTUNIDADE"
    alvo = "C170_INSUMO_AGG"

    DEBUG_SAMPLE_IDS = 40

    # subclasses definem
    codigo = "C170_INSUMO_BASE"
    SLUG_CFOP_ENTRADA = ""
    SLUG_CST_PIS_ALVO_CRED = ""
    SLUG_CST_COF_ALVO_CRED = ""
    SLUG_CST_PIS_SEM_CRED = ""
    SLUG_CST_COF_SEM_CRED = ""

    def aplicar(self, registro: RegistroFiscalDTO) -> Optional[Dict[str, Any]]:
        try:
            if not self._registro_valido(registro):
                return None

            dados = registro.dados or []
            meta0 = self._extrair_meta(dados)
            itens = dados[1:] if len(dados) > 1 else []
            if not itens:
                return None

            cat = self.get_catalogo(registro)
            if not cat:
                return None

            acc = self._init_acc()

            for it in itens:
                if not isinstance(it, dict):
                    continue

                acc["qtd_total"] += 1

                # blindagem defensiva
                if self._bloqueado_guard_rails(it, meta0):
                    continue

                if not self._item_contexto_ok(cat, it):
                    continue

                base_liquida = self._calcular_base_liquida(it)
                if base_liquida <= 0:
                    continue

                self._acumular_item(acc, it, base_liquida)

            if acc["qtd_candidatos"] <= 0 or acc["base_total"] <= 0:
                return None

            prioridade = self._definir_prioridade(cat, acc, meta0)
            desc = self._montar_descricao(acc)
            registro_id_final = self._resolver_anchor(registro, meta0)

            if not registro_id_final:
                return None

            meta_out = self._montar_meta_saida(acc, meta0)

            return {
                "tipo": self.tipo,
                "codigo": self.codigo,
                "regra": getattr(self, "nome", self.__class__.__name__),
                "prioridade": prioridade,
                "descricao": desc,
                "impacto_financeiro": None,
                "registro_id": int(registro_id_final),
                "meta": meta_out,
            }

        except Exception as e:
            logger.exception(
                "ERRO %s | reg=%s id=%s linha=%s empresa_id=%s versao_id=%s | %s",
                self.__class__.__name__,
                getattr(registro, "reg", None),
                getattr(registro, "id", None),
                getattr(registro, "linha", None),
                getattr(registro, "empresa_id", None),
                getattr(registro, "versao_id", None),
                str(e),
            )
            return None

    def _registro_valido(self, registro: RegistroFiscalDTO) -> bool:
        return (registro.reg or "").strip() == self.alvo

    def _extrair_meta(self, dados: list) -> dict:
        if dados and isinstance(dados[0], dict) and "_meta" in dados[0]:
            return dados[0].get("_meta") or {}
        return {}

    def _bloqueado_guard_rails(self, item: dict, meta0: dict) -> bool:
        cod_sit = str(item.get("cod_sit") or meta0.get("cod_sit") or "").strip()
        if cod_sit in {"06", "07"}:
            return True

        participante_pf = item.get("participante_pf")
        if participante_pf is True:
            return True

        doc = str(item.get("cpf_cnpj_participante") or meta0.get("cpf_cnpj_participante") or "")
        doc = "".join(ch for ch in doc if ch.isdigit())
        if len(doc) == 11:
            return True

        return False

    def _item_contexto_ok(self, cat, it: dict) -> bool:
        cfop = str(it.get("cfop") or "").strip()
        cst_pis = str(it.get("cst_pis") or "").strip()
        cst_cof = str(it.get("cst_cofins") or "").strip()

        if not cfop:
            return False

        cfop_ok = self.cfop_match(cat, self.SLUG_CFOP_ENTRADA, cfop)
        if not cfop_ok:
            return False

        pis_ja_credito = self.cst_match(cat, self.SLUG_CST_PIS_ALVO_CRED, cst_pis) if cst_pis else False
        cof_ja_credito = self.cst_match(cat, self.SLUG_CST_COF_ALVO_CRED, cst_cof) if cst_cof else False
        if pis_ja_credito or cof_ja_credito:
            return False

        return True

    def _calcular_base_liquida(self, it: dict) -> Decimal:
        vl_item = self.dec_br(it.get("vl_item")) or Decimal("0")
        vl_desc = self.dec_br(it.get("vl_desc")) or Decimal("0")
        vl_icms = self.dec_br(it.get("vl_icms")) or Decimal("0")
        return vl_item - vl_desc - vl_icms

    def _init_acc(self) -> dict:
        return {
            "base_total": Decimal("0"),
            "qtd_total": 0,
            "qtd_candidatos": 0,
            "base_por_cfop": defaultdict(lambda: Decimal("0")),
            "base_por_ncm": defaultdict(lambda: Decimal("0")),
            "csts_pis": defaultdict(int),
            "csts_cof": defaultdict(int),
            "sample_registro_ids": [],
        }

    def _acumular_item(self, acc: dict, it: dict, base_liquida: Decimal) -> None:
        cfop = str(it.get("cfop") or "").strip()
        cst_pis = str(it.get("cst_pis") or "").strip()
        cst_cof = str(it.get("cst_cofins") or "").strip()
        ncm = str(it.get("ncm") or "").strip()
        rid = int(it.get("registro_id") or 0)

        acc["qtd_candidatos"] += 1
        acc["base_total"] += base_liquida
        acc["base_por_cfop"][cfop] += base_liquida

        if ncm:
            acc["base_por_ncm"][ncm] += base_liquida
        if cst_pis:
            acc["csts_pis"][cst_pis] += 1
        if cst_cof:
            acc["csts_cof"][cst_cof] += 1
        if rid > 0 and len(acc["sample_registro_ids"]) < self.DEBUG_SAMPLE_IDS:
            acc["sample_registro_ids"].append(rid)

    def _definir_prioridade(self, cat, acc: dict, meta0: dict) -> str:
        return "MEDIA"

    def _resolver_anchor(self, registro: RegistroFiscalDTO, meta0: dict) -> int:
        anchor_registro_id = int(meta0.get("anchor_registro_id") or 0) if isinstance(meta0, dict) else 0
        return int(getattr(registro, "id", 0) or 0) or anchor_registro_id

    def _montar_descricao(self, acc: dict) -> str:
        q2 = lambda x: (x or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        base_total = q2(acc["base_total"])

        top_cfops = [c for c, _ in sorted(acc["base_por_cfop"].items(), key=lambda kv: kv[1], reverse=True)[:5]]
        top_ncms = [n for n, _ in sorted(acc["base_por_ncm"].items(), key=lambda kv: kv[1], reverse=True)[:5]]
        top_cst_pis = [c for c, _ in sorted(acc["csts_pis"].items(), key=lambda kv: kv[1], reverse=True)[:5]]
        top_cst_cof = [c for c, _ in sorted(acc["csts_cof"].items(), key=lambda kv: kv[1], reverse=True)[:5]]

        return (
            f"Possível crédito por insumo (agrupado): {acc['qtd_candidatos']} item(ns) candidato(s). "
            f"Base líquida (VL_ITEM - VL_DESC - VL_ICMS) ≈ R$ {self.fmt_br(base_total)}. "
            f"CFOP(s) top: {', '.join(top_cfops) or 'N/D'}. "
            f"NCM(s) top: {', '.join(top_ncms) or 'N/D'}. "
            f"CST PIS top: {', '.join(top_cst_pis) or 'N/D'}, "
            f"CST COFINS top: {', '.join(top_cst_cof) or 'N/D'}. "
            "Revisar natureza do item e enquadramento."
        )

    def _montar_meta_saida(self, acc: dict, meta0: dict) -> dict:
        q2 = lambda x: (x or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        base_total = q2(acc["base_total"])

        top_cfops = [c for c, _ in sorted(acc["base_por_cfop"].items(), key=lambda kv: kv[1], reverse=True)[:5]]
        top_ncms = [n for n, _ in sorted(acc["base_por_ncm"].items(), key=lambda kv: kv[1], reverse=True)[:5]]
        top_cst_pis = [c for c, _ in sorted(acc["csts_pis"].items(), key=lambda kv: kv[1], reverse=True)[:5]]
        top_cst_cof = [c for c, _ in sorted(acc["csts_cof"].items(), key=lambda kv: kv[1], reverse=True)[:5]]

        meta_out = dict(meta0) if isinstance(meta0, dict) else {}
        meta_out.update({
            "fonte_base": self.alvo,
            "qtd_total_itens": int(acc["qtd_total"]),
            "qtd_candidatos": int(acc["qtd_candidatos"]),
            "base_total_liquida": str(base_total),
            "top_cfops": top_cfops,
            "top_ncms": top_ncms,
            "top_cst_pis": top_cst_pis,
            "top_cst_cofins": top_cst_cof,
            "sample_registro_ids": acc["sample_registro_ids"],
            "criterio_base": "VL_ITEM - VL_DESC - VL_ICMS",
        })
        return meta_out