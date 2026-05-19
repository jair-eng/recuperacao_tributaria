from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Tuple
from relatorio_oportunidades.foto_oportunidade.aux_funcoes_foto import _digits, _s, _q2, _key_chave_cod_item, \
    _key_chave, _participante, \
    _dec, _key_chave_cod_item_norm, _key_chave_num_item, _eh_pf_doc, _eh_complemento_valor
from relatorio_oportunidades.foto_oportunidade.foto_herlpers import _eh_item_cafe_ou_agro, _simular_credito, \
    resolver_cenario_especial, _simular_credito_lc192


# ============================================================
# Cruzamento principal
# ============================================================
def cruzar_icms_ipi_com_efd_contrib(
    linhas_icms: List[Dict[str, Any]],
    linhas_contrib: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Cruza linhas normalizadas de ICMS/IPI com EFD Contribuições.

    Estratégia:
      1) chave + cod_item
      2) chave + cod_item_norm
      3) chave + num_item
      4) chave + cfop
      5) chave
    """

    lc192_total_base = Decimal("0")
    lc192_total_pis = Decimal("0")
    lc192_total_cofins = Decimal("0")
    lc192_total_itens = 0

    # --------------------------------------------------------
    # Índices do Contribuições
    # --------------------------------------------------------
    contrib_by_chave_item: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    contrib_by_chave_item_norm: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    contrib_by_chave_num_item: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    contrib_by_chave: Dict[str, List[Dict[str, Any]]] = {}

    for row in linhas_contrib:
        k1 = _key_chave_cod_item(row)
        k1n = _key_chave_cod_item_norm(row)
        k2 = _key_chave(row)
        k3 = _key_chave_num_item(row)

        if k2:
            contrib_by_chave.setdefault(k2, []).append(row)

        if k1[0] and k1[1]:
            contrib_by_chave_item.setdefault(k1, []).append(row)

        if k1n[0] and k1n[1]:
            contrib_by_chave_item_norm.setdefault(k1n, []).append(row)

        if k3[0] and k3[1]:
            contrib_by_chave_num_item.setdefault(k3, []).append(row)

    # --------------------------------------------------------
    # Cruzamento
    # --------------------------------------------------------
    saida: List[Dict[str, Any]] = []

    for icms in linhas_icms:
        chave = _key_chave(icms)
        cod_item = _s(icms.get("cod_item"))
        cod_item_norm = _s(icms.get("cod_item_norm"))
        num_item = _s(icms.get("num_item"))

        match = None
        tipo_match = ""

        # 1) chave + cod_item
        if chave and cod_item:
            candidatos = contrib_by_chave_item.get((chave, cod_item), [])
            if candidatos:
                match = candidatos[0]
                tipo_match = "CHAVE_COD_ITEM"

        # 2) chave + cod_item_norm
        if match is None and chave and cod_item_norm:
            candidatos = contrib_by_chave_item_norm.get((chave, cod_item_norm), [])
            if candidatos:
                match = candidatos[0]
                tipo_match = "CHAVE_COD_ITEM_NORM"

        # 3) chave + num_item
        if match is None and chave and num_item:
            candidatos = contrib_by_chave_num_item.get((chave, num_item), [])
            if candidatos:
                match = candidatos[0]
                tipo_match = "CHAVE_NUM_ITEM"

        # 4/5) fallback por chave
        if match is None and chave:
            candidatos = contrib_by_chave.get(chave, [])

            if len(candidatos) == 1:
                match = candidatos[0]
                tipo_match = "CHAVE"

            elif len(candidatos) > 1:
                cfop_icms = _s(icms.get("cfop"))

                for cand in candidatos:
                    if _s(cand.get("cfop")) == cfop_icms:
                        match = cand
                        tipo_match = "CHAVE_CFOP"
                        break

                if match is None:
                    match = candidatos[0]
                    tipo_match = "CHAVE_MULTI"

        participante_icms = _participante(icms)
        participante_contrib = _participante(match) if match else ""

        empresa = _s(icms.get("empresa")) or (_s(match.get("empresa")) if match else "")
        participante = participante_icms or participante_contrib

        doc_part_icms = _digits(
            icms.get("participante_cnpj") or icms.get("participante_cpf") or icms.get("cpf_cnpj_part"))
        doc_part_contrib = _digits(match.get("participante_cnpj") or match.get("participante_cpf") or match.get(
            "cpf_cnpj_part")) if match else ""
        doc_part = doc_part_icms or doc_part_contrib

        is_pf = _eh_pf_doc(doc_part)

        data = _s(icms.get("data")) or (_s(match.get("dt_doc")) if match else "")
        chave_out = _s(icms.get("chave")) or (_s(match.get("chave")) if match else "")
        numero = _s(icms.get("numero")) or (_s(match.get("num_doc")) if match else "")
        serie = _s(icms.get("serie")) or (_s(match.get("serie")) if match else "")

        cod_item_out = _s(icms.get("cod_item")) or (_s(match.get("cod_item")) if match else "")
        num_item_out = _s(icms.get("num_item")) or (_s(match.get("num_item")) if match else "")
        descricao = _s(icms.get("descricao")) or (_s(match.get("descr_item")) if match else "")
        ncm = _s(icms.get("ncm")) or (_s(match.get("ncm")) if match else "")
        cfop = _s(icms.get("cfop")) or (_s(match.get("cfop")) if match else "")

        valor_item = _dec(icms.get("valor_item"))
        valor_desconto = _dec(icms.get("valor_desconto"))
        valor_icms = _dec(icms.get("valor_icms"))
        valor_ipi = _dec(icms.get("valor_ipi"))

        cst_pis = _s(match.get("cst_pis")) if match else "SEM_EFD"
        vl_base_pis = _dec(match.get("vl_bc_pis")) if match else Decimal("0")
        vl_aliq_pis = _dec(match.get("aliq_pis")) if match else Decimal("0")
        vl_pis = _dec(match.get("vl_pis")) if match else Decimal("0")

        cst_cofins = _s(match.get("cst_cofins")) if match else "SEM_EFD"
        vl_base_cofins = _dec(match.get("vl_bc_cofins")) if match else Decimal("0")
        vl_aliq_cofins = _dec(match.get("aliq_cofins")) if match else Decimal("0")
        vl_cofins = _dec(match.get("vl_cofins")) if match else Decimal("0")

        status_cruzamento = "MATCH" if match else "NAO_ESCRITURADO"

        dominio_ok = _eh_item_cafe_ou_agro({
            "ncm": ncm,
            "descricao": descricao,
            "cod_item": cod_item_out,
        })

        cod_sit_out = _s(icms.get("cod_sit")) or (_s(match.get("cod_sit")) if match else "")
        bloqueado_complemento = _eh_complemento_valor({
            "descricao": descricao,
            "cod_sit": cod_sit_out,
        })

        # ----------------------------------------------------
        # Simulação
        # ----------------------------------------------------

        cenario = resolver_cenario_especial({
            "ncm": ncm,
            "cfop": cfop,
            "periodo": _s(icms.get("periodo")) or _s(match.get("periodo") if match else ""),
            "empresa": empresa,
            "participante": participante,
        })

        if is_pf:
            sim = {
                "elegivel": False,
                "motivo_simulacao": "Participante PF/CPF bloqueado",
                "base_simulada": Decimal("0"),
                "pis_simulado": Decimal("0"),
                "cofins_simulado": Decimal("0"),
                "credito_simulado": Decimal("0"),
                "cst_simulado": "",
                "regra_simulada": "",
            }
        elif bloqueado_complemento:
            sim = {
                "elegivel": False,
                "motivo_simulacao": "Documento complementar de valor bloqueado",
                "base_simulada": Decimal("0"),
                "pis_simulado": Decimal("0"),
                "cofins_simulado": Decimal("0"),
                "credito_simulado": Decimal("0"),
                "cst_simulado": "",
                "regra_simulada": "",
            }
        elif cenario.get("elegivel") and cenario.get("tipo") == "LC192":
            valor_item_lc192 = valor_item
            valor_desc_lc192 = valor_desconto
            valor_icms_lc192 = valor_icms
            origem_base_lc192 = "ICMS_IPI"

            # Se encontrou match na EFD Contribuições, usar a base já escriturada nela.
            # Isso evita simular sobre VL_ITEM cheio do ICMS/IPI quando o C170 da Contribuições
            # já veio líquido de ST/desconto.
            if match:
                base_pis_match = _dec(match.get("vl_bc_pis"))
                base_cofins_match = _dec(match.get("vl_bc_cofins"))

                if base_pis_match > 0:
                    base_match = base_pis_match
                    origem_base_lc192 = "EFD_CONTRIB_BASE_PIS"
                elif base_cofins_match > 0:
                    base_match = base_cofins_match
                    origem_base_lc192 = "EFD_CONTRIB_BASE_COFINS"
                else:
                    base_match = (
                            _dec(match.get("vl_item"))
                            - _dec(match.get("vl_desc"))
                            - _dec(match.get("vl_icms"))
                    )
                    origem_base_lc192 = "EFD_CONTRIB_ITEM_LIQUIDO"

                if base_match > 0:
                    valor_item_lc192 = base_match
                    valor_desc_lc192 = Decimal("0")
                    valor_icms_lc192 = Decimal("0")

            sim = _simular_credito_lc192(
                valor_item=valor_item_lc192,
                valor_desconto=valor_desc_lc192,
                valor_icms=valor_icms_lc192,
                cst_pis_atual=cst_pis,
                cst_cofins_atual=cst_cofins,
            )

            print(
                "[FOTO LC192 SIM]",
                "elegivel=", sim.get("elegivel"),
                "motivo=", sim.get("motivo_simulacao"),
                "base=", sim.get("base_simulada"),
                "pis=", sim.get("pis_simulado"),
                "cofins=", sim.get("cofins_simulado"),
                "credito=", sim.get("credito_simulado"),
                "base_calc=", valor_item - valor_desconto - valor_icms,
                "valor_item=", valor_item,
                "valor_desc=", valor_desconto,
                "valor_icms=", valor_icms,
                flush=True,
            )
            if sim.get("elegivel"):
                lc192_total_base += _q2(sim.get("base_simulada") or 0)
                lc192_total_pis += _q2(sim.get("pis_simulado") or 0)
                lc192_total_cofins += _q2(sim.get("cofins_simulado") or 0)
                lc192_total_itens += 1

        elif not dominio_ok:
            sim = {
                "elegivel": False,
                "motivo_simulacao": "Item fora do domínio café/agro",
                "base_simulada": Decimal("0"),
                "pis_simulado": Decimal("0"),
                "cofins_simulado": Decimal("0"),
                "credito_simulado": Decimal("0"),
                "cst_simulado": "",
                "regra_simulada": "",
            }
        else:
            sim = _simular_credito(
                cfop=cfop,
                cst_pis=cst_pis,
                valor_item=valor_item,
                valor_desconto=valor_desconto,
                valor_icms=valor_icms,
                sem_efd=not bool(match),
            )

        linha = {
            # Cabeçalho/base
            "competencia": _s(icms.get("periodo")) or _s(match.get("periodo") if match else ""),
            "empresa": empresa,
            "participante": participante,
            "data": data,
            "chave": chave_out,
            "numero": numero,
            "serie": serie,

            # Produto/item
            "num_item": num_item_out,
            "cod_item": cod_item_out,
            "cod_item_norm": _s(icms.get("cod_item_norm")) or (_s(match.get("cod_item_norm")) if match else ""),
            "descricao": descricao,
            "ncm": ncm,
            "cfop": cfop,

            # Valores ICMS/IPI
            "valor_item": _q2(valor_item),
            "valor_desconto": _q2(valor_desconto),
            "valor_icms": _q2(valor_icms),
            "valor_ipi": _q2(valor_ipi),

            # PIS atual
            "cst_pis": cst_pis,
            "vl_base_pis": _q2(vl_base_pis),
            "vl_aliq_pis": _q2(vl_aliq_pis),
            "vl_pis": _q2(vl_pis),

            # COFINS atual
            "cst_cofins": cst_cofins,
            "vl_base_cofins": _q2(vl_base_cofins),
            "vl_aliq_cofins": _q2(vl_aliq_cofins),
            "vl_cofins": _q2(vl_cofins),

            # Originais
            "original_cst_pis": cst_pis,
            "original_vl_base_pis": _q2(vl_base_pis),
            "original_vl_aliq_pis": _q2(vl_aliq_pis),
            "original_vl_pis": _q2(vl_pis),

            "original_cst_cofins": cst_cofins,
            "original_vl_base_cofins": _q2(vl_base_cofins),
            "original_vl_aliq_cofins": _q2(vl_aliq_cofins),
            "original_vl_cofins": _q2(vl_cofins),

            # Contábil
            "contabil": _q2(_dec(icms.get("contabil", icms.get("valor_item")))),

            # Simulação
            "base_simulada": sim["base_simulada"],
            "pis_simulado": sim["pis_simulado"],
            "cofins_simulado": sim["cofins_simulado"],
            "credito_simulado": sim["credito_simulado"],
            "cst_simulado": sim["cst_simulado"],
            "regra_simulada": sim["regra_simulada"],
            "elegivel_simulacao": sim["elegivel"],
            "motivo_simulacao": sim["motivo_simulacao"],

            "cenario_fiscal": sim.get("cenario_fiscal", ""),
            "natureza_credito_m": sim.get("natureza_credito_m", ""),

            # Domínio
            "dominio_ok": dominio_ok,

            # Metadados
            "origem": "ICMS_IPI + EFD_CONTRIBUICOES" if match else "ICMS_IPI",
            "origem_item": _s(icms.get("origem_item")),
            "tipo_match": tipo_match,
            "match_encontrado": bool(match),
            "status_cruzamento": status_cruzamento,
            "is_pf": is_pf,
            "doc_participante": doc_part,
            "bloqueado_complemento_valor": bloqueado_complemento,

            "origem_base_lc192": origem_base_lc192 if cenario.get("tipo") == "LC192" else "",
        }

        saida.append(linha)

    print(
        "[FOTO LC192 RESUMO]",
        "itens=", lc192_total_itens,
        "base=", _q2(lc192_total_base),
        "pis=", _q2(lc192_total_pis),
        "cofins=", _q2(lc192_total_cofins),
        "credito=", _q2(lc192_total_pis + lc192_total_cofins),
        flush=True,
    )

    return saida


def resumir_cruzamento(linhas_cruzadas: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_linhas = len(linhas_cruzadas)
    total_match = sum(1 for x in linhas_cruzadas if x.get("match_encontrado"))
    total_nao_escriturado = sum(1 for x in linhas_cruzadas if x.get("status_cruzamento") == "NAO_ESCRITURADO")
    total_sem_match = total_linhas - total_match  # mantido para compatibilidade

    elegiveis = [x for x in linhas_cruzadas if x.get("elegivel_simulacao")]
    total_elegiveis = len(elegiveis)

    linhas_match = [x for x in linhas_cruzadas if x.get("status_cruzamento") == "MATCH"]
    linhas_nao_esc = [x for x in linhas_cruzadas if x.get("status_cruzamento") == "NAO_ESCRITURADO"]

    total_base_simulada = sum((_dec(x.get("base_simulada")) for x in linhas_cruzadas), Decimal("0"))
    total_pis_simulado = sum((_dec(x.get("pis_simulado")) for x in linhas_cruzadas), Decimal("0"))
    total_cofins_simulado = sum((_dec(x.get("cofins_simulado")) for x in linhas_cruzadas), Decimal("0"))
    total_credito_simulado = sum((_dec(x.get("credito_simulado")) for x in linhas_cruzadas), Decimal("0"))

    total_credito_match = sum((_dec(x.get("credito_simulado")) for x in linhas_match), Decimal("0"))
    total_credito_nao_escriturado = sum((_dec(x.get("credito_simulado")) for x in linhas_nao_esc), Decimal("0"))

    por_match: Dict[str, int] = {}
    por_cst: Dict[str, int] = {}
    por_regra: Dict[str, int] = {}

    for x in linhas_cruzadas:
        tm = _s(x.get("tipo_match")) or "SEM_MATCH"
        por_match[tm] = por_match.get(tm, 0) + 1

        cst = _s(x.get("cst_pis")) or "SEM_CST"
        por_cst[cst] = por_cst.get(cst, 0) + 1

        regra = _s(x.get("regra_simulada")) or "SEM_REGRA"
        por_regra[regra] = por_regra.get(regra, 0) + 1

    return {
        "total_linhas": total_linhas,
        "total_match": total_match,
        "total_sem_match": total_sem_match,
        "total_nao_escriturado": total_nao_escriturado,
        "total_elegiveis": total_elegiveis,

        "total_base_simulada": _q2(total_base_simulada),
        "total_pis_simulado": _q2(total_pis_simulado),
        "total_cofins_simulado": _q2(total_cofins_simulado),
        "total_credito_simulado": _q2(total_credito_simulado),

        "total_credito_match": _q2(total_credito_match),
        "total_credito_nao_escriturado": _q2(total_credito_nao_escriturado),

        "por_match": por_match,
        "por_cst_pis": por_cst,
        "por_regra": por_regra,
    }