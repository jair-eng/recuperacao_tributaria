from app.domain.ecd.ecd_index import build_ecd_indexes
from app.domain.ecd.ecd_parser import parse_ecd_lines


with open(r"C:\Users\jcbn1\Downloads\teste\ecd_teste.txt", "r", encoding="latin-1") as f:
    linhas = f.readlines()

result = parse_ecd_lines(
    linhas,
    incluir_saldos_i155=True,
    incluir_resultados_i355=True,
    cod_ctas_relevantes={"470", "504", "5"},
)

print("\n========== CONTAGEM ==========")

for reg, qtd in sorted(result.contagem_por_registro.items()):
    print(reg, qtd)

print("\n========== I050 ==========")
print("total:", len(result.contas_i050))

for x in result.contas_i050[:5]:
    print(x)

print("\n========== I155 ==========")
print("total:", len(result.saldos_i155))

for x in result.saldos_i155[:5]:
    print(x)

print("\n========== J150 ==========")
print("total:", len(result.dres_j150))

for x in result.dres_j150[:5]:
    print(x)

print("\n========== IGNORADOS ==========")
print(result.registros_ignorados)

indexes = build_ecd_indexes(result)

print("\n========== INDEX CONTA 470 ==========")
print(indexes.contas_por_cod_cta.get("470"))

print("\n========== INDEX SALDOS 470 ==========")
for x in indexes.saldos_por_cod_cta.get("470", [])[:5]:
    print(x)

print("\n========== INDEX DRE 470 ==========")
for x in indexes.dre_por_cod_agl.get("470", [])[:5]:
    print(x)

print("\n========== INDEX VINCULO 470 ==========")
print(indexes.vinculos_agl_por_cod_cta.get("470"))