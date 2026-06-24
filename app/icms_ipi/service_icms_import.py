from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ItemFiscalConsolidado
from app.db.models.nf_icms_base import NfIcmsBase
from app.db.models.nf_icms_item import NfIcmsItem
from app.icms_ipi.parser_sped_icms import parse_sped_icms_ipi_preview
from app.icms_ipi.icms_helpers import _norm_str
from app.sped.bloco_D.d100_parser import parse_sped_icms_d100_preview


def gerar_preview_sped_icms(
    *,
    db: Session,
    arquivo_path: str,
    empresa_id: int,
) -> dict[str, Any]:
    """
    Lê o SPED ICMS/IPI e devolve preview sem gravar nada no banco.
    """
    preview = parse_sped_icms_ipi_preview(arquivo_path)

    return {
        "empresa_id": empresa_id,
        "arquivo": preview["arquivo"],
        "fonte": preview.get("fonte", "EFD_ICMS_IPI"),
        "periodo": preview["periodo"],
        "dt_ini": preview["dt_ini"],
        "dt_fin": preview["dt_fin"],
        "empresa": preview.get("empresa"),
        "total_notas": preview["total_notas"],
        "total_itens": preview.get("total_itens", 0),
        "total_vl_doc": preview["total_vl_doc"],
        "total_vl_item": preview.get("total_vl_item", 0),
        "total_vl_icms": preview["total_vl_icms"],
        "participantes_count": preview.get("participantes_count", 0),
        "produtos_count": preview.get("produtos_count", 0),
        "notas_preview": preview["notas_preview"],
        "itens_preview": preview.get("itens_preview", []),
        "notas": preview.get("notas", []),
        "itens": preview.get("itens", []),
        "participantes": preview.get("participantes", {}),
        "produtos": preview.get("produtos", {}),
    }


