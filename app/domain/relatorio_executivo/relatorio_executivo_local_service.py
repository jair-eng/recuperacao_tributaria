from __future__ import annotations

from pathlib import Path
from sqlalchemy.orm import Session

from app.domain.fiscal.bloco_0.reg0150_loader_local import carregar_0150_local
from app.domain.fiscal.bloco_A.a170_loader_local import carregar_a170_local
from app.domain.fiscal.bloco_F.f100_contexto import montar_contexto_f100
from app.domain.fiscal.bloco_F.f100_loader_local import carregar_f100_local
from app.domain.fiscal.bloco_F.f100_participantes import enriquecer_f100_com_participantes
from app.domain.fiscal.catalogo.natureza_credito_catalogo import carregar_mapa_nat_bc_cred
from app.domain.relatorio_executivo.c170_loader_local import carregar_c170_local
from app.domain.relatorio_executivo.contexto_local_ecd_efd import montar_contexto_gap_ecd_efd_local
from app.domain.relatorio_executivo.contexto_recuperacao_local import montar_contexto_recuperacao_local
from app.domain.relatorio_executivo.contrib_loader_local import carregar_contrib_local
from app.domain.relatorio_executivo.exportar_relatorio_ecd_efd import exportar_relatorio_executivo_ecd_efd_por_ctx
from app.domain.sped.maps.reg0150_map import montar_mapa_participantes_0150
from app.utils.sped import listar_txt


def gerar_relatorio_executivo_local(
    db: Session,
    *,
    empresa_id: int | None = None,
    dominio: str = "GERAL",
    pasta_ecd: Path,
    pasta_contrib: Path,
    pasta_icms: Path,
    caminho_saida: Path,
) -> Path:
    pasta_ecd = Path(pasta_ecd)
    pasta_contrib = Path(pasta_contrib)
    pasta_icms = Path(pasta_icms)
    caminho_saida = Path(caminho_saida)

    arquivos_ecd = listar_txt(pasta_ecd)
    arquivos_contrib = listar_txt(pasta_contrib)
    #arquivos_icms = listar_txt(pasta_icms)

    if not arquivos_ecd:
        raise FileNotFoundError(f"Nenhum arquivo .txt encontrado em: {pasta_ecd}")

    if not arquivos_contrib:
        raise FileNotFoundError(f"Nenhum arquivo .txt encontrado em: {pasta_contrib}")

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    print("========== RELATÓRIO EXECUTIVO LOCAL ==========")
    print("empresa_id:", empresa_id)
    print("pasta_ecd:", pasta_ecd)
    print("arquivos_ecd:", len(arquivos_ecd))
    print("pasta_contrib:", pasta_contrib)
    print("arquivos_contrib:", len(arquivos_contrib))
    print("saida:", caminho_saida)

    ctx = montar_contexto_gap_ecd_efd_local(
        db=db,
        empresa_id=empresa_id,
        dominio=dominio,
        pasta_ecd=pasta_ecd,
        pasta_contrib=pasta_contrib,
        periodo=None,
    )
    ctx["mapa_nat_bc_cred"] = carregar_mapa_nat_bc_cred(db)

    registros_0150_contrib = carregar_0150_local(arquivos_contrib)
    mapa_participantes_contrib = montar_mapa_participantes_0150(
        registros_0150_contrib
    )

    f100 = carregar_f100_local(arquivos_contrib)
    f100 = enriquecer_f100_com_participantes(
        f100,
        mapa_participantes_contrib,
    )

    ctx["mapa_nat_bc_cred"] = carregar_mapa_nat_bc_cred(db)

    ctx["f100"] = montar_contexto_f100(
        f100,
        db=db,
        fonte="LOCAL",
        mapa_nat_bc_cred=ctx["mapa_nat_bc_cred"],
    )
    f100_classificado = ctx["f100"]["registros"]

    c170_contrib = carregar_c170_local(arquivos_contrib)
    a170_contrib = carregar_a170_local(arquivos_contrib)
    contrib_ctx = carregar_contrib_local(arquivos_contrib)

    ctx_recuperacao = montar_contexto_recuperacao_local(
        linhas_ecd=ctx.get("linhas_ecd") or [],
        db=db,
        contrib_ctx=contrib_ctx,
        c170_contrib=c170_contrib,
        f100_contrib=f100_classificado,
        a170_contrib=a170_contrib,
        dominio=dominio,
    )

    ctx.update(ctx_recuperacao)


    exportar_relatorio_executivo_ecd_efd_por_ctx(
        ctx=ctx,
        caminho_saida=caminho_saida,
        titulo="Relatório Executivo ECD x EFD - Local",
    )

    print("[REL LOCAL] relatório gerado:", caminho_saida)

    return caminho_saida