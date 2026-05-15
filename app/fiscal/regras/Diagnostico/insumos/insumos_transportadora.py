from decimal import Decimal
from typing import Optional, Dict, Any
from collections import defaultdict

from app.fiscal.contexto import get_fiscal_db
from app.fiscal.dto import RegistroFiscalDTO
from app.fiscal.ent_cat_fiscal import carregar_catalogo_fiscal
from app.fiscal.regras.Diagnostico.base_regras import RegraBase
from app.fiscal.regras.Diagnostico.insumos.insumos_helpers import classificar_item_transp
from app.fiscal.regras.Diagnostico.insumos.transp_combustivel_helper import bypassar_combustivel_manual_por_lc192
from app.fiscal.settings_fiscais import CSTS_TRIB_NCUM


class _BaseRegraC170Transportadora(RegraBase):
    alvo = "C170_INSUMO_AGG"

    # cada filha sobrescreve
    BUCKETS_ALVO: set[str] = set()
    MODO_CORRECAO = "FLUXO_NORMAL"
    PERMITE_AUTOCORRECAO = False
    PERMITE_ACAO_MANUAL = False
    EXIGE_REVISAO_MANUAL = True
    RISCO_FISCAL = None

    def _analisar_itens_transp(
        self,
        registro: RegistroFiscalDTO,
        *,
        buckets_alvo: set[str],
    ) -> Optional[Dict[str, Any]]:

        if (registro.reg or "").strip() != self.alvo:
            return None

        db = get_fiscal_db()
        if db is None:
            raise RuntimeError("DB não disponível no contexto fiscal.")

        meta = registro.meta or {}
        dados = registro.dados or []

        if not dados or not isinstance(dados, list):
            return None

        itens = dados[1:]
        if not itens:
            return None

        cat = self.get_catalogo(registro)
        if not cat:
            return None

        total_score = 0
        base_total = Decimal("0")
        qtd_match = 0

        itens_evidenciados = []
        resumo_por_categoria = defaultdict(lambda: Decimal("0"))
        resumo_por_tipo_insumo = defaultdict(lambda: Decimal("0"))

        for it in itens:
            if not isinstance(it, dict):
                continue

            ncm = str(it.get("ncm") or "").strip()
            desc_original = str(it.get("descricao") or "").strip()
            desc_item = desc_original.lower()
            nome_part_original = str(it.get("nome_participante") or "").strip()
            nome_part = nome_part_original.lower()

            cod_cta = str(it.get("cod_cta") or "").strip()
            origem_cod_cta = str(it.get("origem_cod_cta") or "").strip()
            cst_pis = str(it.get("cst_pis") or "").strip()
            cst_cofins = str(it.get("cst_cofins") or "").strip()

            vl_bc_pis = self.dec_br(it.get("vl_bc_pis")) or Decimal("0")
            vl_pis = self.dec_br(it.get("vl_pis")) or Decimal("0")
            vl_bc_cofins = self.dec_br(it.get("vl_bc_cofins")) or Decimal("0")
            vl_cofins = self.dec_br(it.get("vl_cofins")) or Decimal("0")

            vl_item = self.dec_br(it.get("vl_item")) or Decimal("0")
            vl_desc = self.dec_br(it.get("vl_desc")) or Decimal("0")
            vl_icms = self.dec_br(it.get("vl_icms")) or Decimal("0")

            base = vl_item - vl_desc - vl_icms
            if base <= 0:
                continue

            classificacao = classificar_item_transp(
                cat,
                ncm=ncm,
                desc_item=desc_item,
                nome_part=nome_part_original,
                cod_cta=cod_cta,
                origem_cod_cta=origem_cod_cta,
                cst_pis=cst_pis,
                cst_cofins=cst_cofins,
                cfop=str(it.get("cfop") or "").strip(),
                periodo=str(getattr(registro, "periodo", "") or ""),
                valor_icms=vl_icms,
                origem_dados="EFD",
            )

            score = int(classificacao["score"] or 0)
            bucket = classificacao["bucket"]
            print("[DBG CLASSIFICACAO COMBUSTIVEL]", {
                "descricao": desc_original,
                "ncm": ncm,
                "cfop": str(it.get("cfop") or "").strip(),
                "bucket": bucket,
                "score": score,
                "match_slug": classificacao.get("match_slug"),
                "tratamento_motor": classificacao.get("tratamento_motor"),
            })
            if bucket not in buckets_alvo:
                continue

            evidencias_item = list(classificacao["evidencias"] or [])
            subbucket = classificacao.get("subbucket")
            regime_fiscal = classificacao.get("regime_fiscal")
            tratamento_motor = str(classificacao.get("tratamento_motor") or "")
            permite_autofix_cls = bool(classificacao.get("permite_autofix"))
            flags_cls = classificacao.get("flags") or {}
            teses_aplicaveis = list(classificacao.get("teses_aplicaveis") or [])
            tem_tese = bool(flags_cls.get("tem_tese"))

            is_operacional = False
            is_capitalizavel = False
            is_sensivel = False
            elegivel_autofix = False

            if any(x in desc_item for x in [
                "retifica", "retífica",
                "reforma",
                "motor completo",
                "implemento",
                "melhoria estrutural",
                "adaptacao", "adaptação",
            ]):
                is_capitalizavel = True
                score -= 2
                evidencias_item.append(f"possivel_imobilizado:{desc_original}")

            situacoes_credito = []
            oportunidade_credito = False

            if cst_pis not in CSTS_TRIB_NCUM:
                situacoes_credito.append("CST_NAO_CREDITAVEL")
                oportunidade_credito = True
            elif vl_bc_pis <= 0:
                situacoes_credito.append("BASE_ZERADA")
                oportunidade_credito = True
            elif vl_pis <= 0:
                situacoes_credito.append("CREDITO_NAO_APROVEITADO")
                oportunidade_credito = True

            if not situacoes_credito:
                situacoes_credito.append("OK")

            if bucket in {"PNEUS", "MANUTENCAO", "LUBRIFICANTES", "COMBUSTIVEL", "ARLA32", "SERVICO"}:
                is_operacional = True

            if tratamento_motor in {"ANALISE_MANUAL", "SENSIVEL", "REVISAO_MANUAL"} or tem_tese:
                is_sensivel = True
                elegivel_autofix = False
            elif permite_autofix_cls:
                is_sensivel = False
                elegivel_autofix = True

            if is_capitalizavel:
                tipo_insumo = "POSSIVEL_IMOBILIZADO"
            elif is_sensivel:
                tipo_insumo = "OPERACIONAL_SENSIVEL"
            elif is_operacional:
                tipo_insumo = "OPERACIONAL_SEGURO"
            else:
                tipo_insumo = "INDEFINIDO"

            if score >= 8:
                grau_confianca = "ALTA"
            elif score >= 5:
                grau_confianca = "MEDIA"
            else:
                grau_confianca = "BAIXA"

            if tipo_insumo == "POSSIVEL_IMOBILIZADO":
                acao_sugerida = "ENCAMINHAR_F120_F130"
            elif tipo_insumo == "OPERACIONAL_SENSIVEL":
                acao_sugerida = "REVISAR_MANUAL_SENSIVEL"
                if tem_tese:
                    acao_sugerida = "REVISAR_MANUAL_TESE"
            elif tipo_insumo == "OPERACIONAL_SEGURO" and elegivel_autofix and grau_confianca in {"ALTA", "MEDIA"}:
                acao_sugerida = "REVISAR_CREDITO_C170_AUTOFIX"
            else:
                acao_sugerida = "REVISAR_MANUALMENTE"

            if  not oportunidade_credito:
                continue

            if score < 4 and tipo_insumo == "INDEFINIDO":
                continue

            qtd_match += 1
            total_score += score
            base_total += base

            categoria_resumo = bucket or "OUTROS"
            resumo_por_categoria[categoria_resumo] += base
            resumo_por_tipo_insumo[tipo_insumo] += base

            itens_evidenciados.append({
                "registro_id": int(it.get("registro_id") or 0),
                "pai_id": int(it.get("pai_id") or 0),
                "ncm": ncm,
                "descricao": desc_original[:120],
                "fornecedor": nome_part_original[:120],
                "score": score,
                "bucket": bucket,
                "tipo_insumo": tipo_insumo,
                "grau_confianca": grau_confianca,
                "acao_sugerida": acao_sugerida,
                "elegivel_autofix": elegivel_autofix,
                "situacao_credito": situacoes_credito,
                "situacao_credito_principal": situacoes_credito[0] if situacoes_credito else "OK",
                "cst_pis": cst_pis,
                "cst_cofins": cst_cofins,
                "vl_bc_pis": str(vl_bc_pis),
                "vl_pis": str(vl_pis),
                "vl_bc_cofins": str(vl_bc_cofins),
                "vl_cofins": str(vl_cofins),
                "evidencias": evidencias_item[:],
                "cod_cta": cod_cta,
                "origem_cod_cta": origem_cod_cta,
                "match_source": classificacao.get("match_source"),
                "match_slug": classificacao.get("match_slug"),
                "subbucket": subbucket,
                "regime_fiscal": regime_fiscal,
                "tratamento_motor": tratamento_motor,
                "teses_aplicaveis": teses_aplicaveis[:],
                "flags": dict(flags_cls),
            })

        if qtd_match == 0 or base_total <= 0:
            return None


        return {
            "qtd_match": qtd_match,
            "base_total": base_total,
            "total_score": total_score,
            "itens": itens_evidenciados,
            "resumo_por_categoria": {
                k: str(v.quantize(Decimal("0.01")))
                for k, v in resumo_por_categoria.items()
            },
            "resumo_por_tipo_insumo": {
                k: str(v.quantize(Decimal("0.01")))
                for k, v in resumo_por_tipo_insumo.items()
            },
        }


