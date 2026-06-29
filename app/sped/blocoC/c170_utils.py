from __future__ import annotations
import re
from typing import Any, List, Tuple

from app.Legacy.fiscal.regras.helpers.elegibilidade_dominio import resolver_cst_credito_por_dominio
from app.Legacy.fiscal.settings_fiscais import CSTS_TRIB_NCUM
from dataclasses import dataclass
from app.sped.layouts.c170 import LAYOUT_C170
from app.utils.numbers import fmt_aliq_sped

_RE_CFOP = re.compile(r"^\d{4}$")
_RE_CST = re.compile(r"^\d{2}$")


# --- Funções Auxiliares de Cálculo e Formatação ---

CSTS_CREDITAVEIS = CSTS_TRIB_NCUM;

def _get_dados_list(dados: Any) -> List[Any]:
    if dados is None:
        return []
    if isinstance(dados, list):
        return dados
    # se vier dict {"dados":[...]}
    if isinstance(dados, dict) and "dados" in dados:
        return list(dados.get("dados") or [])
    return list(dados) if isinstance(dados, (tuple,)) else []


def get_cfop(dados: List[Any]) -> str:
    d = _get_dados_list(dados)
    return _norm_str(d[LAYOUT_C170.idx_cfop]) if len(d) > LAYOUT_C170.idx_cfop else ""


def get_cst_pis(dados: List[Any]) -> str:
    d = _get_dados_list(dados)
    return _norm_str(d[LAYOUT_C170.idx_cst_pis]).zfill(2) if len(d) > LAYOUT_C170.idx_cst_pis else ""


def get_cst_cofins(dados: List[Any]) -> str:
    d = _get_dados_list(dados)
    return _norm_str(d[LAYOUT_C170.idx_cst_cofins]).zfill(2) if len(d) > LAYOUT_C170.idx_cst_cofins else ""


def get_vl_item(dados: List[Any]) -> float:
    d = _get_dados_list(dados)
    return _parse_sped_float(d[LAYOUT_C170.idx_vl_item]) if len(d) > LAYOUT_C170.idx_vl_item else 0.0


def get_vl_bc_pis(dados: List[Any]) -> float:
    d = _get_dados_list(dados)
    return _parse_sped_float(d[LAYOUT_C170.idx_vl_bc_pis]) if len(d) > LAYOUT_C170.idx_vl_bc_pis else 0.0


def get_vl_pis(dados: List[Any]) -> float:
    d = _get_dados_list(dados)
    return _parse_sped_float(d[LAYOUT_C170.idx_vl_pis]) if len(d) > LAYOUT_C170.idx_vl_pis else 0.0


def get_vl_bc_cofins(dados: List[Any]) -> float:
    d = _get_dados_list(dados)
    return _parse_sped_float(d[LAYOUT_C170.idx_vl_bc_cofins]) if len(d) > LAYOUT_C170.idx_vl_bc_cofins else 0.0


def get_vl_cofins(dados: List[Any]) -> float:
    d = _get_dados_list(dados)
    return _parse_sped_float(d[LAYOUT_C170.idx_vl_cofins]) if len(d) > LAYOUT_C170.idx_vl_cofins else 0.0

def get_aliq_cofins(dados: List[Any]) -> float:
    d = _get_dados_list(dados)
    return _parse_sped_float(d[LAYOUT_C170.idx_aliq_cofins]) if len(d) > LAYOUT_C170.idx_aliq_cofins else 0.0

def get_aliq_pis(dados: List[Any]) -> float:
    d = _get_dados_list(dados)
    idx = getattr(LAYOUT_C170, "idx_aliq_pis", None)
    return _parse_sped_float(d[idx]) if (idx is not None and len(d) > idx) else 0.0


def get_aliq_cofins(dados: List[Any]) -> float:
    d = _get_dados_list(dados)
    idx = getattr(LAYOUT_C170, "idx_aliq_cofins", None)
    return _parse_sped_float(d[idx]) if (idx is not None and len(d) > idx) else 0.0



def is_cst_51(dados: List[Any]) -> bool:
    return (get_cst_pis(dados) == "51") or (get_cst_cofins(dados) == "51")

def _fmt_sped(valor: float) -> str:
    return f"{valor:.2f}".replace('.', ',')


def _parse_sped_float(valor: Any) -> float:
    if not valor: return 0.0
    try:
        s = str(valor).replace('.', '').replace(',', '.')
        return float(s)
    except:
        return 0.0


