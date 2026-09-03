from __future__ import annotations

from typing import Any, Dict, List
from sqlalchemy.orm import Session
from app.db.models import EfdRevisao
from app.domain.fiscal.frete_transp.ancoras_fretes import resolver_ancora_bloco_f_fim
from app.domain.fiscal.frete_transp.insercao_frete import montar_linha_f100_frete


def montar_linha_f010_frete(
    *,
    cnpj_estabelecimento: str,
) -> str:
    """
    Monta o registro F010.

    Estrutura:

        |F010|CNPJ|

    O CNPJ é gravado apenas com números.
    """

    cnpj = "".join(
        caractere
        for caractere in str(cnpj_estabelecimento or "")
        if caractere.isdigit()
    )

    if len(cnpj) != 14:
        raise ValueError(
            f"CNPJ inválido para criação do F010: "
            f"{cnpj_estabelecimento!r}"
        )

    return f"|F010|{cnpj}|"


def inserir_bloco_f010_f100_linhas_novas(
    db: Session,
    *,
    versao_origem_id: int,
    cnpj_estabelecimento: str,
    fretes: List[Dict[str, Any]],
    registro_id_alvo: int | None,
    linha_ref_alvo: int,
    acao_inicial: str,
    apontamento_ids: list[int] | None = None,
    motivo_codigo: str = "F100_FRETE_AUSENTE_V2",
) -> Dict[str, Any]:
    """
    Insere um bloco completo:

        F010
          F100
          F100
          F100

    utilizando uma única EfdRevisao com `linhas_novas`.

    Esse fluxo deve ser utilizado quando o F010 ainda não existe.
    """

    if not fretes:
        raise ValueError(
            "Nenhum frete informado para criação do bloco F010/F100."
        )

    if acao_inicial not in {
        "INSERT_BEFORE",
        "INSERT_AFTER",
    }:
        raise ValueError(
            f"Ação inválida para inserção do bloco F010/F100: "
            f"{acao_inicial!r}"
        )

    if not registro_id_alvo and not linha_ref_alvo:
        raise ValueError(
            "Nenhuma âncora válida informada para "
            "inserção do bloco F010/F100."
        )

    # ---------------------------------------------------------
    # 1. Cria linha pai F010
    # ---------------------------------------------------------

    linha_f010 = montar_linha_f010_frete(
        cnpj_estabelecimento=cnpj_estabelecimento,
    )

    linhas_novas = [
        linha_f010,
    ]

    # ---------------------------------------------------------
    # 2. Cria os F100 filhos
    # ---------------------------------------------------------

    numeros_f100 = []
    metadados_f100 = []

    for frete in fretes:

        linha_f100 = montar_linha_f100_frete(
            frete=frete,
        )

        linhas_novas.append(
            linha_f100
        )

        numeros_f100.append(
            str(
                frete.get("numero_f100")
                or ""
            ).strip()
        )
        metadados_f100.append({
            "linha": linha_f100,

            "numero_f100": str(
                frete.get("numero_f100")
                or ""
            ).strip(),

            "cod_cred": str(
                frete.get("cod_cred")
                or ""
            ).strip(),

            "nat_bc_cred": str(
                frete.get("nat_bc_cred")
                or ""
            ).strip(),
        })

    # ---------------------------------------------------------
    # 3. Validação estrutural
    # ---------------------------------------------------------

    qtd_f010 = sum(
        1
        for linha in linhas_novas
        if str(linha or "").startswith("|F010|")
    )

    qtd_f100 = sum(
        1
        for linha in linhas_novas
        if str(linha or "").startswith("|F100|")
    )

    if qtd_f010 != 1:
        raise ValueError(
            "Bloco F010/F100 inválido: "
            f"esperado 1 F010, encontrados {qtd_f010}."
        )

    if qtd_f100 != len(fretes):
        raise ValueError(
            "Bloco F010/F100 inválido: "
            f"esperados {len(fretes)} F100, "
            f"encontrados {qtd_f100}."
        )

    # ---------------------------------------------------------
    # 4. Cria uma única revisão para o bloco inteiro
    # ---------------------------------------------------------

    rv = EfdRevisao(
        versao_origem_id=int(
            versao_origem_id
        ),

        versao_revisada_id=None,

        registro_id=(
            int(registro_id_alvo)
            if registro_id_alvo is not None
            else None
        ),

        reg="F010",

        acao=acao_inicial,

        revisao_json={
            "linhas_novas": linhas_novas,
            "metadados_f100": metadados_f100,

            "linha_referencia": int(
                linha_ref_alvo or 0
            ),

            "origem": "CONTRATO_FRETE",

            "tipo_bloco": "F010_F100_V2",

            "cnpj_estabelecimento":
                cnpj_estabelecimento,

            "numeros_f100":
                numeros_f100,

            "apontamento_ids": [
                int(ap_id)
                for ap_id in (
                    apontamento_ids or []
                )
            ],

            "meta": {
                "tipo_operacao": "FRETE",

                "registro_pai": "F010",

                "quantidade_f100":
                    qtd_f100,
            },
        },

        motivo_codigo=motivo_codigo,

        # Um bloco pode representar vários apontamentos.
        # Portanto não vinculamos arbitrariamente um único
        # apontamento à revisão principal.
        apontamento_id=None,
    )

    db.add(rv)
    db.flush()

    return {
        "ok": True,

        "revisao_f010_id":
            int(rv.id),

        "cnpj_estabelecimento":
            cnpj_estabelecimento,

        "f010_inserido":
            1,

        "f100_inseridos":
            qtd_f100,

        "numeros_f100":
            numeros_f100,

        "apontamento_ids":
            apontamento_ids or [],
    }




