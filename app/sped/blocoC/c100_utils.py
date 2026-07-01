from __future__ import annotations

from typing import Optional, List, Any, Dict
from sqlalchemy.orm import Session
from decimal import Decimal, ROUND_HALF_UP
from app.db.models import NfIcmsItem
from app.db.models.efd_revisao import EfdRevisao
from app.db.models.efd_registro import EfdRegistro
from app.icms_ipi.icms_helpers import _only_digits, fmt_sped_num, _campo
from app.icms_ipi.icms_ipi_funcoes import _eh_c100
from app.legacy_service.versao_overlay_service import carregar_linhas_logicas_com_revisoes
from app.sped.formatter import formatar_linha


def salvar_revisao_c100_automatica(
    db: Session,
    *,
    versao_origem_id: int,
    motivo_codigo: str,
    c100_id: Optional[int] = None,
    reg_c100: Optional[EfdRegistro] = None,
    novos_dados: Optional[List[Any]] = None,
    linha_nova: Optional[str] = None,
    apontamento_id: Optional[int] = None,
    detalhe: Optional[Dict[str, Any]] = None,
) -> EfdRevisao:
    """
    Salva/atualiza uma revisão automática do C100 (REPLACE_LINE) para uma versão origem.

    Use assim (recomendado no seu fluxo):
      - você já tem campos_atualizados (novos_dados) vindo do patch_c100_totais_imposto
      - chama com c100_id/reg_c100 + novos_dados

    Alternativa:
      - se você já tem a linha física pronta, passe linha_nova.

    Regras:
      - grava como revisão PENDENTE (versao_revisada_id = NULL)
      - faz UPSERT por (registro_id, reg='C100', acao='REPLACE_LINE', versao_origem_id, versao_revisada_id IS NULL)
    """
    if reg_c100 is None:
        if not c100_id:
            raise ValueError("Informe c100_id ou reg_c100.")
        reg_c100 = db.get(EfdRegistro, int(c100_id))
        if not reg_c100:
            raise ValueError(f"C100 não encontrado: c100_id={c100_id}")

    # Se o chamador passou novos_dados, montamos a linha
    if linha_nova is None:
        if novos_dados is None:
            raise ValueError("Informe novos_dados ou linha_nova.")
        linha_nova = formatar_linha("C100", list(novos_dados)).strip()
    else:
        linha_nova = str(linha_nova).strip()

    payload = {
        "linha_referencia": int(getattr(reg_c100, "linha", 0) or 0),
        "linha_nova": linha_nova,
        "detalhe": detalhe or {"info": "Recalculo automático C100 via itens C170"},
    }

    # UPSERT (evita duplicar revisões)
    rev = (
        db.query(EfdRevisao)
        .filter(
            EfdRevisao.registro_id == int(reg_c100.id),
            EfdRevisao.reg == "C100",
            EfdRevisao.acao == "REPLACE_LINE",
            EfdRevisao.versao_origem_id == int(versao_origem_id),
            EfdRevisao.versao_revisada_id.is_(None),
        )
        .first()
    )

    if rev:
        rev.revisao_json = payload
        rev.motivo_codigo = str(motivo_codigo)
        if apontamento_id is not None:
            rev.apontamento_id = int(apontamento_id)
        db.flush()
        return rev

    rev = EfdRevisao(
        registro_id=int(reg_c100.id),
        reg="C100",
        acao="REPLACE_LINE",
        versao_origem_id=int(versao_origem_id),
        versao_revisada_id=None,
        revisao_json=payload,
        motivo_codigo=str(motivo_codigo),
        apontamento_id=int(apontamento_id) if apontamento_id is not None else None,
    )
    db.add(rev)
    db.flush()
    return rev

def _fmt_decimal_2(v) -> str:
    d = v if isinstance(v, Decimal) else Decimal(str(v or "0"))
    d = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(d).replace(".", ",")

