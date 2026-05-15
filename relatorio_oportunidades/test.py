from app.sped.utils_cod_cta import resolver_cod_cta_para_insert_c170

alvo2 = Linha("C100", [], registro_id=500, pai_id=None)

c170_hist = [""] * 36
c170_hist[2] = "OLEO DIESEL COMBUSTIVEL"
c170_hist[9] = "1102"
c170_hist[35] = "8888"

linhas_base2 = [
    Linha("C170", c170_hist, registro_id=300, pai_id=400),
]

novo2 = [""] * 36
novo2[2] = "DIESEL S10"
novo2[9] = "1102"

ret2 = resolver_cod_cta_para_insert_c170(
    alvo=alvo2,
    linhas_base=linhas_base2,
    cod_cta_padrao_0500="9999",
    dados_c170_novo=novo2,
)

assert ret2 == "8888"