from pathlib import Path
from collections import Counter, defaultdict
from decimal import Decimal

from app.db.session import SessionLocal
from app.domain.relatorio_executivo.IcmsContribuicao.c170_oportunidades_local import meta_from_linha_cruzada_c170_local
from app.utils.sped import listar_txt
from app.domain.relatorio_executivo.c170_loader_local import carregar_c170_local
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.cenarios.avaliador_cenarios import avaliar_cenarios


DOMINIO = "TRANSP"
PASTA_CONTRIB = Path(r"C:\Sped\CONTRIB")
BATCH_SIZE = 500
LIMITE_ITENS = 10000  # coloque 2000 para teste rápido, depois volte para None


def _dec(v) -> Decimal:
    try:
        return Decimal(str(v or "0").replace(",", "."))
    except Exception:
        return Decimal("0")


def _desc(item: dict) -> str:
    return (
        item.get("descr_compl")
        or item.get("descricao")
        or item.get("descr_item")
        or item.get("descr_item_0200")
        or ""
    ).strip()

def resolver_categoria_transp(cls: dict) -> str:
    produto = cls.get("produto") or {}

    if produto.get("pneu"):
        return "Pneus"

    if produto.get("rastreamento_telemetria"):
        return "RastreamentoTelemetria"

    if produto.get("manutencao_veicular") or produto.get("autopeca"):
        return "PecasManutencaoFrota"
    if (
        produto.get("diesel")
        or produto.get("gasolina")
        or produto.get("etanol")
        or produto.get("combustivel")
        or produto.get("arla32")
        or produto.get("lubrificante")
    ):
        return "CombustiveisLubrificantes"


    if produto.get("ativo_imobilizado"):
        return "AtivoImobilizado"

    return "NaoClassificado"


