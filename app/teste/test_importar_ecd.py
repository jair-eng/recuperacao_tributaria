from app.db.session import SessionLocal
from app.domain.ecd.ecd_importer import importar_ecd_arquivo

db = SessionLocal()

try:
    r = importar_ecd_arquivo(
        db,
        empresa_id=1,  # ajuste para o id real da empresa
        caminho_arquivo=r"C:\Users\jcbn1\Downloads\teste\ecd_teste.txt",
        cod_ctas_relevantes={"470", "504", "5"},
        sobrescrever=True,
    )

    print(r)

finally:
    db.close()