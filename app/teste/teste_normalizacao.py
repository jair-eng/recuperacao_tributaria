from pathlib import Path

from app.db.session import SessionLocal
from app.domain.fiscal.bloco_F.f100_loader_local import carregar_f100_local
from app.domain.fiscal.bloco_A.a170_loader_local import carregar_a170_local
from app.domain.relatorio_executivo.c170_loader_local import carregar_c170_local
from app.domain.relatorio_executivo.contexto_local_ecd_efd import montar_linhas_ecd_local
from app.domain.relatorio_executivo.contexto_recuperacao_local import montar_contexto_recuperacao_local
from app.domain.relatorio_executivo.contrib_loader_local import carregar_contrib_local
from app.domain.relatorio_executivo.ecd_loader_local import carregar_ecd_local
from app.utils.sped import listar_txt

arquivos = listar_txt(Path(r"C:\Sped\CONTRIB"))
arquivos_ecd = listar_txt(Path(r"C:\Sped\ECD"))

db = SessionLocal()

dominio = "TRANSP"

c170 = carregar_c170_local(arquivos)
f100 = carregar_f100_local(arquivos)

ecd_ctx = carregar_ecd_local(arquivos_ecd)

linhas_ecd = montar_linhas_ecd_local(
    ecd_ctx=ecd_ctx,
    db=db,
)

a170 = carregar_a170_local(arquivos)

contrib_ctx = carregar_contrib_local(arquivos)
ctx_rec = montar_contexto_recuperacao_local(
    linhas_ecd=linhas_ecd,
    db=db,
    contrib_ctx=contrib_ctx,
    c170_contrib=c170,
    f100_contrib=f100,
    dominio="TRANSP",
    a170_contrib=a170,
)



print("QTD A170:", len(a170))
print("COM CRÉDITO:", sum(1 for x in a170 if x.get("tem_credito")))
print("SEM CRÉDITO:", sum(1 for x in a170 if not x.get("tem_credito")))

from collections import Counter

print("TOP NAT:")
print(Counter(x.get("nat_bc_cred") for x in a170).most_common(20))

print("TOP CST:")
print(Counter(x.get("cst_pis") for x in a170).most_common(20))

print(a170[0])
print("A170:", len(a170))

for chave, item in sorted(
    ctx_rec["por_chave"].items(),
    key=lambda x: x[1].get("valor_creditado_a170", 0),
    reverse=True,
)[:20]:
    if item.get("valor_creditado_a170"):
        print(
            chave,
            item["valor_creditado_a170"],
            item["qtd_a170"],
        )