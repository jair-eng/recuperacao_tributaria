
from typing import Any

from sqlalchemy.orm import Session
from app.db.models.ecd_conta_empresa import EcdContaEmpresa
from app.db.models.ecd_conta_natureza_esperada import EcdContaNaturezaEsperada
from app.domain.ecd.ecd_conta_classificador_service import classificar_conta_ecd


def _get_attr(obj: Any, nome: str, default: str = ""):
    return getattr(obj, nome, default) if obj is not None else default


def materializar_contas_ecd_i050(
    db: Session,
    *,
    empresa_id: int,
    arquivo_id: int | None = None,
    periodo: str | None = None,
    contas_i050: list[Any],
) -> int:
    total = 0

    for conta in contas_i050:
        cod_cta = str(_get_attr(conta, "cod_cta", "") or "").strip()
        if not cod_cta:
            continue

        nome_cta = str(_get_attr(conta, "nome_cta", "") or _get_attr(conta, "cta", "") or "").strip()
        classificacao = classificar_conta_ecd(
            nome_cta=nome_cta,
            cod_nat=str(_get_attr(conta, "cod_nat", "") or "").strip(),
            ind_cta=str(_get_attr(conta, "ind_cta", "") or "").strip(),
            nivel=str(_get_attr(conta, "nivel", "") or "").strip(),
        )

        existente = (
            db.query(EcdContaEmpresa)
            .filter(
                EcdContaEmpresa.empresa_id == empresa_id,
                EcdContaEmpresa.periodo == periodo,
                EcdContaEmpresa.cod_cta == cod_cta,
            )
            .first()
        )

        if existente is None:
            existente = EcdContaEmpresa(
                empresa_id=empresa_id,
                arquivo_id=arquivo_id,
                periodo=periodo,
                cod_cta=cod_cta,
            )
            db.add(existente)

        existente.arquivo_id = arquivo_id
        existente.linha = _get_attr(conta, "linha", None)
        existente.nome_cta = nome_cta
        existente.cod_nat = str(_get_attr(conta, "cod_nat", "") or "").strip()
        existente.ind_cta = str(_get_attr(conta, "ind_cta", "") or "").strip()
        existente.nivel = str(_get_attr(conta, "nivel", "") or "").strip()
        existente.cod_cta_sup = str(_get_attr(conta, "cod_cta_sup", "") or "").strip()

        existente.categoria_sugerida = classificacao["categoria_sugerida"]
        existente.grupo_conta_sugerido = classificacao["grupo_conta_sugerido"]
        existente.elegivel_credito_sugerido = classificacao["elegivel_credito_sugerido"]

        existente.origem = "ECD_I050"
        total += 1

        naturezas = classificacao.get("naturezas_esperadas_sugeridas") or []

        for natureza_codigo in naturezas:
            natureza_codigo = str(natureza_codigo or "").zfill(2)

            natureza_existente = (
                db.query(EcdContaNaturezaEsperada)
                .filter(
                    EcdContaNaturezaEsperada.ecd_conta_empresa_id == existente.id,
                    EcdContaNaturezaEsperada.natureza_codigo == natureza_codigo,
                )
                .first()
            )

            if natureza_existente is None:
                natureza_existente = EcdContaNaturezaEsperada(
                    empresa_id=empresa_id,
                    ecd_conta_empresa_id=existente.id,
                    cod_cta=cod_cta,
                    natureza_codigo=natureza_codigo,
                )
                db.add(natureza_existente)

            natureza_existente.categoria_sugerida = classificacao.get(
                "categoria_sugerida"
            )

            natureza_existente.grupo_conta_sugerido = classificacao.get(
                "grupo_conta_sugerido"
            )

            natureza_existente.fundamento_sugerido = classificacao.get(
                "fundamento_sugerido"
            )

            natureza_existente.origem = "CLASSIFICADOR_ECD"
            natureza_existente.ativo = True


    db.commit()
    return total