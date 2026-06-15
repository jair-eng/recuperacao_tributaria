from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.utils.numbers import to_decimal
from app.utils.sped import ler_linhas_sped


PASTA_ICMS = Path(r"C:\Sped\ICMS_IPI")


def listar_txt(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.glob("*.txt") if p.is_file())


def get(partes: list[str], idx: int, default=None):
    return partes[idx] if len(partes) > idx else default


def carregar_c170_icms_local(arquivos_icms: list[Path]) -> list[dict[str, Any]]:
    registros = []

    periodo_atual = None
    c100_atual = None
    mapa_0200 = {}

    for arquivo in arquivos_icms:
        c100_atual = None

        for partes in ler_linhas_sped(arquivo):
            reg = get(partes, 0, "")

            if reg == "0000":
                dt_ini = get(partes, 4) or get(partes, 6)
                if dt_ini and len(dt_ini) == 8:
                    periodo_atual = dt_ini[4:8] + dt_ini[2:4]

            elif reg == "0200":
                cod_item = get(partes, 1)
                if cod_item:
                    mapa_0200[cod_item] = {
                        "cod_item": cod_item,
                        "descr_item": get(partes, 2),
                        "cod_ncm": get(partes, 7),
                        "tipo_item": get(partes, 6),
                    }

            elif reg == "C100":
                c100_atual = {
                    "arquivo": arquivo.name,
                    "ind_oper": get(partes, 1),
                    "ind_emit": get(partes, 2),
                    "cod_part": get(partes, 3),
                    "cod_mod": get(partes, 4),
                    "cod_sit": get(partes, 5),
                    "ser": get(partes, 6),
                    "num_doc": get(partes, 7),
                    "chv_nfe": get(partes, 8),
                    "dt_doc": get(partes, 9),
                    "dt_e_s": get(partes, 10),
                    "vl_doc": to_decimal(get(partes, 11)),
                }

            elif reg == "C170":
                if not c100_atual:
                    continue

                cod_item = get(partes, 2)
                item_0200 = mapa_0200.get(cod_item) or {}

                registros.append({
                    "origem": "ICMS_C170",
                    "arquivo": arquivo.name,
                    "periodo": periodo_atual,

                    "ind_oper": c100_atual.get("ind_oper"),
                    "ind_emit": c100_atual.get("ind_emit"),
                    "cod_part": c100_atual.get("cod_part"),
                    "cod_mod": c100_atual.get("cod_mod"),
                    "cod_sit": c100_atual.get("cod_sit"),
                    "ser": c100_atual.get("ser"),
                    "num_doc": c100_atual.get("num_doc"),
                    "chv_nfe": c100_atual.get("chv_nfe"),
                    "dt_doc": c100_atual.get("dt_doc"),
                    "dt_e_s": c100_atual.get("dt_e_s"),
                    "vl_doc": c100_atual.get("vl_doc"),

                    "num_item": get(partes, 1),
                    "cod_item": cod_item,
                    "descr_compl": get(partes, 3),
                    "descr_item_0200": item_0200.get("descr_item"),
                    "ncm": item_0200.get("cod_ncm"),
                    "tipo_item": item_0200.get("tipo_item"),

                    "qtd": to_decimal(get(partes, 4)),
                    "unid": get(partes, 5),
                    "vl_item": to_decimal(get(partes, 6)),
                    "vl_desc": to_decimal(get(partes, 7)),
                    "ind_mov": get(partes, 8),

                    "cst_icms": get(partes, 9),
                    "cfop": get(partes, 10),
                    "cod_nat": get(partes, 11),
                })

    return registros


def texto_item(item: dict[str, Any]) -> str:
    return " ".join([
        str(item.get("descr_compl") or ""),
        str(item.get("descr_item_0200") or ""),
        str(item.get("ncm") or ""),
        str(item.get("cfop") or ""),
    ]).upper()


def procurar_por_palavras(
    registros: list[dict[str, Any]],
    palavras: list[str],
) -> list[dict[str, Any]]:
    achados = []

    for item in registros:
        txt = texto_item(item)

        if any(p.upper() in txt for p in palavras):
            achados.append(item)

    return achados


def resumir(nome: str, registros: list[dict[str, Any]]) -> None:
    total = sum((to_decimal(x.get("vl_item")) for x in registros), Decimal("0.00"))

    print()
    print("=" * 80)
    print(nome)
    print("=" * 80)
    print("QTD:", len(registros))
    print("TOTAL VL_ITEM:", total)

    por_cfop = defaultdict(lambda: {"qtd": 0, "valor": Decimal("0.00")})
    por_ncm = defaultdict(lambda: {"qtd": 0, "valor": Decimal("0.00")})

    for item in registros:
        cfop = item.get("cfop") or "SEM_CFOP"
        ncm = item.get("ncm") or "SEM_NCM"

        por_cfop[cfop]["qtd"] += 1
        por_cfop[cfop]["valor"] += to_decimal(item.get("vl_item"))

        por_ncm[ncm]["qtd"] += 1
        por_ncm[ncm]["valor"] += to_decimal(item.get("vl_item"))

    print("\nTOP CFOP:")
    for cfop, dados in sorted(por_cfop.items(), key=lambda x: x[1]["valor"], reverse=True)[:15]:
        print(cfop, dados)

    print("\nTOP NCM:")
    for ncm, dados in sorted(por_ncm.items(), key=lambda x: x[1]["valor"], reverse=True)[:15]:
        print(ncm, dados)

    print("\nAMOSTRA:")
    for item in registros[:20]:
        print(
            item.get("periodo"),
            item.get("cfop"),
            item.get("ncm"),
            item.get("descr_compl"),
            item.get("vl_item"),
            item.get("chv_nfe"),
        )


def main():
    arquivos_icms = listar_txt(PASTA_ICMS)

    print("Arquivos ICMS:", len(arquivos_icms))

    icms_c170 = carregar_c170_icms_local(arquivos_icms)

    print("QTD ICMS C170:", len(icms_c170))
    print("ENTRADAS:", sum(1 for x in icms_c170 if x.get("ind_oper") == "0"))
    print("SAÍDAS:", sum(1 for x in icms_c170 if x.get("ind_oper") == "1"))
    print("COM NCM:", sum(1 for x in icms_c170 if x.get("ncm")))
    print("SEM NCM:", sum(1 for x in icms_c170 if not x.get("ncm")))

    entradas = [x for x in icms_c170 if x.get("ind_oper") == "0"]

    buscas = {
        "ENERGIA": ["ENERGIA", "ELETRICA", "ELÉTRICA"],
        "PEDAGIO": ["PEDAGIO", "PEDÁGIO"],
        "SEGURO": ["SEGURO", "SEGUROS"],
        "RASTREAMENTO": ["RASTREAMENTO", "MONITORAMENTO", "TELEMETRIA"],
        "FRETE": ["FRETE", "TRANSPORTE", "CARRETO"],
        "COMBUSTIVEL": ["DIESEL", "GASOLINA", "ARLA", "LUBRIFICANTE", "OLEO"],
        "PECAS_MANUTENCAO": ["PECA", "PEÇA", "FILTRO", "PNEU", "JUNTA", "VEDADOR", "MOTOR"],
    }

    for nome, palavras in buscas.items():
        achados = procurar_por_palavras(entradas, palavras)
        resumir(nome, achados)


if __name__ == "__main__":
    main()