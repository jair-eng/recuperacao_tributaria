



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
            "TINTA SPRAY",
                    },
    },

    "CAFE": {
        "descricao_contem": {
            # futuro
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