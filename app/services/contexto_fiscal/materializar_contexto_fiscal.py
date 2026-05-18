from sqlalchemy.orm import Session

from app.db.session import SessionLocal

from app.db.models import (
    EfdVersao,
    EfdRegistro,
    ContextoFiscalVersao,
    ItemFiscalConsolidado, NfIcmsItem,
)
from app.domain.sped.maps.icms_item_map import montar_mapa_icms_item, buscar_icms_item_em_mapa
from app.domain.sped.maps.reg0150_map import IDX_0150
from app.domain.sped.maps.reg0200_map import IDX_0200
from app.utils.icms_match import buscar_icms_item
from app.utils.json_utils import campos_json
from app.utils.list_utils import get_safe
from app.utils.numbers import dec_any


def materializar_contexto_fiscal(db: Session, versao_id: int):
    print(f"[CTX] iniciando materialização versao={versao_id}")
    db.query(ItemFiscalConsolidado).filter(
        ItemFiscalConsolidado.versao_id == versao_id
    ).delete(synchronize_session=False)

    db.flush()

    versao = db.query(EfdVersao).filter(EfdVersao.id == versao_id).first()
    if not versao:
        raise ValueError("Versão não encontrada")

    contexto = ContextoFiscalVersao(
        empresa_id=versao.empresa_id,
        versao_id=versao.id,
        periodo=versao.periodo,
        dominio=versao.dominio,
        status="PROCESSANDO",
    )
    db.add(contexto)
    db.flush()

    registros = (
        db.query(EfdRegistro)
        .filter(EfdRegistro.versao_id == versao.id)
        .order_by(EfdRegistro.linha)
        .all()
    )

    print(f"[CTX] registros carregados qtd={len(registros)}")

    mapa_0150 = {}
    mapa_0200 = {}

    for r in registros:
        campos = campos_json(r.conteudo_json)

        if r.reg == "0150":
            cod_part_0150 = str(get_safe(campos, IDX_0150["cod_part"]) or "").strip()
            if cod_part_0150:
                mapa_0150[cod_part_0150] = campos

        elif r.reg == "0200":
            cod_item_0200 = str(get_safe(campos, IDX_0200["cod_item"]) or "").strip()
            if cod_item_0200:
                mapa_0200[cod_item_0200] = campos

    print(
        "[CTX] mapas carregados",
        "0150=", len(mapa_0150),
        "0200=", len(mapa_0200),
        flush=True,
    )
    periodo_base = str(versao.periodo or "").strip()

    if not periodo_base:
        for r in registros:
            if r.reg == "C100":
                c100_tmp = campos_json(r.conteudo_json)
                dt_doc = str(get_safe(c100_tmp, 8) or "").strip()
                if len(dt_doc) == 8:
                    periodo_base = dt_doc[4:8] + dt_doc[2:4]
                    break

    mapa_icms = montar_mapa_icms_item(
        db,
        empresa_id=versao.empresa_id,
        periodo=periodo_base,
    )

    print(
        "[CTX] mapa ICMS carregado",
        "periodo=", periodo_base,
        "full=", len(mapa_icms["full"]),
        "cod=", len(mapa_icms["cod"]),
        "num=", len(mapa_icms["num"]),
        flush=True,
    )

    c100_atual = None
    qtd_itens = 0

    for reg in registros:
        if reg.reg == "C100":
            c100_atual = reg
            continue

        if reg.reg != "C170":
            continue

        if not c100_atual:
            continue

        c100 = campos_json(c100_atual.conteudo_json)
        c170 = campos_json(reg.conteudo_json)
        periodo = str(versao.periodo or "").strip()

        if not periodo:
            dt_doc = str(get_safe(c100, 8) or "").strip()  # C100 DT_DOC: ddmmaaaa
            if len(dt_doc) == 8:
                periodo = dt_doc[4:8] + dt_doc[2:4]  # aaaamm
        chave_nfe = str(get_safe(c100, 7) or "").strip()
        num_item = str(get_safe(c170, 0) or "").strip()

        cod_item = str(get_safe(c170, 1) or "").strip()

        icms_item = buscar_icms_item_em_mapa(
            mapa_icms,
            chave_nfe=chave_nfe,
            num_item=num_item,
            cod_item=cod_item,
        )

        tem_no_icms = icms_item is not None

        cod_part = str(get_safe(c100, 2) or "").strip()

        part_0150 = mapa_0150.get(cod_part)
        item_0200 = mapa_0200.get(cod_item)



        participante_nome = (
            icms_item.participante_nome
            if icms_item and icms_item.participante_nome
            else get_safe(part_0150, IDX_0150["nome"])
            if part_0150
            else None
        )

        participante_doc = None
        participante_tipo_doc = None

        if icms_item and icms_item.participante_cnpj:
            participante_doc = icms_item.participante_cnpj
            participante_tipo_doc = "CNPJ"
        elif part_0150:
            cnpj = get_safe(part_0150, IDX_0150["cnpj"])
            cpf = get_safe(part_0150, IDX_0150["cpf"])

            if cnpj:
                participante_doc = cnpj
                participante_tipo_doc = "CNPJ"
            elif cpf:
                participante_doc = cpf
                participante_tipo_doc = "CPF"

        ncm = (
            icms_item.ncm
            if icms_item and icms_item.ncm
            else get_safe(item_0200, IDX_0200["cod_ncm"])
            if item_0200
            else None
        )


        item = ItemFiscalConsolidado(
            contexto_id=contexto.id,
            empresa_id=versao.empresa_id,
            versao_id=versao.id,
            periodo=periodo,

            registro_id_c100=c100_atual.id,
            registro_id_c170=reg.id,
            nf_icms_item_id=icms_item.id if icms_item else None,

            tem_no_contrib=True,
            tem_no_icms=tem_no_icms,
            status_cruzamento="MATCH" if tem_no_icms else "SO_CONTRIB",

            cod_part=cod_part,
            participante_nome=participante_nome,
            participante_doc=participante_doc,
            participante_tipo_doc=participante_tipo_doc,

            cod_mod=get_safe(c100, 3),
            serie=get_safe(c100, 5),
            num_doc=get_safe(c100, 6),
            chave_nfe=chave_nfe,
            dt_doc=get_safe(c100, 8),

            num_item=num_item,
            cod_item=cod_item,
            descr_item=get_safe(c170, 2),
            ncm=ncm,

            vl_item=dec_any(get_safe(c170, 5)),
            vl_desc=dec_any(get_safe(c170, 6)),
            vl_icms=icms_item.vl_icms if icms_item else None,

            cst_icms=get_safe(c170, 8),
            cfop=get_safe(c170, 9),

            cst_pis=get_safe(c170, 23),
            vl_bc_pis=dec_any(get_safe(c170, 24)),
            vl_pis=dec_any(get_safe(c170, 28)),

            cst_cofins=get_safe(c170, 29),
            vl_bc_cofins=dec_any(get_safe(c170, 30)),
            vl_cofins=dec_any(get_safe(c170, 34)),

            cod_cta=get_safe(c170, 36),

            dominio=versao.dominio,
            regime=None,

            meta={
                "origem": "EFD_CONTRIBUICOES",
                "linha_c100": c100_atual.linha,
                "linha_c170": reg.linha,
                "icms_match": bool(icms_item),
            },
        )
        db.add(item)
        qtd_itens += 1

    contexto.status = "FINALIZADO"
    db.commit()

    print(f"[CTX] finalizado | itens={qtd_itens}")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        materializar_contexto_fiscal(db, versao_id=1)
    finally:
        db.close()