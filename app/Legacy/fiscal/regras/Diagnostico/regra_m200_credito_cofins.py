from app.Legacy.fiscal.dto import RegistroFiscalDTO
from app.Legacy.fiscal.regras.Diagnostico.regra_m100_credito_pis import RegraM100CreditoPIS
from app.Legacy.fiscal.regras.Diagnostico.base_regras import RegraBase


class RegraM200CreditoCOFINS(RegraM100CreditoPIS, RegraBase):

    def aplicar(self, registro: RegistroFiscalDTO):

        return None