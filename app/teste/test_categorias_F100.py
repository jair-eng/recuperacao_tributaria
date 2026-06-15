from pathlib import Path
from collections import defaultdict
from decimal import Decimal

from app.db.session import SessionLocal
from app.domain.fiscal.bloco_0.reg0150_loader_local import carregar_0150_local
from app.domain.fiscal.bloco_F.f100_contexto import classificar_registro_f100_por_natureza
from app.domain.fiscal.bloco_F.f100_loader_local import carregar_f100_local
from app.domain.fiscal.bloco_F.f100_participantes import enriquecer_f100_com_participantes
from app.domain.sped.maps.reg0150_map import montar_mapa_participantes_0150
from app.utils.numbers import to_decimal
from app.utils.sped import listar_txt


PASTA_CONTRIB = Path(r"C:\Sped\CONTRIB")
EMPRESA_ANALISADA = "GO SERV TRANSPORTES"


def eh_propria_empresa(item: dict) -> bool:
    nome = str(item.get("participante_nome") or "").upper()
    return EMPRESA_ANALISADA in nome


def chave_participante(item: dict) -> str:
    return item.get("participante_nome") or "NÃO IDENTIFICADO"


def novo_agregado():
    return {
        "qtd": 0,
        "vl_oper": Decimal("0.00"),
        "vl_bc_pis": Decimal("0.00"),
        "vl_pis": Decimal("0.00"),
        "vl_bc_cofins": Decimal("0.00"),
        "vl_cofins": Decimal("0.00"),
        "exemplos": [],
    }


def adicionar_agregado(agg: dict, item: dict, *, limite_exemplos: int = 15) -> None:
    agg["qtd"] += 1
    agg["vl_oper"] += to_decimal(item.get("vl_oper"))
    agg["vl_bc_pis"] += to_decimal(item.get("vl_bc_pis"))
    agg["vl_pis"] += to_decimal(item.get("vl_pis"))
    agg["vl_bc_cofins"] += to_decimal(item.get("vl_bc_cofins"))
    agg["vl_cofins"] += to_decimal(item.get("vl_cofins"))

    if len(agg["exemplos"]) < limite_exemplos:
        agg["exemplos"].append({
            "cod_part": item.get("cod_part"),
            "participante": item.get("participante_nome"),
            "tipo": item.get("participante_tipo"),
            "cnpj": item.get("participante_cnpj"),
            "cpf": item.get("participante_cpf"),
            "descr_compl": item.get("descr_compl"),
            "vl_oper": item.get("vl_oper"),
            "vl_bc_pis": item.get("vl_bc_pis"),
            "vl_pis": item.get("vl_pis"),
            "vl_bc_cofins": item.get("vl_bc_cofins"),
            "vl_cofins": item.get("vl_cofins"),
            "nat_bc_cred": item.get("nat_bc_cred"),
            "categoria": item.get("categoria"),
            "grupo": item.get("grupo"),
            "fundamento": item.get("fundamento"),
            "origem_classificacao": item.get("origem_classificacao"),
            "arquivo": item.get("arquivo"),
        })


def imprimir_agregado(titulo: str, dados: dict, *, mostrar_exemplos: bool = True) -> None:
    print("\n" + "=" * 100)
    print(titulo)
    print("=" * 100)
    print("QTD:", dados["qtd"])
    print("VL_OPER:", dados["vl_oper"])
    print("VL_BC_PIS:", dados["vl_bc_pis"])
    print("VL_PIS:", dados["vl_pis"])
    print("VL_BC_COFINS:", dados["vl_bc_cofins"])
    print("VL_COFINS:", dados["vl_cofins"])

    if not mostrar_exemplos:
        return

    print("EXEMPLOS:")
    for ex in dados["exemplos"]:
        print(
            " -",
            ex["participante"],
            "| tipo:", ex["tipo"],
            "| cod_part:", ex["cod_part"],
            "| cnpj:", ex["cnpj"],
            "| cpf:", ex["cpf"],
            "| nat:", ex["nat_bc_cred"],
            "| valor:", ex["vl_oper"],
            "| pis:", ex["vl_pis"],
            "| cofins:", ex["vl_cofins"],
            "| grupo:", ex["grupo"],
            "| fundamento:", ex["fundamento"],
            "| origem:", ex["origem_classificacao"],
            "| desc:", ex["descr_compl"],
        )


