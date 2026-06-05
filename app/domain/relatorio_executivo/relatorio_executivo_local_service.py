from __future__ import annotations

from pathlib import Path
from sqlalchemy.orm import Session

from app.domain.fiscal.catalogo.natureza_credito_catalogo import carregar_mapa_nat_bc_cred
from app.domain.relatorio_executivo.contexto_local_ecd_efd import montar_contexto_gap_ecd_efd_local
from app.domain.relatorio_executivo.exportar_relatorio_ecd_efd import exportar_relatorio_executivo_ecd_efd_por_ctx
from app.utils.sped import listar_txt


def gerar_relatorio_executivo_local(
    db: Session,
    *,
    empresa_id: int,
    pasta_ecd: Path,
    pasta_contrib: Path,
    caminho_saida: Path,
) -> Path:
    pasta_ecd = Path(pasta_ecd)
    pasta_contrib = Path(pasta_contrib)
    caminho_saida = Path(caminho_saida)

    arquivos_ecd = listar_txt(pasta_ecd)
    arquivos_contrib = listar_txt(pasta_contrib)

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
        pasta_ecd=pasta_ecd,
        pasta_contrib=pasta_contrib,
        periodo=None,
    )
    ctx["mapa_nat_bc_cred"] = carregar_mapa_nat_bc_cred(db)

    print("[REL LOCAL] linhas_ecd:", len(ctx.get("linhas_ecd") or []))
    print("[REL LOCAL] naturezas:", len(ctx.get("por_natureza") or {}))

    exportar_relatorio_executivo_ecd_efd_por_ctx(
        ctx=ctx,
        caminho_saida=caminho_saida,
        titulo="Relatório Executivo ECD x EFD - Local",
    )

    print("[REL LOCAL] relatório gerado:", caminho_saida)

    return caminho_saida