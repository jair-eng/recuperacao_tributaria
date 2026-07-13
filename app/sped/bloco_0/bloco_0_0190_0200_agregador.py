from __future__ import annotations

from sqlalchemy.orm import Session
from app.db.models import EfdRevisao, NfIcmsBase, NfIcmsItem, EfdRegistro, ItemFiscalConsolidado, Empresa, EfdVersao
from app.domain.relatorio_executivo.extrair_conta_efd_para_fallback import carregar_contas_0500_local
from app.icms_ipi.icms_0150_agregador import resolver_ou_criar_0150_por_cnpj, _buscar_0150_logico_por_cnpj, \
    _buscar_0150_logico_por_cod_part, _fmt_campo, _somente_digitos
from app.icms_ipi.icms_helpers import _campo
from app.legacy_service.versao_overlay_service import carregar_linhas_logicas_com_revisoes_e_insert
from app.sped.bloco_0.bloco_0_helpers import _norm, _norm_upper, _existe_0190_na_versao, _existe_0200_na_versao
from typing import Dict, List, Optional
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.sped.utils_cod_cta import resolver_tipo_conta_por_cenario, resolver_cod_cta_por_catalogo_0500
from app.utils.classificacao_utils import classificar_c170_por_catalogo
from app.utils.sped import montar_cache_mestres_logicos
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def _resolver_ancora_bloco0_mestres_icms_ipi(
    db: Session,
    *,
    versao_origem_id: int,
) -> tuple[int | None, int]:
    # âncora estrutural estável: último 0140 original
    reg = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "0140",
        )
        .order_by(EfdRegistro.linha.desc())
        .first()
    )

    if reg:
        return getattr(reg, "id", None), int(getattr(reg, "linha", 0) or 0)

    # fallback seguro
    for reg_code in ("0120", "0110", "0100", "0001", "0000"):
        reg = (
            db.query(EfdRegistro)
            .filter(
                EfdRegistro.versao_id == int(versao_origem_id),
                EfdRegistro.reg == reg_code,
            )
            .order_by(EfdRegistro.linha.desc())
            .first()
        )
        if reg:
            return getattr(reg, "id", None), int(getattr(reg, "linha", 0) or 0)

    return None, 0

def _resolver_ancora_para_0190(
    db: Session,
    *,
    versao_origem_id: int,
) -> tuple[int | None, int]:
    linhas = carregar_linhas_logicas_com_revisoes_e_insert(
        db,
        versao_origem_id=int(versao_origem_id),
        versao_final_id=None,
    )

    ordem_preferencia = ("0190", "0150", "0140", "0110", "0100", "0001", "0000")

    for reg_ancora in ordem_preferencia:
        candidatos = [
            l for l in linhas
            if str(getattr(l, "reg", "")).upper() == reg_ancora
        ]
        if candidatos:
            ultimo = candidatos[-1]
            return (
                getattr(ultimo, "registro_id", None),
                int(getattr(ultimo, "linha", 0) or 0),
            )

    return None, 0

def _resolver_ancora_para_0200(
    db: Session,
    *,
    versao_origem_id: int,
) -> tuple[int | None, int]:
    linhas = carregar_linhas_logicas_com_revisoes_e_insert(
        db,
        versao_origem_id=int(versao_origem_id),
        versao_final_id=None,
    )

    ordem_preferencia = ("0200", "0190", "0150", "0140", "0110", "0100", "0001", "0000")

    for reg_ancora in ordem_preferencia:
        candidatos = [
            l for l in linhas
            if str(getattr(l, "reg", "")).upper() == reg_ancora
        ]
        if candidatos:
            ultimo = candidatos[-1]
            return (
                getattr(ultimo, "registro_id", None),
                int(getattr(ultimo, "linha", 0) or 0),
            )

    return None, 0