class RegraC170InsumosTransportadoraV1(_BaseRegraC170Transportadora):
    codigo = "TRANSP_INSUMO_V1"
    nome = "Possível crédito por insumos operacionais (Transportadora)"
    tipo = "OPORTUNIDADE"

    BUCKETS_ALVO = {"PNEUS", "LUBRIFICANTES", "MANUTENCAO"}
    MODO_CORRECAO = "FLUXO_NORMAL"
    PERMITE_AUTOCORRECAO = True
    PERMITE_ACAO_MANUAL = False
    EXIGE_REVISAO_MANUAL = False
    RISCO_FISCAL = "MEDIO"

    def aplicar(self, registro: RegistroFiscalDTO) -> Optional[Dict[str, Any]]:
        res = self._analisar_itens_transp(registro, buckets_alvo=self.BUCKETS_ALVO)
        if not res:
            return None

        qtd_match = res["qtd_match"]
        base_total = res["base_total"]
        total_score = res["total_score"]
        itens = res["itens"]

        prioridade = "ALTA" if total_score >= 20 else "MEDIA"

        desc = (
            f"Insumos operacionais identificados (Transportadora): "
            f"{qtd_match} item(ns) com indício de aproveitamento inadequado de crédito. "
            f"Base estimada: R$ {self.fmt_br(base_total)}."
        )

        qtd_itens_autocorrigiveis = sum(
            1 for it in itens
            if it.get("elegivel_autofix") and it.get("tipo_insumo") == "OPERACIONAL_SEGURO"
        )
        base_total_autocorrigiveis = sum(
            Decimal(it.get("vl_bc_pis") or "0")
            for it in itens
            if it.get("elegivel_autofix") and it.get("tipo_insumo") == "OPERACIONAL_SEGURO"
        )

        return {
            "tipo": self.tipo,
            "codigo": self.codigo,
            "regra": self.nome,
            "prioridade": prioridade,
            "descricao": desc,
            "impacto_financeiro": None,
            "registro_id": registro.id,
            "meta": {
                "qtd_itens": qtd_match,
                "base_total": str(base_total),
                "score_total": total_score,
                "qtd_itens_autocorrigiveis": qtd_itens_autocorrigiveis,
                "base_total_autocorrigiveis": str(base_total_autocorrigiveis),
                "resumo_por_categoria": res["resumo_por_categoria"],
                "resumo_por_tipo_insumo": res["resumo_por_tipo_insumo"],
                "itens": itens[:20],
                "permite_autocorrecao": self.PERMITE_AUTOCORRECAO,
                "permite_acao_manual": self.PERMITE_ACAO_MANUAL,
                "exige_revisao_manual": self.EXIGE_REVISAO_MANUAL,
                "modo_correcao": self.MODO_CORRECAO,
                "risco_fiscal": self.RISCO_FISCAL,
                "fonte_base": "C170_INSUMO_AGG",
            }
        }