def patch_c100_totais_imposto(
    campos: list[Any],
    total_pis: float,
    total_cofins: float
) -> list[str]:
    """
    Atualiza VL_PIS e VL_COFINS no C100
    Layout: campos SEM o REG (C100)
    Índices:
      24 -> VL_PIS
      25 -> VL_COFINS
      26 -> VL_PIS_ST
      27 -> VL_COFINS_ST
    """
    novos = ["" if c is None else str(c) for c in campos]

    if len(novos) < 28:
        novos.extend([""] * (28 - len(novos)))
    elif len(novos) > 28:
        novos = novos[:28]

    novos[24] = _fmt_decimal_2(total_pis)
    novos[25] = _fmt_decimal_2(total_cofins)

    # garante explicitamente os dois campos finais
    if not str(novos[26]).strip():
        novos[26] = "0"
    if not str(novos[27]).strip():
        novos[27] = "0"

    return novos

def recalcular_c990(linhas: list[str]) -> list[str]:
    """
    Recalcula QTD_LIN_C do C990.
    """

    qtd = 0
    idx_c990 = None

    for i, l in enumerate(linhas):
        if l.startswith("|C"):
            qtd += 1

        if l.startswith("|C990|"):
            idx_c990 = i

    if idx_c990 is not None:
        linhas[idx_c990] = f"|C990|{qtd}|"

    return linhas

def montar_linha_c100_de_icms(nf):
    campos = [
        "C100",
        "0",
        "1",
        "",
        "55",
        "00",
        nf.serie or "",
        nf.num_doc or "",
        nf.chave_nfe or "",
        nf.dt_doc.strftime("%d%m%Y") if nf.dt_doc else "",
        nf.dt_es.strftime("%d%m%Y") if getattr(nf, "dt_es", None) else (nf.dt_doc.strftime("%d%m%Y") if nf.dt_doc else ""),
        fmt_sped_num(nf.vl_doc),
        "0",
        "0",
        "0",
        fmt_sped_num(nf.vl_doc),
        "0",
        "0",
        "0",
        "0",
        fmt_sped_num(nf.vl_doc),
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
    ]


    return "|" + "|".join(campos) + "|"



def garantir_c010_e_ajustar_c001(linhas: list[str], cnpj_estab: str) -> list[str]:
    """
    Garante a estrutura mínima do bloco C:
    - Se houver C100/C170, C001 deve ser 0
    - Se houver C100 e não houver C010, insere C010 após C001
    """
    tem_c100 = any(l.startswith("|C100|") for l in linhas)
    idx_c001 = next((i for i, l in enumerate(linhas) if l.startswith("|C001|")), None)
    idx_c010 = next((i for i, l in enumerate(linhas) if l.startswith("|C010|")), None)

    if not tem_c100:
        return linhas

    # ajusta C001 para com movimento
    if idx_c001 is not None:
        linhas[idx_c001] = "|C001|0|"

    # insere C010 se faltar
    if idx_c001 is not None and idx_c010 is None:
        linha_c010 = f"|C010|{cnpj_estab}|"
        linhas.insert(idx_c001 + 1, linha_c010)

    return linhas

def garantir_estrutura_bloco_c(linhas: list[str]) -> list[str]:
    """
    Garante estrutura mínima válida do bloco C:
    - Se houver C100/C170, C001 deve ser |C001|0|
    - Se houver C100 e não houver C010, insere C010 após C001
    """
    tem_c100 = any(l.startswith("|C100|") for l in linhas)
    if not tem_c100:
        return linhas

    idx_c001 = next((i for i, l in enumerate(linhas) if l.startswith("|C001|")), None)
    idx_c010 = next((i for i, l in enumerate(linhas) if l.startswith("|C010|")), None)

    if idx_c001 is not None:
        linhas[idx_c001] = "|C001|0|"

    if idx_c001 is not None and idx_c010 is None:
        cnpj_estab = ""

        # tenta 0000 primeiro
        for l in linhas:
            if l.startswith("|0000|"):
                partes = l.strip("|").split("|")
                if len(partes) > 8:
                    cnpj_estab = str(partes[8] or "").strip()
                break

        # fallback no 0140
        if not cnpj_estab:
            for l in linhas:
                if l.startswith("|0140|"):
                    partes = l.strip("|").split("|")
                    if len(partes) > 1:
                        cnpj_estab = str(partes[1] or "").strip()
                    break

        linhas.insert(idx_c001 + 1, f"|C010|{cnpj_estab}|2|")

    return linhas
