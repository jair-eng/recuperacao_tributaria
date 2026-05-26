from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from app.utils.numbers import dec_any
from sqlalchemy.orm import Session

from app.db.models.ecd import (
    EcdArquivo,
    EcdContaI050Db,
    EcdVinculoI052Db,
    EcdSaldoI155Db,
    EcdResultadoI355Db,
    EcdDreJ150Db,
)


@dataclass
class EcdContextoConta:
    cod_cta: str
    conta_nome: str = ""
    cod_nat: str = ""
    ind_cta: str = ""
    nivel: str = ""
    cod_cta_sup: str = ""

    cod_agl: str = ""
    dre_descr: str = ""
    dre_grupo: str = ""
    dre_valor: str = ""
    dre_ind_valor: str = ""

    saldo_dt_ini: str = ""
    saldo_dt_fin: str = ""
    saldo_inicial: str = ""
    saldo_final: str = ""
    debito: str = ""
    credito: str = ""

    resultado_dt_res: str = ""
    resultado_valor: str = ""
    resultado_ind_dc: str = ""

    ecd_arquivo_id: Optional[int] = None
    confianca: str = "BAIXA"
    justificativa: str = "Conta não localizada na ECD."


def _periodo_yyyymm_para_datas(periodo: str) -> tuple[str, str]:
    periodo = str(periodo or "").strip()

    if len(periodo) != 6:
        return "", ""

    ano = periodo[:4]
    mes = periodo[4:6]

    ultimo_dia = {
        "01": "31",
        "02": "28",
        "03": "31",
        "04": "30",
        "05": "31",
        "06": "30",
        "07": "31",
        "08": "31",
        "09": "30",
        "10": "31",
        "11": "30",
        "12": "31",
    }.get(mes, "")

    if not ultimo_dia:
        return "", ""

    return f"01{mes}{ano}", f"{ultimo_dia}{mes}{ano}"


def obter_ecd_arquivo_mais_recente(
    db: Session,
    *,
    empresa_id: int,
    periodo: str,
) -> Optional[EcdArquivo]:
    ano = str(periodo or "")[:4]

    q = db.query(EcdArquivo).filter(EcdArquivo.empresa_id == empresa_id)

    if ano:
        q = q.filter(EcdArquivo.ano == ano)

    return q.order_by(EcdArquivo.id.desc()).first()


