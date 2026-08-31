# class Query:
#
#
#     def __init__(self):
#         self.resultado = []
#         self.ordenacao = None
#
#     def filter(self,filtro):
#         self.resultado.append(filtro)
#
#         return self
#
#     def order_by(self,campo):
#         self.ordenacao = campo
#         return self
#
#     def mostrar(self):
#         print(self.resultado)
#
#
#
# q = Query()
# q.filter("id = 10")
# q.filter("periodo = 202501")
# q.filter("empresa = 15")
#
# q.mostrar()



from pathlib import Path

from app.domain.fiscal.bloco_F.f100_comparacao import carregar_contratos_extraidos, listar_contratos_nao_encontrados

pasta_resultado = Path(
    r"C:\Sped\LEITOR_CONTRATO\resultado"
)

contratos_extraidos = carregar_contratos_extraidos(
    pasta_resultado,
    ano="2021",
    mes="01",
)

contratos_nao_encontrados = listar_contratos_nao_encontrados(
    contratos_extraidos,
    f100,
)

print(
    "Contratos extraídos:",
    len(contratos_extraidos)
)

print(
    "Contratos não encontrados:",
    contratos_nao_encontrados
)