def garantir_0190_para_item(
    db: Session,
    *,
    versao_origem_id: int,
    unid: Optional[str],
    motivo_codigo: str = "CONTRIB_SEM_0190_V1",
    apontamento_id: int | None = None,
    cache_mestres: dict | None = None,
) -> Optional[str]:

    unid_final = _norm_upper(unid)

    if not unid_final:
        print("[DBG 0190] unidade vazia, skip", flush=True)
        return None
    if cache_mestres is not None and unid_final in cache_mestres["0190"]:
        return unid_final

    if cache_mestres is None and _existe_0190_na_versao(
            db,
            versao_origem_id=versao_origem_id,
            unid=unid_final,
    ):
        return unid_final

    if cache_mestres is not None and cache_mestres.get("ancora_0190"):
        registro_id_alvo, linha_ref = cache_mestres["ancora_0190"]
    else:
        registro_id_alvo, linha_ref = _resolver_ancora_bloco0_mestres_icms_ipi(
            db,
            versao_origem_id=versao_origem_id,
        )
        if cache_mestres is not None:
            cache_mestres["ancora_0190"] = (registro_id_alvo, linha_ref)

    # mantém padrão simples e estável
    linha_nova = f"|0190|{unid_final}|Unidade Importada Nfe|"

    rv = EfdRevisao(
        versao_origem_id=int(versao_origem_id),
        versao_revisada_id=None,
        registro_id=registro_id_alvo,
        reg="0190",
        acao="INSERT_AFTER",
        revisao_json={
            "linha_nova": linha_nova,
            "linha_referencia": int(linha_ref or 0),
            "origem": "ICMS_IPI",
            "_ordem_bloco0": 190,
            "motivo": f"Cadastro 0190 necessário para item importado do ICMS/IPI ({unid_final})",
        },
        motivo_codigo=motivo_codigo,
        apontamento_id=apontamento_id,
    )
    db.add(rv)
    db.flush()

    if cache_mestres is not None:
        cache_mestres["0190"].add(unid_final)

    return unid_final

def garantir_0200_para_item(
    db: Session,
    *,
    versao_origem_id: int,
    cod_item: Optional[str],
    descr_item: Optional[str],
    unid: Optional[str],
    ncm: Optional[str] = None,
    motivo_codigo: str = "CONTRIB_SEM_0200_V1",
    apontamento_id: int | None = None,
    cache_mestres: dict | None = None,
) -> Optional[str]:
    cod_item_final = _norm(cod_item)
    descr_item_final = _norm(descr_item)
    unid_final = _norm_upper(unid)
    ncm_final = _norm(ncm)

    if not cod_item_final:
        print("[DBG 0200] cod_item vazio, skip", flush=True)
        return None

    if not descr_item_final:
        descr_item_final = cod_item_final

    if cache_mestres is not None and cod_item_final in cache_mestres["0200"]:
        return cod_item_final

    if cache_mestres is None and _existe_0200_na_versao(
            db,
            versao_origem_id=versao_origem_id,
            cod_item=cod_item_final,
    ):
        return cod_item_final

    if cache_mestres is not None and cache_mestres.get("ancora_0200"):
        registro_id_alvo, linha_ref = cache_mestres["ancora_0200"]
    else:
        registro_id_alvo, linha_ref = _resolver_ancora_bloco0_mestres_icms_ipi(
            db,
            versao_origem_id=versao_origem_id,
        )
        if cache_mestres is not None:
            cache_mestres["ancora_0200"] = (registro_id_alvo, linha_ref)

    # padrão aceito no seu arquivo/PVA
    # |0200|COD_ITEM|DESCR_ITEM|COD_BARRA|COD_ANT_ITEM|UNID_INV|TIPO_ITEM|COD_NCM|EX_IPI|COD_GEN|COD_LST|ALIQ_ICMS|
    cod_gen = ncm_final[:2] if ncm_final else ""

    campos_0200 = [
        "0200",
        cod_item_final,     # COD_ITEM
        descr_item_final,   # DESCR_ITEM
        "",                 # COD_BARRA
        "",                 # COD_ANT_ITEM
        unid_final,         # UNID_INV
        "00",               # TIPO_ITEM
        ncm_final,          # COD_NCM
        "",                 # EX_IPI
        cod_gen,            # COD_GEN
        "",                 # COD_LST
        "",                 # ALIQ_ICMS
    ]
    linha_nova = "|" + "|".join(campos_0200) + "|"

    rv = EfdRevisao(
        versao_origem_id=int(versao_origem_id),
        versao_revisada_id=None,
        registro_id=registro_id_alvo,
        reg="0200",
        acao="INSERT_AFTER",
        revisao_json={
            "linha_nova": linha_nova,
            "linha_referencia": int(linha_ref or 0),
            "origem": "ICMS_IPI",
            "_ordem_bloco0": 200,
            "motivo": f"Cadastro 0200 necessário para item importado do ICMS/IPI ({cod_item_final})",
        },
        motivo_codigo=motivo_codigo,
        apontamento_id=apontamento_id,
    )
    db.add(rv)
    db.flush()

    if cache_mestres is not None:
        cache_mestres["0200"].add(cod_item_final)
    return cod_item_final


