# app/teste/test_gap_ecd_x_efd_natureza.py

from collections import defaultdict

from app.db.session import SessionLocal
from app.db.models.ecd_conta_natureza_esperada import EcdContaNaturezaEsperada
from app.db.models.ecd_conta_empresa import EcdContaEmpresa
from app.db.models.efd_registro import EfdRegistro


def extrair_dados(reg):
    if reg.conteudo_json:
        return reg.conteudo_json.get("dados") or []
    return []


def somar_base_efd_por_natureza(db, versao_id: int):
    """
    Primeiro teste simples:
    busca M105 e M505 e soma campo de base por natureza.
    """

    totais = defaultdict(float)

    registros = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == versao_id,
            EfdRegistro.reg.in_(["M105", "M505"]),
        )
        .all()
    )

    for r in registros:
        dados = extrair_dados(r)

        if not dados:
            continue

        # M105/M505:
        # campo 02 = NAT_BC_CRED
        # campo 04/05 costumam carregar base, dependendo do layout usado
        natureza = str(dados[0] if len(dados) > 0 else "").zfill(2)

        base = "0"
        for idx in [ 4, 2]:
            if len(dados) > idx and dados[idx]:
                base = dados[idx]
                break

        base = (
            str(base)
            .replace(".", "")
            .replace(",", ".")
        )


        try:
            totais[natureza] += float(base)
        except ValueError:
            pass

    return dict(totais)


def buscar_naturezas_esperadas_ecd(db, empresa_id: int):
    rows = (
        db.query(EcdContaNaturezaEsperada, EcdContaEmpresa)
        .join(EcdContaEmpresa, EcdContaEmpresa.id == EcdContaNaturezaEsperada.ecd_conta_empresa_id)
        .filter(
            EcdContaNaturezaEsperada.empresa_id == empresa_id,
            EcdContaNaturezaEsperada.ativo == 1,
        )
        .all()
    )

    esperado = defaultdict(list)

    for n, c in rows:
        esperado[n.natureza_codigo].append({
            "cod_cta": c.cod_cta,
            "nome_cta": c.nome_cta,
            "categoria": n.categoria_sugerida,
            "fundamento": n.fundamento_sugerido,
        })

    return dict(esperado)


if __name__ == "__main__":
    EMPRESA_ID = 1
    VERSAO_ID = 4  # ajuste aqui para a versão EFD Contribuições

    db = SessionLocal()

    regs = (
        db.query(EfdRegistro.reg, EfdRegistro.conteudo_json)
        .filter(
            EfdRegistro.versao_id == VERSAO_ID,
            EfdRegistro.reg.in_(["M105"]),
        )
        .limit(20)
        .all()
    )

    print("REGS BLOCO M:", len(regs))

    for reg, cj in regs:
        print(reg, cj)

    try:
        esperado_ecd = buscar_naturezas_esperadas_ecd(db, EMPRESA_ID)
        declarado_efd = somar_base_efd_por_natureza(db, VERSAO_ID)
        print()
        print("DECLARADO EFD POR NATUREZA:")
        for nat, valor in sorted(declarado_efd.items()):
            print(f"  {nat}: {valor:,.2f}")
        print("=" * 100)
        print("GAP ECD x EFD POR NATUREZA")
        print("=" * 100)

        for natureza in sorted(esperado_ecd.keys()):
            base_efd = declarado_efd.get(natureza, 0)

            print()
            print(f"NATUREZA {natureza}")
            print(f"Base declarada EFD: {base_efd:,.2f}")

            print("Contas ECD esperadas:")
            for conta in esperado_ecd[natureza]:
                print(
                    f"  - {conta['cod_cta']} | "
                    f"{conta['nome_cta']} | "
                    f"{conta['categoria']} | "
                    f"{conta['fundamento']}"
                )

    finally:
        db.close()