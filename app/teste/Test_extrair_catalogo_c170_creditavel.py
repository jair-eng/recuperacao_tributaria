from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import csv
import re

from app.utils.numbers import to_decimal


PASTA_CONTRIB = Path(r"C:\Sped\CONTRIB")
SAIDA_CSV = Path(r"C:\Sped\saida\catalogo_c170_creditaveis_transp.csv")

CSTS_CREDITAVEIS = {
    "50", "51", "52", "53", "54", "55", "56",
    "60", "61", "62", "63", "64", "65", "66", "67",
}


def norm_txt(v: str | None) -> str:
    v = str(v or "").strip().upper()
    v = re.sub(r"\s+", " ", v)
    return v


def listar_txt(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.glob("*.txt") if p.is_file())


def ler_linhas_sped(path: Path):
    with path.open("r", encoding="latin-1", errors="ignore") as f:
        for linha in f:
            linha = linha.rstrip("\n\r")
            if not linha.startswith("|"):
                continue
            yield linha.split("|")


def extrair_0200_e_c170_creditaveis(arquivos: list[Path]) -> list[dict]:
    mapa_0200 = {}
    registros = []

    periodo_atual = None

    for arquivo in arquivos:
        print("[LENDO]", arquivo.name)

        for partes in ler_linhas_sped(arquivo):
            reg = partes[1] if len(partes) > 1 else ""

            if reg == "0000":
                dt_ini = partes[6] if len(partes) > 6 else ""
                periodo_atual = f"{dt_ini[4:8]}{dt_ini[2:4]}" if len(dt_ini) == 8 else None


            elif reg == "0200":

                cod_item = partes[2] if len(partes) > 2 else ""

                descr_item = partes[3] if len(partes) > 3 else ""

                ncm = partes[8] if len(partes) > 8 else ""

                if cod_item:
                    mapa_0200[cod_item] = {

                        "descr_item_0200": norm_txt(descr_item),

                        "ncm": str(ncm or "").strip(),

                    }
            elif reg == "C170":
                cod_item = partes[3] if len(partes) > 3 else ""
                descr_compl = partes[4] if len(partes) > 4 else ""
                cfop = partes[11] if len(partes) > 11 else ""

                cst_pis = str(partes[25] if len(partes) > 25 else "").strip().zfill(2)
                vl_bc_pis = to_decimal(partes[26] if len(partes) > 26 else "0")
                aliq_pis = to_decimal(partes[27] if len(partes) > 27 else "0")
                vl_pis = to_decimal(partes[30] if len(partes) > 30 else "0")


                cod_cta = partes[37] if len(partes) > 37 else ""

                if cst_pis  not in CSTS_CREDITAVEIS:
                    continue

                if vl_bc_pis <= 0 and vl_pis <= 0:
                    continue

                item_0200 = mapa_0200.get(cod_item) or {}

                descricao = norm_txt(descr_compl) or item_0200.get("descr_item_0200") or ""

                registros.append({
                    "periodo": periodo_atual,
                    "arquivo": arquivo.name,
                    "descricao": descricao,
                    "descricao_0200": item_0200.get("descr_item_0200") or "",
                    "ncm": item_0200.get("ncm") or "",
                    "cfop": cfop,
                    "cod_cta": cod_cta,
                    "cst_pis": cst_pis,
                    "vl_bc_pis": vl_bc_pis,
                    "aliq_pis": aliq_pis,

                })

    return registros


def consolidar_para_catalogo(registros: list[dict]) -> list[dict]:
    agg = defaultdict(lambda: {
        "periodos": set(),
        "arquivos": set(),
        "qtd": 0,
        "base_pis": Decimal("0.00"),
        "pis": Decimal("0.00"),
        "cod_ctas": set(),
        "csts_pis": set(),

    })

    for r in registros:
        chave = (
            r.get("cod_item") or "",
            r.get("descricao") or "",
            r.get("ncm") or "",
            r.get("cfop") or "",
        )

        item = agg[chave]
        item["qtd"] += 1
        item["periodos"].add(r.get("periodo") or "")
        item["arquivos"].add(r.get("arquivo") or "")
        item["base_pis"] += to_decimal(r.get("vl_bc_pis"))
        item["pis"] += to_decimal(r.get("vl_pis"))

        if r.get("cod_cta"):
            item["cod_ctas"].add(str(r.get("cod_cta")))

        item["csts_pis"].add(r.get("cst_pis") or "")

    saida = []

    for (cod_item, descricao, ncm, cfop), dados in agg.items():
        saida.append({
            "cod_item": cod_item,
            "descricao": descricao,
            "ncm": ncm,
            "cfop": cfop,
            "qtd_ocorrencias": dados["qtd"],
            "periodos": ", ".join(sorted(p for p in dados["periodos"] if p)),
            "cod_ctas": ", ".join(sorted(dados["cod_ctas"])),
            "csts_pis": ", ".join(sorted(dados["csts_pis"])),
            "base_pis": dados["base_pis"],
            "pis": dados["pis"],

            "sugestao_grupo": "",

        })

    return sorted(
        saida,
        key=lambda x: (
            -int(x["qtd_ocorrencias"]),
            x["descricao"],
        ),
    )


def salvar_csv(rows: list[dict], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)

    campos = [
        "cod_item",
        "descricao",
        "ncm",
        "cfop",
        "qtd_ocorrencias",
        "periodos",
        "cod_ctas",
        "csts_pis",
        "csts_cofins",
        "base_pis",
        "base_cofins",
        "pis",
        "cofins",
        "credito_total",
        "sugestao_grupo",
        "observacao",
    ]

    with caminho.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    arquivos = listar_txt(PASTA_CONTRIB)

    print("Arquivos:", len(arquivos))

    registros = extrair_0200_e_c170_creditaveis(arquivos)
    print("C170 creditáveis:", len(registros))

    consolidados = consolidar_para_catalogo(registros)
    print("Itens consolidados:", len(consolidados))

    salvar_csv(consolidados, SAIDA_CSV)

    print("CSV gerado:", SAIDA_CSV)