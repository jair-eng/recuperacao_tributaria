



BLOQUEIOS_CLASSIFICACAO = {
    "TRANSP": {
        "descricao_contem": {
            "CAFE",
            "CHOCOLATE",
            "COOKIE",
            "BOLO",
            "PANETONE",
            "REFRIG",
            "COCA COLA",
            "OLEO SOJA",
            "OLEO MISTO",
            "GARRAFA TERMICA",
            "GARRAFA",
            "TESOURA",
            "COLA BASTAO",
            "TECLADO",
            "CABO HDMI",
            "SSD",
            "SACOLA",
            "ESTILETE",
            "CAMISA",
            "OLEO MISTO",
            "GARRAFA",
            "LUVA VAQUETA",
            "PAPEL TOALHA",
            "CHAVEIRO",
            "PRANCHETA",
            "TOALHA PAPEL",
            "SARDINHA",
            "ACHOCOLATADO",
            "BOTINA",
            "MADERITE",
            "MARRETA",
            "COSTELA",
            "VEJA MULTIUSO",
            "MULTIUSO",
            "INSETICIDA ",
            "MAIONESE",
            "BALA",
            " HORTELA",
            " RECHEADA",
            "TELA MOSQUITEIRO",
            "SABONETE",
            "PASTA",
            "LIMPA VIDRO",
            "TOMADA",
            "KEYSTONE",
            "AROMATIZADOR",
            "ODORIZADOR",
            "TINTA SPRAY",
            "BOM AR",
            "LAVANDA",
            "PNEUMATICO",
            "PNEUMATICA",
            "PNEUMÁTICO",
            "PNEUMÁTICA",
            "MARTELETE PNEUMATICO",
            "FURADEIRA PNEUMATICA",
            "CHAVE PNEUMATICA",
            "PISTOLA PNEUMATICA",
            "COMPRESSOR PNEUMATICO",
            "SERRA COPO",
            "SOQUETE IMPACTO",
            "SOQUETE ENC 1",
            "SOQUETE ENC 12",
            "CHAVE COMBINADA",
            "CHAVE BIELA",
            "CHAVE ESTRELA",
            "JOGO CHAVE ALLEN",
            "MULTIMETRO",
            "TRENA",
            "SOLDA ARAME MIG",
            "MULTIMIDIA",
            "CENTRAL MULTIMIDIA",
            "MOLDURA PARA MULTIMIDIA",
            "CABO PARA RADIO",
            "APOIO PARA BRACO",
            "CAPA DE CHUVA",
            "CAPA CHUVA",
            "RODIZIO GIRATORIO",
            "RODIZIO FIXO",
            "PARAFUSO SEXTAVADO",
                }
                    },


    "CAFE": {
        "descricao_contem": {
            "ESTOPA BRANCA",
        },
    },

    "GERAL": {
        "descricao_contem": set(),
            },
        }

def item_bloqueado_classificacao(
    *,
    dominio: str,
    descricao: str,
) -> bool:

    regras = BLOQUEIOS_CLASSIFICACAO.get(dominio) or {}

    desc = (descricao or "").upper()

    for termo in regras.get("descricao_contem", []):
        if termo in desc:
            return True

    return False