from __future__ import annotations

import re
from typing import Optional
from pathlib import Path
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from app.domain.fiscal.bloco_F.f100_comparacao import (
    extrair_contrato_do_bloco,
)
from app.domain.fiscal.enquadramento.enquadramento_repository import (
    buscar_enquadramento_por_cenario,
)
from app.domain.fiscal.frete_transp.conta_frete import gerar_cod_cta_frete
from app.domain.fiscal.frete_transp.mestres_fretes import (
    localizar_0140_por_cnpj,
    localizar_0150_contratado, localizar_f010_por_cnpj,
)

def identificar_tipo_pessoa_frete(
    documento: str,
) -> Optional[str]:
    """
    Classifica o contratado como PF ou PJ
    pelo tamanho do documento normalizado.

    CPF  -> 11 dígitos
    CNPJ -> 14 dígitos
    """

    documento_limpo = re.sub(
        r"\D",
        "",
        str(documento or ""),
    )

    if len(documento_limpo) == 11:
        return "PF"

    if len(documento_limpo) == 14:
        return "PJ"

    return None


def codigo_cenario_frete(
    tipo_pessoa: str,
) -> Optional[str]:

    tipo = str(
        tipo_pessoa
        or ""
    ).strip().upper()

    if tipo == "PF":
        return (
            "TRANSP_SUBCONTRATACAO_FRETE_PF"
        )

    if tipo == "PJ":
        return (
            "TRANSP_SUBCONTRATACAO_FRETE_PJ"
        )

    return None




def carregar_contratos_nao_encontrados(
    pasta_resultado: Path,
    periodo: str,
) -> List[Dict[str, Any]]:

    periodo = str(periodo or "").strip()

    if len(periodo) != 6:
        return []

    ano = periodo[:4]
    mes = periodo[4:6]

    caminho = (
        Path(pasta_resultado)
        / ano
        / mes
        / "nao_encontrados.txt"
    )

    if not caminho.exists():
        return []

    texto = caminho.read_text(
        encoding="utf-8"
    )

    blocos = texto.split(
        "-" * 50
    )

    contratos = []

    for bloco in blocos:

        if "Número F100:" not in bloco:
            continue

        contrato = extrair_contrato_do_bloco(
            bloco
        )

        contrato["periodo"] = periodo

        contratos.append(
            contrato
        )

    return contratos


