from sqlalchemy.orm import Session

from app.db.models import (
    EfdVersao,
    EfdRegistro,
    ContextoFiscalVersao,
    ItemFiscalConsolidado, Empresa
)
from app.domain.ecd.ecd_services import obter_contexto_contabil_por_cod_cta, aplicar_ctx_ecd_no_item
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.sped.contextos.contexto_competencia import montar_contexto_competencia
from app.domain.sped.maps.icms_item_map import montar_mapa_icms_item, buscar_icms_item_em_mapa
from app.domain.sped.maps.reg0150_map import IDX_0150
from app.domain.sped.maps.reg0200_map import IDX_0200
from app.domain.sped.maps.c170_map import IDX_C170
from app.domain.sped.services.contabil.resolver_cod_cta_service import resolver_cod_cta_v2, ORIGEM_NAO_RESOLVIDO, \
    montar_candidatos_mesma_natureza
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.utils.json_utils import campos_json
from app.utils.list_utils import get_safe
from app.utils.numbers import dec_any


def materializar_contexto_fiscal(db: Session, versao_id: int):
    print(f"[CTX] iniciando materialização versao={versao_id}")
    db.query(ItemFiscalConsolidado).filter(
        ItemFiscalConsolidado.versao_id == versao_id
    ).delete(synchronize_session=False)

    db.flush()

    versao = db.query(EfdVersao).filter(EfdVersao.id == versao_id).first()
    empresa = (
        db.query(Empresa)
        .filter(Empresa.id == versao.empresa_id)
        .first()
    )

    dominio = (
            versao.dominio
            or (empresa.dominio if empresa else None)
            or "GERAL"
    )
    catalogo = carregar_catalogo_fiscal(
        db,
        empresa_id=versao.empresa_id,
    )

    if not versao:
        raise ValueError("Versão não encontrada")

    contexto = ContextoFiscalVersao(
        empresa_id=versao.empresa_id,
        versao_id=versao.id,
        periodo=versao.periodo,
        dominio=dominio,
        status="PROCESSANDO",
    )
    db.add(contexto)
    db.flush()

    registros = (
        db.query(EfdRegistro)
        .filter(EfdRegistro.versao_id == versao.id)
        .order_by(EfdRegistro.linha)
        .all()
    )

    ctx_competencia = montar_contexto_competencia(
        registros=registros,
    )

    mapa_0150 = {}
    mapa_0200 = {}
    itens_contrib_materializados = []

    for r in registros:
        campos = campos_json(r.conteudo_json)

        if r.reg == "0150":
            cod_part_0150 = str(get_safe(campos, IDX_0150["cod_part"]) or "").strip()
            if cod_part_0150:
                mapa_0150[cod_part_0150] = campos

        elif r.reg == "0200":
            cod_item_0200 = str(get_safe(campos, IDX_0200["cod_item"]) or "").strip()
            if cod_item_0200:
                mapa_0200[cod_item_0200] = campos


    periodo_base = str(versao.periodo or "").strip()

    if not periodo_base:
        for r in registros:
            if r.reg == "C100":
                c100_tmp = campos_json(r.conteudo_json)
                dt_doc = str(get_safe(c100_tmp, 8) or "").strip()
                if len(dt_doc) == 8:
                    periodo_base = dt_doc[4:8] + dt_doc[2:4]
                    break

    mapa_icms = montar_mapa_icms_item(
        db,
        empresa_id=versao.empresa_id,
        periodo=periodo_base,
    )
    chaves_nf_icms = {
        str(item.chave_nfe or "").strip()
        for item in mapa_icms["itens"]
        if str(item.chave_nfe or "").strip()
    }

    c100_atual = None
    qtd_itens = 0
    chaves_contrib = set()

    for reg in registros:

        if reg.reg == "C100":
            c100_atual = reg
            continue

        if reg.reg != "C170":
            continue

        if not c100_atual:
            continue

        c100 = campos_json(c100_atual.conteudo_json)
        c170 = campos_json(reg.conteudo_json)
        periodo = str(versao.periodo or "").strip()

        if not periodo:
            dt_doc = str(get_safe(c100, 8) or "").strip()  # C100 DT_DOC: ddmmaaaa
            if len(dt_doc) == 8:
                periodo = dt_doc[4:8] + dt_doc[2:4]  # aaaamm
        chave_nfe = str(get_safe(c100, 7) or "").strip()
        num_item = str(get_safe(c170, 0) or "").strip()

        cod_item = str(get_safe(c170, 1) or "").strip()
        cod_part = str(get_safe(c100, 2) or "").strip()

        part_0150 = mapa_0150.get(cod_part)
        item_0200 = mapa_0200.get(cod_item)
        chaves_contrib.add((chave_nfe, num_item, cod_item))

        icms_item = buscar_icms_item_em_mapa(
            mapa_icms,
            chave_nfe=chave_nfe,
            num_item=num_item,
            cod_item=cod_item,
        )

        tem_no_icms = icms_item is not None
        tem_nf_icms = bool(chave_nfe and chave_nfe in chaves_nf_icms)
        tem_item_icms = icms_item is not None

        motivo_sem_match_item = None

        if tem_nf_icms and not tem_item_icms:
            motivo_sem_match_item = "NF_ICMS_EXISTE_ITEM_NAO_IDENTIFICADO"


        divergencias = []

        if icms_item:
            ncm_contrib = str(get_safe(item_0200, IDX_0200["cod_ncm"]) or "").strip()
            ncm_icms = str(icms_item.ncm or "").strip()

            if ncm_contrib and ncm_icms and ncm_contrib != ncm_icms:
                divergencias.append("NCM_DIVERGENTE")

            cfop_contrib = str(get_safe(c170, 9) or "").strip()
            cfop_icms = str(icms_item.cfop or "").strip()

            if cfop_contrib and cfop_icms and cfop_contrib != cfop_icms:
                divergencias.append("CFOP_DIVERGENTE")


        participante_nome = (
            icms_item.participante_nome
            if icms_item and icms_item.participante_nome
            else get_safe(part_0150, IDX_0150["nome"])
            if part_0150
            else None
        )

        participante_doc = None
        participante_tipo_doc = None

        if icms_item and icms_item.participante_cnpj:
            participante_doc = icms_item.participante_cnpj
            participante_tipo_doc = "CNPJ"
        elif part_0150:
            cnpj = get_safe(part_0150, IDX_0150["cnpj"])
            cpf = get_safe(part_0150, IDX_0150["cpf"])

            if cnpj:
                participante_doc = cnpj
                participante_tipo_doc = "CNPJ"
            elif cpf:
                participante_doc = cpf
                participante_tipo_doc = "CPF"

        ncm = (
            icms_item.ncm
            if icms_item and icms_item.ncm
            else get_safe(item_0200, IDX_0200["cod_ncm"])
            if item_0200
            else None
        )

        cod_cta_original = get_safe(c170, IDX_C170["cod_cta"])

        conta_resolvida = resolver_cod_cta_v2(
            cod_cta_original=cod_cta_original,
            contabil_0500=ctx_competencia.contabil_0500,
        )

        semantica_fiscal = {
            "contrib": classificar_item_fiscal(
                meta={
                    "dominio": dominio,
                    "cfop": cfop_contrib,
                    "ncm": ncm_contrib,
                },
                catalogo=catalogo,
            ),
            "icms": classificar_item_fiscal(
                meta={
                    "dominio": dominio,
                    "cfop": cfop_icms,
                    "ncm": ncm_icms,
                },
                catalogo=catalogo,
            ) if icms_item else None,
        }

        item = ItemFiscalConsolidado(
            contexto_id=contexto.id,
            empresa_id=versao.empresa_id,
            versao_id=versao.id,
            periodo=periodo,

            registro_id_c100=c100_atual.id,
            registro_id_c170=reg.id,
            nf_icms_item_id=icms_item.id if icms_item else None,

            tem_no_contrib=True,
            tem_no_icms=tem_no_icms,
            status_cruzamento=("DIVERGENTE" if divergencias else "MATCH" if tem_item_icms else "SO_CONTRIB" ),

            cod_part=cod_part,
            participante_nome=participante_nome,
            participante_doc=participante_doc,
            participante_tipo_doc=participante_tipo_doc,

            cod_mod=get_safe(c100, 3),
            serie=get_safe(c100, 5),
            num_doc=get_safe(c100, 6),
            chave_nfe=chave_nfe,
            dt_doc=get_safe(c100, 8),

            num_item=num_item,
            cod_item=cod_item,
            descr_item=get_safe(c170, 2),
            ncm=ncm,

            vl_item=dec_any(get_safe(c170, 5)),
            vl_desc=dec_any(get_safe(c170, 6)),
            vl_icms=icms_item.vl_icms if icms_item else None,

            cst_icms=get_safe(c170, 8),
            cfop=get_safe(c170, 9),

            cst_pis=get_safe(c170, 23),
            vl_bc_pis=dec_any(get_safe(c170, 24)),
            vl_pis=dec_any(get_safe(c170, 28)),

            cst_cofins=get_safe(c170, 29),
            vl_bc_cofins=dec_any(get_safe(c170, 30)),
            vl_cofins=dec_any(get_safe(c170, 34)),

            cod_cta=conta_resolvida.cod_cta,
            cod_cta_origem=conta_resolvida.origem,
            cod_cta_confianca=conta_resolvida.confianca,
            cod_cta_justificativa=conta_resolvida.justificativa,

            dominio=dominio,
            regime=None,

            meta={
                "origem": "EFD_CONTRIBUICOES",
                "linha_c100": c100_atual.linha,
                "linha_c170": reg.linha,
                "tem_nf_icms": tem_nf_icms,
                "tem_item_icms": tem_item_icms,
                "motivo_sem_match_item": motivo_sem_match_item,
                "divergencias": divergencias,
                "semantica_fiscal": semantica_fiscal,
                "comparativo_icms": {
                    "ncm_contrib": ncm_contrib,
                    "ncm_icms": ncm_icms,
                    "cfop_contrib": cfop_contrib,
                    "cfop_icms": cfop_icms,
                }
            },
        )
        ctx_ecd = obter_contexto_contabil_por_cod_cta(
            db,
            empresa_id=versao.empresa_id,
            periodo=periodo,
            cod_cta=item.cod_cta,
        )

        aplicar_ctx_ecd_no_item(item, ctx_ecd)
        itens_contrib_materializados.append(item)
        db.add(item)
        qtd_itens += 1

    # Resolvendo conta na segunda passada
    for item in itens_contrib_materializados:
        if item.cod_cta_origem != ORIGEM_NAO_RESOLVIDO:
            continue

        candidatos = montar_candidatos_mesma_natureza(
            alvo=item,
            itens_referencia=itens_contrib_materializados,
        )

        conta_resolvida = resolver_cod_cta_v2(
            cod_cta_original="",
            contabil_0500=ctx_competencia.contabil_0500,
            candidatos_mesma_natureza=candidatos,
        )

        if conta_resolvida.origem == "MESMA_NATUREZA":
            item.cod_cta = conta_resolvida.cod_cta
            item.cod_cta_origem = conta_resolvida.origem
            item.cod_cta_confianca = conta_resolvida.confianca
            item.cod_cta_justificativa = conta_resolvida.justificativa

            ctx_ecd = obter_contexto_contabil_por_cod_cta(
                db,
                empresa_id=versao.empresa_id,
                periodo=item.periodo,
                cod_cta=item.cod_cta,
            )

            aplicar_ctx_ecd_no_item(item, ctx_ecd)


    for icms_item in mapa_icms["itens"]:
        chave_icms = (
            str(icms_item.chave_nfe or "").strip(),
            str(icms_item.num_item or "").strip(),
            str(icms_item.cod_item or "").strip(),
        )
        modelo = icms_item.base.modelo if icms_item.base else None

        tipo_normalizacao = (
            "CONTRIB_C100_C170_FALTANTE"
            if modelo == "55"
            else "CONTRIB_D100_FALTANTE"
            if modelo == "57"
            else "CONTRIB_DOC_FALTANTE"
        )

        if chave_icms in chaves_contrib:
            continue

        semantica_fiscal = {
            "contrib": None,
            "icms": classificar_item_fiscal(
                meta={
                    "dominio": dominio,
                    "cfop": icms_item.cfop,
                    "ncm": icms_item.ncm,
                },
                catalogo=catalogo,
            ),
        }

        item = ItemFiscalConsolidado(
            contexto_id=contexto.id,
            empresa_id=versao.empresa_id,
            versao_id=versao.id,
            periodo=periodo_base,

            nf_icms_item_id=icms_item.id,

            tem_no_contrib=False,
            tem_no_icms=True,
            status_cruzamento="SO_ICMS",

            chave_nfe=icms_item.chave_nfe,
            num_item=icms_item.num_item,
            cod_item=icms_item.cod_item,
            descr_item=icms_item.descricao,
            ncm=icms_item.ncm,
            cfop=icms_item.cfop,
            cst_icms=icms_item.cst_icms,

            vl_item=icms_item.vl_item,
            vl_desc=icms_item.vl_desc,
            vl_icms=icms_item.vl_icms,

            participante_nome=icms_item.participante_nome,
            participante_doc=icms_item.participante_cnpj,
            participante_tipo_doc="CNPJ" if icms_item.participante_cnpj else None,

            dominio=dominio,
            regime=None,
            cod_mod=modelo,

            cod_cta="",
            cod_cta_origem="NAO_APLICAVEL_SO_ICMS",
            cod_cta_confianca=0,
            cod_cta_justificativa="Item vindo apenas do ICMS/IPI, sem C170 na EFD Contribuições.",

            meta={
                "origem": "EFD_ICMS_IPI",
                "icms_match": True,
                "modelo": modelo,
                "tipo_normalizacao": tipo_normalizacao,
                "semantica_fiscal": semantica_fiscal,
            },
        )

        db.add(item)
        qtd_itens += 1

    contexto.status = "FINALIZADO"
    db.commit()

    print(f"[CTX] finalizado | itens={qtd_itens}")