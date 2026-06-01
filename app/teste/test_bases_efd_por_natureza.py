
from app.db.session import SessionLocal
from app.domain.ecd.ecd_gap_service import montar_contexto_gap_ecd_efd


def main():
    db = SessionLocal()

    try:
        empresa_id = 1
        versao_id = 4
        periodo = "202211"  # ajuste para sua versão

        ctx = montar_contexto_gap_ecd_efd(
            db,
            empresa_id=empresa_id,
            versao_id=versao_id,
            periodo=periodo,
        )

        print("\n========== RESUMO ==========")
        print(ctx["resumo"])

        print("\n========== BASES POR NATUREZA ==========")
        for nat, dados in sorted(ctx["por_natureza"].items()):
            print("-" * 80)
            print("NAT:", nat)
            print("valor_ecd:", dados.get("valor_ecd"))
            print("valor_efd:", dados.get("valor_efd"))
            print("gap:", dados.get("valor_gap"))
            print("status:", dados.get("status"))
            print("contas_ecd:", dados.get("contas_ecd"))
            print("origens:", dados.get("origens"))
            print("categorias:", dados.get("categorias"))
            print("grupos:", dados.get("grupos"))
            print("fundamentos:", dados.get("fundamentos"))
            print("naturezas_esperadas:", dados.get("naturezas_esperadas"))

    finally:
        db.close()


if __name__ == "__main__":
    main()