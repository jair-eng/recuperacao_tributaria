from __future__ import annotations

from dataclasses import dataclass , field
from typing import List, Optional , Any , Dict
from app.Legacy.fiscal.dto import RegistroFiscalDTO
from app.Legacy.fiscal.regras.Diagnostico.insumos.Transp_combustivel_semC170 import RegraTranspCombustivelSemC170V1
from app.Legacy.fiscal.regras.Diagnostico.insumos.insumos_cafe import RegraC170InsumosCafeV1
from app.Legacy.fiscal.regras.Diagnostico.insumos.insumos_transportadora import RegraC170InsumosTransportadoraV1, \
    RegraC170CombustivelTransportadoraV1
from app.Legacy.fiscal.regras.Diagnostico.insumos.transp_combustivel_semC100 import RegraTranspCombustivelSemC100V1
from app.Legacy.fiscal.regras.Diagnostico.regra_c170_cfop_sem_credito_v1 import RegraC170CfopSemCreditoV1
from app.Legacy.fiscal.regras.Diagnostico.regra_comb_lc192_v1 import RegraCombLC192V1
from app.Legacy.fiscal.regras.Diagnostico.regra_contrib_sem_c100_v1 import RegraContribSemC100V1
from app.Legacy.fiscal.regras.Diagnostico.regra_contrib_sem_c170_v1 import RegraContribSemC170V1
from app.Legacy.fiscal.regras.Diagnostico.insumos.regra_emb_insumo_v1 import RegraEmbalagemInsumoV1
from app.Legacy.fiscal.regras.Diagnostico.regra_exportacao import RegraExportacaoRessarcimentoV1
from app.Legacy.fiscal.regras.Diagnostico.insumos.insumos_base import  RegraC170InsumosBase
from app.Legacy.fiscal.regras.Diagnostico.regra_ind_cafe_v1 import RegraIndustrializacaoCafeV1
from app.Legacy.fiscal.regras.Diagnostico.regra_industrializacao_graos_v1 import RegraIndustrializacaoAgroV1
from app.Legacy.fiscal.regras.Diagnostico.insumos.regra_limp_insuV1 import RegraLimpezaInsumoV1
from decimal import Decimal

from app.Legacy.fiscal.regras.Diagnostico.regra_exp_m_zerado_v1 import RegraExportacaoBlocoMZeradoV1
from app.Legacy.fiscal.regras.Diagnostico.base_regras import aplicar_supressao_por_erros_dict, aplicar_bloqueio_por_grupo_dict, \
    aplicar_rebaixamento_por_presenca_dict, RegraBase
from app.Legacy.fiscal.regras.Diagnostico.regra_posto_credito_normal import RegraPostoCreditoNormalV1
from app.Legacy.fiscal.regras.Diagnostico.regra_posto_monofasico_credito_acumulado_v1 import \
    RegraMonofasicoCreditoNaoRessarcivelV1
from app.Legacy.fiscal.constants import DOM_AGRO, DOM_CAFE, DOM_SUP, DOM_GERAL, DOMINIOS_VALIDOS, DOM_TRANSP, DOM_POSTO, \
    DOM_REVENDA_GAS

REGRAS_REGISTRO_POR_DOMINIO = {
    DOM_GERAL: [
        #RegraF600Insumos(),
        #RegraM100CreditoPIS(),
        #RegraM200CreditoCOFINS(),
        RegraMonofasicoCreditoNaoRessarcivelV1(),
        RegraContribSemC170V1(),
        RegraC170CfopSemCreditoV1(),
        RegraContribSemC100V1(),


    ],

    DOM_CAFE: [
        RegraIndustrializacaoCafeV1(),
        RegraExportacaoBlocoMZeradoV1(),
        RegraExportacaoRessarcimentoV1(),

    ],

    DOM_AGRO: [
        RegraIndustrializacaoAgroV1(),
        RegraExportacaoBlocoMZeradoV1(),
        RegraExportacaoRessarcimentoV1(),

    ],

    DOM_SUP: [
        RegraEmbalagemInsumoV1(),
        RegraLimpezaInsumoV1(),
    ],

}

