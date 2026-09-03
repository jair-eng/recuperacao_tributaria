from app.db.models import EfdApontamento

from sqlalchemy.orm import Session
from typing import Any, Dict, Optional
from app.domain.fiscal.frete_transp.insercao_frete import inserir_f100s_do_f010_encadeados, garantir_0150_frete
from app.domain.fiscal.frete_transp.insercao_frete_f010_faltante import inserir_blocos_f010_f100_ausentes
import logging

logger = logging.getLogger(__name__)


def resolver_f010_f100_ausentes_em_lote(
    db: Session,
    *,
    versao_id: int,
    apontamentos: list[EfdApontamento],
) -> dict:
    """
    Agrupa apontamentos de frete pelo estabelecimento contratante
    quando o F010 ainda não existe.

    Um CNPJ gera:

        1 F010
        N F100
    """

    grupos: dict[str, dict] = {}

    skips = 0
    erros = 0

    # =========================================================
    # 1. AGRUPAMENTO
    # =========================================================

    for ap in apontamentos:

        meta = (
            ap.meta_json
            or {}
        )

        if (
            meta.get("tipo_corretiva_v2")
            != "INSERIR_F100_FRETE"
        ):
            continue

        # Este resolvedor cuida apenas do F010 ausente.
        if not bool(
            meta.get("criar_f010")
        ):
            continue

        # 0140 precisa existir nesta primeira etapa.
        # Cenário de criação do 0140 ficará para outro fluxo.
        estabelecimento_0140 = (
            meta.get("estabelecimento_0140")
            or {}
        )

        if not bool(
            estabelecimento_0140.get("existe")
        ):
            skips += 1
            continue

        estabelecimento_f010 = (
            meta.get("estabelecimento_f010")
            or {}
        )

        # Proteção:
        # diagnóstica disse criar_f010,
        # mas aparentemente já há F010.
        if bool(
            estabelecimento_f010.get("existe")
        ):
            skips += 1
            continue

        cnpj = "".join(
            caractere
            for caractere in str(
                estabelecimento_0140.get("cnpj")
                or estabelecimento_f010.get("cnpj")
                or ""
            )
            if caractere.isdigit()
        )

        if len(cnpj) != 14:
            erros += 1
            continue

        grupos.setdefault(
            cnpj,
            {
                "cnpj_estabelecimento":
                    cnpj,

                "contexto_0140":
                    estabelecimento_0140,

                "itens_ctx": [],
            },
        )

        grupos[cnpj][
            "itens_ctx"
        ].append({
            "ap":
                ap,

            "meta":
                meta,
        })

    # =========================================================
    # 2. PREPARAÇÃO DOS GRUPOS ELEGÍVEIS
    # =========================================================

    grupos_elegiveis = []

    for cnpj, grupo in grupos.items():

        itens_ctx = (
            grupo["itens_ctx"]
        )

        # Ordenação determinística
        itens_ctx = sorted(
            itens_ctx,
            key=lambda x: (
                str(
                    (
                            (
                                    x["meta"].get("contrato")
                                    or {}
                            ).get("frete")
                            or {}
                    ).get("data")
                    or ""
                ),
                str(
                    x["meta"].get("numero_f100")
                    or ""
                ),
                int(
                    getattr(
                        x["ap"],
                        "id",
                        0,
                    )
                    or 0
                ),
            ),
        )

        fretes = []
        apontamento_ids = []

        grupo_valido = True

        for item_ctx in itens_ctx:

            ap = item_ctx["ap"]
            meta = item_ctx["meta"]

            contrato = (
                    meta.get("contrato")
                    or {}
            )
            frete_meta = (
                    contrato.get("frete")
                    or {}
            )

            contratado = (
                    contrato.get("contratado")
                    or {}
            )

            estabelecimento_0140 = (
                    meta.get("estabelecimento_0140")
                    or {}
            )

            registro_id_0140 = (
                estabelecimento_0140.get(
                    "registro_id_0140"
                )
            )

            if not registro_id_0140:
                grupo_valido = False
                erros += 1
                break

            documento_contratado = (
                contratado.get("documento")
            )

            nome_contratado = (
                contratado.get("nome")
            )

            tipo_pessoa = (
                meta.get("tipo_pessoa")
            )

            if not documento_contratado:
                grupo_valido = False
                erros += 1
                break

            contexto_0140 = {
                "existe": True,

                "registro_id": int(
                    registro_id_0140
                ),

                "linha_inicio": int(
                    estabelecimento_0140.get(
                        "linha_inicio"
                    )
                    or 0
                ),

                "linha_fim": int(
                    estabelecimento_0140.get(
                        "linha_fim"
                    )
                    or 0
                ),

                "cod_est": (
                    estabelecimento_0140.get(
                        "cod_est"
                    )
                ),

                "cnpj": (
                    estabelecimento_0140.get(
                        "cnpj"
                    )
                ),
            }

            resultado_participante = garantir_0150_frete(
                db,

                versao_id=versao_id,

                contexto_0140=contexto_0140,

                documento=documento_contratado,

                nome=nome_contratado,

                tipo_pessoa=tipo_pessoa,

                ie=contratado.get("ie"),

                cod_mun=contratado.get(
                    "municipio"
                ),

                logradouro=contratado.get(
                    "logradouro"
                ),

                numero=contratado.get(
                    "numero"
                ),

                complemento=contratado.get(
                    "complemento"
                ),

                bairro=contratado.get(
                    "bairro"
                ),

                apontamento_id=int(
                    ap.id
                ),
            )

            cod_part = (
                resultado_participante.get(
                    "cod_part"
                )
            )

            if not cod_part:
                grupo_valido = False
                erros += 1
                break



            frete = {
                "numero_f100":
                    meta.get("numero_f100"),

                "periodo":
                    meta.get("periodo"),

                "cod_part":
                    cod_part,

                "data":
                    frete_meta.get("data"),

                "valor_frete":
                    frete_meta.get("valor_frete"),

                "cst_pis":
                    meta.get(
                        "cst_pis_destino"
                    ),

                "cst_cofins":
                    meta.get(
                        "cst_cofins_destino"
                    ),

                "aliq_pis":
                    meta.get("aliq_pis"),

                "aliq_cofins":
                    meta.get("aliq_cofins"),

                "nat_bc_cred":
                    meta.get("nat_bc_cred"),

                "cod_cred":
                    meta.get("cod_cred"),

                "cod_cta":
                    meta.get("cod_cta"),
            }

            fretes.append(
                frete
            )

            apontamento_ids.append(
                int(ap.id)
            )

        if not grupo_valido:
            continue

        if not fretes:
            continue

        grupos_elegiveis.append({
            "cnpj_estabelecimento":
                cnpj,

            "contexto_0140":
                grupo["contexto_0140"],

            "fretes":
                fretes,

            "apontamento_ids":
                apontamento_ids,

            "apontamentos": [
                x["ap"]
                for x in itens_ctx
            ],
        })

    # =========================================================
    # 3. INSERÇÃO
    # =========================================================

    ids_processados = []

    total_f010 = 0
    total_f100 = 0

    if grupos_elegiveis:

        res_lote = (
            inserir_blocos_f010_f100_ausentes(
                db,
                versao_origem_id=versao_id,
                grupos_elegiveis=grupos_elegiveis,
            )
        )

        total_f010 = int(
            res_lote.get(
                "total_f010_insert"
            )
            or 0
        )

        total_f100 = int(
            res_lote.get(
                "total_f100_insert"
            )
            or 0
        )

        # -----------------------------------------------------
        # Só depois da inserção:
        # marca os apontamentos do grupo como resolvidos
        # -----------------------------------------------------

        esperado_f010 = len(
            grupos_elegiveis
        )

        esperado_f100 = sum(
            len(
                grupo.get("fretes")
                or []
            )
            for grupo in grupos_elegiveis
        )

        if (
                total_f010 != esperado_f010
                or total_f100 != esperado_f100
        ):
            erros += 1

            logger.warning(
                "[F010_F100_LOTE] quantidade divergente | "
                "F010 esperado=%s inserido=%s | "
                "F100 esperado=%s inserido=%s",
                esperado_f010,
                total_f010,
                esperado_f100,
                total_f100,
            )

        else:
            for grupo in grupos_elegiveis:

                for ap in (
                        grupo.get("apontamentos")
                        or []
                ):
                    ap.resolvido = True
                    db.add(ap)

                    ids_processados.append(
                        int(ap.id)
                    )

        db.flush()

    return {
        "ids_processados":
            ids_processados,

        "grupos_processados":
            len(grupos_elegiveis),

        "f010_inseridos":
            total_f010,

        "f100_inseridos":
            total_f100,

        "skips":
            skips,

        "erros":
            erros,
    }



