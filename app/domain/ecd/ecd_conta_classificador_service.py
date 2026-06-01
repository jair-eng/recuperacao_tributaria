from sqlalchemy import text
from app.utils.strings import norm_str, match_palavras


def classificar_conta_ecd(
    *,
    db,
    nome_cta: str,
    cod_nat: str = "",
    ind_cta: str = "",
    nivel: str = "",
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
              AND (cod_nat IS NULL OR cod_nat = '' OR cod_nat = :cod_nat)
            ORDER BY prioridade ASC, categoria ASC, natureza_codigo ASC
        """),
        {"cod_nat": cod_nat},
    ).mappings().all()

    matches = []

    for row in rows:
        if match_palavras(n, row.get("palavras_chave")):
            matches.append(row)

    if not matches:
        return resultado

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