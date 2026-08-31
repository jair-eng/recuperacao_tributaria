from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.db.models import EfdRegistro, EfdVersao, Empresa
from app.domain.fiscal.frete_transp.mestres_fretes import localizar_f010_por_cnpj

from app.domain.relatorio_executivo.extrair_conta_efd_para_fallback import (
    carregar_contas_0500_local,
)

from app.icms_ipi.icms_0150_agregador import (
    _somente_digitos,
)

CAMINHO_CATALOGO_0500 = Path(
    r"C:\Sped\saida\catalogo_0500_contrib.json"
)

def _dados_registro_frete(
    registro: EfdRegistro,
) -> list:
    """
    Retorna os campos armazenados em conteudo_json['dados'].

    Remove o código do registro quando ele também estiver
    presente como primeiro elemento da lista.

    Exemplo:

        ["F100", "0", "24222", ...]

    passa a ser:

        ["0", "24222", ...]
    """

    conteudo = getattr(
        registro,
        "conteudo_json",
        None,
    ) or {}

    if not isinstance(conteudo, dict):
        return []

    dados = list(
        conteudo.get("dados")
        or []
    )

    reg = str(
        getattr(registro, "reg", "")
        or ""
    ).strip()

    if (
        dados
        and str(dados[0] or "").strip() == reg
    ):
        dados = dados[1:]

    return dados


def _campo_frete(
    dados: list,
    indice: int,
) -> Optional[str]:
    """
    Retorna um campo da lista de dados do registro
    de forma segura.
    """

    if indice >= len(dados):
        return None

    valor = dados[indice]

    if valor is None:
        return None

    valor = str(valor).strip()

    return valor or None


