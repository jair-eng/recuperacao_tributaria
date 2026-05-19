from app.db.session import SessionLocal
from app.domain.sped.services.normalizacao.plano_normalizacao_service import (
    gerar_plano_c100_c170_faltante,
    gerar_plano_d100_faltante,
)

db = SessionLocal()

try:
    print("\n========== C100/C170 ==========")

    plano_c100 = gerar_plano_c100_c170_faltante(
        db,
        versao_id=1,
    )

    print("Notas:", len(plano_c100))

    for chave, nota in plano_c100.items():
        print("-" * 80)
        print("chave:", chave)
        print("participante:", nota["participante_nome"])
        print("itens:", len(nota["itens"]))

    print("\n========== D100 ==========")

    plano_d100 = gerar_plano_d100_faltante(
        db,
        versao_id=1,
    )

    print("CTEs:", len(plano_d100))

    for chave, nota in list(plano_d100.items())[:10]:
        print("-" * 80)
        print("chave:", chave)
        print("participante:", nota["participante_nome"])
        print("cfop:", nota["cfop"])
        print("itens:", len(nota["itens"]))

finally:
    db.close()