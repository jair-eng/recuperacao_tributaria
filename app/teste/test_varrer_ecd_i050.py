# app/teste/test_varrer_ecd_i050.py

from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class ContaECD:
    linha: int
    dt_alt: str
    cod_nat: str
    ind_cta: str
    nivel: str
    cod_cta: str
    cod_cta_sup: str
    nome_cta: str


def ler_linhas_sped(path: str) -> List[str]:
    return Path(path).read_text(encoding="latin-1").splitlines()


def parse_i050(linha_txt: str, num_linha: int) -> ContaECD:
    campos = linha_txt.strip().split("|")

    return ContaECD(
        linha=num_linha,
        dt_alt=campos[2] if len(campos) > 2 else "",
        cod_nat=campos[3] if len(campos) > 3 else "",
        ind_cta=campos[4] if len(campos) > 4 else "",
        nivel=campos[5] if len(campos) > 5 else "",
        cod_cta=campos[6] if len(campos) > 6 else "",
        cod_cta_sup=campos[7] if len(campos) > 7 else "",
        nome_cta=campos[8] if len(campos) > 8 else "",
    )


def varrer_i050(path_ecd: str) -> list[ContaECD]:
    contas = []

    for i, linha in enumerate(ler_linhas_sped(path_ecd), start=1):
        if linha.startswith("|I050|"):
            contas.append(parse_i050(linha, i))

    return contas


def classificar_conta_teste(nome: str) -> str:
    n = nome.upper()

    if "COMBUST" in n or "LUBRIFIC" in n:
        return "CombustiveisLubrificantes"

    if "ENERGIA" in n:
        return "EnergiaEletricaOperacional"

    if "FRETE" in n or "CARRETO" in n:
        return "SubcontratacaoFrete"

    if "PEDAG" in n or "ESTACION" in n:
        return "Pedagios"

    if "SEGURO" in n:
        return "SegurosOperacionais"

    if "DEPREC" in n or "AMORT" in n:
        return "DepreciacaoFrota"

    if "PECA" in n or "PNEU" in n or "MANUT" in n:
        return "PecasManutencaoFrota"



    if "MERCADOR" in n:
        if "VENDA" in n or "RECEITA" in n:
            return "ReceitaVendaMercadorias"
        if "REVENDA" in n:
            return "EstoqueRevenda"
        return "MercadoriasInsumoConsumo"
    return "NaoClassificado"


if __name__ == "__main__":
    path_ecd = r"C:\Users\jcbn1\Downloads\teste\ecd_teste.txt"

    contas = varrer_i050(path_ecd)

    print("TOTAL CONTAS I050:", len(contas))
    print("=" * 120)

    for c in contas:
        categoria = classificar_conta_teste(c.nome_cta)

        print(
            f"linha={c.linha} | "
            f"cod_cta={c.cod_cta} | "
            f"nivel={c.nivel} | "
            f"nat={c.cod_nat} | "
            f"ind_cta={c.ind_cta} | "
            f"sup={c.cod_cta_sup} | "
            f"nome={c.nome_cta} | "
            f"categoria={categoria}"
        )