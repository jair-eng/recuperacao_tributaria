from sqlalchemy import text

from app.utils.ecd_gap_utils import eh_categoria_frete
from app.utils.strings import norm_str, match_palavras


def classificar_conta_ecd(
    *,
    db,
    nome_cta: str,
    cod_nat: str = "",
    ind_cta: str = "",
    nivel: str = "",
    participante_tipo: str | None = None,
    nat_bc_cred: str | None = None,
) -> dict:
    n = norm_str(nome_cta or "").upper()
    cod_nat = str(cod_nat or "").strip()

    resultado = {
        "categoria_sugerida": "NaoClassificado",
        "grupo_conta_sugerido": "NAO_CLASSIFICADO",
        "elegivel_credito_sugerido": False,
        "naturezas_esperadas_sugeridas": [],
        "fundamento_sugerido": None,
        "confianca_sugerida": 0,
        "origem_classificacao": "NAO_CLASSIFICADO",
    }

    if not db:
        return resultado

    rows = db.execute(
        text("""
            SELECT
                categoria,
                grupo_conta,
                cod_nat,
                palavras_chave,
                natureza_codigo,
                fundamento,
                prioridade,
                confianca
            FROM ecd_categoria_natureza_esperada
            WHERE ativo = 1
            AND (
                :cod_nat = ''
                OR cod_nat IS NULL
                OR cod_nat = ''
                OR cod_nat = :cod_nat
            )
            ORDER BY prioridade ASC, categoria ASC, natureza_codigo ASC
             """),
            {"cod_nat": cod_nat},
    ).mappings().all()

    nat_real = str(nat_bc_cred or "").strip().zfill(2)

    if nat_real and nat_real != "00":
        rows_nat = [
            row for row in rows
            if str(row.get("natureza_codigo") or "").strip().zfill(2) == nat_real
        ]

        if rows_nat:
            rows = rows_nat

    matches = []

    for row in rows:
        if match_palavras(n, row.get("palavras_chave")):
            matches.append(row)

    if not matches:
        return resultado

    participante_tipo_norm = norm_str(participante_tipo)
    if participante_tipo_norm == "PF":
        filtrados_pf = [
            m for m in matches
            if eh_categoria_frete(m.get("categoria"))
               and "FISICA" in norm_str(m.get("categoria"))
        ]
        if filtrados_pf:
            matches = filtrados_pf

    if participante_tipo_norm == "PJ":
        filtrados_pj = [
            m for m in matches
            if eh_categoria_frete(m.get("categoria"))
               and (
                       "LUCROREAL" in norm_str(m.get("categoria"))
                       or "PJ" in norm_str(m.get("categoria"))
                       or "PRESUMIDO" in norm_str(m.get("categoria"))
               )
        ]
        if filtrados_pj:
            matches = filtrados_pj
    matches = sorted(
        matches,
        key=lambda m: (
            str(m.get("natureza_codigo") or "").zfill(2) == str(nat_bc_cred or "").zfill(2),
            int(m.get("prioridade") or 0),
        ),
        reverse=True,
    )
    primeira = matches[0]
    categoria = primeira["categoria"]

    naturezas = []
    for row in matches:
        if row["categoria"] != categoria:
            continue

        nat = str(row.get("natureza_codigo") or "").strip()
        if nat and nat not in naturezas:
            naturezas.append(nat)

    resultado.update(
        categoria_sugerida=categoria,
        grupo_conta_sugerido=primeira.get("grupo_conta") or "NAO_CLASSIFICADO",
        elegivel_credito_sugerido=bool(naturezas),
        naturezas_esperadas_sugeridas=naturezas,
        fundamento_sugerido=primeira.get("fundamento"),
        confianca_sugerida=int(primeira.get("confianca") or 70),
        origem_classificacao="BANCO",
    )

    return resultado

def classificar_texto_por_natureza_esperada(
    *,
    db,
    texto: str,
    cod_nat: str = "",
    participante_tipo: str | None = None,
    nat_bc_cred: str | None = None,
) -> dict:
    r = classificar_conta_ecd(
        db=db,
        nome_cta=texto,
        cod_nat=cod_nat,
        participante_tipo=participante_tipo,
        nat_bc_cred=nat_bc_cred,
    )

    return {
        "categoria": r.get("categoria_sugerida"),
        "grupo": r.get("grupo_conta_sugerido"),
        "elegivel_credito": r.get("elegivel_credito_sugerido"),
        "naturezas_esperadas": r.get("naturezas_esperadas_sugeridas") or [],
        "fundamento": r.get("fundamento_sugerido"),
        "confianca": r.get("confianca_sugerida"),
        "origem_classificacao": r.get("origem_classificacao"),
    }