def inserir_blocos_f010_f100_ausentes(
    db: Session,
    *,
    versao_origem_id: int,
    grupos_elegiveis: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Insere vários blocos F010 + F100 ausentes.

    Cada estabelecimento gera uma revisão própria:

        revisão 1:
            F010 A
            F100
            F100

        revisão 2:
            F010 B
            F100

    Todos são inseridos antes do F990.
    """

    total_f010_insert = 0
    total_f100_insert = 0

    detalhes = []

    if not grupos_elegiveis:
        return {
            "ok": True,
            "total_f010_insert": 0,
            "total_f100_insert": 0,
            "detalhes": [],
        }

    # ---------------------------------------------------------
    # Âncora estrutural do Bloco F
    # ---------------------------------------------------------

    (
        registro_id_alvo,
        linha_ref_alvo,
        acao_inicial,
    ) = resolver_ancora_bloco_f_fim(
        db,
        versao_origem_id=versao_origem_id,
    )

    # ---------------------------------------------------------
    # Insere um bloco para cada estabelecimento
    # ---------------------------------------------------------

    for grupo in grupos_elegiveis:

        cnpj = str(
            grupo.get("cnpj_estabelecimento")
            or ""
        ).strip()

        fretes = (
            grupo.get("fretes")
            or []
        )

        apontamento_ids = (
            grupo.get("apontamento_ids")
            or []
        )

        if not cnpj or not fretes:
            continue

        res_bloco = inserir_bloco_f010_f100_linhas_novas(
            db,
            versao_origem_id=versao_origem_id,

            cnpj_estabelecimento=cnpj,

            fretes=fretes,

            registro_id_alvo=registro_id_alvo,
            linha_ref_alvo=linha_ref_alvo,
            acao_inicial=acao_inicial,

            apontamento_ids=apontamento_ids,
        )

        total_f010_insert += int(
            res_bloco.get("f010_inserido")
            or 0
        )

        total_f100_insert += int(
            res_bloco.get("f100_inseridos")
            or 0
        )

        detalhes.append(
            res_bloco
        )

    db.flush()

    return {
        "ok": True,

        "versao_origem_id":
            int(versao_origem_id),

        "total_f010_insert":
            total_f010_insert,

        "total_f100_insert":
            total_f100_insert,

        "detalhes":
            detalhes,
    }