def _buscar_cod_cta_em_f100_existente(
    db: Session,
    *,
    versao_id: int,
    contexto_f010: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Procura um COD_CTA já utilizado em registros F100 de frete
    da própria EFD-Contribuições.

    Quando houver contexto F010 disponível, restringe a busca
    ao intervalo estrutural daquele estabelecimento dentro do
    Bloco F.

    A busca prioriza registros F100 compatíveis com operações
    de frete, evitando utilizar uma conta contábil pertencente
    a outro tipo de operação registrada no F100.

    Critérios utilizados:

    - registro F100 pertencente à versão analisada;
    - registro localizado dentro do F010 do contratante,
      quando esse contexto estiver disponível;
    - NAT_BC_CRED igual a 14;
    - descrição da operação relacionada a contrato de transporte.

    O objetivo é preservar o padrão contábil já utilizado pela
    própria empresa para operações de frete antes de recorrer
    ao catálogo 0500 como fallback.
    """

    query = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_id),
            EfdRegistro.reg == "F100",
        )
    )

    # --------------------------------------------------------
    # Restringe ao estabelecimento correto no Bloco F
    # --------------------------------------------------------

    if contexto_f010:

        linha_inicio = int(
            contexto_f010.get("linha_inicio")
            or 0
        )

        linha_fim = int(
            contexto_f010.get("linha_fim")
            or 0
        )

        if linha_inicio:
            query = query.filter(
                EfdRegistro.linha > linha_inicio
            )

        if linha_fim:
            query = query.filter(
                EfdRegistro.linha < linha_fim
            )

    registros_f100 = (
        query
        .order_by(
            EfdRegistro.linha.asc()
        )
        .all()
    )

    # --------------------------------------------------------
    # Analisa os F100 encontrados
    # --------------------------------------------------------

    for registro in registros_f100:

        dados = _dados_registro_frete(
            registro
        )

        # Layout F100 após remover REG:
        #
        # 0  IND_OPER
        # 1  COD_PART
        # 2  COD_ITEM
        # 3  DT_OPER
        # 4  VL_OPER
        # 5  CST_PIS
        # 6  VL_BC_PIS
        # 7  ALIQ_PIS
        # 8  VL_PIS
        # 9  CST_COFINS
        # 10 VL_BC_COFINS
        # 11 ALIQ_COFINS
        # 12 VL_COFINS
        # 13 NAT_BC_CRED
        # 14 IND_ORIG_CRED
        # 15 COD_CTA
        # 16 COD_CCUS
        # 17 DESC_DOC_OPER

        nat_bc_cred = _campo_frete(
            dados,
            13,
        )

        cod_cta = _campo_frete(
            dados,
            15,
        )

        descricao = str(
            _campo_frete(
                dados,
                17,
            )
            or ""
        ).strip().upper()

        # ----------------------------------------------------
        # Filtra F100 compatível com frete
        # ----------------------------------------------------

        if nat_bc_cred != "14":
            continue

        if "CONTRATO DE TRANSPORTE" not in descricao:
            continue

        if not cod_cta:
            continue

        return cod_cta

    return None


def _buscar_cod_cta_catalogo_0500(
    db: Session,
    *,
    versao_id: int,
) -> Optional[str]:
    """
    Busca uma conta contábil no catálogo 0500 previamente
    extraído para a empresa da versão analisada.

    Esta etapa funciona como fallback quando não foi possível
    resolver o COD_CTA a partir dos F100 já existentes.
    """

    versao = (
        db.query(EfdVersao)
        .filter(
            EfdVersao.id == int(versao_id)
        )
        .first()
    )

    if not versao:
        return None

    empresa_id = int(
        getattr(
            versao,
            "empresa_id",
            0,
        )
        or 0
    )

    if not empresa_id:
        return None

    empresa = (
        db.query(Empresa)
        .filter(
            Empresa.id == empresa_id
        )
        .first()
    )

    if not empresa:
        return None

    cnpj_empresa = _somente_digitos(
        getattr(
            empresa,
            "cnpj",
            None,
        )
    )

    if not cnpj_empresa:
        return None

    contas = carregar_contas_0500_local(
        caminho_catalogo=CAMINHO_CATALOGO_0500,
        cnpj_empresa=cnpj_empresa,
    )

    if not contas:
        return None

    # Primeira versão:
    # não inventa conta e não usa código fixo.
    #
    # Só aceita uma resolução inequívoca.
    contas_validas = []

    for conta in contas:

        cod_cta = str(
            conta.get("cod_cta")
            or ""
        ).strip()

        if not cod_cta:
            continue

        if cod_cta in {
            "0000",
            "999999",
        }:
            continue

        contas_validas.append(
            cod_cta
        )

    contas_unicas = list(
        dict.fromkeys(
            contas_validas
        )
    )

    if len(contas_unicas) == 1:
        return contas_unicas[0]

    return None


def gerar_cod_cta_frete(
    db: Session,
    *,
    versao_id: int,
    cnpj_contratante: str,
) -> Dict[str, Any]:
    """
      Resolve o código da conta contábil (COD_CTA) para novos
      registros F100 de frete.

      Estratégia:

      1. Procura primeiro o COD_CTA utilizado nos registros F100
         já existentes da EFD-Contribuições da versão analisada.

      2. Havendo contexto 0140, prioriza a conta utilizada no
         estabelecimento correspondente ao contratante.

      3. Se não houver conta utilizável nos F100 existentes,
         consulta como fallback o catálogo local:

             C:\\Sped\\saida\\catalogo_0500_contrib.json

         O catálogo é filtrado pelo CNPJ da empresa correspondente
         à versão analisada.

      4. Se nenhuma conta puder ser determinada com segurança,
         retorna COD_CTA como None, sem utilizar valores hard coded.

      Retorno:

          {
              "cod_cta": str | None,
              "resolvido": bool,
              "origem": "F100_EXISTENTE"
                        | "CATALOGO_0500"
                        | "NAO_RESOLVIDO"
          }

      Esse resultado deve seguir na meta do apontamento para que
      a corretiva não precise repetir a resolução da conta.
      """

    contexto_f010 = localizar_f010_por_cnpj(
        db,
        versao_id=versao_id,
        cnpj=cnpj_contratante,
    )

    # ============================================================
    # 1. PRIORIDADE: F100 EXISTENTE
    # ============================================================

    cod_cta = _buscar_cod_cta_em_f100_existente(
        db,
        versao_id=versao_id,
        contexto_f010=contexto_f010,
    )

    if cod_cta:

        return {
            "cod_cta": cod_cta,
            "resolvido": True,
            "origem": "F100_EXISTENTE",
        }

    # ============================================================
    # 2. FALLBACK: CATÁLOGO 0500
    # ============================================================

    cod_cta = _buscar_cod_cta_catalogo_0500(
        db,
        versao_id=versao_id,
    )

    if cod_cta:

        return {
            "cod_cta": cod_cta,
            "resolvido": True,
            "origem": "CATALOGO_0500",
        }

    # ============================================================
    # 3. NÃO RESOLVIDO
    # ============================================================

    return {
        "cod_cta": None,
        "resolvido": False,
        "origem": "NAO_RESOLVIDO",
    }