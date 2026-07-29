from __future__ import annotations

from pathlib import Path
from sqlalchemy.orm import Session

from app.domain.fiscal.bloco_0.reg0150_loader_local import carregar_0150_local
from app.domain.fiscal.bloco_A.a170_loader_local import carregar_a170_local
from app.domain.fiscal.bloco_F.f100_contexto import montar_contexto_f100
from app.domain.fiscal.bloco_F.f100_loader_local import carregar_f100_local
from app.domain.fiscal.bloco_F.f100_participantes import enriquecer_f100_com_participantes
from app.domain.fiscal.catalogo.natureza_credito_catalogo import carregar_mapa_nat_bc_cred
from app.domain.relatorio_executivo.IcmsContribuicao.c170_icms_loader_local import carregar_c170_icms_local
from app.domain.relatorio_executivo.IcmsContribuicao.c170_oportunidades_local import \
    diagnosticar_oportunidades_c170_local
from app.domain.relatorio_executivo.IcmsContribuicao.cruzar_c170_icms_contrib_local import \
    cruzar_c170_icms_contrib_local
from app.domain.relatorio_executivo.c170_loader_local import carregar_c170_local
from app.domain.relatorio_executivo.contexto_local_ecd_efd import montar_contexto_gap_ecd_efd_local
from app.domain.relatorio_executivo.contexto_recuperacao_local import montar_contexto_recuperacao_local
from app.domain.relatorio_executivo.contrib_loader_local import carregar_contrib_local
from app.domain.relatorio_executivo.exportar_relatorio_ecd_efd import exportar_relatorio_executivo_ecd_efd_por_ctx
from app.domain.relatorio_executivo.extrair_conta_efd_para_fallback import gerar_catalogo_0500_local
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
    arquivos_icms = listar_txt(pasta_icms)

    if not arquivos_icms:
        raise FileNotFoundError(f"Nenhum arquivo .txt encontrado em: {pasta_icms}")

        # ECD é opcional.
    if not arquivos_ecd:
        print(
            "[RELATÓRIO LOCAL][SEM_ECD]",
            "Nenhum arquivo ECD encontrado.",
            "O relatório seguirá somente com EFD Contribuições e ICMS/IPI.",
            "pasta=", pasta_ecd,
            flush=True,
        )

    if not arquivos_contrib:
        raise FileNotFoundError(f"Nenhum arquivo .txt encontrado em: {pasta_contrib}")

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    caminho_catalogo_0500 = (
            caminho_saida.parent / "catalogo_0500_contrib.json"
    )

    resumo_0500 = gerar_catalogo_0500_local(
        arquivos_contrib=arquivos_contrib,
        caminho_saida=caminho_catalogo_0500,
    )

    print(
        "[CATALOGO 0500]",
        "arquivos_lidos=", resumo_0500["arquivos_lidos"],
        "linhas_0500=", resumo_0500["linhas_0500"],
        "contas_unicas=", resumo_0500["contas_unicas"],
        "empresas=", resumo_0500["empresas"],
        "substituidos=", resumo_0500["registros_substituidos"],
        "saida=", resumo_0500["arquivo_saida"],
        flush=True,
    )

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
    ctx["possui_ecd"] = bool(arquivos_ecd)
    ctx["sem_ecd"] = not bool(arquivos_ecd)
    ctx["arquivos_ecd"] = len(arquivos_ecd)
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

    c170_icms = carregar_c170_icms_local(arquivos_icms)

    from collections import Counter

    print(
        "[DBG ENTRADA CRUZAMENTO]",
        {
            "qtd_icms": len(c170_icms),
            "qtd_contrib": len(c170_contrib),
            "periodos_icms": dict(
                Counter(
                    str(item.get("periodo") or "")
                    for item in c170_icms
                )
            ),
            "periodos_contrib": dict(
                Counter(
                    str(item.get("periodo") or "")
                    for item in c170_contrib
                )
            ),
        },
    )
    linhas_cruzadas_c170 = cruzar_c170_icms_contrib_local(
        c170_icms=c170_icms,
        c170_contrib=c170_contrib,
    )

    ########


    print(
        "[DBG CRUZADAS STATUS]",
        Counter(
            str(item.get("status_cruzamento") or "")
            for item in linhas_cruzadas_c170
        ),
    )

    print(
        "[DBG CRUZADAS PERIODO]",
        Counter(
            str(item.get("periodo") or "")
            for item in linhas_cruzadas_c170
        ),
    )

    print(
        "[DBG CRUZADAS CATEGORIA BRUTA]",
        Counter(
            (
                str(item.get("cod_item") or ""),
                str(item.get("descricao") or ""),
                str(item.get("ncm") or ""),
                str(item.get("cfop") or ""),
            )
            for item in linhas_cruzadas_c170
        ).most_common(20),
    )
    #####

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

    ctx["oportunidades_c170"] = diagnosticar_oportunidades_c170_local(
        db=db,
        linhas_cruzadas=linhas_cruzadas_c170,
        dominio=dominio,
    )

    exportar_relatorio_executivo_ecd_efd_por_ctx(
        ctx=ctx,
        caminho_saida=caminho_saida,
        titulo="Relatório Executivo ECD x EFD - Local",
    )

    print(
        "[REL LOCAL] relatório gerado:",
        caminho_saida,
        "| possui_ecd=",
        bool(arquivos_ecd),
        flush=True,
    )

    return caminho_saida