# --- Suas Defs Originais de Validação ---

def _ensure_len(campos: list[str], idx: int, nome: str) -> None:
    if len(campos) <= idx:
        raise ValueError(f"C170 inválido: faltam campos para {nome} (idx={idx}, len={len(campos)}).")


def _norm_str(v: Any) -> str:
    return "" if v is None else str(v).strip()


def validar_cfop(cfop: str) -> str:
    c = _norm_str(cfop)
    if not _RE_CFOP.match(c):
        raise ValueError("CFOP inválido: esperado 4 dígitos (ex: 1102).")
    return c


def validar_cst(cst: str) -> str:
    c = _norm_str(cst)
    if not _RE_CST.match(c):
        raise ValueError("CST inválido: esperado 2 dígitos (ex: 06, 50).")
    return c

def get_base_credito_c170(dados: List[Any]) -> float:
    d = _get_dados_list(dados)
    vl_item = get_vl_item(d)

    vl_desc = _parse_sped_float(d[LAYOUT_C170.idx_vl_desc]) if len(d) > LAYOUT_C170.idx_vl_desc else 0.0
    vl_icms = _parse_sped_float(d[LAYOUT_C170.idx_vl_icms]) if len(d) > LAYOUT_C170.idx_vl_icms else 0.0

    base = vl_item - vl_desc - vl_icms
    return max(base, 0.0)

# --- A Função Patch Atualizada com a Lógica de Cálculo ---

def patch_c170_campos(
    campos: list[Any],
    *,
    cfop=None,
    cst_pis=None,
    cst_cofins=None,
    dominio: str | None = None,
    contexto: str | None = None,
    fator_base_credito: float | None = None,
    aliq_pis: str | None = None,
    aliq_cofins: str | None = None,
) -> list[str]:

    novos = ["" if c is None else str(c).strip() for c in campos]

    offset = 1 if novos and novos[0] == "C170" else 0

    try:
        valor_item = float((novos[5 + offset] or "0").replace(',', '.'))
    except Exception:
        valor_item = 0.0

    try:
        valor_desc = float((novos[6 + offset] or "0").replace(',', '.'))
    except Exception:
        valor_desc = 0.0

    try:
        valor_icms = float((novos[13 + offset] or "0").replace(',', '.'))
    except Exception:
        valor_icms = 0.0

    base_credito = valor_item - valor_desc - valor_icms
    if base_credito < 0:
        base_credito = 0.0

    if fator_base_credito is not None:
        base_credito = base_credito * float(fator_base_credito)

    # se não vier CST explícito, tenta resolver por domínio
    if dominio and (not cst_pis or not cst_cofins):
        cst_pis_dom, cst_cofins_dom = resolver_cst_credito_por_dominio(
            dominio=dominio,
            contexto=contexto,
        )
        cst_pis = cst_pis or cst_pis_dom
        cst_cofins = cst_cofins or cst_cofins_dom

    aliq_pis_calc = fmt_aliq_sped(aliq_pis or "1,6500")
    aliq_cofins_calc = fmt_aliq_sped(aliq_cofins or "7,6000")

    aliq_pis_num = float(aliq_pis_calc.replace(",", "."))
    aliq_cofins_num = float(aliq_cofins_calc.replace(",", "."))

    csts_creditaveis_patch = set(CSTS_CREDITAVEIS or set())

    if contexto == "LC192":
        csts_creditaveis_patch.add("61")

    if cst_pis:
        novos[23 + offset] = str(cst_pis).zfill(2)
        if str(cst_pis).zfill(2) in csts_creditaveis_patch:
            novos[24 + offset] = f"{base_credito:.2f}".replace('.', ',')
            novos[25 + offset] = aliq_pis_calc
            novos[28 + offset] = f"{(base_credito * (aliq_pis_num / 100.0)):.2f}".replace('.', ',')

    if cst_cofins:
        novos[29 + offset] = str(cst_cofins).zfill(2)
        if str(cst_cofins).zfill(2) in csts_creditaveis_patch:
            novos[30 + offset] = f"{base_credito:.2f}".replace('.', ',')
            novos[31 + offset] = aliq_cofins_calc
            novos[34 + offset] = f"{(base_credito * (aliq_cofins_num / 100.0)):.2f}".replace('.', ',')

    if cfop:
        novos[9 + offset] = str(cfop)

    return novos

