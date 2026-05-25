
from app.utils.lc192_utils import eh_periodo_lc192

# LC192 combustiveis em periodo da pandemia

def cenario_lc192(meta, classificacao):

    dominio = meta.get("dominio")

    operacao = classificacao["operacao"]
    produto = classificacao["produto"]

    out = {
        "ativo": False,
        "fundamento_legal": [],
        "justificativa": [],
    }

    periodo = (
            meta.get("periodo")
            or meta.get("dt_doc")
            or meta.get("data_doc")
    )

    if not eh_periodo_lc192(periodo):
        out["justificativa"].append("periodo_fora_lc192")
        return out

    # -----------------------------------
    # Gates básicos
    # -----------------------------------

    if not operacao["entrada"]:
        out["justificativa"].append("nao_entrada")
        return out

    if operacao["transferencia"]:
        out["justificativa"].append("transferencia")
        return out

    if operacao["imobilizado"]:
        out["justificativa"].append("imobilizado")
        return out

    # -----------------------------------
    # Transportadora
    # -----------------------------------

    if dominio == "TRANSP":

        if produto["diesel"]:

            out["ativo"] = True

            out["fundamento_legal"] = [
                "LC192_2022",
            ]

            out["justificativa"] = [
                "entrada_combustivel",
                "diesel_transporte",
                "dominio_transportadora",
            ]

            return out

    # -----------------------------------
    # Posto
    # -----------------------------------

    if dominio == "POSTO":

        if produto["combustivel"]:

            out["ativo"] = True

            out["fundamento_legal"] = [
                "LC192_2022",
            ]

            out["justificativa"] = [
                "entrada_combustivel",
                "combustivel_revenda",
                "dominio_posto",
            ]

            return out

    # -----------------------------------
    # Revenda gás
    # -----------------------------------

    if dominio == "REVENDA_GAS":

        if ( produto["glp"] ):

            out["ativo"] = True

            out["fundamento_legal"] = [
                "LC192_2022",
            ]

            out["justificativa"] = [
                "entrada_combustivel",
                "combustivel_operacional",
                "dominio_revenda_gas",
            ]

            return out

    return out