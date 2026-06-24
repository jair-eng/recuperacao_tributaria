from pathlib import Path
from collections import Counter, defaultdict
from decimal import Decimal

from app.db.session import SessionLocal
from app.utils.sped import listar_txt
from app.domain.relatorio_executivo.c170_loader_local import carregar_c170_local
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.cenarios.avaliador_cenarios import avaliar_cenarios
from app.domain.relatorio_executivo.IcmsContribuicao.c170_oportunidades_local import (
    resolver_categoria_c170_por_catalogo,
)

DOMINIO = "TRANSP"
PASTA_CONTRIB = Path(r"C:\Sped\CONTRIB")
LIMITE_ITENS = 10000


def dec(v):
    try:
        return Decimal(str(v or "0").replace(",", "."))
    except Exception:
        return Decimal("0")


def desc(item):
    return (
        item.get("descr_compl")
        or item.get("descricao")
        or item.get("descr_item")
        or item.get("descr_item_0200")
        or ""
    ).strip()


def meta_item(item):
    return {
        "periodo": item.get("periodo"),
        "cod_item": item.get("cod_item"),
        "descr_item": desc(item),
        "ncm": item.get("ncm") or item.get("cod_ncm") or item.get("ncm_0200"),
        "cfop": item.get("cfop"),
        "cod_cta": item.get("cod_cta"),
        "vl_item": item.get("vl_item"),
        "cst_pis": item.get("cst_pis"),
        "cst_cofins": item.get("cst_cofins"),
        "vl_bc_pis": item.get("vl_bc_pis"),
        "vl_bc_cofins": item.get("vl_bc_cofins"),
        "vl_pis": item.get("vl_pis"),
        "vl_cofins": item.get("vl_cofins"),
        "dominio": DOMINIO,
    }


def motivo_falha(meta, cls, categoria, cenario):
    op = (cls or {}).get("operacao") or {}
    prod = (cls or {}).get("produto") or {}

    if not cls:
        return "SEM_CLASSIFICACAO"

    if meta.get("dominio") != "TRANSP":
        return "DOMINIO_NAO_TRANSP"

    if not op.get("entrada"):
        return "OPERACAO_NAO_ENTRADA"

    if op.get("transferencia"):
        return "OPERACAO_TRANSFERENCIA"

    if op.get("imobilizado"):
        return "OPERACAO_IMOBILIZADO"

    if op.get("servico"):
        return "OPERACAO_SERVICO"

    if op.get("sem_credito"):
        return "OPERACAO_SEM_CREDITO"

    if categoria == "NaoClassificado":
        return "CATEGORIA_NAO_CLASSIFICADA"

    flags_produto = [
        "diesel",
        "gasolina",
        "etanol",
        "lubrificante",
        "pneu",
        "filtro",
        "arla32",
        "manutencao_veicular",
        "autopeca",
        "rastreamento_telemetria",
        "ativo_imobilizado",
    ]

    if not any(prod.get(k) for k in flags_produto):
        return "CATEGORIA_SEM_FLAG_PRODUTO"

    if cenario and not cenario.get("ativo"):
        just = cenario.get("justificativa") or []
        if just:
            return "CENARIO_INATIVO_" + "_".join(map(str, just[:2])).upper()

    return "FALHA_CENARIO_NAO_EXPLICADA"


def flags_produto(cls):
    prod = (cls or {}).get("produto") or {}
    return ",".join(
        k for k, v in prod.items()
        if v is True
    ) or "-"


