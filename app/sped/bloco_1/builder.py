from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, List, Tuple
from app.sped.blocoM.m_utils import _clean_sped_line, _reg_of_line
from app.sped.bloco_1.reg1100 import linha_1100
from app.sped.bloco_1.reg1500 import linha_1500
from app.sped.bloco_1.utils_1500 import yyyymm_to_mmyyyy
from app.utils.numbers import dec_any, q2


def _fmt_br(valor: Any) -> str:
    return str(q2(dec_any(valor))).replace(".", ",")


def _parse_reg_dados(linha: str) -> Tuple[str, List[str]]:
    ln = _clean_sped_line(linha)
    parts = ln.strip("|").split("|")
    if not parts:
        return "", []
    return parts[0].upper(), parts[1:]




def _extrair_saldo(dados: List[str]) -> Decimal:
    for v in reversed(dados):
        s = (v or "").strip()
        if not s:
            continue
        return dec_any(s)
    return Decimal("0")



def _limpar_parte_bloco_1(parte: list[str]) -> list[str]:
    return [
        _clean_sped_line(ln)
        for ln in (parte or [])
        if not str(ln or "").startswith("|1001|")
        and not str(ln or "").startswith("|1990|")
    ]


def extrair_creditos_mes_bloco_m_por_cod_cred(
    linhas_bloco_m: List[str],
    cod_cred: str,
) -> Tuple[Decimal, Decimal]:
    credito_pis = Decimal("0")
    credito_cofins = Decimal("0")
    cod_cred = str(cod_cred or "").strip()

    for ln in linhas_bloco_m or []:
        reg = _reg_of_line(ln)
        if reg not in ("M100", "M500"):
            continue

        reg2, dados = _parse_reg_dados(ln)
        if not dados:
            continue

        cod = str(dados[0] or "").strip()

        if cod != cod_cred:
            continue

        if reg == "M100" and reg2 == "M100":
            credito_pis += _extrair_saldo(dados)

        elif reg == "M500" and reg2 == "M500":
            credito_cofins += _extrair_saldo(dados)

    return credito_pis, credito_cofins


@dataclass(frozen=True)
class Reg1100:
    periodo: str
    orig_cred: str
    cod_cred: str
    saldo: Decimal
    linha: str


@dataclass(frozen=True)
class Reg1500:
    periodo: str
    orig_cred: str
    cod_cred: str
    saldo: Decimal
    linha: str



def _chave_1100_1500(linha: str) -> tuple[str, str, str]:
    """
    Chave do estoque:
      PER_APU_CRED + ORIG_CRED + COD_CRED
    """
    reg, dados = _parse_reg_dados(linha)

    if reg not in ("1100", "1500") or len(dados) < 4:
        return "", "", ""

    return (
        str(dados[0] or "").strip(),
        str(dados[1] or "").strip(),
        str(dados[3] or "").strip(),
    )

def _chave_ordenacao_bloco_1(linha: str) -> tuple[int, str]:
    reg, dados = _parse_reg_dados(linha)

    try:
        ordem_reg = int(reg)
    except (TypeError, ValueError):
        ordem_reg = 9999

    periodo_ordem = ""

    if reg in ("1100", "1500") and dados:
        periodo_mmaaaa = str(dados[0] or "").strip()

        if len(periodo_mmaaaa) == 6:
            periodo_ordem = (
                periodo_mmaaaa[2:6]
                + periodo_mmaaaa[0:2]
            )

    return ordem_reg, periodo_ordem

def _somar_saldo_v2_em_linha_1100_1500(
    linha: str,
    valor_add: Decimal,
) -> str:
    valor_add = dec_any(valor_add)

    parts = _clean_sped_line(linha).strip("|").split("|")

    if not parts or parts[0] not in ("1100", "1500"):
        return _clean_sped_line(linha)

    # REG + 17 campos = 18 posições: indices 0..17
    while len(parts) < 18:
        parts.append("")

    # índices com REG incluso:
    # Campo 05 = parts[5]
    # Campo 07 = parts[7]
    # Campo 12 = parts[11]
    # Campo 18 = parts[17]
    for idx in (5, 7, 11, 17):
        parts[idx] = _fmt_br(dec_any(parts[idx]) + valor_add)

    # corta qualquer sobra acidental para não criar campo extra
    parts = parts[:18]

    return "|" + "|".join(parts) + "|"

def _estoque_attr(est: Any, nome: str, padrao: Any = None) -> Any:
    """
    Aceita objeto SQLAlchemy, dataclass ou dict.
    """
    if isinstance(est, dict):
        return est.get(nome, padrao)
    return getattr(est, nome, padrao)