REGRAS_AGG_POR_DOMINIO = {
    DOM_GERAL: [
        RegraC170InsumosBase(),



    ],
    DOM_CAFE: [
    RegraC170InsumosCafeV1(),

    ],
    DOM_TRANSP: [
            RegraC170InsumosTransportadoraV1(),
            #RegraTranspCredPresumidoNaoAproveitadoV1(), quando for mexer tirar o comentario
            RegraC170CombustivelTransportadoraV1(),
            RegraTranspCombustivelSemC100V1(),
            RegraTranspCombustivelSemC170V1(),
            RegraCombLC192V1(),

        ],
    DOM_POSTO: [
                RegraPostoCreditoNormalV1(),
                RegraCombLC192V1(),
            ],
    DOM_REVENDA_GAS:[
                RegraCombLC192V1(),

    ],
    }


@dataclass(slots=True)
class ApontamentoDTO:
    # ---- obrigatórios (SEM default) ----
    registro_id: int
    tipo: str
    codigo: str
    descricao: str

    # ---- opcionais (COM default) ----
    impacto_financeiro: Optional[float] = None
    prioridade: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    regra: Optional[str] = None

@dataclass(slots=True)
class ResultadoVarredura:
    apontamentos: List[ApontamentoDTO]
    erros: List[str]

def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, Decimal):
        return float(v)

    s = str(v).strip()
    if not s:
        return None

    # Se tiver vírgula, assume pt-BR: "1.234,56"
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    # Senão, assume padrão: "1234.56" (não remove ponto)

    try:
        return float(s)
    except Exception:
        return None


def _norm_codigo(c: Any) -> Optional[str]:
    if c is None:
        return None
    s = str(c).strip()
    return s or None

def _dedup_regras(regras):
    out, seen = [], set()
    for r in regras:
        k = getattr(r, "codigo", r.__class__.__name__)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out