def _parse_linha_sped_to_reg_dados(linha: str) -> Tuple[str, List[Any]]:
    s = (linha or "").strip()
    if not s: raise ValueError("Linha SPED vazia")
    s = s.lstrip("\ufeff")
    anchor = "|C170|"
    p = s.find(anchor)
    if p >= 0: s = s[p:]
    if not s.startswith("|"):
        p2 = s.find("|")
        if p2 >= 0: s = s[p2:]
    s = s.strip()
    if not (s.startswith("|") and "|" in s[1:]):
        raise ValueError(f"Linha SPED inválida: {s[:80]}")
    parts = s.strip().strip("|").split("|")
    reg = parts[0].strip().upper()
    dados = parts[1:]
    return reg, dados

from typing import Any, List, Tuple


def _parse_linha_sped_to_reg_dados_preservando_finais_vazios(linha: str) -> Tuple[str, List[Any]]:
    s = (linha or "").strip()
    if not s:
        raise ValueError("Linha SPED vazia")

    s = s.lstrip("\ufeff")

    anchor = "|C170|"
    p = s.find(anchor)
    if p >= 0:
        s = s[p:]

    if not s.startswith("|"):
        p2 = s.find("|")
        if p2 >= 0:
            s = s[p2:]

    s = s.strip()
    if not (s.startswith("|") and "|" in s[1:]):
        raise ValueError(f"Linha SPED inválida: {s[:80]}")

    # remove só o primeiro pipe; preserva vazios do final
    corpo = s[1:]

    # se terminar com pipe, remove apenas UM pipe estrutural final
    # e preserva os pipes extras que representam campos vazios reais
    if corpo.endswith("|"):
        corpo = corpo[:-1]

    parts = corpo.split("|")
    reg = parts[0].strip().upper()
    dados = parts[1:]
    return reg, dados


@dataclass
class RegistroLike:
    id: int
    registro_id: int
    pai_id: int
    reg: str
    linha: int
    conteudo_json: dict


def linhas_para_rows_like(linhas) -> List[RegistroLike]:
    out: List[RegistroLike] = []
    for l in linhas:
        rid = int(getattr(l, "registro_id", 0) or 0)
        pid = int(getattr(l, "pai_id", 0) or 0)
        out.append(
            RegistroLike(
                id=rid,                         # ✅
                registro_id=rid,                 # ✅ (se existir no RegistroLike)
                pai_id=pid,                      # ✅ (se existir no RegistroLike)
                reg=str(l.reg),
                linha=int(l.linha),
                conteudo_json={"dados": list(l.dados or [])},
            )
        )
    return out


# -----------------------------
# Helpers
# -----------------------------
def _normalizar_linha_sped(linha: str) -> str:
    s = (linha or "").strip()
    if not s:
        return ""
    if not s.startswith("|"):
        s = "|" + s
    if not s.endswith("|"):
        s = s + "|"
    return s


def _validar_linha_c170(linha: str) -> str:
    """
    Valida e normaliza uma linha SPED C170 no formato pipe.
    Levanta ValueError se inválida.
    """
    s = _normalizar_linha_sped(linha)
    if not s:
        raise ValueError("linha_nova vazia após formatação")

    # precisa conter o token exato do registro
    if "|C170|" not in s:
        raise ValueError("linha_nova inválida: não contém |C170|")

    # validação mínima: deve ter ao menos reg + 1 campo
    partes = s.split("|")
    # Ex: ["", "C170", "campo1", ... , ""]
    if len(partes) < 4 or (partes[1] or "").strip() != "C170":
        raise ValueError("linha_nova inválida: estrutura C170 inesperada")

    return s