def main():
    arquivos = listar_txt(PASTA_CONTRIB)
    db = SessionLocal()

    try:
        catalogo = carregar_catalogo_fiscal(db)
        c170 = carregar_c170_local(arquivos)

        print()
        print("===== DIAGNOSTICO GERAL CATALOGO TRANSP =====")
        print("Arquivos CONTRIB:", len(arquivos))
        print("C170:", len(c170))
        print()

        print("===== CHECK NCMs IMPORTANTES =====")
        for ncm in [
            "27101921",  # diesel
            "27101932",  # lubrificante
            "40112090",  # pneus
            "87163900",  # semirreboque
            "84713019",  # computador
        ]:
            print(f"NCM {ncm}: {catalogo.grupos_ncm(ncm)}")
        print()

        total = 0
        classificados = 0
        nao_classificados = 0

        por_categoria = defaultdict(lambda: {
            "qtd": 0,
            "valor": Decimal("0"),
        })

        por_cfop = defaultdict(lambda: {
            "qtd": 0,
            "valor": Decimal("0"),
        })

        por_cst = defaultdict(lambda: {
            "qtd": 0,
            "valor": Decimal("0"),
        })

        por_ncm = defaultdict(lambda: {
            "qtd": 0,
            "valor": Decimal("0"),
            "categorias": Counter(),
        })

        nao_classificados_desc = defaultdict(lambda: {
            "qtd": 0,
            "valor": Decimal("0"),
            "ncm": Counter(),
            "cfop": Counter(),
            "cst": Counter(),
        })

        cenarios = Counter()

        amostras_por_categoria = defaultdict(list)

        c170_processar = c170[:LIMITE_ITENS] if LIMITE_ITENS else c170

        for idx, item in enumerate(c170_processar, start=1):
            if idx % BATCH_SIZE == 0 or idx == 1:
                print(f"[PROGRESSO] {idx}/{len(c170_processar)} itens processados...")
            total += 1

            descricao = _desc(item)
            valor = _dec(item.get("vl_item"))

            ncm = (
                item.get("ncm")
                or item.get("cod_ncm")
                or item.get("ncm_0200")
                or ""
            )

            cfop = str(item.get("cfop") or "")
            cst = str(item.get("cst_pis") or "")

            meta = {
                "periodo": item.get("periodo"),
                "cod_item": item.get("cod_item"),
                "descr_item": (
                        item.get("descr_compl")
                        or item.get("descricao")
                        or item.get("descr_item")
                        or item.get("descr_item_0200")
                ),
                "ncm": (
                        item.get("ncm")
                        or item.get("cod_ncm")
                        or item.get("ncm_0200")
                ),
                "cfop": item.get("cfop"),
                "cod_cta": item.get("cod_cta"),
                "vl_item": item.get("vl_item"),
                "vl_desc": item.get("vl_desc"),
                "cst_pis": item.get("cst_pis"),
                "cst_cofins": item.get("cst_cofins"),
                "vl_bc_pis": item.get("vl_bc_pis"),
                "vl_bc_cofins": item.get("vl_bc_cofins"),
                "vl_pis": item.get("vl_pis"),
                "vl_cofins": item.get("vl_cofins"),
                "origem": "TESTE_CATALOGO_TRANSP_C170_LOCAL",
                "dominio": DOMINIO,
            }


            cls = classificar_item_fiscal(
                catalogo=catalogo,
                meta=meta,
            )

            categoria = resolver_categoria_transp(cls)

            por_categoria[categoria]["qtd"] += 1
            por_categoria[categoria]["valor"] += valor

            por_cfop[cfop]["qtd"] += 1
            por_cfop[cfop]["valor"] += valor

            por_cst[cst]["qtd"] += 1
            por_cst[cst]["valor"] += valor

            por_ncm[ncm]["qtd"] += 1
            por_ncm[ncm]["valor"] += valor
            por_ncm[ncm]["categorias"][categoria] += 1


            if len(amostras_por_categoria[categoria]) < 10:
                amostras_por_categoria[categoria].append({
                    "descricao": descricao,
                    "ncm": ncm,
                    "cfop": cfop,
                    "cst": cst,
                    "valor": valor,
                })

            if categoria == "NaoClassificado":
                nao_classificados += 1

                chave = descricao[:120].strip().upper() or "(SEM DESCRICAO)"

                nao_classificados_desc[chave]["qtd"] += 1
                nao_classificados_desc[chave]["valor"] += valor
                nao_classificados_desc[chave]["ncm"][ncm] += 1
                nao_classificados_desc[chave]["cfop"][cfop] += 1
                nao_classificados_desc[chave]["cst"][cst] += 1
            else:
                classificados += 1

            try:
                cenario = avaliar_cenarios(
                    meta,
                    cls,
                )

                nome_cenario = "SEM_CENARIO"

                if cenario and cenario.get("ativo"):
                    nome_cenario = (
                            cenario.get("cenario")
                            or cenario.get("codigo")
                            or cenario.get("nome")
                            or (cenario.get("fundamento_legal") or ["SEM_NOME"])[0]
                    )
            except Exception as e:
                nome_cenario = f"ERRO_CENARIO: {type(e).__name__}"

            cenarios[nome_cenario] += 1

        cobertura = (classificados / total * 100) if total else 0

        print("\n===== COBERTURA CATALOGO TRANSP =====")
        print(f"TOTAL ITENS...........: {total}")
        print(f"CLASSIFICADOS.........: {classificados}")
        print(f"NAO CLASSIFICADOS.....: {nao_classificados}")
        print(f"COBERTURA.............: {cobertura:.2f}%")

        print("\n===== CLASSIFICADOS POR CATEGORIA =====")
        for categoria, dados in sorted(
            por_categoria.items(),
            key=lambda x: x[1]["valor"],
            reverse=True,
        ):
            print(
                f"{categoria:<45} "
                f"qtd={dados['qtd']:<8} "
                f"valor={dados['valor']:.2f}"
            )

        print("\n===== CENARIOS IDENTIFICADOS =====")
        for nome, qtd in cenarios.most_common(50):
            print(f"{nome:<55} qtd={qtd}")

        print("\n===== TOP CFOP POR VALOR =====")
        for cfop, dados in sorted(
            por_cfop.items(),
            key=lambda x: x[1]["valor"],
            reverse=True,
        )[:30]:
            print(f"CFOP={cfop:<8} qtd={dados['qtd']:<8} valor={dados['valor']:.2f}")

        print("\n===== TOP CST PIS POR VALOR =====")
        for cst, dados in sorted(
            por_cst.items(),
            key=lambda x: x[1]["valor"],
            reverse=True,
        )[:30]:
            print(f"CST={cst:<8} qtd={dados['qtd']:<8} valor={dados['valor']:.2f}")

        print("\n===== TOP NCM POR VALOR =====")
        for ncm, dados in sorted(
            por_ncm.items(),
            key=lambda x: x[1]["valor"],
            reverse=True,
        )[:50]:
            print(
                f"NCM={ncm:<10} "
                f"qtd={dados['qtd']:<8} "
                f"valor={dados['valor']:.2f} "
                f"categorias={dados['categorias'].most_common(3)}"
            )

        print("\n===== TOP NAO CLASSIFICADOS POR VALOR =====")
        for desc, dados in sorted(
            nao_classificados_desc.items(),
            key=lambda x: x[1]["valor"],
            reverse=True,
        )[:50]:
            print()
            print(desc)
            print(f"  qtd.....: {dados['qtd']}")
            print(f"  valor...: {dados['valor']:.2f}")
            print(f"  ncm.....: {dados['ncm'].most_common(5)}")
            print(f"  cfop....: {dados['cfop'].most_common(5)}")
            print(f"  cst.....: {dados['cst'].most_common(5)}")

        print("\n===== TOP NAO CLASSIFICADOS POR QUANTIDADE =====")
        for desc, dados in sorted(
            nao_classificados_desc.items(),
            key=lambda x: x[1]["qtd"],
            reverse=True,
        )[:50]:
            print()
            print(desc)
            print(f"  qtd.....: {dados['qtd']}")
            print(f"  valor...: {dados['valor']:.2f}")
            print(f"  ncm.....: {dados['ncm'].most_common(5)}")
            print(f"  cfop....: {dados['cfop'].most_common(5)}")
            print(f"  cst.....: {dados['cst'].most_common(5)}")

        print("\n===== AMOSTRAS POR CATEGORIA =====")
        for categoria, amostras in sorted(amostras_por_categoria.items()):
            print()
            print(f"--- {categoria} ---")
            for a in amostras:
                print(
                    f"{a['descricao'][:90]} | "
                    f"NCM={a['ncm']} | "
                    f"CFOP={a['cfop']} | "
                    f"CST={a['cst']} | "
                    f"VALOR={a['valor']:.2f}"
                )

        assert total > 0

    finally:
        db.close()


if __name__ == "__main__":
    main()