def main():
    db = SessionLocal()

    try:
        arquivos_contrib = listar_txt(PASTA_CONTRIB)

        registros_0150 = carregar_0150_local(arquivos_contrib)
        mapa_participantes = montar_mapa_participantes_0150(registros_0150)

        f100 = carregar_f100_local(arquivos_contrib)
        f100 = enriquecer_f100_com_participantes(
            f100,
            mapa_participantes,
        )

        qtd_original = len(f100)
        total_original = sum(to_decimal(i.get("vl_oper")) for i in f100)

        f100 = [
            item for item in f100
            if not eh_propria_empresa(item)
        ]

        qtd_sem_propria = len(f100)
        total_sem_propria = sum(to_decimal(i.get("vl_oper")) for i in f100)

        classificados = [
            classificar_registro_f100_por_natureza(
                db=db,
                item=item,
            )
            for item in f100
        ]

        por_tipo = defaultdict(lambda: Decimal("0.00"))
        por_categoria = defaultdict(novo_agregado)
        por_natureza = defaultdict(novo_agregado)
        por_participante = defaultdict(novo_agregado)
        por_categoria_participante = defaultdict(novo_agregado)

        for item in classificados:
            tipo = item.get("participante_tipo") or "N/I"
            categoria = item.get("categoria") or "NaoClassificado"
            nat = str(item.get("nat_bc_cred") or "00").zfill(2)
            participante = chave_participante(item)

            por_tipo[tipo] += to_decimal(item.get("vl_oper"))

            adicionar_agregado(por_categoria[categoria], item)
            adicionar_agregado(por_natureza[nat], item)
            adicionar_agregado(por_participante[participante], item)

            chave_cat_part = f"{categoria} | {participante}"
            adicionar_agregado(
                por_categoria_participante[chave_cat_part],
                item,
                limite_exemplos=3,
            )

        print("\nRESUMO F100")
        print("QTD ORIGINAL:", qtd_original)
        print("TOTAL ORIGINAL:", total_original)
        print("QTD SEM PRÓPRIA EMPRESA:", qtd_sem_propria)
        print("TOTAL SEM PRÓPRIA EMPRESA:", total_sem_propria)

        print("\nPOR TIPO")
        for tipo, valor in sorted(por_tipo.items()):
            print(tipo, valor)

        print("\nPOR CATEGORIA")
        for categoria, dados in sorted(
            por_categoria.items(),
            key=lambda x: x[1]["vl_oper"],
            reverse=True,
        ):
            imprimir_agregado(categoria, dados)

        print("\nPOR NATUREZA")
        for nat, dados in sorted(
            por_natureza.items(),
            key=lambda x: x[1]["vl_oper"],
            reverse=True,
        ):
            imprimir_agregado(f"NAT {nat}", dados, mostrar_exemplos=False)

        print("\nTOP 100 PARTICIPANTES")
        for participante, dados in sorted(
            por_participante.items(),
            key=lambda x: x[1]["vl_oper"],
            reverse=True,
        )[:200]:
            print(
                participante,
                "| qtd:", dados["qtd"],
                "| valor:", dados["vl_oper"],
                "| pis:", dados["vl_pis"],
                "| cofins:", dados["vl_cofins"],
            )

        print("\nTOP 100 CATEGORIA + PARTICIPANTE")
        for chave, dados in sorted(
            por_categoria_participante.items(),
            key=lambda x: x[1]["vl_oper"],
            reverse=True,
        )[:200]:
            print(
                chave,
                "| qtd:", dados["qtd"],
                "| valor:", dados["vl_oper"],
                "| pis:", dados["vl_pis"],
                "| cofins:", dados["vl_cofins"],
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()