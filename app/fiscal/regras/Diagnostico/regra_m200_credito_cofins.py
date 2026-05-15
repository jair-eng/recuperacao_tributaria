from app.fiscal.dto import RegistroFiscalDTO
from decimal import Decimal, ROUND_HALF_UP
from app.fiscal.regras.Diagnostico.regra_m100_credito_pis import RegraM100CreditoPIS
from app.fiscal.regras.Diagnostico.base_regras import RegraBase


class RegraM200CreditoCOFINS(RegraM100CreditoPIS, RegraBase):

    def aplicar(self, registro: RegistroFiscalDTO):

        return None