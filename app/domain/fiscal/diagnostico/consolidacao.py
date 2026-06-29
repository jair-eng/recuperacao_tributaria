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
                    "qtd_pendente": 0,
                    "qtd_resolvido": 0,
                    "ids_origem": [],
                    "status": "Pendente",
                    "resolvido": False,
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

        is_resolvido = bool(apontamento.get("resolvido")) or (
            str(apontamento.get("status") or "").lower() == "resolvido"
        )

        if is_resolvido:
            grupo["qtd_resolvido"] += 1
        else:
            grupo["qtd_pendente"] += 1

        grupo["resolvido"] = grupo["qtd_pendente"] == 0
        grupo["status"] = "Resolvido" if grupo["resolvido"] else "Pendente"

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