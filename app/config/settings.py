from dotenv import load_dotenv
import os
from decimal import Decimal

load_dotenv()


DB_USER = os.getenv("DB_USER", "sped_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "recuperacao_tributaria_v1")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

# Impacto financeiro estimado (MVP)
ALIQUOTA_PIS = Decimal("0.0165")
ALIQUOTA_COFINS = Decimal("0.0760")
ALIQUOTA_TOTAL = ALIQUOTA_PIS + ALIQUOTA_COFINS
IND_AGRO_ALIQUOTA_EFETIVA = Decimal("0.0736")
ALIQUOTA_PIS_PCT = Decimal("1.65")
ALIQUOTA_COFINS_PCT = Decimal("7.60")


# Crédito presumido transporte (Lei 10.833/2003)
ALIQUOTA_PIS_PRESUMIDO = Decimal("0.012375")
ALIQUOTA_COFINS_PRESUMIDO = Decimal("0.057")