def importar_sped_icms(
    *,
    db: Session,
    arquivo_path: str,
    empresa_id: int,
    sobrescrever_existentes: bool = False,
) -> dict[str, Any]:
    """
    Importa SPED ICMS/IPI para:
      - nf_icms_base (cabeçalho)
      - nf_icms_item (itens)

    Regras:
    - usa o parser para montar notas e itens
    - grava por empresa_id + periodo + chave_nfe
    - se sobrescrever_existentes=True, atualiza cabeçalho e recria itens da nota
    - se sobrescrever_existentes=False:
        * mantém cabeçalho existente
        * preenche itens se a nota ainda não tiver itens
        * evita duplicar itens já carregados

    Ajuste importante:
    - se houver duplicidade em nf_icms_base para a mesma chave, consolida em um único base_row
      e remove os duplicados com seus itens.
    """
    preview_c100 = parse_sped_icms_ipi_preview(arquivo_path)
    preview_d100 = parse_sped_icms_d100_preview(arquivo_path)

    periodo = preview_c100["periodo"] or preview_d100.get("periodo")
    nome_arquivo = Path(arquivo_path).name

    notas = list(preview_c100.get("notas", [])) + list(preview_d100.get("notas", []))
    itens = list(preview_c100.get("itens", [])) + list(preview_d100.get("itens", []))

    print(
        "[DBG IMPORT RESUMO]",
        "notas_c100=", len(preview_c100.get("notas", [])),
        "notas_d100=", len(preview_d100.get("notas", [])),
        "itens_c100=", len(preview_c100.get("itens", [])),
        "itens_d100=", len(preview_d100.get("itens", [])),
        flush=True,
    )

    for n in notas[:10]:
        print(
            "[DBG IMPORT COMBINADO]",
            "modelo=", getattr(n, "modelo", None),
            "chave=", getattr(n, "chave_nfe", None),
            "num_doc=", getattr(n, "num_doc", None),
            flush=True,
        )

    inseridas = 0
    atualizadas = 0
    ignoradas = 0
    itens_inseridos = 0
    itens_removidos = 0
    bases_duplicadas_removidas = 0

    # índice dos itens por chave
    itens_por_chave: dict[str, list[Any]] = {}
    for it in itens:
        chave = getattr(it, "chave_nfe", None)
        if not chave:
            continue
        itens_por_chave.setdefault(chave, []).append(it)

    for nota in notas:
        nota_chave_nfe = _norm_str(getattr(nota, "chave_nfe", None))

        if not nota_chave_nfe:
            ignoradas += 1
            print(...)
            continue
        existentes = (
            db.query(NfIcmsBase)
            .filter(
                NfIcmsBase.empresa_id == empresa_id,
                NfIcmsBase.periodo == periodo,
                NfIcmsBase.chave_nfe == nota.chave_nfe,
            )
            .order_by(NfIcmsBase.id.asc())
            .all()
        )

        base_row = None

        if existentes:
            # Escolhe a mais antiga como principal e elimina duplicatas
            base_row = existentes[0]
            duplicadas = existentes[1:]

            if duplicadas:
                ids_dup = [int(x.id) for x in duplicadas]

                ids_itens_icms_dup = [
                    x[0]
                    for x in (
                        db.query(NfIcmsItem.id)
                        .filter(NfIcmsItem.nf_icms_base_id.in_(ids_dup))
                        .all()
                    )
                ]

                if ids_itens_icms_dup:
                    db.query(ItemFiscalConsolidado).filter(
                        ItemFiscalConsolidado.nf_icms_item_id.in_(ids_itens_icms_dup)
                    ).delete(synchronize_session=False)

                removidos_dup_itens = (
                    db.query(NfIcmsItem)
                    .filter(NfIcmsItem.nf_icms_base_id.in_(ids_dup))
                    .delete(synchronize_session=False)
                )

                itens_removidos += int(removidos_dup_itens or 0)

                removidos_dup_bases = (
                    db.query(NfIcmsBase)
                    .filter(NfIcmsBase.id.in_(ids_dup))
                    .delete(synchronize_session=False)
                )

                bases_duplicadas_removidas += int(removidos_dup_bases or 0)

                print(
                    "[IMPORT_ICMS][DEDUP]",
                    "chave=", nota.chave_nfe,
                    "base_principal=", base_row.id,
                    "duplicadas_removidas=", ids_dup,
                    flush=True,
                )

            if sobrescrever_existentes:
                base_row.dt_doc = nota.dt_doc
                base_row.num_doc = getattr(nota, "num_doc", None)
                base_row.serie = getattr(nota, "serie", None)
                base_row.vl_doc = nota.vl_doc
                base_row.vl_icms = nota.vl_icms

                base_row.cod_part = getattr(nota, "cod_part", None)
                base_row.modelo = getattr(nota, "modelo", None)
                base_row.codigos_0460_json = getattr(nota, "codigos_0460", []) or []
                base_row.evidencias_0460_json = getattr(nota, "evidencias_0460", []) or []

                base_row.participante_nome = getattr(nota, "participante_nome", None)
                base_row.participante_cod_pais = getattr(nota, "participante_cod_pais", None)
                base_row.participante_cnpj = getattr(nota, "participante_cnpj", None)
                base_row.participante_cpf = getattr(nota, "participante_cpf", None)
                base_row.participante_ie = getattr(nota, "participante_ie", None)
                base_row.participante_cod_mun = getattr(nota, "participante_cod_mun", None)
                base_row.participante_suframa = getattr(nota, "participante_suframa", None)
                base_row.participante_end = getattr(nota, "participante_end", None)
                base_row.participante_num = getattr(nota, "participante_num", None)
                base_row.participante_compl = getattr(nota, "participante_compl", None)
                base_row.participante_bairro = getattr(nota, "participante_bairro", None)

                base_row.fonte = nota.fonte
                base_row.nome_arquivo = nome_arquivo

                ids_itens_icms = [
                    x[0]
                    for x in (
                        db.query(NfIcmsItem.id)
                        .filter(NfIcmsItem.nf_icms_base_id == base_row.id)
                        .all()
                    )
                ]

                if ids_itens_icms:
                    db.query(ItemFiscalConsolidado).filter(
                        ItemFiscalConsolidado.nf_icms_item_id.in_(ids_itens_icms)
                    ).delete(synchronize_session=False)

                removidos = (
                    db.query(NfIcmsItem)
                    .filter(NfIcmsItem.nf_icms_base_id == base_row.id)
                    .delete(synchronize_session=False)
                )
                itens_removidos += int(removidos or 0)
                atualizadas += 1
            else:
                ignoradas += 1

        else:
            base_row = NfIcmsBase(
                empresa_id=empresa_id,
                periodo=periodo,
                chave_nfe=nota.chave_nfe,
                dt_doc=nota.dt_doc,
                num_doc=getattr(nota, "num_doc", None),
                serie=getattr(nota, "serie", None),
                vl_doc=nota.vl_doc,
                vl_icms=nota.vl_icms,

                cod_part=getattr(nota, "cod_part", None),
                modelo=getattr(nota, "modelo", None),
                codigos_0460_json=getattr(nota, "codigos_0460", []) or [],
                evidencias_0460_json=getattr(nota, "evidencias_0460", []) or [],

                participante_nome=getattr(nota, "participante_nome", None),
                participante_cod_pais=getattr(nota, "participante_cod_pais", None),
                participante_cnpj=getattr(nota, "participante_cnpj", None),
                participante_cpf=getattr(nota, "participante_cpf", None),
                participante_ie=getattr(nota, "participante_ie", None),
                participante_cod_mun=getattr(nota, "participante_cod_mun", None),
                participante_suframa=getattr(nota, "participante_suframa", None),
                participante_end=getattr(nota, "participante_end", None),
                participante_num=getattr(nota, "participante_num", None),
                participante_compl=getattr(nota, "participante_compl", None),
                participante_bairro=getattr(nota, "participante_bairro", None),

                fonte=nota.fonte,
                nome_arquivo=nome_arquivo,
            )

            db.add(base_row)
            db.flush()  # garante id para os itens
            inseridas += 1

        # Se a nota já existe e não é para sobrescrever,
        # só insere itens se ainda não houver itens para ela.
        if existentes and not sobrescrever_existentes:
            ja_tem_itens = (
                db.query(NfIcmsItem.id)
                .filter(NfIcmsItem.nf_icms_base_id == base_row.id)
                .first()
                is not None
            )
            if ja_tem_itens:
                continue

        for item in itens_por_chave.get(nota.chave_nfe, []):
            novo_item = NfIcmsItem(
                nf_icms_base_id=base_row.id,
                empresa_id=empresa_id,
                periodo=periodo,
                chave_nfe=item.chave_nfe,

                num_item=getattr(item, "num_item", None),
                cod_item=getattr(item, "cod_item", None),
                cod_item_norm=getattr(item, "cod_item_norm", None),

                descricao=getattr(item, "descricao", None),
                ncm=getattr(item, "ncm", None),
                cfop=getattr(item, "cfop", None),

                participante_cnpj=getattr(item, "participante_cnpj", None),
                participante_nome=getattr(item, "participante_nome", None),

                qtd=getattr(item, "qtd", 0) or 0,
                unid=getattr(item, "unid", None),
                cst_icms=getattr(item, "cst_icms", None),
                aliq_icms=getattr(item, "aliq_icms", 0) or 0,

                vl_item=getattr(item, "vl_item", 0) or 0,
                vl_desc=getattr(item, "vl_desc", 0) or 0,
                vl_icms=getattr(item, "vl_icms", 0) or 0,
                vl_ipi=getattr(item, "vl_ipi", 0) or 0,
                contabil=getattr(item, "vl_item", 0) or 0,

                origem_item=getattr(item, "origem_item", None),
                nome_arquivo=nome_arquivo,
            )
            db.add(novo_item)
            itens_inseridos += 1

    db.commit()

    total_importado = (
        db.query(NfIcmsBase)
        .filter(
            NfIcmsBase.empresa_id == empresa_id,
            NfIcmsBase.periodo == periodo,
        )
        .count()
    )

    total_itens_importados = (
        db.query(NfIcmsItem)
        .filter(
            NfIcmsItem.empresa_id == empresa_id,
            NfIcmsItem.periodo == periodo,
        )
        .count()
    )

    return {
        "ok": True,
        "empresa_id": empresa_id,
        "arquivo": nome_arquivo,
        "periodo": periodo,
        "total_lido_notas": len(notas),
        "total_lido_itens": len(itens),
        "inseridas": inseridas,
        "atualizadas": atualizadas,
        "ignoradas": ignoradas,
        "itens_inseridos": itens_inseridos,
        "itens_removidos": itens_removidos,
        "bases_duplicadas_removidas": bases_duplicadas_removidas,
        "total_importado_empresa_periodo": total_importado,
        "total_itens_importados_empresa_periodo": total_itens_importados,
        "total_vl_doc": preview_c100["total_vl_doc"] + preview_d100.get("total_vl_doc", 0),
        "total_vl_icms": preview_c100["total_vl_icms"] + preview_d100.get("total_vl_icms", 0),
        "total_vl_item": preview_c100.get("total_vl_item", 0) + preview_d100.get("total_vl_item", 0),
    }