from __future__ import annotations


from decimal import Decimal
from typing import Any

from app.domain.relatorio_executivo.contrib_loader_local import montar_efd_por_mes_natureza_local
from app.utils.classificacao_utils import agregar_por_categoria, montar_ecd_por_chave, montar_c170_por_chave, \
    montar_f100_por_chave, montar_a170_por_chave
from app.utils.ecd_gap_utils import resolver_modo_recuperacao, resolver_status_recuperacao
from app.utils.ecd_observacao_utils import montar_observacao
from app.utils.numbers import to_decimal


def montar_contexto_recuperacao_local(
    *,
    linhas_ecd: list[dict[str, Any]],
    db,
    contrib_ctx: dict[str, Any],
    c170_contrib: list[dict[str, Any]],
    f100_contrib: list[dict[str, Any]],
    a170_contrib: list[dict[str, Any]],
    dominio: str = "GERAL",
) -> dict[str, Any]:

    def montar_visao(
        *,
        ecd_map: dict,
        c170_map: dict,
        f100_map: dict,
        a170_map: dict,
        por_periodo: bool = False,
    ) -> dict[str, dict[str, Any]]:

        todas_chaves = (
            set(ecd_map.keys())
            | set(c170_map.keys())
            | set(f100_map.keys())
            | set(a170_map.keys())
        )

        resultado = {}

        for chave in todas_chaves:
            if por_periodo:
                periodo, nat, categoria = chave
                chave_saida = f"{periodo}|{nat}|{categoria}"
            else:
                nat, categoria = chave
                periodo = None
                chave_saida = f"{nat}|{categoria}"

            ecd = ecd_map.get(chave, {})
            c170 = c170_map.get(chave, {})
            f100 = f100_map.get(chave, {})
            a170 = a170_map.get(chave, {})

            valor_ecd = to_decimal(ecd.get("valor_ecd"))

            valor_c170 = to_decimal(c170.get("valor_creditado_c170"))
            valor_oportunidade_c170 = to_decimal(
                c170.get("valor_oportunidade_c170")
            )

            valor_f100 = to_decimal(f100.get("valor_creditado_f100"))

            valor_a170 = to_decimal(a170.get("valor_creditado_a170"))
            valor_sem_credito_a170 = to_decimal(
                a170.get("valor_sem_credito_a170")
            )

            valor_creditado_total = (
                valor_c170
                + valor_f100
                + valor_a170
            )

            valor_documentado_total = (
                valor_creditado_total
                + valor_sem_credito_a170
            )

            valor_gap_ecd = max(
                Decimal("0.00"),
                valor_ecd - valor_documentado_total,
            )

            qtd_c170 = int(c170.get("qtd_c170") or 0)
            qtd_f100 = int(f100.get("qtd_f100") or 0)

            tem_c170 = qtd_c170 > 0
            tem_f100 = qtd_f100 > 0
            tem_credito = valor_creditado_total > 0

            modo = resolver_modo_recuperacao(
                tem_c170=tem_c170,
                tem_f100=tem_f100,
                tem_credito=tem_credito,
            )

            status = resolver_status_recuperacao(
                valor_ecd=valor_ecd,
                valor_creditado_total=valor_creditado_total,
                tem_c170=tem_c170,
                tem_f100=tem_f100,
            )



            linha = {
                "nat_bc_cred": nat,
                "categoria": categoria,
                "valor_ecd": valor_ecd,

                "valor_creditado_c170": valor_c170,
                "valor_oportunidade_c170": valor_oportunidade_c170,
                "qtd_c170_oportunidade": int(
                    c170.get("qtd_c170_oportunidade") or 0
                ),
                "qtd_c170_sem_credito": int(
                    c170.get("qtd_c170_sem_credito") or 0
                ),
                "valor_creditado_f100": valor_f100,
                "valor_creditado_a170": valor_a170,
                "valor_sem_credito_a170": valor_sem_credito_a170,
                "valor_creditado_total": valor_creditado_total,
                "valor_documentado_total": valor_documentado_total,
                "valor_gap_ecd": valor_gap_ecd,

                # compatibilidade temporária
                "valor_recuperavel": valor_gap_ecd,

                "qtd_contas": int(ecd.get("qtd_contas") or 0),
                "qtd_c170": qtd_c170,
                "qtd_f100": qtd_f100,
                "qtd_a170": int(a170.get("qtd_a170") or 0),
                "qtd_a170_creditado": int(
                    a170.get("qtd_a170_creditado") or 0
                ),
                "qtd_a170_sem_credito": int(
                    a170.get("qtd_a170_sem_credito") or 0
                ),

                "modo_recuperacao": modo,
                "status": status,
                "observacao": montar_observacao(status, modo),
                "dominio": dominio,
                "exemplo_descricao": (
                        c170.get("exemplo_descricao")
                        or f100.get("exemplo_descricao")
                        or a170.get("exemplo_descricao")
                        or ""
                ),
                "exemplo_participante": (
                        c170.get("exemplo_participante")
                        or f100.get("exemplo_participante")
                        or ""
                ),
                "exemplo_cod_cta": (
                        c170.get("exemplo_cod_cta")
                        or f100.get("exemplo_cod_cta")
                        or a170.get("exemplo_cod_cta")
                        or ""
                ),
                "exemplo_ncm": (
                        c170.get("exemplo_ncm")
                        or f100.get("exemplo_ncm")
                        or a170.get("exemplo_ncm")
                        or ""
                ),

            }

            if por_periodo:
                linha["periodo"] = periodo

            resultado[chave_saida] = linha

        return resultado

    # Consolidado
    ecd_por_chave = montar_ecd_por_chave(linhas_ecd)
    c170_por_chave = montar_c170_por_chave(
        db=db,
        c170_contrib=c170_contrib,
        dominio=dominio,
    )


    f100_por_chave = montar_f100_por_chave(
        db=db,
        f100_contrib=f100_contrib,
    )
    a170_por_chave = montar_a170_por_chave(
        db=db,
        a170_contrib=a170_contrib,
        dominio=dominio,
    )

    por_chave = montar_visao(
        ecd_map=ecd_por_chave,
        c170_map=c170_por_chave,
        f100_map=f100_por_chave,
        a170_map=a170_por_chave,
        por_periodo=False,
    )

    # Mensal
    ecd_por_periodo_chave = montar_ecd_por_chave(
        linhas_ecd,
        por_periodo=True,
    )
    c170_por_periodo_chave = montar_c170_por_chave(
        db=db,
        c170_contrib=c170_contrib,
        dominio=dominio,
        por_periodo=True,
    )
    f100_por_periodo_chave = montar_f100_por_chave(
        db=db,
        f100_contrib=f100_contrib,
        por_periodo=True,
    )
    a170_por_periodo_chave = montar_a170_por_chave(
        db=db,
        a170_contrib=a170_contrib,
        dominio=dominio,
        por_periodo=True,
    )

    por_periodo_chave = montar_visao(
        ecd_map=ecd_por_periodo_chave,
        c170_map=c170_por_periodo_chave,
        f100_map=f100_por_periodo_chave,
        a170_map=a170_por_periodo_chave,
        por_periodo=True,
    )

    efd_por_mes_nat = montar_efd_por_mes_natureza_local(contrib_ctx)


    return {
        "por_chave": por_chave,
        "por_categoria": agregar_por_categoria(por_chave),
        "por_periodo_chave": por_periodo_chave,
        "efd_por_mes_nat": efd_por_mes_nat,
    }