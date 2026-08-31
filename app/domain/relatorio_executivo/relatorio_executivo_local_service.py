from __future__ import annotations

from pathlib import Path
from sqlalchemy.orm import Session
from decimal import Decimal, ROUND_HALF_UP
from app.domain.fiscal.bloco_0.reg0150_loader_local import carregar_0150_local
from app.domain.fiscal.bloco_A.a170_loader_local import carregar_a170_local
from app.domain.fiscal.bloco_F.f100_comparacao import carregar_contratos_extraidos, listar_contratos_nao_encontrados, \
    salvar_contratos_nao_encontrados
from app.domain.fiscal.bloco_F.f100_contexto import montar_contexto_f100
from app.domain.fiscal.bloco_F.f100_loader_local import carregar_f100_local
from app.domain.fiscal.bloco_F.f100_participantes import enriquecer_f100_com_participantes
from app.domain.fiscal.catalogo.natureza_credito_catalogo import carregar_mapa_nat_bc_cred
from app.domain.fiscal.frete_transp.diagnostico_frete_f100 import identificar_tipo_pessoa_frete
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
    pasta_resultado = Path(r"C:\Sped\LEITOR_CONTRATO\resultado")

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

    periodos_f100 = {
        str(item.get("periodo"))
        for item in f100
        if item.get("periodo")
    }
    print(
        "🔥 ENTROU EM gerar_relatorio_executivo_local",
        flush=True,
    )

    print(
        "🔥 PERIODOS F100 ANTES DO FOR:",
        periodos_f100,
        flush=True,
    )

    contratos_nao_encontrados_total = []
    f100_recuperaveis = []

    for periodo in sorted(periodos_f100):

        ano = periodo[:4]
        mes = periodo[4:6]

        # ---------------------------------------------------------
        # Contratos extraídos daquela competência
        # ---------------------------------------------------------
        contratos_periodo = carregar_contratos_extraidos(
            pasta_resultado,
            ano=ano,
            mes=mes,
        )

        # ---------------------------------------------------------
        # F100 existentes naquela competência
        # ---------------------------------------------------------
        f100_periodo = [
            item
            for item in f100
            if str(item.get("periodo") or "") == periodo
        ]

        # ---------------------------------------------------------
        # Contratos que não estão no EFD-Contribuições
        # ---------------------------------------------------------
        contratos_nao_encontrados = listar_contratos_nao_encontrados(
            contratos_periodo,
            f100_periodo,
        )

        print(
            "[F100 RELATÓRIO]",
            "periodo=", periodo,
            "| contratos=", len(contratos_periodo),
            "| f100=", len(f100_periodo),
            "| nao_encontrados=", len(contratos_nao_encontrados),
            flush=True,
        )

        # Continua salvando exatamente como já fazemos hoje
        salvar_contratos_nao_encontrados(
            contratos_nao_encontrados,
            pasta_resultado,
            periodo,
        )

        contratos_nao_encontrados_total.extend(
            contratos_nao_encontrados
        )

        # ---------------------------------------------------------
        # Calcula potencial de crédito dos F100 ausentes
        # ---------------------------------------------------------
        for contrato in contratos_nao_encontrados:

            contratado = contrato.get("contratado") or {}
            contratante = contrato.get("contratante") or {}
            frete_contrato = contrato.get("frete") or {}

            documento_contratado = str(
                contratado.get("documento") or ""
            ).strip()

            tipo_pessoa = identificar_tipo_pessoa_frete(
                documento_contratado
            )

            # ---------------------------------------------
            # Valor do frete
            # ---------------------------------------------
            valor_raw = frete_contrato.get("valor_frete")

            valor_txt = str(
                valor_raw or "0"
            ).strip()

            try:
                if "," in valor_txt:
                    valor_txt = (
                        valor_txt
                        .replace(".", "")
                        .replace(",", ".")
                    )

                valor_frete = Decimal(valor_txt)

            except Exception:
                valor_frete = Decimal("0.00")

            valor_frete = valor_frete.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            # ---------------------------------------------
            # Enquadramento PF / PJ
            # ---------------------------------------------
            if tipo_pessoa == "PF":

                cst_pis = "60"
                cst_cofins = "60"

                nat_bc_cred = "14"
                cod_cred = "107"

                aliq_pis_pct = Decimal("1.2375")
                aliq_cofins_pct = Decimal("5.7")

                aliq_pis_calc = Decimal("0.012375")
                aliq_cofins_calc = Decimal("0.057")

            elif tipo_pessoa == "PJ":

                cst_pis = "50"
                cst_cofins = "50"

                nat_bc_cred = "14"
                cod_cred = "101"

                aliq_pis_pct = Decimal("1.65")
                aliq_cofins_pct = Decimal("7.6")

                aliq_pis_calc = Decimal("0.0165")
                aliq_cofins_calc = Decimal("0.076")

            else:
                # Documento inválido ou não identificado.
                # Não estimamos crédito automaticamente.
                continue

            # ---------------------------------------------
            # Crédito potencial
            # ---------------------------------------------
            credito_pis = (
                    valor_frete * aliq_pis_calc
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            credito_cofins = (
                    valor_frete * aliq_cofins_calc
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            credito_total = (
                    credito_pis + credito_cofins
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            numero_f100 = str(
                contrato.get("numero_f100")
                or ""
            ).strip()

            f100_recuperaveis.append({
                "competencia": periodo,
                "numero_f100": numero_f100,

                "data": frete_contrato.get("data"),

                "contratante": contratante.get("nome"),
                "documento_contratante": contratante.get("documento"),

                "contratado": contratado.get("nome"),
                "documento_contratado": documento_contratado,
                "tipo_pessoa": tipo_pessoa,

                "valor_frete": valor_frete,

                "cst_pis": cst_pis,
                "aliq_pis": aliq_pis_pct,
                "credito_pis": credito_pis,

                "cst_cofins": cst_cofins,
                "aliq_cofins": aliq_cofins_pct,
                "credito_cofins": credito_cofins,

                "nat_bc_cred": nat_bc_cred,
                "cod_cred": cod_cred,

                "credito_total": credito_total,

                "origem": "CONTRATO_FRETE_NAO_ESCRITURADO",
            })

    ctx["f100_recuperaveis"] = f100_recuperaveis

    total_base_f100 = sum(
        (
            item["valor_frete"]
            for item in f100_recuperaveis
        ),
        Decimal("0.00"),
    )

    total_pis_f100 = sum(
        (
            item["credito_pis"]
            for item in f100_recuperaveis
        ),
        Decimal("0.00"),
    )

    total_cofins_f100 = sum(
        (
            item["credito_cofins"]
            for item in f100_recuperaveis
        ),
        Decimal("0.00"),
    )

    total_credito_f100 = (
            total_pis_f100 + total_cofins_f100
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    ctx["resumo_f100_recuperaveis"] = {
        "quantidade": len(f100_recuperaveis),
        "base": total_base_f100,
        "pis": total_pis_f100,
        "cofins": total_cofins_f100,
        "credito_total": total_credito_f100,
    }

    print(
        "[F100 RECUPERÁVEIS]",
        "qtd=", len(f100_recuperaveis),
        "| base=", total_base_f100,
        "| pis=", total_pis_f100,
        "| cofins=", total_cofins_f100,
        "| credito=", total_credito_f100,
        flush=True,
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