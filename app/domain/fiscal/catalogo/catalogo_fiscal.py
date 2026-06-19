from __future__ import annotations


from dataclasses import dataclass
from typing import Dict, Set

from app.utils.strings import norm_code, only_digits


# -------------------------------------------------
# Utils internos
# -------------------------------------------------

def _is_range_token(tok: str) -> bool:
    return "-" in tok and tok.count("-") == 1


def _match_token(token: str, value: str) -> bool:
    """
    token: item do catálogo (ex: "2202*", "22021000", "1001-1008")
    value: valor a testar (ex: "22021000", "2202.10.00")
    """

    token = norm_code(token)
    if not token:
        return False

    # Prefixo (2202*)
    if token.endswith("*"):
        pref = only_digits(token[:-1])
        val = only_digits(value)
        return bool(pref) and val.startswith(pref)

    # Faixa (1001-1008)
    if _is_range_token(token):
        a, b = token.split("-", 1)
        a = only_digits(a)
        b = only_digits(b)
        val = only_digits(value)

        if not (a and b and val):
            return False

        n = max(len(a), len(b), len(val))
        a = a.zfill(n)
        b = b.zfill(n)
        val = val.zfill(n)

        return a <= val <= b

    # Match exato por dígitos
    return only_digits(token) == only_digits(value)


# -------------------------------------------------
# Catálogo Fiscal
# -------------------------------------------------

@dataclass(frozen=True)
class CatalogoFiscal:
    """
    slug -> set(codigos)

    Exemplos de códigos:
      2202*
      22021000
      1001-1008
    """
    grupos: Dict[str, Set[str]]

    def grupos_match(
            self,
            value: str,
            *,
            prefixo: str | None = None,
    ) -> Set[str]:

        out = set()

        for slug in self.grupos.keys():

            if prefixo and not norm_code(slug).startswith(norm_code(prefixo)):
                continue

            if self.match(slug, value):
                out.add(slug)

        return out

    # Compat dict-like
    def get(self, slug: str, default=None):
        return self.grupos.get(slug, default)

    def keys(self):
        return self.grupos.keys()

    def items(self):
        return self.grupos.items()

    def __contains__(self, slug: str) -> bool:
        return slug in self.grupos

    def __getitem__(self, slug: str) -> Set[str]:
        return self.grupos[slug]

    # API própria
    def codigos(self, slug: str) -> Set[str]:
        return set(self.grupos.get(slug, set()) or set())

    def match(self, slug: str, value: str) -> bool:
        v = (value or "").strip()
        if not v:
            return False

        itens = self.grupos.get(slug) or set()
        for tok in itens:
            if _match_token(tok, v):
                return True
        return False

    # match por descricao
    def desc_match(self, slug: str, texto: str) -> bool:
        v = norm_code(texto)
        if not v:
            return False

        itens = self.grupos.get(slug) or set()

        for tok in itens:
            t = norm_code(tok)
            if not t:
                continue

            if len(t) < 4:
                continue

            if t in v:
                return True

        return False

    def grupos_cfop(self, cfop: str) -> Set[str]:
        return self.grupos_match(cfop, prefixo="CFOP_")


    def grupos_cst_pis(self, cst: str) -> Set[str]:
        return self.grupos_match(cst, prefixo="CST_PIS_")


    def grupos_cst_cofins(self, cst: str) -> Set[str]:
        return self.grupos_match(cst, prefixo="CST_COFINS_")

    def grupos_ncm(self, ncm: str) -> Set[str]:
        out = set()

        out |= self.grupos_match(ncm, prefixo="NCM_")
        out |= self.grupos_match(ncm, prefixo="AUTO_NCM_")
        out |= self.grupos_match(ncm, prefixo="ATIVO_IMOBILIZADO_")

        return out

    # Conveniências
    def ncm_match(self, slug: str, ncm: str) -> bool:
        return self.match(slug, ncm)

    def cfop_match(self, slug: str, cfop: str) -> bool:
        return self.match(slug, cfop)

    def cst_match(self, slug: str, cst: str) -> bool:
        return self.match(slug, cst)

    # Compat com código legado
    def match_codigo(self, slug: str, valor: str) -> bool:
        return self.match(slug, valor)
