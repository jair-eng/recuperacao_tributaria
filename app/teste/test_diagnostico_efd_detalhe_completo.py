# app/teste/test_diagnostico_efd_detalhe_completo.py

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

        print("\n========== DIAGNOSTICO EFD ==========")

        for nat, dados in sorted(ctx["por_natureza"].items()):
            print("-" * 80)
            print("NAT:", nat)
            print("Status:", dados.get("status"))
            print("Base ECD Esperada:", fmt(dados.get("valor_ecd")))
            print("Base EFD Declarada:", fmt(dados.get("valor_efd")))
            print("GAP:", fmt(dados.get("valor_gap")))
            print("Categorias:", dados.get("categorias"))
            print("Contas ECD:", dados.get("contas_ecd"))

        print("\n========== DETALHE COMPLETO ==========")

        for nat, dados in sorted(ctx["por_natureza"].items()):
            print("-" * 80)
            print("Natureza:", nat)
            print("Status:", dados.get("status"))

            print("\nBases:")
            print("  ECD esperada:", fmt(dados.get("valor_ecd")))
            print("  EFD declarada:", fmt(dados.get("valor_efd")))
            print("  GAP:", fmt(dados.get("valor_gap")))

            print("\nClassificação ECD:")
            print("  Categorias:", dados.get("categorias"))
            print("  Grupos:", dados.get("grupos"))
            print("  Fundamentos:", dados.get("fundamentos"))
            print("  Naturezas esperadas:", dados.get("naturezas_esperadas"))

            print("\nRastreabilidade:")
            print("  Contas ECD:", dados.get("contas_ecd"))
            print("  Origens:", dados.get("origens"))

            if dados.get("status") == "SEM_EFD":
                print("\nDiagnóstico:")
                print("  ECD possui base elegível, mas a EFD não declarou base nesta natureza.")

            elif dados.get("status") == "SEM_ECD":
                print("\nDiagnóstico:")
                print("  EFD declarou base, mas não há conta ECD elegível vinculada a esta natureza.")

            elif dados.get("status") == "PARCIAL":
                print("\nDiagnóstico:")
                print("  EFD declarou parcialmente a base esperada pela ECD.")

            elif dados.get("status") == "COBERTO":
                print("\nDiagnóstico:")
                print("  Base EFD cobre integralmente a base esperada pela ECD.")

            elif dados.get("status") == "EXCEDENTE_EFD":
                print("\nDiagnóstico:")
                print("  EFD declarou base superior à base esperada pela ECD.")

        print("\n========== RESUMO ==========")
        print(ctx["resumo"])

    finally:
        db.close()


if __name__ == "__main__":
    main()