def garantir_0500_conta_padrao(
    db: Session,
    *,
    versao_origem_id: int,
    cod_cta: str | None = None,
    nome_cta: str | None = None,
    apontamento_id: int | None = None,
) -> str:

    cod_cta = str(cod_cta or "").strip() or "999999"
    nome_cta = str(nome_cta or "").strip() or "CONTA CONTABIL A DEFINIR"

    if _existe_0500_conta_padrao_na_versao_ou_revisao(
        db,
        versao_origem_id=versao_origem_id,
        cod_cta=cod_cta,
    ):
        return cod_cta

    registro_id_alvo, linha_ref = _resolver_ancora_bloco0_mestres_icms_ipi(
        db,
        versao_origem_id=versao_origem_id,    )


    linha_nova = f"|0500|01012014|04|A|5|{cod_cta}|{nome_cta}|||"

    rv = EfdRevisao(
        versao_origem_id=int(versao_origem_id),
        versao_revisada_id=None,
        registro_id=registro_id_alvo,
        reg="0500",
        acao="INSERT_AFTER",
        revisao_json={
            "linha_nova": linha_nova,
            "linha_referencia": int(linha_ref or 0),
            "origem": "ICMS_IPI",
            "motivo": f"Cadastro 0500 necessário para conta contábil padrão ({cod_cta})",
            "cod_cta": cod_cta,
            "nome_cta": nome_cta,
            "_ordem_bloco0": 500,
        },
        motivo_codigo="CONTRIB_CONTA_0500_V1",
        apontamento_id=apontamento_id,
    )
    db.add(rv)
    db.flush()

    logger.warning(
        "[0500_CTA_CRIADO] rv_id=%s linha_ref=%s cod_cta=%s nome_cta=%s linha=%s",
        rv.id,
        linha_ref,
        cod_cta,
        nome_cta,
        linha_nova,
    )

    return cod_cta

def _existe_0500_conta_padrao_na_versao_ou_revisao(
    db: Session,
    *,
    versao_origem_id: int,
    cod_cta: str,
) -> bool:
    cod_cta = (cod_cta or "").strip()
    if not cod_cta:
        return True

    # base
    regs = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "0500",
        )
        .all()
    )
    for reg in regs:
        conteudo = getattr(reg, "conteudo_json", None) or {}
        dados = list(conteudo.get("dados") or []) if isinstance(conteudo, dict) else []
        if len(dados) > 4 and str(dados[4] or "").strip() == cod_cta:
            return True

    # revisão
    revs = (
        db.query(EfdRevisao)
        .filter(
            EfdRevisao.versao_origem_id == int(versao_origem_id),
            EfdRevisao.reg == "0500",
            EfdRevisao.acao.in_(["INSERT_AFTER", "INSERT_BEFORE"]),
        )
        .all()
    )
    for rv in revs:
        j = getattr(rv, "revisao_json", None) or {}
        if str(j.get("cod_cta") or "").strip() == cod_cta:
            return True

    return False

def _cod_cta_valido_para_0500(cod_cta: str | None) -> bool:
    cod = str(cod_cta or "").strip().upper()

    return bool(
        cod
        and cod not in {
            "0000",
            "NAO_APLICAVEL_SO_ICMS",
            "NAO_APLICAVEL",
            "SEM_CONTA",
        }
    )


