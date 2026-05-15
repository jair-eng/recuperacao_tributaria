from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.icms_ipi.icms_ipi_cruzamento_service import cruzar_versao_com_icms_ipi
from app.db.models.efd_revisao import EfdRevisao


def run_test():
    db: Session = SessionLocal()

    versao_id = 90   # <-- AJUSTA AQUI
    empresa_id = 10  # <-- AJUSTA AQUI
    periodo = "202206"

    print("\n==============================")
    print("TESTE CRUZAMENTO SEM INSERT")
    print("==============================")

    # -----------------------------
    # 1) Contar revisões antes
    # -----------------------------
    before = db.query(EfdRevisao).filter(
        EfdRevisao.versao_origem_id == versao_id
    ).count()

    print(f"Revisões antes: {before}")

    # -----------------------------
    # 2) Rodar cruzamento (modo diagnóstico)
    # -----------------------------
    res = cruzar_versao_com_icms_ipi(
        db=db,
        versao_origem_id=versao_id,
        empresa_id=empresa_id,
        periodo=periodo,
        usar_overlay=True,
        aplicar_revisoes_insert=False,  # 🚨 ponto chave
    )

    print(f"\nOK: {res.get('ok')}")
    print(f"Total itens analisados: {len(res.get('itens', []))}")

    # -----------------------------
    # 3) Filtrar itens sem C170
    # -----------------------------
    faltantes = [
        i for i in res.get("itens", [])
        if i.get("tipo_match") == "CONTRIB_SEM_C170"
    ]

    print(f"\nItens sem C170: {len(faltantes)}")

    for i in faltantes:
        print({
            "chave_nfe": i.get("chave_nfe"),
            "registro_id_ancora": i.get("registro_id_ancora"),
            "linha_ancora": i.get("linha_ancora"),
            "status": i.get("status"),
        })

    # -----------------------------
    # 4) Contar revisões depois
    # -----------------------------
    after = db.query(EfdRevisao).filter(
        EfdRevisao.versao_origem_id == versao_id
    ).count()

    print(f"\nRevisões depois: {after}")

    if after != before:
        print("❌ ERRO: Foram criadas revisões indevidas!")
    else:
        print("✅ OK: Nenhuma revisão criada (modo diagnóstico funcionando)")

    print("\n==============================\n")


if __name__ == "__main__":
    run_test()