def main():
    db = SessionLocal()

    try:
        catalogo = carregar_catalogo_fiscal(db)
        arquivos = listar_txt(PASTA_CONTRIB)
        itens = carregar_c170_local(arquivos)
        itens = itens[:LIMITE_ITENS] if LIMITE_ITENS else itens

        resumo_categoria = Counter()
        resumo_cenario = Counter()
        resumo_falha = Counter()

        falhas = defaultdict(lambda: {
            "qtd": 0,
            "valor": Decimal("0"),
            "exemplos": [],
        })

        for i, item in enumerate(itens, start=1):
            meta = meta_item(item)
            valor = dec(meta.get("vl_item"))

            cls = classificar_item_fiscal(
                catalogo=catalogo,
                meta=meta,
            )

            categoria = resolver_categoria_c170_por_catalogo(
                meta=meta,
                catalogo=catalogo,
                dominio=DOMINIO,
            )

            try:
                cenario = avaliar_cenarios(meta, cls)
            except Exception as e:
                cenario = {
                    "ativo": False,
                    "cenario": f"ERRO_{type(e).__name__}",
                    "justificativa": [str(e)],
                }

            nome_cenario = "SEM_CENARIO"
            if cenario and cenario.get("ativo"):
                nome_cenario = (
                    cenario.get("cenario")
                    or cenario.get("codigo")
                    or cenario.get("nome")
                    or "CENARIO_SEM_NOME"
                )

            resumo_categoria[categoria] += 1
            resumo_cenario[nome_cenario] += 1

            if nome_cenario == "SEM_CENARIO":
                motivo = motivo_falha(meta, cls, categoria, cenario)
                resumo_falha[motivo] += 1

                chave = (
                    motivo,
                    categoria,
                    str(meta.get("cfop") or ""),
                    str(meta.get("cst_pis") or ""),
                    str(meta.get("ncm") or ""),
                )

                falhas[chave]["qtd"] += 1
                falhas[chave]["valor"] += valor

                if len(falhas[chave]["exemplos"]) < 3:
                    falhas[chave]["exemplos"].append({
                        "desc": meta.get("descr_item"),
                        "cod_item": meta.get("cod_item"),
                        "periodo": meta.get("periodo"),
                        "cfop": meta.get("cfop"),
                        "cst": meta.get("cst_pis"),
                        "ncm": meta.get("ncm"),
                        "valor": valor,
                        "dominio": meta.get("dominio"),
                        "operacao": (cls or {}).get("operacao"),
                        "produto_flags": flags_produto(cls),
                        "cenario": cenario,
                        "meta": meta,
                        "classificacao": cls,
                    })

        print("\n===== RESUMO CATEGORIA =====")
        for k, v in resumo_categoria.most_common():
            print(f"{k:<40} {v}")

        print("\n===== RESUMO CENARIO =====")
        for k, v in resumo_cenario.most_common():
            print(f"{k:<55} {v}")

        print("\n===== POR QUE FICOU SEM_CENARIO =====")
        for k, v in resumo_falha.most_common():
            print(f"{k:<45} {v}")

        print("\n===== TOP FALHAS CIRURGICAS =====")
        for (motivo, categoria, cfop, cst, ncm), dados in sorted(
            falhas.items(),
            key=lambda x: x[1]["valor"],
            reverse=True,
        )[:40]:
            print("\n" + "-" * 90)
            print(f"MOTIVO....: {motivo}")
            print(f"CATEGORIA.: {categoria}")
            print(f"CFOP......: {cfop}")
            print(f"CST.......: {cst}")
            print(f"NCM.......: {ncm}")
            print(f"QTD.......: {dados['qtd']}")
            print(f"VALOR.....: {dados['valor']:.2f}")

            for ex in dados["exemplos"]:
                print(
                    f"  - {ex['desc']} | "
                    f"COD={ex['cod_item']} | "
                    f"PER={ex['periodo']} | "
                    f"NCM={ex['ncm']} | "
                    f"CFOP={ex['cfop']} | "
                    f"CST={ex['cst']} | "
                    f"VALOR={ex['valor']:.2f}"
                )
                print(f"    DOMINIO={ex['dominio']}")
                print(f"    PRODUTO_FLAGS={ex['produto_flags']}")
                print(f"    OPERACAO={ex['operacao']}")
                print(f"    CENARIO={ex['cenario']}")
                if motivo == "FALHA_CENARIO_NAO_EXPLICADA":
                    print("\n===== FALHA CENARIO =====")
                    print(ex)

    finally:
        db.close()


if __name__ == "__main__":
    main()