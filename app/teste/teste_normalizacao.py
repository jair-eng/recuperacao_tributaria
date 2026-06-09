from pathlib import Path

from app.db.session import SessionLocal

from app.domain.fiscal.bloco_0.reg0150_loader_local import carregar_0150_local
from app.domain.fiscal.bloco_F.f100_contexto import montar_contexto_f100
from app.domain.fiscal.bloco_F.f100_loader_local import carregar_f100_local
from app.domain.fiscal.bloco_F.f100_participantes import enriquecer_f100_com_participantes
from app.domain.sped.maps.reg0150_map import montar_mapa_participantes_0150


arquivo_contrib = Path(r"C:\Sped\CONTRIB\arquivo_teste.txt")

db = SessionLocal()

try:
    f100 = carregar_f100_local([arquivo_contrib])

    registros_0150_contrib = carregar_0150_local([arquivo_contrib])
    mapa_participantes_contrib = montar_mapa_participantes_0150(
        registros_0150_contrib
    )

    f100 = enriquecer_f100_com_participantes(
        f100,
        mapa_participantes_contrib,
    )

    ctx_f100 = montar_contexto_f100(
        f100,
        db=db,
        fonte="LOCAL",
    )


    print("QTD F100:", ctx_f100["qtd_f100"])
    print("QTD PF:", ctx_f100["qtd_pf"])
    print("QTD PJ:", ctx_f100["qtd_pj"])
    print("VL TOTAL:", ctx_f100["vl_total"])

    print("\nCST60 NAT14:")
    print(ctx_f100["cst60_nat14"])

    print("\nPRIMEIROS CLASSIFICADOS:")
    for item in ctx_f100["registros"][:10]:
        print(
            item.get("participante_tipo"),
            item.get("participante_nome"),
            item.get("desc_doc_oper"),
            "=>",
            item.get("categoria"),
            item.get("grupo"),
            item.get("naturezas_esperadas"),
            item.get("fundamento"),
            item.get("confianca"),
        )

finally:
    db.close()