def obter_contexto_contabil_por_cod_cta(
    db: Session,
    *,
    empresa_id: int,
    periodo: str,
    cod_cta: str,
) -> EcdContextoConta:
    cod_cta = str(cod_cta or "").strip()

    if not cod_cta:
        return EcdContextoConta(
            cod_cta="",
            confianca="NENHUMA",
            justificativa="Item fiscal sem COD_CTA.",
        )

    ecd = obter_ecd_arquivo_mais_recente(
        db,
        empresa_id=empresa_id,
        periodo=periodo,
    )

    if not ecd:
        return EcdContextoConta(
            cod_cta=cod_cta,
            confianca="NENHUMA",
            justificativa="Nenhuma ECD importada para empresa/período.",
        )

    conta = (
        db.query(EcdContaI050Db)
        .filter(
            EcdContaI050Db.ecd_arquivo_id == ecd.id,
            EcdContaI050Db.cod_cta == cod_cta,
        )
        .first()
    )

    if not conta:
        return EcdContextoConta(
            cod_cta=cod_cta,
            ecd_arquivo_id=ecd.id,
            confianca="BAIXA",
            justificativa="COD_CTA não encontrado no I050 da ECD.",
        )

    dt_ini, dt_fin = _periodo_yyyymm_para_datas(periodo)

    saldo = None
    if dt_ini and dt_fin:
        saldo = (
            db.query(EcdSaldoI155Db)
            .filter(
                EcdSaldoI155Db.ecd_arquivo_id == ecd.id,
                EcdSaldoI155Db.cod_cta == cod_cta,
                EcdSaldoI155Db.dt_ini == dt_ini,
                EcdSaldoI155Db.dt_fin == dt_fin,
            )
            .first()
        )

    resultado = None
    if dt_fin:
        resultado = (
            db.query(EcdResultadoI355Db)
            .filter(
                EcdResultadoI355Db.ecd_arquivo_id == ecd.id,
                EcdResultadoI355Db.cod_cta == cod_cta,
                EcdResultadoI355Db.dt_res == dt_fin,
            )
            .first()
        )

    vinculo = (
        db.query(EcdVinculoI052Db)
        .filter(
            EcdVinculoI052Db.ecd_arquivo_id == ecd.id,
            EcdVinculoI052Db.cod_cta_i050 == cod_cta,
        )
        .first()
    )

    dre = None
    cod_agl = ""

    if vinculo and vinculo.cod_agl:
        cod_agl = vinculo.cod_agl
        if dt_ini and dt_fin:
            dre = (
                db.query(EcdDreJ150Db)
                .filter(
                    EcdDreJ150Db.ecd_arquivo_id == ecd.id,
                    EcdDreJ150Db.cod_agl == cod_agl,
                    EcdDreJ150Db.dt_ini == dt_ini,
                    EcdDreJ150Db.dt_fin == dt_fin,
                )
                .first()
            )

    confianca = "MEDIA"
    justificativas = ["COD_CTA localizado no I050."]

    if saldo:
        confianca = "ALTA"
        justificativas.append("Saldo I155 localizado no período.")

    if dre:
        confianca = "ALTA"
        justificativas.append("Conta vinculada à DRE J150 no período.")

    if resultado:
        justificativas.append("Resultado I355 localizado no período.")

    return EcdContextoConta(
        cod_cta=cod_cta,
        conta_nome=conta.cta or "",
        cod_nat=conta.cod_nat or "",
        ind_cta=conta.ind_cta or "",
        nivel=conta.nivel or "",
        cod_cta_sup=conta.cod_cta_sup or "",

        cod_agl=cod_agl,
        dre_descr=(dre.descr_cod_agl if dre else "") or "",
        dre_grupo=(dre.ind_grp_dre if dre else "") or "",
        dre_valor=str(dre.vl_cta) if dre and dre.vl_cta is not None else "",
        dre_ind_valor=(dre.ind_vl if dre else "") or "",

        saldo_dt_ini=(saldo.dt_ini if saldo else "") or "",
        saldo_dt_fin=(saldo.dt_fin if saldo else "") or "",
        saldo_inicial=str(saldo.vl_sld_ini) if saldo and saldo.vl_sld_ini is not None else "",
        saldo_final=str(saldo.vl_sld_fin) if saldo and saldo.vl_sld_fin is not None else "",
        debito=str(saldo.vl_deb) if saldo and saldo.vl_deb is not None else "",
        credito=str(saldo.vl_cred) if saldo and saldo.vl_cred is not None else "",

        resultado_dt_res=(resultado.dt_res if resultado else "") or "",
        resultado_valor=str(resultado.vl_cta) if resultado and resultado.vl_cta is not None else "",
        resultado_ind_dc=(resultado.ind_dc if resultado else "") or "",

        ecd_arquivo_id=ecd.id,
        confianca=confianca,
        justificativa=" ".join(justificativas),
    )

def aplicar_ctx_ecd_no_item(item, ctx_ecd):
    item.ecd_arquivo_id = ctx_ecd.ecd_arquivo_id
    item.ecd_conta_nome = ctx_ecd.conta_nome
    item.ecd_cod_nat = ctx_ecd.cod_nat
    item.ecd_ind_cta = ctx_ecd.ind_cta
    item.ecd_nivel = ctx_ecd.nivel
    item.ecd_cod_cta_sup = ctx_ecd.cod_cta_sup
    item.ecd_cod_agl = ctx_ecd.cod_agl
    item.ecd_dre_descr = ctx_ecd.dre_descr
    item.ecd_dre_grupo = ctx_ecd.dre_grupo
    item.ecd_dre_valor = dec_any(ctx_ecd.dre_valor)
    item.ecd_saldo_inicial = dec_any(ctx_ecd.saldo_inicial)
    item.ecd_saldo_final = dec_any(ctx_ecd.saldo_final)
    item.ecd_debito = dec_any(ctx_ecd.debito)
    item.ecd_credito = dec_any(ctx_ecd.credito)
    item.ecd_resultado_valor = dec_any(ctx_ecd.resultado_valor)
    item.ecd_confianca = ctx_ecd.confianca
    item.ecd_justificativa = ctx_ecd.justificativa