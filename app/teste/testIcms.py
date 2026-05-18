from app.db.session import SessionLocal
from app.db.models.nf_icms_item import NfIcmsItem
from app.db.models.nf_icms_base import NfIcmsBase

db = SessionLocal()

qtd_total = db.query(NfIcmsItem).count()

qtd_join = (
    db.query(NfIcmsItem)
    .join(NfIcmsBase, NfIcmsBase.id == NfIcmsItem.nf_icms_base_id)
    .count()
)

print("Itens ICMS total:", qtd_total)
print("Itens ICMS com NF pai:", qtd_join)

amostra = (
    db.query(NfIcmsBase, NfIcmsItem)
    .join(NfIcmsItem, NfIcmsItem.nf_icms_base_id == NfIcmsBase.id)
    .limit(10)
    .all()
)

for nf, item in amostra:
    print("-" * 80)
    print("nf_id:", nf.id)
    print("empresa_id:", getattr(nf, "empresa_id", None))
    print("periodo:", getattr(nf, "periodo", None))
    print("chave_nfe:", getattr(nf, "chave_nfe", None))
    print("num_item:", getattr(item, "num_item", None))
    print("cod_item:", getattr(item, "cod_item", None))
    print("cfop:", getattr(item, "cfop", None))
    print("ncm:", getattr(item, "ncm", None))

chave = "31220813345678000199550010000050101000005010"

achou = (
    db.query(NfIcmsItem)
    .filter(
        NfIcmsItem.empresa_id == 1,
        NfIcmsItem.periodo == "202208",
        NfIcmsItem.chave_nfe == chave,
    )
    .all()
)

print("ICMS encontrados para chave:", len(achou))

for item in achou:
    print(item.id, item.num_item, item.cod_item, item.cfop, item.ncm)

db.close()