from __future__ import annotations
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.Legacy.fiscal.settings_fiscais import _cst_sem_credito
from app.db.models.efd_registro import EfdRegistro
from app.db.models.efd_revisao import EfdRevisao
from sqlalchemy import func
from app.sped.blocoC.c100_utils import patch_c100_totais_imposto, salvar_revisao_c100_automatica
from app.sped.blocoC.c170_utils import patch_c170_campos, _validar_linha_c170
from app.sped.formatter import formatar_linha
import traceback
from app.sped.logic.consolidador import (
    _get_dados,
    calcular_totais_filhos, norm,
    popular_pai_id, eh_pf_por_c100, ensure_len,
    calcular_totais_filhos_overlay
)


def revisar_c170(
    db: Session,
    *,
    registro_id: int,
    versao_origem_id: int,
    cfop: Optional[str],
    cst_pis: Optional[str],
    cst_cofins: Optional[str],
    motivo_codigo: str,
    apontamento_id: Optional[int] = None,
    dominio: Optional[str] = None,
    contexto: Optional[str] = None,
    fator_base_credito: Optional[float] = None,
    aliq_pis: Optional[str] = None,
    aliq_cofins: Optional[str] = None,

    # novos campos explícitos
    vl_bc_pis: Any = None,
    vl_pis: Any = None,
    vl_bc_cofins: Any = None,
    vl_cofins: Any = None,
    natureza_credito_m: Optional[str] = None,
    meta_fiscal: Optional[Dict[str, Any]] = None,
    cod_cred: Optional[str] = None,
    nat_bc_cred: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Realiza a revisão de um registro C170 (CNPJ já validado no chamador).
    Blindado contra registros com poucos campos (IndexError).
    """

    cfop = norm(cfop)
    cst_pis = norm(cst_pis)
    cst_cofins = norm(cst_cofins)

    # 1) Localiza o registro na versão certa
    r = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.id == int(registro_id),
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "C170",
        )
        .first()
    )
    if not r:
        raise ValueError("Registro C170 não encontrado na versão informada.")

    dados_originais = _get_dados(r) or []

    # 2) Blindagem: garante tamanho mínimo para índices usados
    # CFOP (9), CST_PIS (23), CST_COFINS (29)
    for idx in (9, 23, 29):
        ensure_len(dados_originais, idx)

    # 3) Aplica patch
    novos_campos = patch_c170_campos(
        dados_originais,
        cfop=cfop,
        cst_pis=cst_pis,
        cst_cofins=cst_cofins,
        dominio=dominio,
        contexto=contexto,
        fator_base_credito=fator_base_credito,
        aliq_pis=aliq_pis,
        aliq_cofins=aliq_cofins,

        vl_bc_pis=vl_bc_pis,
        vl_pis=vl_pis,
        vl_bc_cofins=vl_bc_cofins,
        vl_cofins=vl_cofins,
    )
    # ✅ se CST virar não creditável, zera campos de PIS/COFINS
    if _cst_sem_credito(cst_pis) or _cst_sem_credito(cst_cofins):
        for idx in (24, 25, 26, 27, 28, 30, 31, 32, 33, 34):
            ensure_len(novos_campos, idx)

        novos_campos[24] = "0"
        novos_campos[25] = "0"
        novos_campos[26] = ""
        novos_campos[27] = "0"
        novos_campos[28] = "0"

        novos_campos[30] = "0"
        novos_campos[31] = "0"
        novos_campos[32] = ""
        novos_campos[33] = "0"
        novos_campos[34] = "0"

    # blindagem extra
    for idx in (9, 23, 29):
        ensure_len(novos_campos, idx)

    # 4) Formata linha nova + valida
    linha_nova = formatar_linha("C170", novos_campos).strip()
    linha_nova = _validar_linha_c170(linha_nova)

    meta_fiscal_final = dict(meta_fiscal or {})

    codigo_cenario = (
            meta_fiscal_final.get("codigo_cenario")
            or meta_fiscal_final.get("cenario")
            or contexto
    )

    enquadramento_final = dict(meta_fiscal_final.get("enquadramento") or {})

    cod_cred_final = (
            meta_fiscal_final.get("cod_cred")
            or meta_fiscal_final.get("tipo_credito_codigo")
            or cod_cred
            or enquadramento_final.get("tipo_credito_codigo")
            or enquadramento_final.get("cod_cred")
    )

    nat_bc_cred_final = (
            meta_fiscal_final.get("nat_bc_cred")
            or meta_fiscal_final.get("base_credito_codigo")
            or nat_bc_cred
            or natureza_credito_m
            or enquadramento_final.get("base_credito_codigo")
            or enquadramento_final.get("nat_bc_cred")
    )

    cst_pis_final = (
            cst_pis
            or meta_fiscal_final.get("cst_pis_destino")
            or meta_fiscal_final.get("cst_pis")
            or enquadramento_final.get("cst_pis_destino")
            or enquadramento_final.get("cst_pis")
    )

    cst_cofins_final = (
            cst_cofins
            or meta_fiscal_final.get("cst_cofins_destino")
            or meta_fiscal_final.get("cst_cofins")
            or enquadramento_final.get("cst_cofins_destino")
            or enquadramento_final.get("cst_cofins")
    )

    if cst_pis_final not in (None, ""):
        cst_pis_final = str(cst_pis_final).strip().zfill(2)

    if cst_cofins_final not in (None, ""):
        cst_cofins_final = str(cst_cofins_final).strip().zfill(2)

    enquadramento_final.update({
        "cst_pis_destino": cst_pis_final,
        "cst_cofins_destino": cst_cofins_final,
        "cst_pis": cst_pis_final,
        "cst_cofins": cst_cofins_final,
        "aliq_pis": aliq_pis,
        "aliq_cofins": aliq_cofins,
    })

    meta_fiscal_final.update({
        "codigo_cenario": codigo_cenario,
        "cenario": codigo_cenario,
        "enquadramento": enquadramento_final,

        "cst_pis_destino": cst_pis_final,
        "cst_cofins_destino": cst_cofins_final,
        "cst_pis": cst_pis_final,
        "cst_cofins": cst_cofins_final,

        "aliq_pis": aliq_pis,
        "aliq_cofins": aliq_cofins,
        "vl_bc_pis": vl_bc_pis,
        "vl_pis": vl_pis,
        "vl_bc_cofins": vl_bc_cofins,
        "vl_cofins": vl_cofins,

        "cod_cred": cod_cred_final,
        "tipo_credito_codigo": cod_cred_final,
        "nat_bc_cred": nat_bc_cred_final,
        "base_credito_codigo": nat_bc_cred_final,
        "cod_base_credito": nat_bc_cred_final,
        "contexto_credito": codigo_cenario,
        "natureza_credito_m": nat_bc_cred_final,
    })

    payload_rev = {
        "linha_referencia": int(getattr(r, "linha", 0)),
        "linha_nova": linha_nova,

        "meta": {
            **meta_fiscal_final,

            "tipo_apontamento": motivo_codigo,
            "tipo_corretiva_v2": "PATCH_C170_EXISTENTE",

            "cst_pis": cst_pis_final,
            "cst_cofins": cst_cofins_final,
            "cst_pis_destino": cst_pis_final,
            "cst_cofins_destino": cst_cofins_final,

            "aliq_pis": aliq_pis,
            "aliq_cofins": aliq_cofins,
            "vl_bc_pis": vl_bc_pis,
            "vl_pis": vl_pis,
            "vl_bc_cofins": vl_bc_cofins,
            "vl_cofins": vl_cofins,

            "codigo_cenario": codigo_cenario,
            "contexto": codigo_cenario,
            "dominio": dominio,

            "cod_cred": cod_cred_final,
            "nat_bc_cred": nat_bc_cred_final,
            "natureza_credito_m": nat_bc_cred_final,
        },

        "detalhe": {
            "tipo": "PATCH_C170_FINAL",
            "set": {
                "cfop": cfop,

                "cst_pis": cst_pis_final,
                "cst_cofins": cst_cofins_final,
                "cst_pis_destino": cst_pis_final,
                "cst_cofins_destino": cst_cofins_final,

                "vl_bc_pis": vl_bc_pis,
                "aliq_pis": aliq_pis,
                "vl_pis": vl_pis,

                "vl_bc_cofins": vl_bc_cofins,
                "aliq_cofins": aliq_cofins,
                "vl_cofins": vl_cofins,

                "contexto": codigo_cenario,
                "cod_cred": cod_cred_final,
                "nat_bc_cred": nat_bc_cred_final,
                "natureza_credito_m": nat_bc_cred_final,

                "pf": False,
            },
        },
    }

    # 5) Persistência (apaga só PENDENTES da mesma linha/registro)
    db.query(EfdRevisao).filter(
        EfdRevisao.versao_origem_id == int(versao_origem_id),
        EfdRevisao.versao_revisada_id.is_(None),
        EfdRevisao.registro_id == int(r.id),
        EfdRevisao.reg == "C170",
        EfdRevisao.acao == "REPLACE_LINE",
    ).delete(synchronize_session=False)

    db.add(
        EfdRevisao(
            versao_origem_id=int(versao_origem_id),
            versao_revisada_id=None,
            registro_id=int(r.id),
            reg="C170",
            acao="REPLACE_LINE",
            revisao_json=payload_rev,
            motivo_codigo=str(motivo_codigo),
            apontamento_id=apontamento_id,
        )
    )

    db.flush()
    return {"status": "alterado", "registro_id": int(r.id)}


# =====================================================================
# Revisão em lote C170 (+ consolidação C100)
# =====================================================================
def revisar_c170_lote(
    db: Session,
    *,
    versao_origem_id: int,
    alteracoes: List[Dict[str, Any]],
    motivo_codigo: str,
    apontamento_id: Optional[int] = None,
    dominio: Optional[str] = None,
    contexto: Optional[str] = None,
    fator_base_credito: Optional[float] = None,
    aliq_pis: Optional[str] = None,
    aliq_cofins: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executa a revisão em lote dos registros C170 e consolida os totais nos pais (C100).
    Implementa contagem de registros ignorados por trava de CPF.
    """
    usar_overlay_no_c100 = False


    resultados: List[Dict[str, Any]] = []
    c100_afetados = set()

    total_alterado = 0
    total_ignorado_pf = 0
    total_ignorado_sit = 0
    sit_ignorados_detalhe: List[Dict[str, Any]] = []
    total_erros = 0
    erros_detalhe: List[Dict[str, Any]] = []  # top 10

    # Garante hierarquia pai_id populada
    popular_pai_id(db, versao_origem_id)

    # ✅ mapa estrutural (estilo Foto): C170 -> último C100 anterior (por linha)
    rows_min = (
        db.query(EfdRegistro.id, EfdRegistro.reg)
        .filter(EfdRegistro.versao_id == int(versao_origem_id))
        .order_by(EfdRegistro.linha.asc())
        .all()
    )

    c170_to_c100: dict[int, int] = {}
    last_c100_id = 0
    for rid, reg in rows_min:
        reg_u = (reg or "").strip().upper()
        if reg_u == "C100":
            last_c100_id = int(rid)
        elif reg_u == "C170":
            if last_c100_id:
                c170_to_c100[int(rid)] = int(last_c100_id)

    for item in alteracoes:
        reg_id = item.get("registro_id")
        try:
            # --- validação defensiva do input ---
            if reg_id is None:
                raise ValueError("Item sem registro_id")

            reg_db = db.get(EfdRegistro, int(reg_id))
            if not reg_db:
                raise ValueError("Registro não encontrado no banco")

            # ✅ valida versão + tipo de registro cedo (evita ruído)
            if int(reg_db.versao_id) != int(versao_origem_id):
                raise ValueError("Registro não pertence à versão informada")
            if (reg_db.reg or "").strip().upper() != "C170":
                raise ValueError("Registro_id não é C170")

            # 🛡️ TRAVA COD_SIT (C100 complementar/cancelada) — não depende de pai_id
            c100_id = int(getattr(reg_db, "pai_id", 0) or 0)
            if c100_id <= 0:
                c100_id = int(c170_to_c100.get(int(reg_db.id), 0) or 0)

            if c100_id > 0:
                reg_c100 = db.get(EfdRegistro, int(c100_id))
                if reg_c100 and (reg_c100.reg or "").strip().upper() == "C100":
                    dados_c100 = _get_dados(reg_c100) or []
                    off_c100 = 1 if dados_c100 and str(dados_c100[0]).strip().upper() == "C100" else 0
                    cod_sit_raw = str(dados_c100[4 + off_c100]).strip() if len(dados_c100) > 4 + off_c100 else ""
                    cod_sit = "".join(ch for ch in cod_sit_raw if ch.isdigit()).zfill(2)

                    if cod_sit in {"06", "07"}:
                        print("🧱 BLOQUEADO COD_SIT", cod_sit, "C170=", reg_db.id, "C100=", c100_id)
                        total_ignorado_sit += 1
                        if len(sit_ignorados_detalhe) < 20:
                            sit_ignorados_detalhe.append({
                                "status": "ignorado_cod_sit",
                                "registro_id": int(reg_db.id),
                                "c100_id": int(c100_id),
                                "cod_sit": cod_sit,
                            })
                        resultados.append({
                            "status": "ignorado_cod_sit",
                            "registro_id": int(reg_db.id),
                            "c100_id": int(c100_id),
                            "msg": f"Ignorado: C100 COD_SIT={cod_sit} (complementar/cancelada)."
                        })
                        continue

            # 🛡️ TRAVA PF
            if reg_db.pai_id:
                is_pf = eh_pf_por_c100(
                    db,
                    versao_id=int(versao_origem_id),
                    registro_id=int(reg_db.id),
                )
                if is_pf:
                    total_ignorado_pf += 1
                    resultados.append({
                        "status": "ignorado_pf",
                        "registro_id": int(reg_db.id),
                        "c100_id": int(reg_db.pai_id),
                        "msg": "Ignorado: participante PF (CPF) não gera crédito."
                    })
                    continue

            novo_cst_pis = str(item.get("cst_pis") or "").strip()
            novo_cst_cofins = str(item.get("cst_cofins") or "").strip()

            if _cst_sem_credito(novo_cst_pis) or _cst_sem_credito(novo_cst_cofins):
                usar_overlay_no_c100 = True

            # ✅ processa revisão
            res = revisar_c170(
                db,
                registro_id=int(reg_db.id),
                versao_origem_id=int(versao_origem_id),

                cfop=item.get("cfop"),
                cst_pis=item.get("cst_pis"),
                cst_cofins=item.get("cst_cofins"),

                motivo_codigo=motivo_codigo,
                apontamento_id=apontamento_id,

                dominio=(
                        item.get("dominio")
                        or dominio
                ),
                contexto=(
                        item.get("contexto")
                        or item.get("codigo_cenario")
                        or contexto
                ),
                fator_base_credito=(
                    item.get("fator_base_credito")
                    if item.get("fator_base_credito") is not None
                    else fator_base_credito
                ),

                aliq_pis=(
                    item.get("aliq_pis")
                    if item.get("aliq_pis") not in (None, "")
                    else aliq_pis
                ),
                aliq_cofins=(
                    item.get("aliq_cofins")
                    if item.get("aliq_cofins") not in (None, "")
                    else aliq_cofins
                ),

                vl_bc_pis=item.get("vl_bc_pis"),
                vl_pis=item.get("vl_pis"),
                vl_bc_cofins=item.get("vl_bc_cofins"),
                vl_cofins=item.get("vl_cofins"),

                natureza_credito_m=(
                        item.get("natureza_credito_m")
                        or item.get("nat_bc_cred")
                ),
                meta_fiscal=item.get("meta_fiscal"),
                cod_cred=item.get("cod_cred"),
                nat_bc_cred=item.get("nat_bc_cred"),
            )

            resultados.append(res)

            if res.get("status") == "alterado":
                total_alterado += 1

                c100_id_final = int(getattr(reg_db, "pai_id", 0) or 0)
                if c100_id_final <= 0:
                    c100_id_final = int(c170_to_c100.get(int(reg_db.id), 0) or 0)

                if c100_id_final > 0:
                    c100_afetados.add(c100_id_final)

        except Exception as e:
            total_erros += 1
            err = str(e)
            resultados.append({"error": err, "registro_id": reg_id})

            # log detalhado
            print("❌ ERRO LOTE registro_id=", reg_id, "err=", err)
            print(traceback.format_exc())

            if len(erros_detalhe) < 10:
                erros_detalhe.append({"registro_id": reg_id, "erro": err})

    # --- CONSOLIDAÇÃO C100 ---

    for c100_id in c100_afetados:

        try:

            if usar_overlay_no_c100:

                total_pis, total_cofins = calcular_totais_filhos_overlay(
                    db,
                    versao_origem_id=int(versao_origem_id),
                    versao_final_id=None,
                    c100_id=int(c100_id),
                )
            else:

                total_pis, total_cofins = calcular_totais_filhos(
                    db,
                    int(versao_origem_id),
                    int(c100_id),
                )

            reg_c100 = db.get(EfdRegistro, int(c100_id))
            if not reg_c100:
                continue

            dados_c100 = _get_dados(reg_c100) or []

            campos_atualizados = patch_c100_totais_imposto(
                dados_c100,
                total_pis,
                total_cofins,
            )
            ensure_len(campos_atualizados, 28)

            salvar_revisao_c100_automatica(
                db,
                versao_origem_id=int(versao_origem_id),
                motivo_codigo=f"{motivo_codigo}_AUTO_SUM",
                reg_c100=reg_c100,
                novos_dados=campos_atualizados,
                apontamento_id=apontamento_id,
            )


        except Exception as e:
            print(f"❌ Erro na consolidação C100 {c100_id}: {e}")
            print(traceback.format_exc())

    db.flush()

    return {
        "status": "ok",
        "total_alterado": total_alterado,
        "total_ignorado_pf": total_ignorado_pf,
        "total_ignorado_sit": total_ignorado_sit,
        "sit_ignorados_detalhe": sit_ignorados_detalhe,
        "total_erros": total_erros,
        "erros_detalhe": erros_detalhe,
        "detalhes": resultados,
    }

# =====================================================================
# Revisão global (por filtros origem) -> monta lote e executa
# =====================================================================
def revisar_c170_global(
    db: Session,
    *,
    versao_origem_id: int,
    filtros_origem: Dict[str, Any],
    valores_novos: Dict[str, Any],
    motivo_codigo: str,
    apontamento_id: Optional[int] = None,
) -> Dict[str, Any]:

    # 2) Query base (ATENÇÃO: filtra origem SEM overlay pendente)
    query = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "C170",
        )
    )

    cfop_f = str(filtros_origem.get("cfop") or "").strip()
    cst_pis_f = str(filtros_origem.get("cst_pis") or "").strip()

    # JSON: CFOP = dados[9], CST_PIS = dados[23]
    if cfop_f:
        query = query.filter(
            func.json_unquote(func.json_extract(EfdRegistro.conteudo_json, "$.dados[9]")) == cfop_f
        )

    if cst_pis_f:
        query = query.filter(
            func.json_unquote(func.json_extract(EfdRegistro.conteudo_json, "$.dados[23]")) == cst_pis_f
        )

    registros = query.all()
    if not registros:
        return {
            "status": "vazio",
            "escopo_filtro": "origem_sem_overlay",
            "candidatos": 0,
            "total_alterado": 0,
            "total_ignorado_pf": 0,
            "total_erros": 0,
        }

    # 3) Monta lote com novos valores (None => não altera aquele campo)
    novo_cfop = valores_novos.get("cfop") if valores_novos.get("cfop") not in ("", None) else None
    novo_pis = valores_novos.get("cst_pis") if valores_novos.get("cst_pis") not in ("", None) else None
    novo_cof = valores_novos.get("cst_cofins") if valores_novos.get("cst_cofins") not in ("", None) else None

    lote: List[Dict[str, Any]] = []

    for r in registros:
        lote.append({
            "registro_id": int(r.id),

            "cfop": (
                str(novo_cfop).strip()
                if novo_cfop is not None
                else None
            ),
            "cst_pis": (
                str(novo_pis).strip()
                if novo_pis is not None
                else None
            ),
            "cst_cofins": (
                str(novo_cof).strip()
                if novo_cof is not None
                else None
            ),

            "aliq_pis": valores_novos.get("aliq_pis"),
            "aliq_cofins": valores_novos.get("aliq_cofins"),

            "vl_bc_pis": valores_novos.get("vl_bc_pis"),
            "vl_pis": valores_novos.get("vl_pis"),
            "vl_bc_cofins": valores_novos.get("vl_bc_cofins"),
            "vl_cofins": valores_novos.get("vl_cofins"),

            "dominio": valores_novos.get("dominio"),
            "contexto": (
                    valores_novos.get("contexto")
                    or valores_novos.get("codigo_cenario")
            ),

            "natureza_credito_m": (
                    valores_novos.get("natureza_credito_m")
                    or valores_novos.get("nat_bc_cred")
            ),
            "cod_cred": valores_novos.get("cod_cred"),
            "nat_bc_cred": valores_novos.get("nat_bc_cred"),
            "meta_fiscal": valores_novos.get("meta_fiscal"),
        })

    # 4) Executa lote
    res_lote = revisar_c170_lote(
        db,
        versao_origem_id=int(versao_origem_id),
        alteracoes=lote,
        motivo_codigo=motivo_codigo,
        apontamento_id=apontamento_id,
    )

    # 5) Retorna contadores reais (nomes consistentes)
    alterados = int(res_lote.get("total_alterado") or 0)
    ignorados_pf = int(res_lote.get("total_ignorado_pf") or 0)
    erros = int(res_lote.get("total_erros") or 0)

    return {
        "status": "ok",
        "escopo_filtro": "origem_sem_overlay",
        "candidatos": len(registros),
        "total_alterado": alterados,
        "total_ignorado_pf": ignorados_pf,
        "total_erros": erros,
        "detalhes": res_lote,
    }

