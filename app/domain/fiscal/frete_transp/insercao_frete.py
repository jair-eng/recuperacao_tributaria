from __future__ import annotations

from typing import Any, Dict, List
from sqlalchemy.orm import Session
from app.db.models import EfdRevisao
from app.legacy_service.versao_overlay_service import (
    carregar_linhas_logicas_com_revisoes_e_insert,
)
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import logging

from app.utils.numbers import to_decimal

logger = logging.getLogger(__name__)


def montar_linha_f100_frete(
    *,
    frete: Dict[str, Any],
) -> str:
    """
    Monta a linha do registro F100 da EFD-Contribuições para uma
    operação de frete identificada pelo diagnóstico do sistema.

    Esta função é responsável apenas pela construção textual do
    registro F100. Ela não cria revisão, não grava no banco e não
    resolve âncoras de inserção.

    Espera-se que o dicionário ``frete`` já contenha os dados fiscais
    necessários para a escrituração.

    Estrutura utilizada pelo projeto:

        |F100|
        |IND_OPER|
        |COD_PART|
        |COD_ITEM|
        |DT_OPER|
        |VL_OPER|
        |CST_PIS|
        |VL_BC_PIS|
        |ALIQ_PIS|
        |VL_PIS|
        |CST_COFINS|
        |VL_BC_COFINS|
        |ALIQ_COFINS|
        |VL_COFINS|
        |NAT_BC_CRED|
        |IND_ORIG_CRED|
        |COD_CTA|
        |COD_CCUS|
        |DESC_DOC_OPER|

    Exemplo real utilizado como referência:

        |F100|0|25143||01122025|3005|60|3005|1,2375|37,19|
        60|3005|5,7|171,29|14|0|43101||
        Contrato de Transporte numero 702|

    Para os fretes tratados atualmente pelo projeto:

        IND_OPER       = 0
        COD_ITEM       = vazio
        VL_BC_PIS      = VL_OPER
        VL_BC_COFINS   = VL_OPER
        IND_ORIG_CRED  = 0
        COD_CCUS       = vazio

    Os valores de PIS e COFINS são calculados a partir do valor
    da operação e das respectivas alíquotas.

    Exemplo:

        VL_OPER = 4200
        ALIQ_PIS = 1,2375
        ALIQ_COFINS = 5,7

        VL_PIS =
            4200 * 1,2375 / 100
            = 51,975
            = 51,98

        VL_COFINS =
            4200 * 5,7 / 100
            = 239,40

    Parâmetros
    ----------
    frete:
        Dicionário contendo os dados necessários para geração do F100.

        Campos esperados:

            numero_f100
            cod_part
            data
            valor_frete
            cst_pis
            cst_cofins
            aliq_pis
            aliq_cofins
            nat_bc_cred
            cod_cta

    Retorno
    -------
    str
        Linha completa do F100 pronta para ser armazenada em
        ``EfdRevisao.revisao_json["linha_nova"]``.

    Observação
    ----------
    A função não decide se o F100 deve ou não ser criado.
    Essa decisão pertence ao diagnóstico/corretiva.

    Também não define onde o registro será inserido. A posição é
    responsabilidade da rotina de inserção encadeada, que utiliza
    o F010 existente ou o F100 anteriormente inserido como âncora.
    """

    # ------------------------------------------------------------
    # Dados principais da operação
    # ------------------------------------------------------------

    numero_f100 = str(frete.get("numero_f100") or "").strip()
    cod_part = str(frete.get("cod_part") or "").strip()

    data_operacao = str(frete.get("data") or "").strip()

    # ------------------------------------------------------------
    # Conversão da data:
    #
    # entrada:
    #     02/01/2021
    #
    # saída SPED:
    #     02012021
    # ------------------------------------------------------------

    if not data_operacao:
        raise ValueError(
            "Data da operação não informada para geração do F100."
        )

    try:
        dt_oper = datetime.strptime(
            data_operacao,
            "%d/%m/%Y",
        ).strftime("%d%m%Y")

    except ValueError as exc:
        raise ValueError(
            f"Data inválida para geração do F100: {data_operacao!r}"
        ) from exc



    valor_operacao = to_decimal(
        frete.get("valor_frete")
    )

    aliq_pis = to_decimal(
        frete.get("aliq_pis")
    )

    aliq_cofins = to_decimal(
        frete.get("aliq_cofins")
    )

    # ------------------------------------------------------------
    # Cálculo dos créditos
    # ------------------------------------------------------------

    valor_pis = (
        valor_operacao
        * aliq_pis
        / Decimal("100")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    valor_cofins = (
        valor_operacao
        * aliq_cofins
        / Decimal("100")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    # ------------------------------------------------------------
    # Formatação numérica para o SPED
    #
    # Decimal:
    #     51.98
    #
    # SPED:
    #     51,98
    #
    # Também removemos zeros desnecessários:
    #
    #     4200.00 -> 4200
    #     239.40  -> 239,4
    # ------------------------------------------------------------

    def formatar_decimal(valor: Decimal) -> str:

        texto = format(valor, "f")

        if "." in texto:
            texto = texto.rstrip("0").rstrip(".")

        return texto.replace(".", ",")

    vl_oper = formatar_decimal(valor_operacao)
    vl_pis = formatar_decimal(valor_pis)
    vl_cofins = formatar_decimal(valor_cofins)

    aliq_pis_txt = formatar_decimal(aliq_pis)
    aliq_cofins_txt = formatar_decimal(aliq_cofins)

    # ------------------------------------------------------------
    # Dados fiscais
    # ------------------------------------------------------------

    cst_pis = str(
        frete.get("cst_pis") or ""
    ).strip()

    cst_cofins = str(
        frete.get("cst_cofins") or ""
    ).strip()

    nat_bc_cred = str(
        frete.get("nat_bc_cred") or ""
    ).strip()

    cod_cta = str(
        frete.get("cod_cta") or ""
    ).strip()

    # ------------------------------------------------------------
    # Validações mínimas
    # ------------------------------------------------------------

    if not numero_f100:
        raise ValueError(
            "Número do contrato/F100 não informado."
        )

    if not cod_part:
        raise ValueError(
            "COD_PART não informado para geração do F100."
        )

    if valor_operacao <= 0:
        raise ValueError(
            f"Valor de frete inválido: {valor_operacao}"
        )

    if not cst_pis:
        raise ValueError(
            "CST PIS não informado para geração do F100."
        )

    if not cst_cofins:
        raise ValueError(
            "CST COFINS não informado para geração do F100."
        )

    if not nat_bc_cred:
        raise ValueError(
            "NAT_BC_CRED não informado para geração do F100."
        )

    if not cod_cta:
        raise ValueError(
            "COD_CTA não informado para geração do F100."
        )

    # ------------------------------------------------------------
    # Descrição da operação
    # ------------------------------------------------------------

    desc_doc_oper = (
        f"Contrato de Transporte numero {numero_f100}"
    )

    # ------------------------------------------------------------
    # Montagem dos campos na ordem física do F100
    # ------------------------------------------------------------

    campos = [
        "F100",             # REG
        "0",                # IND_OPER
        cod_part,           # COD_PART
        "",                 # COD_ITEM
        dt_oper,            # DT_OPER
        vl_oper,            # VL_OPER
        cst_pis,            # CST_PIS
        vl_oper,            # VL_BC_PIS
        aliq_pis_txt,       # ALIQ_PIS
        vl_pis,             # VL_PIS
        cst_cofins,         # CST_COFINS
        vl_oper,            # VL_BC_COFINS
        aliq_cofins_txt,    # ALIQ_COFINS
        vl_cofins,          # VL_COFINS
        nat_bc_cred,        # NAT_BC_CRED
        "0",                # IND_ORIG_CRED
        cod_cta,            # COD_CTA
        "",                 # COD_CCUS
        desc_doc_oper,      # DESC_DOC_OPER
    ]

    # ------------------------------------------------------------
    # Proteção contra alteração acidental do layout
    # ------------------------------------------------------------

    if len(campos) != 19:
        raise ValueError(
            "Layout F100 inválido: "
            f"esperados 19 campos, encontrados {len(campos)}."
        )

    return "|" + "|".join(campos) + "|"

def _criar_revisao_insert_f100_frete_v2(
    db: Session,
    *,
    versao_origem_id: int,
    registro_id_alvo: int | None,
    linha_ref: int,
    acao: str,
    frete: Dict[str, Any],
    apontamento_id: int | None = None,
    motivo_codigo: str = "CORRETIVA_F100_FRETE",
) -> EfdRevisao:
    """
    Cria uma revisão de inserção para um registro F100 de frete.

    Esta função recebe uma âncora já resolvida e registra no banco
    uma EfdRevisao contendo a nova linha F100.

    A função não decide qual deve ser a âncora. Essa responsabilidade
    pertence à rotina de inserção.

    No cenário atual, em que o F010 já existe:

        primeiro F100:
            âncora = F010
            ação   = INSERT_AFTER

        próximos F100:
            âncora = F100 inserido anteriormente
            ação   = INSERT_AFTER

    Parâmetros
    ----------
    db:
        Sessão SQLAlchemy utilizada para persistência.

    versao_origem_id:
        ID da versão original da EFD que receberá a revisão.

    registro_id_alvo:
        ID do registro utilizado como âncora da inserção.

        Exemplo:
            ID do F010 para o primeiro F100.

    linha_ref:
        Número da linha física/lógica utilizada como referência
        para a inserção.

    acao:
        Tipo da inserção.

        Valores esperados atualmente:

            INSERT_AFTER
            INSERT_BEFORE

        Para F100 dentro de F010 existente utilizaremos
        INSERT_AFTER.

    frete:
        Dicionário contendo todos os dados necessários para
        montar a linha F100.

    apontamento_id:
        ID do apontamento que originou a corretiva.

    motivo_codigo:
        Código utilizado para identificar o motivo da revisão.

    Retorno
    -------
    EfdRevisao
        Objeto de revisão criado e já submetido a ``db.flush()``.

    Observação
    ----------
    O ``flush`` envia a revisão para a sessão/banco e permite obter
    seu ID, mas não realiza o commit da transação.
    """

    # ------------------------------------------------------------
    # Validação da referência de inserção
    #
    # O primeiro F100 normalmente utiliza o registro_id físico
    # do F010 como âncora.
    #
    # Após a primeira inserção, entretanto, o F100 criado existe
    # somente no overlay e possui registro_id=None.
    #
    # Nesse caso, o encadeamento é mantido através da
    # linha_referencia lógica, seguindo o mesmo mecanismo já
    # utilizado pela inserção encadeada dos registros C170.
    # ------------------------------------------------------------

    if not registro_id_alvo and not linha_ref:
        raise ValueError(
            "Nenhuma referência válida informada para inserção do F100."
        )

    # ------------------------------------------------------------
    # Validação da ação
    # ------------------------------------------------------------

    acoes_permitidas = {
        "INSERT_AFTER",
        "INSERT_BEFORE",
    }

    if acao not in acoes_permitidas:
        raise ValueError(
            f"Ação inválida para inserção do F100: {acao!r}"
        )

    # ------------------------------------------------------------
    # Montagem da linha física do F100
    # ------------------------------------------------------------

    linha_nova = montar_linha_f100_frete(
        frete=frete,
    )

    # ------------------------------------------------------------
    # Criação da revisão
    # ------------------------------------------------------------

    rv = EfdRevisao(
        versao_origem_id=int(versao_origem_id),
        versao_revisada_id=None,
        registro_id=(
            int(registro_id_alvo)
            if registro_id_alvo is not None
            else None
        ),
        reg="F100",
        acao=acao,
        revisao_json={
            "linha_nova": linha_nova,
            "linha_referencia": int(linha_ref or 0),

            # Informações úteis para rastreabilidade
            "origem": "CONTRATO_FRETE",
            "numero_f100": frete.get("numero_f100"),
            "cod_part": frete.get("cod_part"),
            "periodo": frete.get("periodo"),

            "meta": {
                "tipo_operacao": "FRETE",
                "registro_pai": "F010",
                "nat_bc_cred": str(
                    frete.get("nat_bc_cred") or ""
                ).strip(),

                "cod_cred": str(
                    frete.get("cod_cred") or ""
                ).strip(),
            },
        },
        motivo_codigo=motivo_codigo,
        apontamento_id=apontamento_id,
    )

    db.add(rv)

    # Precisamos do ID da revisão para posteriormente
    # encontrá-la no overlay.
    db.flush()

    return rv

def inserir_f100s_do_f010_encadeados(
    db: Session,
    *,
    versao_origem_id: int,
    fretes: List[Dict[str, Any]],
    registro_id_f010: int,
    linha_f010: int,
    apontamento_id: int | None = None,
    motivo_codigo: str = "CORRETIVA_F100_FRETE",
) -> Dict[str, Any]:
    """
    Insere registros F100 de frete de forma encadeada dentro
    de um F010 já existente.

    Regra de inserção:

    1. O primeiro F100 utiliza o próprio F010 como âncora,
       com ação INSERT_AFTER.

    2. Após cada inserção, o overlay da EFD é recarregado.

    3. O F100 recém-inserido é localizado pelo revisao_id.

    4. Esse F100 passa a ser a âncora do próximo registro,
       também utilizando INSERT_AFTER.

    Dessa forma, múltiplos F100 pertencentes ao mesmo F010
    são mantidos em sequência:

        |F010|...|
        |F100|1|
        |F100|2|
        |F100|3|

    sem que todos dependam da mesma âncora F010.
    """

    total_inseridos = 0

    registro_id_alvo = int(registro_id_f010)
    linha_ref_alvo = int(linha_f010 or 0)
    acao = "INSERT_AFTER"

    revisao_fim_bloco_id = None

    for frete in fretes:

        # --------------------------------------------------------
        # Criação da revisão
        # --------------------------------------------------------

        rv = _criar_revisao_insert_f100_frete_v2(
            db,
            versao_origem_id=versao_origem_id,
            registro_id_alvo=registro_id_alvo,
            linha_ref=linha_ref_alvo,
            acao=acao,
            frete=frete,
            apontamento_id=apontamento_id,
            motivo_codigo=motivo_codigo,
        )

        db.add(rv)
        db.flush()

        revisao_fim_bloco_id = int(rv.id)
        total_inseridos += 1

        # --------------------------------------------------------
        # Recarrega overlay para localizar o F100 recém-inserido
        # --------------------------------------------------------

        linhas = carregar_linhas_logicas_com_revisoes_e_insert(
            db,
            versao_origem_id=int(versao_origem_id),
            versao_final_id=None,
        )

        linha_f100_inserido = None

        for linha in linhas:

            if (
                str(getattr(linha, "reg", "")).upper() == "F100"
                and getattr(linha, "revisao_id", None) == rv.id
            ):
                linha_f100_inserido = linha
                break

        # --------------------------------------------------------
        # Novo F100 vira âncora do próximo
        # --------------------------------------------------------

        if linha_f100_inserido:
            registro_id_alvo = getattr(
                linha_f100_inserido,
                "registro_id",
                None,
            )

            linha_ref_alvo = int(
                getattr(
                    linha_f100_inserido,
                    "linha",
                    0,
                )
                or 0
            )

            acao = "INSERT_AFTER"

        else:
            logger.warning(
                "[F100_FRETE] F100 inserido não localizado "
                "no overlay | revisao_id=%s numero_f100=%s",
                rv.id,
                frete.get("numero_f100"),
            )

    return {
        "total_inseridos": total_inseridos,
        "registro_id_fim_bloco": registro_id_alvo,
        "linha_fim_bloco": linha_ref_alvo,
        "revisao_fim_bloco_id": revisao_fim_bloco_id,
    }
