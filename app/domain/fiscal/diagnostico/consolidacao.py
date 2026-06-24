from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.utils.numbers import to_decimal


def _slug_valor(valor: Any) -> str:
    texto = str(valor or "SEM_VALOR").strip()
    texto = texto.replace(" ", "_").replace("/", "_").replace("\\", "_")
    texto = texto.replace("-", "_").replace(".", "_")
    return texto.upper()


def consolidar_apontamentos(
    apontamentos: list[dict[str, Any]],
    *,
    campos_chave: list[str],
    campos_soma: list[str] | None = None,
    campo_itens: str = "itens",
) -> list[dict[str, Any]]:
    """
    Consolida apontamentos/diagnósticos por campos-chave.

    Importante:
    - Não substitui os apontamentos reais do banco.
    - Gera itens consolidados apenas para exibição.
    - Mantém os itens originais em `itens`.
    - Cria um `id` sintético seguro para evitar erro de key no Streamlit.
    """

    campos_soma = campos_soma or []

    grupos: dict[tuple, dict[str, Any]] = {}

    for apontamento in apontamentos:
        chave = tuple(apontamento.get(campo) for campo in campos_chave)

        if chave not in grupos:
            id_sintetico = "consolidado_" + "_".join(
                _slug_valor(valor) for valor in chave
            )

            grupos[chave] = {
                campo: apontamento.get(campo)
                for campo in campos_chave
            }

            grupos[chave].update(
                {
                    "id": id_sintetico,
                    "is_consolidado": True,
                    "registro_id": None,
                    "item_fiscal_consolidado_id": None,
                    "qtd": 0,
                    "qtd_itens": 0,
                    "ids_origem": [],
                    "status": apontamento.get("status") or "Pendente",
                    "tipo": apontamento.get("tipo"),
                    "prioridade": apontamento.get("prioridade"),
                    "descricao": apontamento.get("descricao"),
                    "codigo": apontamento.get("codigo"),
                    "cenario": apontamento.get("cenario"),
                    campo_itens: [],
                }
            )

            for campo in campos_soma:
                grupos[chave][campo] = Decimal("0.00")

        grupo = grupos[chave]

        grupo["qtd"] += 1
        grupo["qtd_itens"] += 1
        grupo[campo_itens].append(apontamento)

        origem_id = apontamento.get("id")
        if origem_id is not None:
            grupo["ids_origem"].append(origem_id)

        for campo in campos_soma:
            grupo[campo] += to_decimal(apontamento.get(campo))

    return sorted(
        grupos.values(),
        key=lambda x: (
            str(x.get("codigo") or x.get("codigo_diagnostico") or ""),
            str(x.get("cenario") or ""),
            str(x.get("categoria") or ""),
            str(x.get("status_oportunidade") or ""),
        ),
    )