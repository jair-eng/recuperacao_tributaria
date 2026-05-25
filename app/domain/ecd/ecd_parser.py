

from collections import defaultdict
from typing import Optional
from app.domain.ecd.ecd_maps import IDX_0000, IDX_I010, IDX_I030, IDX_I050, IDX_I052, IDX_I150, IDX_I155, IDX_I350, \
    IDX_I355, IDX_J005, IDX_J100, IDX_J150, IDX_J900, IDX_J930
from app.domain.ecd.ecd_models import EcdParseResult, EcdContaI050, EcdPeriodoResultadoI350, EcdPeriodoI150, \
    EcdDemonstracaoJ005, EcdIdentificacao0000, EcdI010, EcdI030, EcdVinculoI052, EcdSaldoI155, EcdResultadoI355, \
    EcdBalancoJ100, EcdDreJ150, EcdTermoEncerramentoJ900, EcdSignatarioJ930
from app.utils.sped import get_sped_str, split_linha_sped



def parse_ecd_lines(
    linhas: list[str],
    *,
    incluir_saldos_i155: bool = False,
    incluir_resultados_i355: bool = False,
    incluir_balanco_j100: bool = False,
    incluir_dre_j150: bool = True,
    cod_ctas_relevantes: set[str] | None = None,
) -> EcdParseResult:
    result = EcdParseResult()

    conta_atual_i050: Optional[EcdContaI050] = None
    periodo_atual_i150: Optional[EcdPeriodoI150] = None
    periodo_atual_i350: Optional[EcdPeriodoResultadoI350] = None
    demonstracao_atual_j005: Optional[EcdDemonstracaoJ005] = None

    contagem = defaultdict(int)
    ignorados = defaultdict(int)

    for numero_linha, linha in enumerate(linhas, start=1):
        linha = str(linha or "").strip()
        if not linha.startswith("|"):
            continue

        dados = split_linha_sped(linha)
        if not dados:
            continue

        reg = dados[0].upper().strip()
        contagem[reg] += 1

        if reg == "0000":
            result.identificacao = EcdIdentificacao0000(
                cod_ver=get_sped_str(dados, IDX_0000, "COD_VER"),
                dt_ini=get_sped_str(dados, IDX_0000, "DT_INI"),
                dt_fin=get_sped_str(dados, IDX_0000, "DT_FIN"),
                nome=get_sped_str(dados, IDX_0000, "NOME"),
                cnpj=get_sped_str(dados, IDX_0000, "CNPJ"),
                uf=get_sped_str(dados, IDX_0000, "UF"),
                ie=get_sped_str(dados, IDX_0000, "IE"),
                cod_mun=get_sped_str(dados, IDX_0000, "COD_MUN"),
            )
            continue

        if reg == "I010":
            result.i010 = EcdI010(
                ind_esc=get_sped_str(dados, IDX_I010, "IND_ESC"),
                cod_ver_lc=get_sped_str(dados, IDX_I010, "COD_VER_LC"),
            )
            continue

        if reg == "I030":
            result.i030 = EcdI030(
                dnrc_abert=get_sped_str(dados, IDX_I030, "DNRC_ABERT"),
                num_ord=get_sped_str(dados, IDX_I030, "NUM_ORD"),
                nat_livr=get_sped_str(dados, IDX_I030, "NAT_LIVR"),
                qtd_lin=get_sped_str(dados, IDX_I030, "QTD_LIN"),
                nome=get_sped_str(dados, IDX_I030, "NOME"),
                nire=get_sped_str(dados, IDX_I030, "NIRE"),
                cnpj=get_sped_str(dados, IDX_I030, "CNPJ"),
                dt_arq=get_sped_str(dados, IDX_I030, "DT_ARQ"),
                desc_mun=get_sped_str(dados, IDX_I030, "DESC_MUN"),
                dt_ex_social=get_sped_str(dados, IDX_I030, "DT_EX_SOCIAL"),
            )
            continue

        if reg == "I050":
            conta_atual_i050 = EcdContaI050(
                linha=numero_linha,
                dt_alt=get_sped_str(dados, IDX_I050, "DT_ALT"),
                cod_nat=get_sped_str(dados, IDX_I050, "COD_NAT"),
                ind_cta=get_sped_str(dados, IDX_I050, "IND_CTA"),
                nivel=get_sped_str(dados, IDX_I050, "NIVEL"),
                cod_cta=get_sped_str(dados, IDX_I050, "COD_CTA"),
                cod_cta_sup=get_sped_str(dados, IDX_I050, "COD_CTA_SUP"),
                cta=get_sped_str(dados, IDX_I050, "CTA"),
            )
            result.contas_i050.append(conta_atual_i050)
            continue

        if reg == "I052":
            if conta_atual_i050 is None:
                ignorados["I052_SEM_I050"] += 1
                continue

            result.vinculos_i052.append(
                EcdVinculoI052(
                    linha=numero_linha,
                    cod_cta_i050=conta_atual_i050.cod_cta,
                    cod_ccus=get_sped_str(dados, IDX_I052, "COD_CCUS"),
                    cod_agl=get_sped_str(dados, IDX_I052, "COD_AGL"),
                )
            )
            continue

        if reg == "I150":
            periodo_atual_i150 = EcdPeriodoI150(
                linha=numero_linha,
                dt_ini=get_sped_str(dados, IDX_I150, "DT_INI"),
                dt_fin=get_sped_str(dados, IDX_I150, "DT_FIN"),
            )
            result.periodos_i150.append(periodo_atual_i150)
            continue

        if reg == "I155":
            if not incluir_saldos_i155:
                continue

            if periodo_atual_i150 is None:
                ignorados["I155_SEM_I150"] += 1
                continue

            cod_cta = get_sped_str(dados, IDX_I155, "COD_CTA")

            if cod_ctas_relevantes and cod_cta not in cod_ctas_relevantes:
                ignorados["I155_FORA_FILTRO_COD_CTA"] += 1
                continue

            result.saldos_i155.append(
                EcdSaldoI155(
                    linha=numero_linha,
                    dt_ini=periodo_atual_i150.dt_ini,
                    dt_fin=periodo_atual_i150.dt_fin,
                    cod_cta=cod_cta,
                    cod_ccus=get_sped_str(dados, IDX_I155, "COD_CCUS"),
                    vl_sld_ini=get_sped_str(dados, IDX_I155, "VL_SLD_INI"),
                    ind_dc_ini=get_sped_str(dados, IDX_I155, "IND_DC_INI"),
                    vl_deb=get_sped_str(dados, IDX_I155, "VL_DEB"),
                    vl_cred=get_sped_str(dados, IDX_I155, "VL_CRED"),
                    vl_sld_fin=get_sped_str(dados, IDX_I155, "VL_SLD_FIN"),
                    ind_dc_fin=get_sped_str(dados, IDX_I155, "IND_DC_FIN"),
                )
            )
            continue

        if reg == "I350":
            periodo_atual_i350 = EcdPeriodoResultadoI350(
                linha=numero_linha,
                dt_res=get_sped_str(dados, IDX_I350, "DT_RES"),
            )
            result.periodos_i350.append(periodo_atual_i350)
            continue

        if reg == "I355":
            if not incluir_resultados_i355:
                continue

            if periodo_atual_i350 is None:
                ignorados["I355_SEM_I350"] += 1
                continue

            cod_cta = get_sped_str(dados, IDX_I355, "COD_CTA")

            if cod_ctas_relevantes and cod_cta not in cod_ctas_relevantes:
                ignorados["I355_FORA_FILTRO_COD_CTA"] += 1
                continue

            result.resultados_i355.append(
                EcdResultadoI355(
                    linha=numero_linha,
                    dt_res=periodo_atual_i350.dt_res,
                    cod_cta=cod_cta,
                    cod_ccus=get_sped_str(dados, IDX_I355, "COD_CCUS"),
                    vl_cta=get_sped_str(dados, IDX_I355, "VL_CTA"),
                    ind_dc=get_sped_str(dados, IDX_I355, "IND_DC"),
                )
            )
            continue

        if reg == "J005":
            demonstracao_atual_j005 = EcdDemonstracaoJ005(
                linha=numero_linha,
                dt_ini=get_sped_str(dados, IDX_J005, "DT_INI"),
                dt_fin=get_sped_str(dados, IDX_J005, "DT_FIN"),
                id_dem=get_sped_str(dados, IDX_J005, "ID_DEM"),
                cab_dem=get_sped_str(dados, IDX_J005, "CAB_DEM"),
            )
            result.demonstracoes_j005.append(demonstracao_atual_j005)
            continue

        if reg == "J100":
            if not incluir_balanco_j100:
                continue

            if demonstracao_atual_j005 is None:
                ignorados["J100_SEM_J005"] += 1
                continue

            result.balancos_j100.append(
                EcdBalancoJ100(
                    linha=numero_linha,
                    dt_ini=demonstracao_atual_j005.dt_ini,
                    dt_fin=demonstracao_atual_j005.dt_fin,
                    cod_agl=get_sped_str(dados, IDX_J100, "COD_AGL"),
                    ind_cod_agl=get_sped_str(dados, IDX_J100, "IND_COD_AGL"),
                    nivel_agl=get_sped_str(dados, IDX_J100, "NIVEL_AGL"),
                    cod_agl_sup=get_sped_str(dados, IDX_J100, "COD_AGL_SUP"),
                    ind_grp_bal=get_sped_str(dados, IDX_J100, "IND_GRP_BAL"),
                    descr_cod_agl=get_sped_str(dados, IDX_J100, "DESCR_COD_AGL"),
                    vl_cta=get_sped_str(dados, IDX_J100, "VL_CTA"),
                    ind_dc_bal=get_sped_str(dados, IDX_J100, "IND_DC_BAL"),
                    vl_cta_ini=get_sped_str(dados, IDX_J100, "VL_CTA_INI"),
                    ind_dc_bal_ini=get_sped_str(dados, IDX_J100, "IND_DC_BAL_INI"),
                    nota_exp_ref=get_sped_str(dados, IDX_J100, "NOTA_EXP_REF"),
                )
            )
            continue

        if reg == "J150":
            if not incluir_dre_j150:
                continue

            if demonstracao_atual_j005 is None:
                ignorados["J150_SEM_J005"] += 1
                continue

            result.dres_j150.append(
                EcdDreJ150(
                    linha=numero_linha,
                    dt_ini=demonstracao_atual_j005.dt_ini,
                    dt_fin=demonstracao_atual_j005.dt_fin,
                    nu_ordem=get_sped_str(dados, IDX_J150, "NU_ORDEM"),
                    cod_agl=get_sped_str(dados, IDX_J150, "COD_AGL"),
                    ind_cod_agl=get_sped_str(dados, IDX_J150, "IND_COD_AGL"),
                    nivel_agl=get_sped_str(dados, IDX_J150, "NIVEL_AGL"),
                    cod_agl_sup=get_sped_str(dados, IDX_J150, "COD_AGL_SUP"),
                    descr_cod_agl=get_sped_str(dados, IDX_J150, "DESCR_COD_AGL"),
                    vl_cta=get_sped_str(dados, IDX_J150, "VL_CTA"),
                    ind_vl=get_sped_str(dados, IDX_J150, "IND_VL"),
                    vl_cta_ult_dre=get_sped_str(dados, IDX_J150, "VL_CTA_ULT_DRE"),
                    ind_vl_ult_dre=get_sped_str(dados, IDX_J150, "IND_VL_ULT_DRE"),
                    ind_grp_dre=get_sped_str(dados, IDX_J150, "IND_GRP_DRE"),
                    nota_exp_ref=get_sped_str(dados, IDX_J150, "NOTA_EXP_REF"),
                )
            )
            continue

        if reg == "J900":
            result.encerramentos_j900.append(
                EcdTermoEncerramentoJ900(
                    linha=numero_linha,
                    dnrc_encer=get_sped_str(dados, IDX_J900, "DNRC_ENCER"),
                    num_ord=get_sped_str(dados, IDX_J900, "NUM_ORD"),
                    nat_livr=get_sped_str(dados, IDX_J900, "NAT_LIVR"),
                    nome=get_sped_str(dados, IDX_J900, "NOME"),
                    qtd_lin=get_sped_str(dados, IDX_J900, "QTD_LIN"),
                    dt_ini_escr=get_sped_str(dados, IDX_J900, "DT_INI_ESCR"),
                    dt_fin_escr=get_sped_str(dados, IDX_J900, "DT_FIN_ESCR"),
                )
            )
            continue

        if reg == "J930":
            result.signatarios_j930.append(
                EcdSignatarioJ930(
                    linha=numero_linha,
                    ident_nom=get_sped_str(dados, IDX_J930, "IDENT_NOM"),
                    ident_cpf_cnpj=get_sped_str(dados, IDX_J930, "IDENT_CPF_CNPJ"),
                    ident_qualif=get_sped_str(dados, IDX_J930, "IDENT_QUALIF"),
                    cod_assin=get_sped_str(dados, IDX_J930, "COD_ASSIN"),
                    ind_crc=get_sped_str(dados, IDX_J930, "IND_CRC"),
                    email=get_sped_str(dados, IDX_J930, "EMAIL"),
                    fone=get_sped_str(dados, IDX_J930, "FONE"),
                    uf_crc=get_sped_str(dados, IDX_J930, "UF_CRC"),
                )
            )
            continue

    result.contagem_por_registro = dict(contagem)
    result.registros_ignorados = dict(ignorados)

    return result