def diagnosticar_fretes_f100_ausentes(
    *,
    db: Session,
    versao_id: int,
    dominio: str,
    periodo: str,
    pasta_resultado: Path,
) -> List[Dict[str, Any]]:

    diagnosticos = []

    # =====================================================
    # 1. SOMENTE TRANSPORTADORA
    # =====================================================

    dominio = str(
        dominio or ""
    ).strip().upper()

    if dominio != "TRANSP":
        return diagnosticos

    # =====================================================
    # 2. CARREGA CONTRATOS FALTANTES
    # =====================================================

    contratos = carregar_contratos_nao_encontrados(
        pasta_resultado=pasta_resultado,
        periodo=periodo,
    )

    if not contratos:
        return diagnosticos

    # =====================================================
    # 3. PROCESSA CADA CONTRATO
    # =====================================================

    for contrato in contratos:

        numero_f100 = str(
            contrato.get("numero_f100")
            or ""
        ).strip()

        contratante = (
            contrato.get("contratante")
            or {}
        )

        contratado = (
            contrato.get("contratado")
            or {}
        )

        documento_contratante = (
            contratante.get("documento")
        )

        documento_contratado = (
            contratado.get("documento")
        )

        # =================================================
        # 4. IDENTIFICA PF / PJ
        # =================================================

        tipo_pessoa = identificar_tipo_pessoa_frete(
            documento_contratado
        )

        if not tipo_pessoa:

            diagnosticos.append({
                "ativo": True,
                "codigo": "FRETE_DOCUMENTO_INVALIDO_V2",
                "tipo": "ERRO_CONTEXTO",
                "prioridade": "ALTA",
                "descricao": (
                    f"Não foi possível identificar PF/PJ "
                    f"do contratado do contrato {numero_f100}."
                ),
                "meta": {
                    "origem": "CONTRATO_FRETE",
                    "numero_f100": numero_f100,
                    "periodo": periodo,
                    "contrato": contrato,
                    "acao_automatica_permitida": False,
                },
            })

            continue

        # =================================================
        # 5. CENÁRIO
        # =================================================

        codigo_cenario = codigo_cenario_frete(
            tipo_pessoa
        )

        if not codigo_cenario:

            diagnosticos.append({
                "ativo": True,
                "codigo": "FRETE_CENARIO_NAO_IDENTIFICADO_V2",
                "tipo": "ERRO_CONFIGURACAO",
                "prioridade": "ALTA",
                "descricao": (
                    f"Cenário fiscal não identificado "
                    f"para o contrato {numero_f100}."
                ),
                "meta": {
                    "origem": "CONTRATO_FRETE",
                    "numero_f100": numero_f100,
                    "periodo": periodo,
                    "tipo_pessoa": tipo_pessoa,
                    "contrato": contrato,
                    "acao_automatica_permitida": False,
                },
            })

            continue

        # =================================================
        # 6. ENQUADRAMENTO
        # =================================================

        enquadramento = buscar_enquadramento_por_cenario(
            db,
            codigo_cenario,
        )

        if not enquadramento:

            diagnosticos.append({
                "ativo": True,
                "codigo": "FRETE_ENQUADRAMENTO_NAO_ENCONTRADO_V2",
                "tipo": "ERRO_CONFIGURACAO",
                "prioridade": "ALTA",
                "descricao": (
                    f"Enquadramento fiscal não encontrado "
                    f"para o cenário {codigo_cenario}."
                ),
                "meta": {
                    "origem": "CONTRATO_FRETE",
                    "numero_f100": numero_f100,
                    "periodo": periodo,
                    "tipo_pessoa": tipo_pessoa,
                    "codigo_cenario": codigo_cenario,
                    "contrato": contrato,
                    "acao_automatica_permitida": False,
                },
            })

            continue

        # =================================================
        # 7. LOCALIZA 0140 DO CONTRATANTE E F010
        # =================================================

        contexto_0140 = localizar_0140_por_cnpj(
            db,
            versao_id=versao_id,
            cnpj=documento_contratante,
        )
        contexto_f010 = localizar_f010_por_cnpj(
            db,
            versao_id=versao_id,
            cnpj=documento_contratante,
        )

        #Cod Conta

        conta_frete = gerar_cod_cta_frete(
            db,
            versao_id=versao_id,
            cnpj_contratante=documento_contratante,
        )

        print(
            "CONTA FRETE:",
            conta_frete,
        )

        # =================================================
        # 8. LOCALIZA 0150 SOMENTE SE HOUVER 0140
        # =================================================

        participante = None

        if contexto_0140:

            participante = localizar_0150_contratado(
                db,
                versao_id=versao_id,
                contexto_0140=contexto_0140,
                documento=documento_contratado,
            )

        # =================================================
        # 9. PREPARA NECESSIDADES DA CORRETIVA
        # =================================================

        criar_0140 = not bool(
            contexto_0140
        )
        criar_f010 = not bool(
            contexto_f010
        )

        criar_0150 = not bool(
            participante
        )

        criar_f100 = True

        # =================================================
        # 10. META BASE
        # =================================================

        meta = {
            "origem": "CONTRATO_FRETE",

            "numero_f100": numero_f100,
            "periodo": periodo,

            "contrato": contrato,

            "tipo_pessoa": tipo_pessoa,

            "codigo_cenario": codigo_cenario,
            "cenario": codigo_cenario,

            "enquadramento": enquadramento,

            "cod_cred": (
                enquadramento.get("cod_cred")
            ),

            "tipo_credito_codigo": (
                enquadramento.get(
                    "tipo_credito_codigo"
                )
            ),

            "nat_bc_cred": (
                enquadramento.get(
                    "nat_bc_cred"
                )
            ),

            "base_credito_codigo": (
                enquadramento.get(
                    "base_credito_codigo"
                )
            ),

            "cst_pis_destino": (
                enquadramento.get(
                    "cst_pis_destino"
                )
            ),

            "cst_cofins_destino": (
                enquadramento.get(
                    "cst_cofins_destino"
                )
            ),

            "aliq_pis": (
                enquadramento.get(
                    "aliq_pis"
                )
            ),

            "aliq_cofins": (
                enquadramento.get(
                    "aliq_cofins"
                )
            ),
            "cod_cta": conta_frete.get(
                "cod_cta"
            ),

            "cod_cta_resolvido": conta_frete.get(
                "resolvido"
            ),

            "origem_cod_cta": conta_frete.get(
                "origem"
            ),

            "estabelecimento_0140": {
                "existe": bool(
                    contexto_0140
                ),

                "registro_id_0140": (
                    contexto_0140.get(
                        "registro_id"
                    )
                    if contexto_0140
                    else None
                ),

                "cod_est": (
                    contexto_0140.get(
                        "cod_est"
                    )
                    if contexto_0140
                    else None
                ),

                "linha_inicio": (
                    contexto_0140.get(
                        "linha_inicio"
                    )
                    if contexto_0140
                    else None
                ),

                "linha_fim": (
                    contexto_0140.get(
                        "linha_fim"
                    )
                    if contexto_0140
                    else None
                ),

                "cnpj": documento_contratante,
            },
            "estabelecimento_f010": {
                "existe": bool(
                    contexto_f010
                ),

                "registro_id_f010": (
                    contexto_f010.get("registro_id")
                    if contexto_f010
                    else None
                ),

                "linha_inicio": (
                    contexto_f010.get("linha_inicio")
                    if contexto_f010
                    else None
                ),

                "linha_fim": (
                    contexto_f010.get("linha_fim")
                    if contexto_f010
                    else None
                ),

                "cnpj": documento_contratante,
            },

            "participante": {
                "existe": bool(
                    participante
                ),

                "registro_id_0150": (
                    participante.get(
                        "registro_id"
                    )
                    if participante
                    else None
                ),

                "cod_part": (
                    participante.get(
                        "cod_part"
                    )
                    if participante
                    else None
                ),

                "documento": (
                    documento_contratado
                ),
            },

            "criar_0140": criar_0140,
            "criar_0150": criar_0150,
            "criar_f010": criar_f010,
            "criar_f100": criar_f100,

            "recalcular_bloco_m": True,

            "tipo_corretiva_v2":
                "INSERIR_F100_FRETE",

            "acao_automatica_permitida": True,
        }

        diagnosticos.append({
            "ativo": True,
            "codigo": "F100_FRETE_AUSENTE_V2",
            "tipo": "OPORTUNIDADE",
            "prioridade": "ALTA",
            "descricao": (
                f"Contrato de transporte {numero_f100} "
                f"não escriturado no registro F100."
            ),
            "meta": meta,
        })

    return diagnosticos