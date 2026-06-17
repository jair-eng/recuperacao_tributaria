from pathlib import Path
from collections import Counter
from decimal import Decimal
from app.db.session import SessionLocal
from app.domain.relatorio_executivo.IcmsContribuicao.c170_icms_loader_local import carregar_c170_icms_local
from app.domain.relatorio_executivo.IcmsContribuicao.c170_oportunidades_local import \
    diagnosticar_oportunidades_c170_local
from app.domain.relatorio_executivo.IcmsContribuicao.cruzar_c170_icms_contrib_local import \
    cruzar_c170_icms_contrib_local
from app.domain.relatorio_executivo.c170_loader_local import carregar_c170_local
from app.utils.numbers import to_decimal


PASTA_ICMS = Path(r"C:\Sped\ICMS_IPI")
PASTA_CONTRIB = Path(r"C:\Sped\CONTRIB")


def main():
    db = SessionLocal()

    try:
        c170_icms = carregar_c170_icms_local(
            arquivos_icms=sorted(PASTA_ICMS.glob("*.txt")),
        )

        c170_contrib = carregar_c170_local(
            arquivos_contrib=sorted(PASTA_CONTRIB.glob("*.txt")),
        )

        linhas_cruzadas = cruzar_c170_icms_contrib_local(
            c170_icms=c170_icms,
            c170_contrib=c170_contrib,
        )

        oportunidades = diagnosticar_oportunidades_c170_local(
            db=db,
            linhas_cruzadas=linhas_cruzadas[:2000],
            dominio="TRANSP",
        )

        print("=" * 80)
        print("OPORTUNIDADES C170 LOCAL")
        print("=" * 80)

        print("C170 ICMS:", len(c170_icms))
        print("C170 CONTRIB:", len(c170_contrib))
        print("LINHAS CRUZADAS:", len(linhas_cruzadas))
        print("OPORTUNIDADES:", len(oportunidades))

        por_status = Counter(x.get("status_oportunidade") for x in oportunidades)
        por_categoria = Counter(x.get("categoria") for x in oportunidades)
        por_nat = Counter(x.get("nat_bc_cred") for x in oportunidades)

        total_base = sum(
            (to_decimal(x.get("base_recuperavel")) for x in oportunidades),
            Decimal("0.00"),
        )
        total_pis = sum(
            (to_decimal(x.get("pis_recuperavel")) for x in oportunidades),
            Decimal("0.00"),
        )
        total_cofins = sum(
            (to_decimal(x.get("cofins_recuperavel")) for x in oportunidades),
            Decimal("0.00"),
        )

        print()
        print("TOTAL BASE:", total_base)
        print("TOTAL PIS:", total_pis)
        print("TOTAL COFINS:", total_cofins)
        print("TOTAL CRÉDITO:", total_pis + total_cofins)

        print()
        print("POR STATUS")
        for k, v in por_status.most_common():
            print(k, v)

        print()

        print("OPORTUNIDADES:", len(oportunidades))
        print("TOTAL BASE:", total_base)
        print("TOTAL CRÉDITO:", total_pis + total_cofins)

        print("POR STATUS")
        for k, v in por_status.most_common():
            print(k, v)

        print("POR CATEGORIA")
        for k, v in por_categoria.most_common(20):
            print(k, v)

        print("POR NAT")
        for k, v in por_nat.most_common(20):
            print(k, v)

        for x in oportunidades[:10]:
            print(x["periodo"], x["status_oportunidade"], x["categoria"], x["cfop"], x["descricao"],
                  x["base_recuperavel"], x["credito_recuperavel"])

        for x in c170_icms[:20]:
            print(
                x.get("cod_item"),
                x.get("descr_item"),
                x.get("ncm"),
                x.get("cod_ncm"),
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()