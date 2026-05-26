from __future__ import annotations

from sqlalchemy.orm import Session
from app.db.models import EfdRevisao, NfIcmsBase, NfIcmsItem, EfdRegistro
from app.icms_ipi.icms_0150_agregador import resolver_ou_criar_0150_por_cnpj, _buscar_0150_logico_por_cnpj, \
    _buscar_0150_logico_por_cod_part, _fmt_campo, _somente_digitos
from app.icms_ipi.icms_helpers import _campo
from app.legacy_service.versao_overlay_service import carregar_linhas_logicas_com_revisoes_e_insert
from app.sped.bloco_0.bloco_0_helpers import _norm, _norm_upper, _existe_0190_na_versao, _existe_0200_na_versao
from typing import Dict, List, Optional




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
) -> Optional[str]:
    unid_final = _norm_upper(unid)
    if not unid_final:
        print("[DBG 0190] unidade vazia, skip", flush=True)
        return None

    if _existe_0190_na_versao(
        db,
        versao_origem_id=versao_origem_id,
        unid=unid_final,
    ):

        return unid_final

    registro_id_alvo, linha_ref = _resolver_ancora_para_0190(
        db,
        versao_origem_id=versao_origem_id,
    )

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
            "motivo": f"Cadastro 0190 necessário para item importado do ICMS/IPI ({unid_final})",
        },
        motivo_codigo=motivo_codigo,
        apontamento_id=apontamento_id,
    )
    db.add(rv)
    db.flush()

    print(
        "[DBG 0190 CRIADO]",
        {
            "rv_id": rv.id,
            "unid": unid_final,
            "linha_nova": linha_nova,
            "linha_ref": linha_ref,
        },
        flush=True,
    )

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

    if _existe_0200_na_versao(
        db,
        versao_origem_id=versao_origem_id,
        cod_item=cod_item_final,
    ):

        return cod_item_final

    registro_id_alvo, linha_ref = _resolver_ancora_para_0200(
        db,
        versao_origem_id=versao_origem_id,
    )

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
            "motivo": f"Cadastro 0200 necessário para item importado do ICMS/IPI ({cod_item_final})",
        },
        motivo_codigo=motivo_codigo,
        apontamento_id=apontamento_id,
    )
    db.add(rv)
    db.flush()

    print(
        "[DBG 0200 CRIADO]",
        {
            "rv_id": rv.id,
            "cod_item": cod_item_final,
            "descr_item": descr_item_final,
            "unid": unid_final,
            "ncm": ncm_final,
            "linha_nova": linha_nova,
            "linha_ref": linha_ref,
        },
        flush=True,
    )

    return cod_item_final


def _existe_cod_item_0200_na_versao_ou_revisao(
    db: Session,
    *,
    versao_origem_id: int,
    cod_item: str,
) -> bool:
    cod_item = (cod_item or "").strip()
    if not cod_item:
        return True

    linhas = carregar_linhas_logicas_com_revisoes_e_insert(
        db,
        versao_origem_id=int(versao_origem_id),
        versao_final_id=None,
    )

    for l in linhas:
        if str(getattr(l, "reg", "")).upper() != "0200":
            continue

        dados = list(getattr(l, "dados", []) or [])
        # ajuste o índice se necessário
        cod_item_linha = str(_campo(dados, 1) or "").strip()
        if cod_item_linha == cod_item:
            return True

    return False

def _existe_unidade_0190_na_versao_ou_revisao(
    db: Session,
    *,
    versao_origem_id: int,
    unid: str,
) -> bool:
    unid = (unid or "").strip().upper()
    if not unid:
        return True

    linhas = carregar_linhas_logicas_com_revisoes_e_insert(
        db,
        versao_origem_id=int(versao_origem_id),
        versao_final_id=None,
    )

    for l in linhas:
        if str(getattr(l, "reg", "")).upper() != "0190":
            continue

        dados = list(getattr(l, "dados", []) or [])
        # ajuste o índice se seu helper _campo for diferente
        unid_linha = str(_campo(dados, 1) or "").strip().upper()
        if unid_linha == unid:
            return True

    return False


