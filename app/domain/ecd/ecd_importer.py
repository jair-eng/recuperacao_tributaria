from __future__ import annotations

from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from app.domain.ecd.ecd_parser import parse_ecd_lines
from app.db.models.ecd import (
    EcdArquivo,
    EcdContaI050Db,
    EcdVinculoI052Db,
    EcdSaldoI155Db,
    EcdResultadoI355Db,
    EcdDreJ150Db,
)
from app.utils.numbers import to_decimal


def importar_ecd_arquivo(
    db: Session,
    *,
    empresa_id: int,
    caminho_arquivo: str,
    nome_arquivo: Optional[str] = None,
    sobrescrever: bool = True,
    cod_ctas_relevantes: set[str] | None = None,
) -> dict:
    path = Path(caminho_arquivo)

    with path.open("r", encoding="latin-1", errors="ignore") as f:
        linhas = f.readlines()

    parsed = parse_ecd_lines(
        linhas,
        incluir_saldos_i155=True,
        incluir_resultados_i355=True,
        incluir_balanco_j100=False,
        incluir_dre_j150=True,
        cod_ctas_relevantes=cod_ctas_relevantes,
    )

    ident = parsed.identificacao
    periodo_inicio = ident.dt_ini if ident else None
    periodo_fim = ident.dt_fin if ident else None
    ano = periodo_inicio[-4:] if periodo_inicio and len(periodo_inicio) == 8 else None
    cnpj = ident.cnpj if ident else None
    nome_empresa = ident.nome if ident else None

    if sobrescrever and cnpj and periodo_inicio and periodo_fim:
        antigos = (
            db.query(EcdArquivo)
            .filter(
                EcdArquivo.empresa_id == empresa_id,
                EcdArquivo.cnpj == cnpj,
                EcdArquivo.periodo_inicio == periodo_inicio,
                EcdArquivo.periodo_fim == periodo_fim,
            )
            .all()
        )

        for antigo in antigos:
            db.delete(antigo)

        if antigos:
            db.flush()

    ecd = EcdArquivo(
        empresa_id=empresa_id,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        ano=ano,
        nome_arquivo=nome_arquivo or path.name,
        cnpj=cnpj,
        nome_empresa=nome_empresa,
        total_linhas=len(linhas),
    )

    db.add(ecd)
    db.flush()

    for c in parsed.contas_i050:
        db.add(
            EcdContaI050Db(
                ecd_arquivo_id=ecd.id,
                empresa_id=empresa_id,
                linha=c.linha,
                dt_alt=c.dt_alt,
                cod_nat=c.cod_nat,
                ind_cta=c.ind_cta,
                nivel=c.nivel,
                cod_cta=c.cod_cta,
                cod_cta_sup=c.cod_cta_sup,
                cta=c.cta,
            )
        )

    for v in parsed.vinculos_i052:
        db.add(
            EcdVinculoI052Db(
                ecd_arquivo_id=ecd.id,
                empresa_id=empresa_id,
                linha=v.linha,
                cod_cta_i050=v.cod_cta_i050,
                cod_ccus=v.cod_ccus,
                cod_agl=v.cod_agl,
            )
        )

    for s in parsed.saldos_i155:
        db.add(
            EcdSaldoI155Db(
                ecd_arquivo_id=ecd.id,
                empresa_id=empresa_id,
                linha=s.linha,
                dt_ini=s.dt_ini,
                dt_fin=s.dt_fin,
                cod_cta=s.cod_cta,
                cod_ccus=s.cod_ccus,
                vl_sld_ini=to_decimal(s.vl_sld_ini),
                ind_dc_ini=s.ind_dc_ini,
                vl_deb=to_decimal(s.vl_deb),
                vl_cred=to_decimal(s.vl_cred),
                vl_sld_fin=to_decimal(s.vl_sld_fin),
                ind_dc_fin=s.ind_dc_fin,
            )
        )

    for r in parsed.resultados_i355:
        db.add(
            EcdResultadoI355Db(
                ecd_arquivo_id=ecd.id,
                empresa_id=empresa_id,
                linha=r.linha,
                dt_res=r.dt_res,
                cod_cta=r.cod_cta,
                cod_ccus=r.cod_ccus,
                vl_cta=to_decimal(r.vl_cta),
                ind_dc=r.ind_dc,
            )
        )

    for d in parsed.dres_j150:
        db.add(
            EcdDreJ150Db(
                ecd_arquivo_id=ecd.id,
                empresa_id=empresa_id,
                linha=d.linha,
                dt_ini=d.dt_ini,
                dt_fin=d.dt_fin,
                nu_ordem=d.nu_ordem,
                cod_agl=d.cod_agl,
                ind_cod_agl=d.ind_cod_agl,
                nivel_agl=d.nivel_agl,
                cod_agl_sup=d.cod_agl_sup,
                descr_cod_agl=d.descr_cod_agl,
                vl_cta=to_decimal(d.vl_cta),
                ind_vl=d.ind_vl,
                vl_cta_ult_dre=to_decimal(d.vl_cta_ult_dre),
                ind_vl_ult_dre=d.ind_vl_ult_dre,
                ind_grp_dre=d.ind_grp_dre,
                nota_exp_ref=d.nota_exp_ref,
            )
        )

    db.commit()

    return {
        "ok": True,
        "ecd_arquivo_id": ecd.id,
        "empresa_id": empresa_id,
        "nome_arquivo": ecd.nome_arquivo,
        "periodo_inicio": periodo_inicio,
        "periodo_fim": periodo_fim,
        "ano": ano,
        "cnpj": cnpj,
        "nome_empresa": nome_empresa,
        "total_linhas": len(linhas),
        "contagem_por_registro": parsed.contagem_por_registro,
        "registros_ignorados": parsed.registros_ignorados,
        "totais_importados": {
            "contas_i050": len(parsed.contas_i050),
            "vinculos_i052": len(parsed.vinculos_i052),
            "saldos_i155": len(parsed.saldos_i155),
            "resultados_i355": len(parsed.resultados_i355),
            "dres_j150": len(parsed.dres_j150),
        },
    }