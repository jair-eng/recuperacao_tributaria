from app.db.session import SessionLocal
from app.db.models.efd_registro import EfdRegistro
from app.db.models.item_fiscal_consolidado import ItemFiscalConsolidado


VERSAO_ID = 1


def main():
    db = SessionLocal()

    try:
        qtd_c170 = (
            db.query(EfdRegistro)
            .filter(
                EfdRegistro.versao_id == VERSAO_ID,
                EfdRegistro.reg == "C170",
            )
            .count()
        )

        itens = (
            db.query(ItemFiscalConsolidado)
            .filter(ItemFiscalConsolidado.versao_id == VERSAO_ID)
            .order_by(
                ItemFiscalConsolidado.chave_nfe,
                ItemFiscalConsolidado.num_item,
            )
            .all()
        )

        print("\n=== RESUMO ===")
        print("C170 no EfdRegistro:", qtd_c170)
        print("Itens consolidados:", len(itens))

        print("\n=== ITENS CONSOLIDADOS ===")
        for item in itens:
            print("-" * 80)
            print("id:", item.id)
            print("chave_nfe:", item.chave_nfe)
            print("num_item:", item.num_item)
            print("cod_item:", item.cod_item)
            print("descricao:", item.descr_item)
            print("ncm:", item.ncm)
            print("cfop:", item.cfop)
            print("cst_pis:", item.cst_pis)
            print("cst_cofins:", item.cst_cofins)
            print("vl_item:", item.vl_item)
            print("vl_desc:", item.vl_desc)
            print("vl_icms:", item.vl_icms)
            print("cod_part:", item.cod_part)
            print("participante_nome:", item.participante_nome)
            print("cod_cta:", item.cod_cta)
            print("status_cruzamento:", item.status_cruzamento)
            print("tem_no_contrib:", item.tem_no_contrib)
            print("tem_no_icms:", item.tem_no_icms)
            print("registro_c100_id:", item.registro_id_c100)
            print("registro_c170_id:", item.registro_id_c170)
            print("nf_icms_item_id:", item.nf_icms_item_id)

    finally:
        db.close()


if __name__ == "__main__":
    main()