def garantir_0500_conta_padrao(
    db: Session,
    *,
    versao_origem_id: int,
    cod_cta: str = "25666",
    nome_cta: str = "Conta mercadorias",
    apontamento_id: int | None = None,
) -> str:
    if _existe_0500_conta_padrao_na_versao_ou_revisao(
        db,
        versao_origem_id=versao_origem_id,
        cod_cta=cod_cta,
    ):
        return cod_cta

    # âncora simples no bloco 0
    registro_id_alvo = None
    linha_ref = 0
    for reg_code in ("0500", "0400", "0200", "0190", "0150", "0140", "0120", "0110", "0100", "0001", "0000"):
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
            registro_id_alvo = getattr(reg, "id", None)
            linha_ref = int(getattr(reg, "linha", 0) or 0)
            break

    nome_cta = "Mercadorias"
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
        },
        motivo_codigo="CONTRIB_CONTA_0500_V1",
        apontamento_id=apontamento_id,
    )
    db.add(rv)
    db.flush()

    print(
        "[DBG 0500 CRIADO]",
        {"rv_id": rv.id, "linha_ref": linha_ref, "cod_cta": cod_cta},
        flush=True,
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

def _garantir_mestres_para_notas_elegiveis(
    db: Session,
    *,
    versao_origem_id: int,
    notas_elegiveis: List[tuple[NfIcmsBase, List[NfIcmsItem], str]],
) -> Dict[str, int]:
    total_0150 = 0
    total_0190 = 0
    total_0200 = 0
    total_0500 = 0

    unids_vistas: set[str] = set()
    cod_items_vistos: set[str] = set()

    # 0) garante 0500 uma vez só para a versão
    cod_cta_antes = _existe_0500_conta_padrao_na_versao_ou_revisao(
        db,
        versao_origem_id=versao_origem_id,
        cod_cta="25666",
    )

    if not cod_cta_antes:
        garantir_0500_conta_padrao(
            db,
            versao_origem_id=versao_origem_id,
            cod_cta="25666",
            nome_cta="Conta mercadorias",
        )
        total_0500 += 1

    for nf, itens, chave in notas_elegiveis:
        cod_part_nf = _fmt_campo(getattr(nf, "cod_part", None))
        cnpj_nf = _somente_digitos(getattr(nf, "participante_cnpj", None))

        ja_existia_0150_antes = False

        if cod_part_nf:
            found = _buscar_0150_logico_por_cod_part(
                db,
                versao_id=versao_origem_id,
                cod_part=cod_part_nf,
            )
            if found:
                ja_existia_0150_antes = True

        if not ja_existia_0150_antes and cnpj_nf:
            found = _buscar_0150_logico_por_cnpj(
                db,
                versao_id=versao_origem_id,
                cnpj=cnpj_nf,
            )
            if found:
                ja_existia_0150_antes = True

        cod_part_final = resolver_ou_criar_0150_por_cnpj(
            db,
            versao_id=versao_origem_id,
            nf=nf,
        )

        nf.cod_part = cod_part_final

        if cod_part_final and not ja_existia_0150_antes:
            total_0150 += 1

        # 2) garante 0190/0200 só dos itens desta NF elegível
        for it in itens:
            unid_item = (getattr(it, "unid", None) or "").strip().upper()
            cod_item_item = (getattr(it, "cod_item", None) or "").strip()
            descr_item_item = (getattr(it, "descricao", None) or "").strip()

            if unid_item and unid_item not in unids_vistas:
                existed_0190 = _existe_unidade_0190_na_versao_ou_revisao(
                    db,
                    versao_origem_id=versao_origem_id,
                    unid=unid_item,
                )

                if not existed_0190:
                    garantir_0190_para_item(
                        db,
                        versao_origem_id=versao_origem_id,
                        unid=unid_item,
                    )
                    total_0190 += 1

                unids_vistas.add(unid_item)

            if cod_item_item and cod_item_item not in cod_items_vistos:
                existed_0200 = _existe_cod_item_0200_na_versao_ou_revisao(
                    db,
                    versao_origem_id=versao_origem_id,
                    cod_item=cod_item_item,
                )

                if not existed_0200:
                    garantir_0200_para_item(
                        db,
                        versao_origem_id=versao_origem_id,
                        cod_item=cod_item_item,
                        descr_item=descr_item_item,
                        unid=unid_item,
                        ncm=getattr(it, "ncm", None),
                    )
                    total_0200 += 1

                cod_items_vistos.add(cod_item_item)

    return {
        "total_0150": total_0150,
        "total_0190": total_0190,
        "total_0200": total_0200,
        "total_0500": total_0500,
    }