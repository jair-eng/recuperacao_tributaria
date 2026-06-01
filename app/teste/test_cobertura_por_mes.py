# app/teste/test_cobertura_por_mes.py

from decimal import Decimal
from app.db.session import SessionLocal
from app.domain.ecd.ecd_gap_service import montar_contexto_gap_ecd_efd


def fmt(v):
    if v is None:
        return "0,00"
    if not isinstance(v, Decimal):
        v = Decimal(str(v or "0"))
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


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

        ecd = Decimal(str(resumo.get("total_ecd_elegivel") or "0"))
        efd = Decimal(str(resumo.get("total_efd_declarada") or "0"))
        gap = Decimal(str(resumo.get("total_gap") or "0"))

        if ecd > 0:
            cobertura = ((efd / ecd) * Decimal("100")).quantize(Decimal("0.01"))
        else:
            cobertura = Decimal("0.00")

        if efd <= 0:
            status = "ZERADO"
        elif ecd <= 0 and efd > 0:
            status = "SEM_ECD"
        else:
            status = "OK"

        print("\n========== COBERTURA POR MÊS ==========")
        print("Ano-Mês:", periodo)
        print("Despesa Elegível ECD:", fmt(ecd))
        print("Base Declarada EFD:", fmt(efd))
        print("GAP Mensal:", fmt(gap if gap > 0 else Decimal("0")))
        print("% Cobertura:", f"{cobertura}%")
        print("Status EFD:", status)

        print("\n========== DETALHE POR NATUREZA ==========")
        for nat, dados in sorted(ctx["por_natureza"].items()):
            print("-" * 80)
            print("NAT:", nat)
            print("ECD:", fmt(dados.get("valor_ecd")))
            print("EFD:", fmt(dados.get("valor_efd")))
            print("GAP:", fmt(dados.get("valor_gap")))
            print("Status:", dados.get("status"))
            print("Categorias:", dados.get("categorias"))

    finally:
        db.close()


if __name__ == "__main__":
    main()