def montar_bloco_1_com_estoque_v2(
    *,
    linhas_sped: List[str],
    periodo_atual: str,  # YYYYMM
    estoques_v2: List[Any],
) -> List[str]:
    """
    Monta o Bloco 1 usando credito_estoque_v2.

    Regras:
      - periodo_atual e períodos do estoque são comparados em YYYYMM;
      - o período escrito nos registros 1100/1500 é convertido para MMYYYY;
      - preserva os registros originais;
      - remove apenas 1001/1990 antigos;
      - insere ou soma 1100/1500;
      - recompõe o 1990.
    """

    periodo_atual = str(periodo_atual or "").strip()

    if len(periodo_atual) != 6:
        raise ValueError(
            f"periodo_atual inválido em montar_bloco_1_com_estoque_v2: "
            f"{periodo_atual!r}; esperado YYYYMM"
        )

    parte_limpa = _limpar_parte_bloco_1(linhas_sped)

    linhas_resultado: list[str] = []
    mapa_idx_por_chave: dict[tuple[str, str, str, str], int] = {}

    for ln in parte_limpa:
        reg = _reg_of_line(ln)
        linha_limpa = _clean_sped_line(ln)

        if reg in ("1100", "1500"):
            chave = _chave_1100_1500(linha_limpa)
            mapa_idx_por_chave[(reg, *chave)] = len(linhas_resultado)

        linhas_resultado.append(linha_limpa)

    for est in estoques_v2 or []:
        periodo_origem = str(
            _estoque_attr(est, "periodo_origem", "") or ""
        ).strip()

        periodo_escrituracao = str(
            _estoque_attr(est, "periodo_escrituracao", "") or ""
        ).strip()

        cod_cred = str(
            _estoque_attr(est, "cod_cred", "101") or "101"
        ).strip()

        orig_cred = str(
            _estoque_attr(est, "orig_cred", "01") or "01"
        ).strip()

        saldo_pis = dec_any(
            _estoque_attr(est, "saldo_pis", Decimal("0"))
        )
        saldo_cofins = dec_any(
            _estoque_attr(est, "saldo_cofins", Decimal("0"))
        )

        if not periodo_origem or len(periodo_origem) != 6:
            continue

        # Comparações sempre em YYYYMM.
        if periodo_origem >= periodo_atual:
            continue

        if (
            periodo_escrituracao
            and periodo_escrituracao > periodo_atual
        ):
            continue

        # Formato utilizado dentro das linhas 1100/1500.
        periodo_origem_mmaaaa = yyyymm_to_mmyyyy(periodo_origem)

        if saldo_pis > 0:
            chave_1100 = (
                "1100",
                periodo_origem_mmaaaa,
                orig_cred,
                cod_cred,
            )

            if chave_1100 in mapa_idx_por_chave:
                idx = mapa_idx_por_chave[chave_1100]
                linhas_resultado[idx] = (
                    _somar_saldo_v2_em_linha_1100_1500(
                        linhas_resultado[idx],
                        saldo_pis,
                    )
                )
            else:
                mapa_idx_por_chave[chave_1100] = len(linhas_resultado)
                linhas_resultado.append(
                    linha_1100(
                        periodo=periodo_origem_mmaaaa,
                        cod_cont=cod_cred,
                        valor=saldo_pis,
                        orig_cred=orig_cred,
                    )
                )

        if saldo_cofins > 0:
            chave_1500 = (
                "1500",
                periodo_origem_mmaaaa,
                orig_cred,
                cod_cred,
            )

            if chave_1500 in mapa_idx_por_chave:
                idx = mapa_idx_por_chave[chave_1500]
                linhas_resultado[idx] = (
                    _somar_saldo_v2_em_linha_1100_1500(
                        linhas_resultado[idx],
                        saldo_cofins,
                    )
                )
            else:
                mapa_idx_por_chave[chave_1500] = len(linhas_resultado)
                linhas_resultado.append(
                    linha_1500(
                        periodo=periodo_origem_mmaaaa,
                        cod_cont=cod_cred,
                        valor=saldo_cofins,
                        orig_cred=orig_cred,
                    )
                )

    linhas_resultado.sort(key=_chave_ordenacao_bloco_1)

    tem_movimento = bool(linhas_resultado)
    ind_mov = "0" if tem_movimento else "1"

    bloco = [f"|1001|{ind_mov}|"]
    bloco.extend(linhas_resultado)
    bloco.append(f"|1990|{len(bloco) + 1}|")

    return bloco