def consolidar_apontamentos_contrib_sem_c170(apontamentos: list):
    """
    Consolida apontamentos CONTRIB_SEM_C170_V1 por nota/C100,
    mantendo compatibilidade com a autocorreção.

    Resultado:
    - 1 apontamento por (registro_id_c100, linha_c100)
    - meta com nf_icms_item_ids daquela nota
    """

    outros = []
    grupo_c170 = []

    for ap in apontamentos:
        codigo = str(getattr(ap, "codigo", "") or "")
        if codigo == "CONTRIB_SEM_C170_V1":
            grupo_c170.append(ap)
        else:
            outros.append(ap)

    if not grupo_c170:
        return apontamentos

    grupos: dict[tuple[int, int], list] = {}

    for ap in grupo_c170:
        meta = getattr(ap, "meta", {}) or {}

        registro_id_c100 = int(
            meta.get("registro_id_c100")
            or meta.get("registro_id_ancora")
            or getattr(ap, "registro_id", 0)
            or 0
        )
        linha_c100 = int(
            meta.get("linha_c100")
            or meta.get("linha_ancora")
            or 0
        )

        # se não tiver base mínima, não consolida esse cara
        if not registro_id_c100 or not linha_c100:
            outros.append(ap)
            continue

        chave = (registro_id_c100, linha_c100)
        if chave not in grupos:
            grupos[chave] = []
        grupos[chave].append(ap)

    consolidados = []

    for (registro_id_c100, linha_c100), aps in grupos.items():
        base = aps[0]

        metas = [getattr(ap, "meta", {}) or {} for ap in aps]

        chaves_nfe = []
        numeros_nf = []
        nf_icms_item_ids = []
        numeros_item = []
        cod_items = []
        cfops = []
        ncms = []
        descricoes_item = []
        itens_contexto = []

        impacto_total = 0.0

        for m, ap in zip(metas, aps):
            chave_nfe = str(m.get("chave_nfe") or "").strip()
            if chave_nfe:
                chaves_nfe.append(chave_nfe)

            numero_nf = str(m.get("numero_nf") or "").strip()
            if numero_nf:
                numeros_nf.append(numero_nf)

            nf_icms_item_id = m.get("nf_icms_item_id")
            if nf_icms_item_id:
                try:
                    nf_icms_item_ids.append(int(nf_icms_item_id))
                except Exception:
                    pass

            num_item = str(m.get("num_item") or "").strip()
            if num_item:
                numeros_item.append(num_item)

            cod_item = str(m.get("cod_item") or "").strip()
            if cod_item:
                cod_items.append(cod_item)

            cfop = str(m.get("cfop") or "").strip()
            if cfop:
                cfops.append(cfop)

            ncm = str(m.get("ncm") or "").strip()
            if ncm:
                ncms.append(ncm)

            descricao_item = str(m.get("descricao_item") or "").strip()
            if descricao_item:
                descricoes_item.append(descricao_item)

            itens_contexto.append({
                "nf_icms_item_id": m.get("nf_icms_item_id"),
                "num_item": num_item,
                "cod_item": cod_item,
                "descricao_item": descricao_item,
                "cfop": cfop,
                "ncm": ncm,
                "valor_item_icms": m.get("valor_item_icms"),
                "valor_icms_icms": m.get("valor_icms_icms"),
                "valor_ipi_icms": m.get("valor_ipi_icms"),
                "chave_nfe": chave_nfe,
                "numero_nf": numero_nf,
            })

            try:
                impacto_total += float(getattr(ap, "impacto_financeiro", 0) or 0)
            except Exception:
                pass

        chaves_nfe_uniq = sorted(set(chaves_nfe))
        numeros_nf_uniq = sorted(set(numeros_nf))
        nf_icms_item_ids_uniq = sorted(set(nf_icms_item_ids))
        numeros_item_uniq = sorted(set(numeros_item))
        cod_items_uniq = sorted(set(cod_items))
        cfops_uniq = sorted(set(cfops))
        ncms_uniq = sorted(set(ncms))
        descricoes_item_uniq = sorted(set(descricoes_item))

        numero_ref = numeros_nf_uniq[0] if numeros_nf_uniq else "-"
        chave_ref = chaves_nfe_uniq[0] if chaves_nfe_uniq else "-"

        base.descricao = (
            f"Existem {len(aps)} itens presentes no ICMS/IPI e ausentes no C170 da "
            f"EFD Contribuições para a NF-e {chave_ref} | número {numero_ref}."
        )

        meta_base = getattr(base, "meta", {}) or {}
        base.meta = {
            **meta_base,
            "registro_id_c100": int(registro_id_c100),
            "linha_c100": int(linha_c100),
            "nf_icms_item_ids": nf_icms_item_ids_uniq,
            "qtd_itens": len(aps),
            "qtd_notas": len(chaves_nfe_uniq) if chaves_nfe_uniq else 1,
            "chaves_nfe": chaves_nfe_uniq,
            "numeros_nf": numeros_nf_uniq,
            "numeros_item": numeros_item_uniq,
            "cod_items": cod_items_uniq,
            "cfops": cfops_uniq,
            "ncms": ncms_uniq,
            "descricoes_item": descricoes_item_uniq,
            "itens_contexto": itens_contexto,
            "agrupado": True,
        }

        base.impacto_financeiro = impacto_total
        consolidados.append(base)

    return outros + consolidados