def executar_varredura(
    registros: List[RegistroFiscalDTO],
    *,
    capturar_erros: bool = True,
    dominio: str = DOM_GERAL,
) -> ResultadoVarredura:
    apontamentos: List[ApontamentoDTO] = []
    erros: List[str] = []

    achados_raw = []

    # ✅ Warm-up catálogo (1x por varredura)
    try:
        if registros:
            # pega um registro qualquer que tenha empresa_id
            r0 = next((r for r in registros if getattr(r, "empresa_id", None)), registros[0])
            # chama uma vez pra encher o cache por empresa_id
            RegraBase.get_catalogo(r0, db=None)
    except Exception:
        # não pode derrubar varredura por isso
        pass

    dominio = (dominio or DOM_GERAL).strip().upper()
    if dominio not in DOMINIOS_VALIDOS:
        dominio = DOM_GERAL

    regras_registro = list(REGRAS_REGISTRO_POR_DOMINIO.get(DOM_GERAL, []))
    regras_registro += list(REGRAS_REGISTRO_POR_DOMINIO.get(dominio, [])) if dominio != DOM_GERAL else []

    regras_agg = list(REGRAS_AGG_POR_DOMINIO.get(DOM_GERAL, []))
    regras_agg += list(REGRAS_AGG_POR_DOMINIO.get(dominio, [])) if dominio != DOM_GERAL else []

    regras_registro = _dedup_regras(regras_registro)
    regras_agg = _dedup_regras(regras_agg)

    print("[DBG] DOMINIO:", dominio, flush=True)
    print("[DBG] REGRAS_REGISTRO:", [getattr(r, "codigo", r.__class__.__name__) for r in regras_registro], flush=True)
    print("[DBG] REGRAS_AGG:", [getattr(r, "codigo", r.__class__.__name__) for r in regras_agg], flush=True)

    for registro in registros:
        for regra in regras_registro:

            try:
                achado = regra.aplicar(registro)
                if not achado:
                    continue

                # aceita Achado (dataclass) OU dict (MVP)
                if hasattr(achado, "__dataclass_fields__") and achado.__class__.__name__ == "Achado":
                    raw_meta = getattr(achado, "meta", None) or {}
                    achado = {
                        "registro_id": achado.registro_id,
                        "tipo": achado.tipo,
                        "codigo": achado.codigo,
                        "descricao": achado.descricao,
                        "impacto_financeiro": achado.impacto_financeiro,
                        "prioridade": getattr(achado, "prioridade", None),
                        "meta": dict(raw_meta) if isinstance(raw_meta, dict) else {},
                        "regra": achado.regra or getattr(regra, "nome", None),
                    }

                # garante mínimos (para não guardar lixo)
                descricao = str(achado.get("descricao") or "").strip()
                if not descricao:
                    continue

                # normaliza campos básicos já aqui (facilita postprocess)
                achado["tipo"] = str(achado.get("tipo") or getattr(regra, "tipo", "OPORTUNIDADE"))
                achado["codigo"] = _norm_codigo(achado.get("codigo") or getattr(regra, "codigo", None))
                achado["regra"] = achado.get("regra") or getattr(regra, "nome", None)

                rid = achado.get("registro_id")
                achado["registro_id"] = int(rid) if rid is not None else int(registro.id)

                raw_meta = achado.get("meta") or {}
                achado["meta"] = dict(raw_meta) if isinstance(raw_meta, dict) else {}

                achados_raw.append(achado)

            except Exception as e:
                if capturar_erros:
                    erros.append(
                        f"{getattr(regra, 'codigo', regra.__class__.__name__)} "
                        f"(reg={registro.reg} linha={registro.linha} id={registro.id}): {e}"
                    )
                else:
                    raise

    # -----------------------------
    # Regras por AGG (RegistroFiscalDTO)
    # -----------------------------
    for registro in registros:
        if not isinstance(registro, RegistroFiscalDTO):
            continue
        for regra in regras_agg:
            try:
                achado = regra.aplicar(registro)
                if not achado:
                    continue

                if hasattr(achado, "__dataclass_fields__") and achado.__class__.__name__ == "Achado":
                    raw_meta = getattr(achado, "meta", None) or {}
                    achado = {
                        "registro_id": achado.registro_id,
                        "tipo": achado.tipo,
                        "codigo": achado.codigo,
                        "descricao": achado.descricao,
                        "impacto_financeiro": achado.impacto_financeiro,
                        "prioridade": getattr(achado, "prioridade", None),
                        "meta": dict(raw_meta) if isinstance(raw_meta, dict) else {},
                        "regra": achado.regra or getattr(regra, "nome", None),
                    }

                descricao = str(achado.get("descricao") or "").strip()
                if not descricao:
                    continue

                achado["tipo"] = str(achado.get("tipo") or getattr(regra, "tipo", "OPORTUNIDADE"))
                achado["codigo"] = _norm_codigo(achado.get("codigo") or getattr(regra, "codigo", None))
                achado["regra"] = achado.get("regra") or getattr(regra, "nome", None)

                rid = achado.get("registro_id")
                achado["registro_id"] = int(rid) if rid is not None else int(registro.id)

                raw_meta = achado.get("meta") or {}
                achado["meta"] = dict(raw_meta) if isinstance(raw_meta, dict) else {}

                achados_raw.append(achado)

            except Exception as e:
                if capturar_erros:
                    erros.append(
                        f"{getattr(regra, 'codigo', regra.__class__.__name__)} "
                        f"(reg={registro.reg} linha={registro.linha} id={registro.id}): {e}"
                    )
                else:
                    raise
    print("CÓDIGOS antes:", sorted({a.get("codigo") for a in achados_raw}), flush=True)
    # ✅ pós-processamento 1 (bloqueio/supressão pontual por código)
    achados_raw = aplicar_supressao_por_erros_dict(achados_raw)
    print("CÓDIGOS depois:", sorted({a.get("codigo") for a in achados_raw}), flush=True)

    # ✅ pós-processamento 1.1 (rebaixamento por presença — evita poluição)
    if dominio in (DOM_CAFE, DOM_AGRO):
        achados_raw = aplicar_rebaixamento_por_presenca_dict(
            achados_raw,
            se_existe="CAFE_C190_V1",
            rebaixar=["IND_AGRO_V1"],
            prioridade_alvo="BAIXA",
        )

    # ✅ pós-processamento 2 (agrupamento + erro crítico bloqueia/rebaixa oportunidades do grupo)
    achados_raw = aplicar_bloqueio_por_grupo_dict(
        achados_raw,
        erros_criticos=("EXP_M_ZERADO_V1",),
        rebaixar_prioridade=True,
    )

    # ✅ agora converte para DTO
    for achado in achados_raw:
        impacto = _safe_float(achado.get("impacto_financeiro"))

        apontamentos.append(
            ApontamentoDTO(
                registro_id=int(achado["registro_id"]),
                tipo=str(achado.get("tipo")),
                codigo=str(achado.get("codigo")),
                descricao=str(achado.get("descricao")),
                impacto_financeiro=impacto,
                prioridade=achado.get("prioridade"),
                meta=achado.get("meta") or {},
                regra=achado.get("regra"),
            )
        )

    return ResultadoVarredura(apontamentos=apontamentos, erros=erros)
