# app/teste/test_resumo_executivo_gap_ecd_efd.py

from decimal import Decimal
from app.db.session import SessionLocal
from app.domain.ecd.ecd_gap_service import montar_contexto_gap_ecd_efd


def fmt(v):
    if v is None:
        return "0,00"

    if not isinstance(v, Decimal):
        v = Decimal(str(v or "0"))

    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v):
    if v is None:
        return "0,00%"

    if not isinstance(v, Decimal):
        v = Decimal(str(v or "0"))

    return f"{v:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    db = SessionLocal()

    try:
        empresa_id = 1
        versao_id = 4
        periodo = "202211"

        ctx = montar_contexto_gap_ecd_efd(
            db,
            empresa_id=empresa_id,
            versao_id=versao_id,
            periodo=periodo,
        )

        resumo = ctx["resumo"]
        por_natureza = ctx["por_natureza"]

        total_ecd = Decimal(str(resumo.get("total_ecd_elegivel") or "0"))
        total_efd = Decimal(str(resumo.get("total_efd_declarada") or "0"))
        total_gap = Decimal(str(resumo.get("total_gap") or "0"))
        total_gap_positivo = Decimal(str(resumo.get("total_gap_positivo") or "0"))
        total_gap_negativo = Decimal(str(resumo.get("total_gap_negativo") or "0"))

        cobertura_pct = (
            ((total_efd / total_ecd) * Decimal("100")).quantize(Decimal("0.01"))
            if total_ecd > 0
            else Decimal("0.00")
        )

        qtd_sem_efd = 0
        qtd_sem_ecd = 0
        qtd_parcial = 0
        qtd_coberto = 0
        qtd_excedente = 0

        for _, dados in por_natureza.items():
            status = dados.get("status")

            if status == "SEM_EFD":
                qtd_sem_efd += 1
            elif status == "SEM_ECD":
                qtd_sem_ecd += 1
            elif status == "PARCIAL":
                qtd_parcial += 1
            elif status == "COBERTO":
                qtd_coberto += 1
            elif status == "EXCEDENTE_EFD":
                qtd_excedente += 1

        if total_ecd <= 0 and total_efd <= 0:
            status_geral = "SEM_DADOS"
        elif total_ecd > 0 and total_efd <= 0:
            status_geral = "EFD_ZERADA_COM_ECD"
        elif cobertura_pct < Decimal("70.00"):
            status_geral = "BAIXA_COBERTURA"
        elif total_gap_positivo > 0:
            status_geral = "COM_GAP"
        else:
            status_geral = "OK"

        print("\n========== RESUMO EXECUTIVO ==========")
        print("Período:", periodo)
        print("Status Geral:", status_geral)
        print("Cobertura EFD:", pct(cobertura_pct))

        print("\n========== VALORES ==========")
        print("Total ECD Elegível:", fmt(total_ecd))
        print("Total EFD Declarada:", fmt(total_efd))
        print("GAP Líquido:", fmt(total_gap))
        print("GAP Positivo:", fmt(total_gap_positivo))
        print("GAP Negativo:", fmt(total_gap_negativo))

        print("\n========== NATUREZAS ==========")
        print("Total Naturezas:", resumo.get("total_naturezas"))
        print("Naturezas com GAP Positivo:", resumo.get("naturezas_com_gap_positivo"))
        print("Naturezas com GAP Negativo:", resumo.get("naturezas_com_gap_negativo"))

        print("\n========== STATUS POR NATUREZA ==========")
        print("SEM_EFD:", qtd_sem_efd)
        print("SEM_ECD:", qtd_sem_ecd)
        print("PARCIAL:", qtd_parcial)
        print("COBERTO:", qtd_coberto)
        print("EXCEDENTE_EFD:", qtd_excedente)

        print("\n========== TOP GAPS ==========")
        gaps = []

        for nat, dados in por_natureza.items():
            valor_gap = Decimal(str(dados.get("valor_gap") or "0"))

            if valor_gap > 0:
                gaps.append(
                    {
                        "nat": nat,
                        "gap": valor_gap,
                        "ecd": dados.get("valor_ecd"),
                        "efd": dados.get("valor_efd"),
                        "status": dados.get("status"),
                        "categorias": dados.get("categorias") or [],
                    }
                )

        gaps = sorted(gaps, key=lambda x: x["gap"], reverse=True)

        for item in gaps[:10]:
            print("-" * 80)
            print("NAT:", item["nat"])
            print("Status:", item["status"])
            print("GAP:", fmt(item["gap"]))
            print("ECD:", fmt(item["ecd"]))
            print("EFD:", fmt(item["efd"]))
            print("Categorias:", item["categorias"])

    finally:
        db.close()


if __name__ == "__main__":
    main()