class RegraC170CombustivelTransportadoraV1(_BaseRegraC170Transportadora):
    codigo = "TRANSP_COMBUSTIVEL_V1"
    nome = "Possível crédito por combustíveis sensíveis (Transportadora)"
    tipo = "OPORTUNIDADE"

    BUCKETS_ALVO = {"COMBUSTIVEL"}
    MODO_CORRECAO = "MANUAL_ONLY"
    PERMITE_AUTOCORRECAO = False
    PERMITE_ACAO_MANUAL = True
    EXIGE_REVISAO_MANUAL = True
    RISCO_FISCAL = "ALTO"

    def aplicar(self, registro: RegistroFiscalDTO) -> Optional[Dict[str, Any]]:
        meta = registro.meta or {}
        reg = (getattr(registro, "reg", None) or "").strip()

        db = get_fiscal_db()
        if db is None:
            raise RuntimeError("DB não disponível no contexto fiscal.")

        empresa_id = meta.get("empresa_id") or getattr(registro, "empresa_id", None)
        catalogo = carregar_catalogo_fiscal(db, empresa_id=empresa_id)

        if reg != "C170_INSUMO_AGG":

            return None

        res = self._analisar_itens_transp(registro, buckets_alvo=self.BUCKETS_ALVO)
        if not res:
            return None

        qtd_match = res["qtd_match"]
        base_total = res["base_total"]
        total_score = res["total_score"]
        itens = res["itens"]

        for it in itens:
            it["registro_id_c170"] = it.get("registro_id")
            it["registro_id_c100"] = it.get("pai_id")

        # Excecao do Periodo Pandemia fora
        itens = [
            it for it in itens
            if not bypassar_combustivel_manual_por_lc192(
                meta=meta,
                item=it,
                catalogo=catalogo,
            )
        ]

        if not itens:
            return None

        prioridade = "ALTA" if total_score >= 20 else "MEDIA"

        ncms_combustivel = sorted({
            str(it.get("ncm") or "").strip()
            for it in itens
            if str(it.get("ncm") or "").strip()
        })
        ncms_txt = ", ".join(ncms_combustivel) if ncms_combustivel else "NCM não identificado"

        if len(ncms_combustivel) == 1:
            trecho_ncm = f"NCM {ncms_txt}"
        elif len(ncms_combustivel) > 1:
            trecho_ncm = f"NCMs {ncms_txt}"
        else:
            trecho_ncm = "NCM não identificado"

        desc = (
            f"Combustíveis/sensíveis detectados ({trecho_ncm}) — revisão manual recomendada. "
            f"{qtd_match} item(ns) encontrados no SPED. "
            f"Base estimada: R$ {self.fmt_br(base_total)}."
        )

        qtd_combustivel = sum(1 for it in itens if it.get("bucket") == "COMBUSTIVEL")

        rid = int(registro.id or 0)
        if rid <= 0:
            return None

        return {
            "tipo": self.tipo,
            "codigo": self.codigo,
            "regra": self.nome,
            "prioridade": prioridade,
            "descricao": desc,
            "impacto_financeiro": None,
            "registro_id": rid,
            "meta": {
                "executor_fluxo": "COMBUSTIVEL_MANUAL",
                "executor_contexto": {
                    "origem_execucao": "C170_EXISTENTE",
                    "permite_editar_c170_existente": True,
                    "permite_inserir_c170": False,
                    "permite_inserir_c100": False,
                },
                "qtd_itens": qtd_match,
                "base_total": str(base_total),
                "score_total": total_score,
                "qtd_combustivel": qtd_combustivel,
                "resumo_por_categoria": res["resumo_por_categoria"],
                "resumo_por_tipo_insumo": res["resumo_por_tipo_insumo"],
                "itens": itens[:20],
                "permite_autocorrecao": self.PERMITE_AUTOCORRECAO,
                "permite_acao_manual": self.PERMITE_ACAO_MANUAL,
                "exige_revisao_manual": self.EXIGE_REVISAO_MANUAL,
                "modo_correcao": self.MODO_CORRECAO,
                "acao_manual_sugerida": "APLICAR_CORRECAO_COMBUSTIVEL",
                "risco_fiscal": self.RISCO_FISCAL,
                "fonte_base": "C170_INSUMO_AGG",
            }
        }