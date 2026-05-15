# create_tables.py

from app.db.session import engine
from app.db.models.base import Base

# IMPORTANTE:
from app.db.models.models_all import *

Base.metadata.create_all(bind=engine)

print("Tabelas criadas com sucesso.")