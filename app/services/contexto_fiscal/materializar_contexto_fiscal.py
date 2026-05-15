from sqlalchemy.orm import Session

from app.db.session import SessionLocal

from app.db.models import (
    EfdVersao,
    EfdRegistro,
    ContextoFiscalVersao,
    ItemFiscalConsolidado,
)
from app.utils.json_utils import campos_json
from app.utils.list_utils import get_safe
from app.utils.numbers import dec_any


def materializar_contexto_fiscal(db: Session, versao_id: int):
    print(f"[CTX] iniciando materialização versao={versao_id}")

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

        item = ItemFiscalConsolidado(
            contexto_id=contexto.id,
            empresa_id=versao.empresa_id,
            versao_id=versao.id,
            periodo=versao.periodo,

            registro_id_c100=c100_atual.id,
            registro_id_c170=reg.id,

            tem_no_contrib=True,
            tem_no_icms=False,
            status_cruzamento="SO_CONTRIB",

            cod_part=get_safe(c100, 2),
            cod_mod=get_safe(c100, 3),
            serie=get_safe(c100, 5),
            num_doc=get_safe(c100, 6),
            chave_nfe=get_safe(c100, 7),
            dt_doc=get_safe(c100, 8),

            num_item=get_safe(c170, 0),
            cod_item=get_safe(c170, 1),
            descr_item=get_safe(c170, 2),
            vl_item=dec_any(get_safe(c170, 5)),
            vl_desc=dec_any(get_safe(c170, 6)),
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