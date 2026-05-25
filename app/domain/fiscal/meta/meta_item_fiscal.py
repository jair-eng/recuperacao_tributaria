

# item fiscal transformado em meta
def meta_from_item_fiscal(item):
    return {
        "dominio": item.dominio,
        "periodo": item.periodo,
        "cfop": item.cfop,
        "ncm": item.ncm,
        "descr_item": item.descr_item,

        "cst_pis": item.cst_pis,
        "cst_cofins": item.cst_cofins,
        "vl_bc_pis": item.vl_bc_pis,
        "vl_bc_cofins": item.vl_bc_cofins,
        "vl_pis": item.vl_pis,
        "vl_cofins": item.vl_cofins,

        "vl_item": item.vl_item,
        "vl_desc": item.vl_desc,
        "vl_icms": item.vl_icms,

        "registro_id_c100": item.registro_id_c100,
        "registro_id_c170": item.registro_id_c170,
        "nf_icms_item_id": item.nf_icms_item_id,
        "chave_nfe": item.chave_nfe,
        "num_item": item.num_item,
        "cod_item": item.cod_item,
    }