def _aplicar_corretiva_frete_v2(
    db: Session,
    *,
    apontamento: EfdApontamento,
    meta: Dict[str, Any],
    cache: dict | None = None,
) -> Dict[str, Any]:
    """
    Aplica a corretiva V2 para contratos de frete ausentes no F100.

    Cenário atualmente suportado:

    - 0140 já existe;
    - 0150 já existe;
    - F010 já existe;
    - F100 do contrato está ausente.

    Cenários que exigem criação de 0140, 0150 ou F010
    serão tratados posteriormente.
    """

    versao_id = int(apontamento.versao_id)

    criar_0140 = bool(meta.get("criar_0140"))
    criar_0150 = bool(meta.get("criar_0150"))
    criar_f010 = bool(meta.get("criar_f010"))
    criar_f100 = bool(meta.get("criar_f100"))

    # ------------------------------------------------------------
    # Validação do cenário atualmente suportado
    # ------------------------------------------------------------
    if criar_0140 or criar_f010:
        return {
            "ok": False,
            "status": "skip",
            "msg": (
                "Corretiva de frete ainda não suporta criação "
                "de 0140, 0150 ou F010."
            ),
        }

    if not criar_f100:
        return {
            "ok": False,
            "status": "skip",
            "msg": "Apontamento não requer criação de F100.",
        }

    # ------------------------------------------------------------
    # F010 diagnosticado
    # ------------------------------------------------------------
    estabelecimento_f010 = meta.get("estabelecimento_f010") or {}

    registro_id_f010 = estabelecimento_f010.get("registro_id_f010")
    linha_f010 = estabelecimento_f010.get("linha_inicio")

    if not registro_id_f010 or linha_f010 is None:
        return {
            "ok": False,
            "status": "erro",
            "msg": (
                "F010 existente sem registro_id ou linha_inicio "
                "para inserção do F100."
            ),
        }

    # ------------------------------------------------------------
    # Garantir participante 0150
    # ------------------------------------------------------------

    estabelecimento_0140 = (
            meta.get("estabelecimento_0140")
            or {}
    )

    registro_id_0140 = (
        estabelecimento_0140.get(
            "registro_id_0140"
        )
    )

    linha_inicio_0140 = (
        estabelecimento_0140.get(
            "linha_inicio"
        )
    )

    linha_fim_0140 = (
        estabelecimento_0140.get(
            "linha_fim"
        )
    )

    if not registro_id_0140:
        return {
            "ok": False,
            "status": "erro",
            "msg": (
                "0140 existente sem registro_id_0140 "
                "para garantir participante."
            ),
        }

    # ------------------------------------------------------------
    # Dados do contratado vindos do contrato
    # ------------------------------------------------------------

    contrato = meta.get("contrato") or {}

    contratado = (
            contrato.get("contratado")
            or {}
    )

    documento_contratado = (
        contratado.get("documento")
    )

    nome_contratado = (
        contratado.get("nome")
    )

    tipo_pessoa = (
        meta.get("tipo_pessoa")
    )

    if not documento_contratado:
        return {
            "ok": False,
            "status": "erro",
            "msg": (
                "Contrato de frete sem documento "
                "do contratado."
            ),
        }

    # ------------------------------------------------------------
    # Converte o contexto armazenado no apontamento para
    # o formato esperado pelas funções de mestres de frete.
    # ------------------------------------------------------------

    contexto_0140 = {
        "existe": bool(
            estabelecimento_0140.get("existe")
        ),

        "registro_id": int(
            registro_id_0140
        ),

        "linha_inicio": int(
            linha_inicio_0140 or 0
        ),

        "linha_fim": int(
            linha_fim_0140 or 0
        ),

        "cod_est": (
            estabelecimento_0140.get(
                "cod_est"
            )
        ),

        "cnpj": (
            estabelecimento_0140.get(
                "cnpj"
            )
        ),
    }

    # ------------------------------------------------------------
    # Garante que o 0150 exista no estabelecimento.
    #
    # Pode acontecer:
    #
    # 1. já existe no 0140;
    # 2. existe em outro 0140 e será reutilizado;
    # 3. não existe na versão e será criado.
    # ------------------------------------------------------------

    resultado_participante = (
        garantir_0150_frete(
            db,

            versao_id=versao_id,

            contexto_0140=contexto_0140,

            documento=documento_contratado,

            nome=nome_contratado,

            tipo_pessoa=tipo_pessoa,

            ie=contratado.get("ie"),

            cod_mun=contratado.get(
                "municipio"
            ),

            logradouro=contratado.get(
                "logradouro"
            ),

            numero=contratado.get(
                "numero"
            ),

            complemento=contratado.get(
                "complemento"
            ),

            bairro=contratado.get(
                "bairro"
            ),

            apontamento_id=int(
                apontamento.id
            ),
        )
    )

    cod_part = (
        resultado_participante.get(
            "cod_part"
        )
    )

    if not cod_part:
        return {
            "ok": False,
            "status": "erro",
            "msg": (
                "Não foi possível resolver COD_PART "
                "para o contrato de frete."
            ),
        }

    # ------------------------------------------------------------
    # Dados do contrato
    # ------------------------------------------------------------

    frete = contrato.get("frete") or {}
    enq = meta.get("enquadramento") or {}

    numero_f100 = (
        meta.get("numero_f100")
        or contrato.get("numero_f100")
    )

    valor_frete = frete.get("valor_frete")
    data_frete = frete.get("data")

    # ------------------------------------------------------------
    # Enquadramento fiscal
    # ------------------------------------------------------------
    cst_pis = (
        meta.get("cst_pis_destino")
        or enq.get("cst_pis_destino")
    )

    cst_cofins = (
        meta.get("cst_cofins_destino")
        or enq.get("cst_cofins_destino")
    )

    aliq_pis = (
        enq.get("aliq_pis")
        or meta.get("aliq_pis")
    )

    aliq_cofins = (
        enq.get("aliq_cofins")
        or meta.get("aliq_cofins")
    )

    nat_bc_cred = (
        enq.get("nat_bc_cred")
        or enq.get("base_credito_codigo")
        or meta.get("nat_bc_cred")
    )

    cod_cred = (
        meta.get("cod_cred")
        or meta.get("tipo_credito_codigo")
        or meta.get("tipo_credito")
        or enq.get("cod_cred")
        or enq.get("tipo_credito_codigo")
        or enq.get("tipo_credito")
    )

    cod_cta = meta.get("cod_cta")

    # ------------------------------------------------------------
    # Dados necessários para montagem do F100
    # ------------------------------------------------------------
    frete_para_insercao = {
        "numero_f100": str(numero_f100 or "").strip(),
        "cod_part": str(cod_part or "").strip(),
        "data": data_frete,
        "valor_frete": valor_frete,
        "cst_pis": cst_pis,
        "cst_cofins": cst_cofins,
        "aliq_pis": aliq_pis,
        "aliq_cofins": aliq_cofins,
        "nat_bc_cred": nat_bc_cred,
        "cod_cred": cod_cred,
        "cod_cta": cod_cta,
        "periodo": meta.get("periodo"),
    }

    # ------------------------------------------------------------
    # Criar revisão INSERT do F100
    # ------------------------------------------------------------
    resultado_insercao = inserir_f100s_do_f010_encadeados(
        db,
        versao_origem_id=versao_id,
        fretes=[frete_para_insercao],
        registro_id_f010=int(registro_id_f010),
        linha_f010=int(linha_f010),
        apontamento_id=int(apontamento.id),
        motivo_codigo="CORRETIVA_F100_FRETE",
    )

    total_inseridos = int(
        resultado_insercao.get("total_inseridos") or 0
    )

    if total_inseridos <= 0:
        return {
            "ok": False,
            "status": "erro",
            "msg": "Nenhum F100 foi inserido pela corretiva de frete.",
        }

    # ------------------------------------------------------------
    # Resultado
    # ------------------------------------------------------------
    return {
        "ok": True,
        "status": "APLICADO",
        "tipo_corretiva": "INSERIR_F100_FRETE",

        "apontamento_id": int(apontamento.id),
        "versao_id": versao_id,

        "registro_id_f010": int(registro_id_f010),
        "linha_f010": int(linha_f010),

        "cod_part": str(cod_part),

        "0150_criado": bool(
            resultado_participante.get(
                "criado"
            )
        ),

        "0150_origem": (
            resultado_participante.get(
                "origem"
            )
        ),

        "revisao_0150_id": (
            resultado_participante.get(
                "revisao_id"
            )
        ),
        "numero_f100": str(numero_f100),
        "data_frete": data_frete,
        "valor_frete": valor_frete,

        "cod_cta": cod_cta,
        "cod_cred": cod_cred,
        "nat_bc_cred": nat_bc_cred,

        "cst_pis": cst_pis,
        "aliq_pis": aliq_pis,
        "cst_cofins": cst_cofins,
        "aliq_cofins": aliq_cofins,

        "total_inseridos": total_inseridos,
        "linha_fim_bloco": resultado_insercao.get("linha_fim_bloco"),
        "revisao_fim_bloco_id": resultado_insercao.get(
            "revisao_fim_bloco_id"
        ),
    }