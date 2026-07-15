from sqlalchemy.orm import Session

from app.db.models import (
    EfdVersao,
    EfdRegistro,
    ContextoFiscalVersao,
    ItemFiscalConsolidado, Empresa
)
from app.domain.ecd.ecd_services import obter_contexto_contabil_por_cod_cta, aplicar_ctx_ecd_no_item
from app.domain.fiscal.catalogo.bloqueio_classificacao_por_dominio import item_bloqueado_classificacao
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.sped.contextos.contexto_competencia import montar_contexto_competencia
from app.domain.sped.maps.icms_item_map import montar_mapa_icms_item, buscar_icms_item_em_mapa
from app.domain.sped.maps.reg0150_map import IDX_0150
from app.domain.sped.maps.reg0200_map import IDX_0200
from app.domain.sped.maps.c170_map import IDX_C170
from app.domain.sped.services.resolver_cod_cta_service import resolver_cod_cta_v2, ORIGEM_NAO_RESOLVIDO, \
    montar_candidatos_mesma_natureza
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.utils.json_utils import campos_json
from app.utils.list_utils import get_safe
from app.utils.numbers import dec_any

def materializar_contexto_fiscal(db: Session, versao_id: int):
    import time
    import logging

    logger = logging.getLogger(__name__)
    t0 = time.perf_counter()

    logger.info("## [CTX v%s] inicio ##", versao_id)

    # --------------------------------------------------
    # Helpers/cache locais
    # --------------------------------------------------
    ctx_ecd_cache = {}
    classif_cache = {}

    def get_ctx_ecd_cached(*, empresa_id: int, periodo: str, cod_cta: str):
        key = (int(empresa_id), str(periodo or ""), str(cod_cta or ""))
        if key not in ctx_ecd_cache:
            ctx_ecd_cache[key] = obter_contexto_contabil_por_cod_cta(
                db,
                empresa_id=empresa_id,
                periodo=periodo,
                cod_cta=cod_cta,
            )
        return ctx_ecd_cache[key]

    def classificar_cached(*, dominio: str, cfop: str | None, ncm: str | None):
        key = (str(dominio or ""), str(cfop or ""), str(ncm or ""))
        if key not in classif_cache:
            classif_cache[key] = classificar_item_fiscal(
                meta={
                    "dominio": dominio,
                    "cfop": cfop,
                    "ncm": ncm,
                },
                catalogo=catalogo,
            )
        return classif_cache[key]

    # --------------------------------------------------
    # 0) Limpa materialização anterior em lotes
    # --------------------------------------------------
    total_del = 0
    while True:
        ids = [
            row[0]
            for row in (
                db.query(ItemFiscalConsolidado.id)
                .filter(ItemFiscalConsolidado.versao_id == int(versao_id))
                .order_by(ItemFiscalConsolidado.id.asc())
                .limit(1000)
                .all()
            )
        ]

        if not ids:
            break

        apagados = (
            db.query(ItemFiscalConsolidado)
            .filter(ItemFiscalConsolidado.id.in_(ids))
            .delete(synchronize_session=False)
        )
        total_del += int(apagados or 0)
        db.flush()

    logger.info(
        "## [CTX v%s] itens antigos apagados=%s tempo=%.3fs ##",
        versao_id,
        total_del,
        time.perf_counter() - t0,
    )

    # --------------------------------------------------
    # 1) Carrega versão / empresa / catálogo
    # --------------------------------------------------
    versao = db.query(EfdVersao).filter(EfdVersao.id == int(versao_id)).first()
    if not versao:
        raise ValueError("Versão não encontrada")

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

    logger.info(
        "## [CTX v%s] versao carregada dominio=%s tempo=%.3fs ##",
        versao_id,
        dominio,
        time.perf_counter() - t0,
    )

    # --------------------------------------------------
    # 2) Cria contexto
    # --------------------------------------------------
    contexto = ContextoFiscalVersao(
        empresa_id=versao.empresa_id,
        versao_id=versao.id,
        periodo=versao.periodo,
        dominio=dominio,
        status="PROCESSANDO",
    )
    db.add(contexto)
    db.flush()

    # --------------------------------------------------
    # 3) Carrega registros uma vez
    # --------------------------------------------------
    registros = (
        db.query(EfdRegistro)
        .filter(EfdRegistro.versao_id == versao.id)
        .order_by(EfdRegistro.linha.asc(), EfdRegistro.id.asc())
        .all()
    )

    logger.info(
        "## [CTX v%s] registros carregados=%s tempo=%.3fs ##",
        versao_id,
        len(registros),
        time.perf_counter() - t0,
    )

    ctx_competencia = montar_contexto_competencia(
        registros=registros,
    )

    # --------------------------------------------------
    # 4) Mapas SPED Contribuições
    # --------------------------------------------------
    mapa_0150 = {}
    mapa_0200 = {}
    c100_por_chave_contrib = {}

    periodo_base = str(versao.periodo or "").strip()

    c100_atual = None
    registros_c170 = []

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

        elif r.reg == "C100":
            c100_atual = r
            chave_c100 = str(get_safe(campos, 7) or "").strip()
            if chave_c100:
                c100_por_chave_contrib[chave_c100] = {
                    "registro_id_c100": r.id,
                    "linha_c100": r.linha,
                    "campos": campos,
                }

            if not periodo_base:
                dt_doc = str(get_safe(campos, 8) or "").strip()
                if len(dt_doc) == 8:
                    periodo_base = dt_doc[4:8] + dt_doc[2:4]

        elif r.reg == "C170" and c100_atual:
            registros_c170.append((c100_atual, r))

    logger.info(
        "## [CTX v%s] mapas contrib prontos | 0150=%s 0200=%s C100=%s C170=%s tempo=%.3fs ##",
        versao_id,
        len(mapa_0150),
        len(mapa_0200),
        len(c100_por_chave_contrib),
        len(registros_c170),
        time.perf_counter() - t0,
    )

    # --------------------------------------------------
    # 5) Mapa ICMS
    # --------------------------------------------------
    mapa_icms = montar_mapa_icms_item(
        db,
        empresa_id=versao.empresa_id,
        periodo=periodo_base,
    )

    icms_itens = mapa_icms.get("itens") or []

    chaves_nf_icms = {
        str(item.chave_nfe or "").strip()
        for item in icms_itens
        if str(item.chave_nfe or "").strip()
    }

    logger.info(
        "## [CTX v%s] mapa icms itens=%s tempo=%.3fs ##",
        versao_id,
        len(icms_itens),
        time.perf_counter() - t0,
    )

    # --------------------------------------------------
    # 6) Materializa C170 Contribuições
    # --------------------------------------------------
    novos_items = []
    itens_contrib_materializados = []
    chaves_contrib = set()

    for c100_atual, reg in registros_c170:
        c100 = campos_json(c100_atual.conteudo_json)
        c170 = campos_json(reg.conteudo_json)

        periodo = str(versao.periodo or "").strip()
        if not periodo:
            dt_doc = str(get_safe(c100, 8) or "").strip()
            if len(dt_doc) == 8:
                periodo = dt_doc[4:8] + dt_doc[2:4]

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

        ncm_contrib = str(get_safe(item_0200, IDX_0200["cod_ncm"]) or "").strip() if item_0200 else ""
        ncm_icms = str(icms_item.ncm or "").strip() if icms_item else ""

        cfop_contrib = str(get_safe(c170, 9) or "").strip()
        cfop_icms = str(icms_item.cfop or "").strip() if icms_item else ""

        divergencias = []

        if icms_item:
            if ncm_contrib and ncm_icms and ncm_contrib != ncm_icms:
                divergencias.append("NCM_DIVERGENTE")

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

        descricao_item = str(
            get_safe(c170, 2) or ""
        ).strip()

        bloqueado_classificacao = item_bloqueado_classificacao(
            dominio=dominio,
            descricao=descricao_item,
        )

        semantica_fiscal = {
            "contrib": classificar_cached(
                dominio=dominio,
                cfop=cfop_contrib,
                ncm=ncm_contrib,
            ),
            "icms": (
                classificar_cached(
                    dominio=dominio,
                    cfop=cfop_icms,
                    ncm=ncm_icms,
                )
                if icms_item
                else None
            ),
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
            status_cruzamento=(
                "DIVERGENTE"
                if divergencias
                else "MATCH"
                if tem_item_icms
                else "SO_CONTRIB"
            ),

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
                "bloqueado_classificacao": bloqueado_classificacao,
                "motivo_bloqueio_classificacao": (
                    "DESCRICAO_CONTAMINANTE"
                    if bloqueado_classificacao
                    else None
                ),
                "semantica_fiscal": semantica_fiscal,
                "comparativo_icms": {
                    "ncm_contrib": ncm_contrib,
                    "ncm_icms": ncm_icms,
                    "cfop_contrib": cfop_contrib,
                    "cfop_icms": cfop_icms,
                },
            },
        )

        ctx_ecd = get_ctx_ecd_cached(
            empresa_id=versao.empresa_id,
            periodo=periodo,
            cod_cta=item.cod_cta,
        )
        aplicar_ctx_ecd_no_item(item, ctx_ecd)

        itens_contrib_materializados.append(item)
        novos_items.append(item)

    logger.info(
        "## [CTX v%s] c170 materializados=%s | cache_ecd=%s cache_classif=%s tempo=%.3fs ##",
        versao_id,
        len(itens_contrib_materializados),
        len(ctx_ecd_cache),
        len(classif_cache),
        time.perf_counter() - t0,
    )

    # --------------------------------------------------
    # 7) Segunda passada para cod_cta não resolvido
    # --------------------------------------------------
    qtd_mesma_natureza = 0

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

            ctx_ecd = get_ctx_ecd_cached(
                empresa_id=versao.empresa_id,
                periodo=item.periodo,
                cod_cta=item.cod_cta,
            )
            aplicar_ctx_ecd_no_item(item, ctx_ecd)

            qtd_mesma_natureza += 1

    logger.info(
        "## [CTX v%s] segunda passada cod_cta=%s tempo=%.3fs ##",
        versao_id,
        qtd_mesma_natureza,
        time.perf_counter() - t0,
    )

    # --------------------------------------------------
    # 8) Materializa SO_ICMS
    # --------------------------------------------------
    qtd_so_icms = 0
    qtd_so_icms_sem_c100 = 0
    qtd_so_icms_sem_c170 = 0

    for icms_item in icms_itens:
        chave_nfe_icms = str(icms_item.chave_nfe or "").strip()
        num_item_icms = str(icms_item.num_item or "").strip()
        cod_item_icms = str(icms_item.cod_item or "").strip()

        chave_icms = (
            chave_nfe_icms,
            num_item_icms,
            cod_item_icms,
        )

        # Se já existe este item na EFD Contribuições, não é SO_ICMS.
        if chave_icms in chaves_contrib:
            continue

        nf_base = getattr(icms_item, "base", None)

        modelo = (
                str(getattr(nf_base, "cod_mod", None) or "")
                or str(getattr(nf_base, "modelo", None) or "")
                or str(getattr(icms_item, "cod_mod", None) or "")
        ).strip()

        if not modelo:
            modelo = None

        c100_contrib = c100_por_chave_contrib.get(chave_nfe_icms)

        registro_id_c100_contrib = (
            c100_contrib["registro_id_c100"] if c100_contrib else None
        )
        linha_c100_contrib = (
            c100_contrib["linha_c100"] if c100_contrib else None
        )

        contrib_tem_c100 = bool(registro_id_c100_contrib)

        if modelo == "55":
            if contrib_tem_c100:
                tipo_normalizacao = "CONTRIB_SEM_C170"
                tipo_corretiva_v2 = "INSERIR_C170_EM_C100_EXISTENTE"
                reg_ancora = "C100"
                registro_id_ancora = registro_id_c100_contrib
                linha_ancora = linha_c100_contrib
                qtd_so_icms_sem_c170 += 1
            else:
                tipo_normalizacao = "CONTRIB_SEM_C100_C170"
                tipo_corretiva_v2 = "INSERIR_C100_C170"
                reg_ancora = "C990"
                registro_id_ancora = None
                linha_ancora = None
                qtd_so_icms_sem_c100 += 1

        elif modelo == "57":
            tipo_normalizacao = "CONTRIB_D100_FALTANTE"
            tipo_corretiva_v2 = "INSERIR_D100"
            reg_ancora = "D100"
            registro_id_ancora = None
            linha_ancora = None

        else:
            tipo_normalizacao = "CONTRIB_DOC_FALTANTE"
            tipo_corretiva_v2 = "NAO_SUPORTADO"
            reg_ancora = None
            registro_id_ancora = None
            linha_ancora = None

        descricao_item = str(
            getattr(icms_item, "descricao", None) or ""
        ).strip()

        bloqueado_classificacao = item_bloqueado_classificacao(
            dominio=dominio,
            descricao=descricao_item,
        )

        semantica_fiscal = {
            "contrib": None,
            "icms": classificar_cached(
                dominio=dominio,
                cfop=icms_item.cfop,
                ncm=icms_item.ncm,
            ),
        }

        nf_icms_base_id = int(getattr(icms_item, "nf_icms_base_id", 0) or 0)

        if not nf_icms_base_id and nf_base is not None:
            nf_icms_base_id = int(getattr(nf_base, "id", 0) or 0)

        dt_doc_nf = getattr(nf_base, "dt_doc", None) if nf_base else None
        dt_es_nf = getattr(nf_base, "dt_es", None) if nf_base else None

        dt_doc_txt = dt_doc_nf.isoformat() if hasattr(dt_doc_nf, "isoformat") else dt_doc_nf
        dt_es_txt = dt_es_nf.isoformat() if hasattr(dt_es_nf, "isoformat") else dt_es_nf

        item = ItemFiscalConsolidado(
            contexto_id=contexto.id,
            empresa_id=versao.empresa_id,
            versao_id=versao.id,
            periodo=periodo_base,

            registro_id_c100=registro_id_c100_contrib,
            nf_icms_item_id=icms_item.id,

            tem_no_contrib=contrib_tem_c100,
            tem_no_icms=True,
            status_cruzamento="SO_ICMS",

            chave_nfe=chave_nfe_icms,
            num_item=num_item_icms,
            cod_item=cod_item_icms,
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

                # --------------------------------------------------
                # Identificação NF / item ICMS
                # --------------------------------------------------
                "nf_icms_base_id": nf_icms_base_id,
                "nf_icms_item_id": int(icms_item.id),
                "chave_nfe": chave_nfe_icms,
                "num_item": num_item_icms,
                "cod_item": cod_item_icms,

                # Dados do documento/pai ICMS
                "cod_mod": modelo,
                "modelo": modelo,
                "cod_part": getattr(nf_base, "cod_part", None) if nf_base else None,
                "serie": getattr(nf_base, "serie", None) if nf_base else None,
                "num_doc": getattr(nf_base, "num_doc", None) if nf_base else None,
                "dt_doc": dt_doc_txt,
                "dt_es": dt_es_txt,

                # --------------------------------------------------
                # Normalização V2 — fonte da verdade
                # --------------------------------------------------
                "status_cruzamento": "SO_ICMS",
                "tipo_normalizacao": tipo_normalizacao,
                "tipo_corretiva_v2": tipo_corretiva_v2,

                "contrib_tem_c100": contrib_tem_c100,
                "registro_id_c100": registro_id_c100_contrib,
                "linha_c100": linha_c100_contrib,

                "reg_ancora": reg_ancora,
                "registro_id_ancora": registro_id_ancora,
                "linha_ancora": linha_ancora,

                "semantica_fiscal": semantica_fiscal,

                "bloqueado_classificacao": bloqueado_classificacao,
                "motivo_bloqueio_classificacao": (
                    "DESCRICAO_CONTAMINANTE"
                    if bloqueado_classificacao
                    else None
                ),
            },
        )

        novos_items.append(item)
        qtd_so_icms += 1

    logger.info(
        "## [CTX v%s] so_icms materializados=%s sem_c100=%s sem_c170=%s tempo=%.3fs ##",
        versao_id,
        qtd_so_icms,
        qtd_so_icms_sem_c100,
        qtd_so_icms_sem_c170,
        time.perf_counter() - t0,
    )

    # --------------------------------------------------
    # 9) Bulk save final
    # --------------------------------------------------
    if novos_items:
        db.bulk_save_objects(novos_items)
        db.flush()

    contexto.status = "FINALIZADO"
    db.add(contexto)
    db.commit()

    logger.info(
        "## [CTX v%s] finalizado | itens=%s | cache_ecd=%s | cache_classif=%s | tempo=%.3fs ##",
        versao_id,
        len(novos_items),
        len(ctx_ecd_cache),
        len(classif_cache),
        time.perf_counter() - t0,
    )

    print(f"[CTX] finalizado | itens={len(novos_items)}")