def _garantir_mestres_para_notas_elegiveis(
    db: Session,
    *,
    versao_origem_id: int,
    notas_elegiveis: List[tuple[NfIcmsBase, List[NfIcmsItem], str]],
    cache_mestres: dict | None = None,
) -> Dict[str, int]:

    total_0150 = 0
    total_0190 = 0
    total_0200 = 0
    total_0500 = 0

    if cache_mestres is None:
        cache_mestres = montar_cache_mestres_logicos(
            db,
            versao_origem_id=versao_origem_id,
        )

    unids_vistas: set[str] = set()
    cod_items_vistos: set[str] = set()

    versao = (
        db.query(EfdVersao)
        .filter(EfdVersao.id == int(versao_origem_id))
        .first()
    )

    empresa_id = int(getattr(versao, "empresa_id", 0) or 0)
    empresa = (db.query(Empresa)
        .filter(Empresa.id == empresa_id)
        .first()
    )

    cnpj_empresa = _somente_digitos(getattr(empresa, "cnpj", None))

    contas_0500 = carregar_contas_0500_local(caminho_catalogo=Path(r"C:\Sped\saida\catalogo_0500_contrib.json"),cnpj_empresa=cnpj_empresa,)


    for nf, itens, chave in notas_elegiveis:
        cod_part_nf = _fmt_campo(getattr(nf, "cod_part", None))
        cnpj_nf = _somente_digitos(getattr(nf, "participante_cnpj", None))

        ja_existia_0150_antes = (
            cod_part_nf in cache_mestres["0150_cod_part"]
            or cnpj_nf in cache_mestres["0150_cnpj"]
        )

        cod_part_final = resolver_ou_criar_0150_por_cnpj(
            db,
            versao_id=versao_origem_id,
            nf=nf,
            cache_mestres=cache_mestres,
        )

        nf.cod_part = cod_part_final

        if cod_part_final and not ja_existia_0150_antes:
            total_0150 += 1

        for it in itens:
            unid_item = (getattr(it, "unid", None) or "").strip().upper()
            cod_item_item = (getattr(it, "cod_item", None) or "").strip()
            descr_item_item = (getattr(it, "descricao", None) or "").strip()

            if unid_item and unid_item not in unids_vistas:
                if unid_item not in cache_mestres["0190"]:
                    garantir_0190_para_item(
                        db,
                        versao_origem_id=versao_origem_id,
                        unid=unid_item,
                        cache_mestres=cache_mestres,
                    )
                    cache_mestres["0190"].add(unid_item)
                    total_0190 += 1

                unids_vistas.add(unid_item)

            if cod_item_item and cod_item_item not in cod_items_vistos:
                if cod_item_item not in cache_mestres["0200"]:
                    garantir_0200_para_item(
                        db,
                        versao_origem_id=versao_origem_id,
                        cod_item=cod_item_item,
                        descr_item=descr_item_item,
                        unid=unid_item,
                        ncm=getattr(it, "ncm", None),
                        cache_mestres=cache_mestres,
                    )
                    cache_mestres["0200"].add(cod_item_item)
                    total_0200 += 1

                cod_items_vistos.add(cod_item_item)

            nf_icms_item_id = int(getattr(it, "id", 0) or 0)

            if nf_icms_item_id:
                item_cons = (
                    db.query(ItemFiscalConsolidado)
                    .filter(
                        ItemFiscalConsolidado.versao_id == int(versao_origem_id),
                        ItemFiscalConsolidado.nf_icms_item_id == nf_icms_item_id,
                    )
                    .first()
                )
                logger.warning(
                    "[0500_CTA_DBG_ITEM] nf_icms_item_id=%s achou_item_cons=%s cod_item=%s desc=%s "
                    "cod_cta=%s cod_cta_origem=%s categoria_catalogo=%s categoria_ecd=%s periodo=%s",
                    nf_icms_item_id,
                    bool(item_cons),
                    getattr(it, "cod_item", None),
                    getattr(it, "descricao", None),
                    getattr(item_cons, "cod_cta", None) if item_cons else None,
                    getattr(item_cons, "cod_cta_origem", None) if item_cons else None,
                    getattr(item_cons, "categoria_catalogo", None) if item_cons else None,
                    getattr(item_cons, "categoria_ecd", None) if item_cons else None,
                    getattr(item_cons, "periodo", None) if item_cons else None,
                )

                if item_cons:
                    cod_cta_real = (
                            str(getattr(item_cons, "cod_cta", "") or "").strip()
                            or str(getattr(item_cons, "cod_cta_origem", "") or "").strip()
                    )

                    nome_cta_real = (
                            str(getattr(item_cons, "conta_nome", "") or "").strip()
                            or str(getattr(item_cons, "ecd_conta_nome", "") or "").strip()
                            or ""
                    )
                    categoria_busca = (
                            str(getattr(item_cons, "categoria_ecd", "") or "").strip()
                            or str(getattr(item_cons, "categoria_catalogo", "") or "").strip()
                    )

                    if not categoria_busca:
                        item_catalogo = {
                            "descr_compl": (
                                    str(getattr(item_cons, "descr_item", "") or "").strip()
                                    or str(getattr(it, "descricao", "") or "").strip()
                            ),
                            "cod_item": str(getattr(it, "cod_item", "") or "").strip(),
                            "ncm": str(getattr(it, "ncm", "") or "").strip(),
                        }

                        cls_cat = classificar_c170_por_catalogo(
                            item=item_catalogo,
                            catalogo=carregar_catalogo_fiscal(db),
                            dominio=str(getattr(item_cons, "dominio", "")),
                        )
                        categoria_busca = str(cls_cat.get("categoria") or "").strip()
                        if categoria_busca.upper() == "NAOCLASSIFICADO":
                            categoria_busca = ""

                        logger.warning("[ITEM] categoria=%s", categoria_busca)
                        logger.warning(
                            "[0500_CTA_DBG_CATALOGO] nf_icms_item_id=%s categoria=%s origem=%s slug=%s",
                            nf_icms_item_id,
                            categoria_busca,
                            cls_cat.get("origem_classificacao"),
                            cls_cat.get("slug_match"),
                        )

                    if not _cod_cta_valido_para_0500(cod_cta_real) and categoria_busca:

                        fundamentos = getattr(item_cons, "fundamento_legal", None)

                        tipo_conta = resolver_tipo_conta_por_cenario(
                            dominio=getattr(item_cons, "dominio", ""),
                            categoria=categoria_busca,
                            fundamentos=fundamentos,
                        )

                        conta_resolvida = resolver_cod_cta_por_catalogo_0500(
                            tipo_conta=tipo_conta,
                            categoria=categoria_busca,
                            contas_0500=contas_0500,
                            uf_filial=None,
                        )

                        cod_cta_real = str(conta_resolvida.get("cod_cta") or "0000").strip()
                        nome_cta_real = str(
                            conta_resolvida.get("nome_cta") or "CONTA NAO RESOLVIDA"
                        ).strip()

                        logger.warning(
                            "[0500_CTA_RESOLVE] categoria=%s  cod_cta=%s nome=%s origem=%s",
                            categoria_busca,

                            cod_cta_real,
                            nome_cta_real,
                            conta_resolvida.get("origem_resolucao"),
                        )

                    logger.warning(
                        "[0500_CTA_DBG_FINAL] nf_icms_item_id=%s cod_cta_final=%s valido=%s nome_cta=%s ja_no_cache=%s",
                        nf_icms_item_id,
                        cod_cta_real,
                        _cod_cta_valido_para_0500(cod_cta_real),
                        nome_cta_real,
                        cod_cta_real in cache_mestres["0500"] if cod_cta_real else None,
                    )

                    cod_cta_real = cod_cta_real if _cod_cta_valido_para_0500(cod_cta_real) else "999999"
                    nome_cta_real = nome_cta_real or (
                        "CONTA CONTABIL A DEFINIR"
                        if cod_cta_real == "999999"
                        else "Conta ECD"
                    )

                    if cod_cta_real not in cache_mestres["0500"]:
                        garantir_0500_conta_padrao(
                            db,
                            versao_origem_id=versao_origem_id,
                            cod_cta=cod_cta_real,
                            nome_cta=nome_cta_real,
                        )
                        cache_mestres["0500"].add(cod_cta_real)
                        total_0500 += 1

    return {
        "total_0150": total_0150,
        "total_0190": total_0190,
        "total_0200": total_0200,
        "total_0500": total_0500,
    }