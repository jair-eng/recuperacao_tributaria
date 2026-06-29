from app.domain.fiscal.cenarios.cenario_posto_cred_normal import cenario_posto_credito_normal
from app.domain.fiscal.cenarios.cenario_lc192 import cenario_lc192
from app.domain.fiscal.cenarios.cenario_cafe import cenario_cafe
from app.domain.fiscal.cenarios.cenario_insumo_transportadora import cenario_insumo_transportadora
from app.domain.fiscal.cenarios.cenario_insumo_cafe import cenario_insumo_cafe
from app.domain.fiscal.cenarios.cenario_insumo_revenda_gas import cenario_insumo_revenda_gas
from app.domain.fiscal.cenarios.cenario_ativo_imobilizado import cenario_ativo_imobilizado
import logging

logger = logging.getLogger(__name__)


CENARIOS_FISCAIS = [
    cenario_posto_credito_normal,
    cenario_insumo_cafe,
    cenario_insumo_revenda_gas,
    cenario_insumo_transportadora,
    cenario_cafe,
    cenario_lc192,
    cenario_ativo_imobilizado,
]


def avaliar_cenarios(meta, classificacao):
    for fn in CENARIOS_FISCAIS:
        nome = getattr(fn, "__name__", str(fn))
        logger.warning(
            "## [DEBUG_TEMP_AVALIAR_CENARIOS_IN] dominio=%s status=%s tipo_norm=%s cfop=%s ncm=%s produto=%s operacao=%s ##",
            meta.get("dominio"),
            meta.get("status_cruzamento"),
            meta.get("tipo_normalizacao"),
            meta.get("cfop"),
            meta.get("ncm"),
            (classificacao or {}).get("produto"),
            (classificacao or {}).get("operacao"),
        )
        try:
            cenario = fn(meta, classificacao)


            if cenario and cenario.get("ativo"):

                return cenario

        except Exception as e:
            print(
                "[AVALIAR_CENARIO][ERRO]",
                "fn=", nome,
                "cod_item=", meta.get("cod_item"),
                "erro=", repr(e),
                flush=True,
            )

    return None