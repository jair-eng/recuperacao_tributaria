from decimal import Decimal

from app.sped.bloco_1.builder import montar_bloco_1_com_estoque_v2


class EstoqueFake:

    def __init__(
        self,
        periodo_origem,
        periodo_escrituracao,
        cod_cred,
        saldo_pis,
        saldo_cofins,
        orig_cred="01",
    ):
        self.periodo_origem = periodo_origem
        self.periodo_escrituracao = periodo_escrituracao
        self.cod_cred = cod_cred
        self.orig_cred = orig_cred
        self.saldo_pis = saldo_pis
        self.saldo_cofins = saldo_cofins


linhas = [
    "|1001|0|",
    "|1100|052021|01||101|100,00|0,00|100,00|0,00|0,00|0,00|100,00|0,00|0,00|0,00|0,00|0,00|100,00|",
    "|1990|3|",
]

estoques = [
    EstoqueFake(
        periodo_origem="052021",
        periodo_escrituracao="062021",
        cod_cred="101",
        saldo_pis=Decimal("219.34"),
        saldo_cofins=Decimal("1010.28"),
    )
]

bloco = montar_bloco_1_com_estoque_v2(
    linhas_sped=linhas,
    periodo_atual="062021",
    estoques_v2=estoques,
)

print()

print("====================================")
print(" BLOCO 1 GERADO")
print("====================================")

for ln in bloco:
    print(ln)