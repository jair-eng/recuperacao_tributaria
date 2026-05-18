from app.db.session import SessionLocal
from app.db.models.nf_icms_item import NfIcmsItem
from app.db.models.nf_icms_base import NfIcmsBase

db = SessionLocal()

ids = [15, 16, 17]

for item_id in ids:
    item, base = (
        db.query(NfIcmsItem, NfIcmsBase)
        .join(NfIcmsBase, NfIcmsBase.id == NfIcmsItem.nf_icms_base_id)
        .filter(NfIcmsItem.id == item_id)
        .first()
    )

    print("-" * 80)
    print("item_id:", item.id)
    print("item.cod_item:", item.cod_item)
    print("item.ncm:", item.ncm)
    print("item.participante_nome:", item.participante_nome)
    print("item.participante_cnpj:", item.participante_cnpj)

    print("base_id:", base.id)
    print("base.participante_nome:", base.participante_nome)
    print("base.participante_cnpj:", base.participante_cnpj)
    print("base.participante_cpf:", base.participante_cpf)

db.close()