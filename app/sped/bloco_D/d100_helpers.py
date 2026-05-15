
import re

from app.db.models import EfdRegistro
from app.sped.bloco_D.d100_dataclass import EvidenciasPrestadorD100
from app.sped.bloco_D.d100_utils import _to_float_br, _only_digits
import logging

logger = logging.getLogger(__name__)


_RE_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_RE_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_RE_PLACA = re.compile(r"\b[A-Z]{3}-?\d[A-Z0-9]\d{2}\b", re.IGNORECASE)
_RE_ANTT = re.compile(r"\bANTT[:\s-]*([0-9]{6,12})\b", re.IGNORECASE)

PF_KEYWORDS = [
    "MOTORISTA", "CONDUTOR", "CPF", "RG", "CNH", "LIB:", "CH:", "CARRETA", "PLACA", "UF:"
]

PJ_KEYWORDS = [
    "LTDA", "EIRELI", "ME", "MEI", "LOGISTICA", "TRANSPORTES", "TRANSPORTADORA"
]

AUTONOMO_KEYWORDS = [
    "TAC", "AUTONOMO", "MOTORISTA", "CARRETA", "PLACA", "ANTT"
]

SUBCONTRATACAO_KEYWORDS = [
    "SUBCONTRAT", "REDESPACHO", "TERCEIRO"
]


def obter_base_d100(meta: dict) -> float:
    vl_serv = _to_float_br(meta.get("vl_serv"))
    vl_doc = _to_float_br(meta.get("vl_doc"))

    return vl_serv or vl_doc or 0.0


def calcular_credito_presumido(base: float) -> dict:
    pis = round(base * 0.012375, 2)
    cofins = round(base * 0.057, 2)
    return {
        "pis": pis,
        "cofins": cofins,
        "total": round(pis + cofins, 2),
    }
def parece_nome_pessoa(txt: str) -> bool:
    # heurística simples:
    # duas palavras sem sufixo empresarial
    partes = txt.strip().split()

    if len(partes) >= 2 and len(partes) <= 4:
        if not any(k in txt for k in ["LTDA", "EIRELI", "S/A", "SA"]):
            return True

    return False

def parece_pj_texto(txt: str | None) -> bool:
    s = str(txt or "").upper()
    # 🔴 sinais fortes (confiáveis)
    sinais_fortes = [
        " LTDA",
        " EIRELI",
        " S/A",
        " SA ",
        " SOCIEDADE",    ]

    # 🟡 sinais médios (usar com cuidado)
    sinais_medios = [
        " TRANSPORTES",
        " LOGISTICA",
    ]
    if any(k in s for k in sinais_fortes):
        return True

    # só usa sinais médios se não tiver padrão de pessoa
    if any(k in s for k in sinais_medios) and not parece_nome_pessoa(s):
        return True
    return False

def extrair_cpf_texto(txt: str | None) -> list[str]:
    s = str(txt or "")
    return list(dict.fromkeys(_only_digits(m.group(0)) for m in _RE_CPF.finditer(s) if len(_only_digits(m.group(0))) == 11))


def extrair_cnpj_texto(txt: str | None) -> list[str]:
    s = str(txt or "")
    return list(dict.fromkeys(_only_digits(m.group(0)) for m in _RE_CNPJ.finditer(s) if len(_only_digits(m.group(0))) == 14))


def extrair_placas_texto(txt: str | None) -> list[str]:
    s = str(txt or "").upper()
    return list(dict.fromkeys(m.group(0).replace("-", "") for m in _RE_PLACA.finditer(s)))


def extrair_antt_texto(txt: str | None) -> list[str]:
    s = str(txt or "")
    return list(dict.fromkeys(m.group(1) for m in _RE_ANTT.finditer(s)))


def parece_transportador_autonomo(txt: str | None) -> bool:
    s = str(txt or "").upper()

    return any(k in s for k in [
        "CARRETA",
        "MOTORISTA",
        "PLACA",
        "ANTT",
        "UF:",
    ])

def qualificar_prestador_d100(meta: dict) -> dict:
    ev = _extrair_evidencias_prestador(meta)
    pf_eval = classificar_forca_evidencia_pf(ev)

    cnpj_empresa = _only_digits(
        meta.get("cnpj_empresa")
        or meta.get("empresa_cnpj")
        or ""
    )
    pj_eval = classificar_forca_evidencia_pj(ev, cnpj_empresa)

    cpfs = ev.get("cpfs") or []
    cnpjs = ev.get("cnpjs") or []
    textos = ev.get("textos") or []
    antts = ev.get("antts") or []

    cpf_principal = ev.get("cpf_principal")
    antt_principal = antts[0] if antts else None
    nome_prestador = ev.get("nome_prestador")

    cnpj_empresa_norm = _only_digits(
        meta.get("cnpj_empresa") or meta.get("empresa_cnpj") or ""
    )

    cnpjs_validos = [
        c for c in cnpjs
        if _only_digits(c) != cnpj_empresa_norm
    ]

    score_pf = int(pf_eval.get("score") or 0)
    score_pj = int(pj_eval.get("score") or 0)

    ha_pj_textual = any(parece_pj_texto(txt) for txt in textos)
    ha_pf_textual = any(parece_transportador_autonomo(txt) for txt in textos)

    def _base_payload() -> dict:
        return {
            "tipo": "INDETERMINADO",
            "evidencia": "nenhuma",
            "cpf": None,
            "cnpj": None,
            "nome": nome_prestador,
            "antt": antt_principal,
            "forca_evidencia_pf": pf_eval.get("classe"),
            "score_pf": score_pf,
            "forca_evidencia_pj": pj_eval.get("classe"),
            "score_pj": score_pj,
            "candidato_credito_presumido": False,
            "permite_credito_presumido": False,
            "tipo_credito": "NAO_CALCULADO",
            "status_motor": "NAO_CALCULADO",
            "exige_revisao_manual": True,
        }

    # 1) conflito explícito ou heurístico forte -> não automatiza
    if (cnpjs_validos and cpfs) or (cpfs and ha_pj_textual) or (score_pf >= 4 and score_pj >= 4):
        return {
            **_base_payload(),
            "tipo": "INDETERMINADO",
            "evidencia": "conflito_pf_pj",
            "cpf": cpf_principal,
            "cnpj": cnpjs_validos[0] if cnpjs_validos else None,
            "nome": nome_prestador,
            "antt": antt_principal,
            "tipo_credito": "PENDENTE_CLASSIFICACAO",
            "status_motor": "PENDENTE_REVISAO",
            "permite_credito_presumido": False,
            "candidato_credito_presumido": False,
            "exige_revisao_manual": True,
        }

    # 2) PJ com CNPJ explícito
    if cnpjs_validos:
        return {
            **_base_payload(),
            "tipo": "PJ",
            "evidencia": "cnpj_0460",
            "cpf": None,
            "cnpj": cnpjs_validos[0],
            "nome": nome_prestador,
            "antt": antt_principal,
            "tipo_credito": "PJ_DEPENDE_REGIME",
            "status_motor": "PENDENTE_REVISAO",
            "permite_credito_presumido": False,
            "candidato_credito_presumido": False,
            "exige_revisao_manual": True,
        }

    # 3) PJ heurístico
    if ha_pj_textual or score_pj >= 4:
        txt_pj = next((txt for txt in textos if parece_pj_texto(txt)), nome_prestador)
        return {
            **_base_payload(),
            "tipo": "PJ",
            "evidencia": "pj_heuristica",
            "cpf": None,
            "cnpj": None,
            "nome": txt_pj,
            "antt": antt_principal,
            "tipo_credito": "PJ_DEPENDE_REGIME",
            "status_motor": "PENDENTE_REVISAO",
            "permite_credito_presumido": False,
            "candidato_credito_presumido": False,
            "exige_revisao_manual": True,
        }

    # 4) PF explícito forte -> só aqui libera automático
    if cpfs and score_pf >= 7 and score_pj <= 0:
        return {
            **_base_payload(),
            "tipo": "PF",
            "evidencia": "cpf_0460",
            "cpf": cpf_principal,
            "cnpj": None,
            "nome": nome_prestador,
            "antt": antt_principal,
            "tipo_credito": "PRESUMIDO_PF",
            "status_motor": "CALCULADO",
            "permite_credito_presumido": True,
            "candidato_credito_presumido": True,
            "exige_revisao_manual": False,
            "base_legal": "PF_CTE_CREDITO_PRESUMIDO",
            "nivel_confianca": pf_eval.get("classe"),
        }

    # 5) PF heurístico -> candidato, sem autocorreção
    if ha_pf_textual or (cpfs and score_pf >= 4):
        txt_pf = next((txt for txt in textos if parece_transportador_autonomo(txt)), nome_prestador)
        return {
            **_base_payload(),
            "tipo": "PF",
            "evidencia": "pf_heuristica",
            "cpf": cpf_principal if cpfs else None,
            "cnpj": None,
            "nome": txt_pf,
            "antt": antt_principal,
            "tipo_credito": "PRESUMIDO_PF",
            "status_motor": "PENDENTE_REVISAO",
            "permite_credito_presumido": False,
            "candidato_credito_presumido": True,
            "exige_revisao_manual": True,
        }

    return _base_payload()

def resolver_ancora_transp(db, versao_id: int) -> tuple[int, str, int | None]:
    candidatos = ["M210", "M610", "F550", "F010", "0000"]

    for reg in candidatos:
        row = (
            db.query(EfdRegistro)
            .filter(EfdRegistro.versao_id == int(versao_id))
            .filter(EfdRegistro.reg == reg)
            .order_by(EfdRegistro.linha.asc(), EfdRegistro.id.asc())
            .first()
        )
        if row:
            return int(row.id), reg, getattr(row, "linha", None)

    return 0, "", None

def escolher_nome_prestador(textos: list[str]) -> str | None:
    for txt in textos:
        txt_up = txt.upper()

        if "ANTT" in txt_up:
            return txt.strip()

    for txt in textos:
        txt_up = txt.upper()

        if any(k in txt_up for k in ["LIB", "RG", "CH"]):
            return txt.strip()

    for txt in textos:
        txt_up = txt.upper()

        # heurística simples de nome (evita carreta/placa)
        if "-" in txt and not any(k in txt_up for k in ["CARRETA", "PLACA", "UF"]):
            return txt.strip()

    return None

def _extrair_evidencias_prestador(meta: dict) -> dict:
    evids = meta.get("evidencias_0460") or []
    """print(
        "[D100_PREST] RAW EVIDS",
        meta.get("num_doc"),
        meta.get("evidencias_0460"),
        flush=True,
    )"""

    if isinstance(evids, str):
        evids = [evids]

    cpfs: list[str] = []
    cpfs_fortes: list[str] = []
    cpfs_aux: list[str] = []
    cnpjs: list[str] = []
    antts: list[str] = []
    placas: list[str] = []
    textos: list[str] = []

    for txt in evids:
        txt = str(txt or "").strip()
        if not txt:
            continue

        txt_up = txt.upper()
        textos.append(txt)

        for cpf in extrair_cpf_texto(txt):
            if cpf not in cpfs:
                cpfs.append(cpf)

            if "LIB" in txt_up or "CH" in txt_up or "RG" in txt_up:
                if cpf not in cpfs_aux:
                    cpfs_aux.append(cpf)
            else:
                if cpf not in cpfs_fortes:
                    cpfs_fortes.append(cpf)

        for cnpj in extrair_cnpj_texto(txt):
            if cnpj not in cnpjs:
                cnpjs.append(cnpj)

        for antt in extrair_antt_texto(txt):
            if antt not in antts:
                antts.append(antt)

        for placa in extrair_placas_texto(txt):
            if placa not in placas:
                placas.append(placa)

    cpf_principal = cpfs_fortes[0] if cpfs_fortes else (cpfs[0] if cpfs else None)
    nome_prestador = escolher_nome_prestador(textos)

    return {
        "cpfs": cpfs,
        "cpfs_fortes": cpfs_fortes,
        "cpfs_aux": cpfs_aux,
        "cpf_principal": cpf_principal,
        "cnpjs": cnpjs,
        "antts": antts,
        "placas": placas,
        "textos": textos,
        "nome_prestador": nome_prestador,
    }

def classificar_forca_evidencia_pf(ev: dict) -> dict:
    """
    Classifica a força da evidência de PF com base no conteúdo do 0460.
    Não tenta afirmar papel exato — apenas mede confiança.
    """

    score = 0

    textos = ev.get("textos") or []
    cpfs = ev.get("cpfs") or []
    antts = ev.get("antts") or []

    # -------------------------
    # sinais positivos
    # -------------------------
    if cpfs:
        score += 4

    if antts:
        score += 3

    for txt in textos:
        txt_up = txt.upper()

        if any(k in txt_up for k in ["CARRETA", "PLACA", "UF"]):
            score += 2
            break

    # tentativa simples de nome de pessoa (heurística leve)
    for txt in textos:
        if "-" in txt and not any(k in txt.upper() for k in ["LTDA", "ME", "TRANSP"]):
            score += 2
            break

    # -------------------------
    # penalidades
    # -------------------------
    for txt in textos:
        txt_up = txt.upper()

        if any(k in txt_up for k in ["LTDA", "EIRELI", "S/A", "SA", "ME", "EPP"]):
            score -= 6

    for txt in textos:
        txt_up = txt.upper()

        if "LIB" in txt_up:
            score -= 1
        if "RG" in txt_up:
            score -= 1
        if "CH" in txt_up:
            score -= 1

    # -------------------------
    # classificação final
    # -------------------------
    if score >= 7:
        classe = "PF_EVIDENCIA_FORTE"
    elif score >= 4:
        classe = "PF_EVIDENCIA_MEDIA"
    elif score >= 1:
        classe = "PF_EVIDENCIA_FRACA"
    else:
        classe = "SEM_EVIDENCIA_PF"

    return {
        "classe": classe,
        "score": score,
    }

def classificar_forca_evidencia_pj(ev: dict, cnpj_empresa: str | None = None) -> dict:
    score = 0
    evidencias: list[str] = []

    textos_raw = ev.get("textos") or []
    cnpjs_raw = ev.get("cnpjs") or []

    textos = [str(t).strip().upper() for t in textos_raw if str(t).strip()]
    cnpjs = list({_only_digits(c) for c in cnpjs_raw if _only_digits(c)})
    cnpj_empresa_norm = _only_digits(cnpj_empresa)

    # -------------------------
    # sinais positivos
    # -------------------------
    if cnpjs:
        score += 5
        evidencias.append("cnpj_detectado")

    padroes_empresariais = [
        r"\bLTDA\b",
        r"\bEIRELI\b",
        r"\bMEI\b",
        r"\bEPP\b",
        r"\bS\/A\b",
        r"\bSA\b",
        r"\bEMPRESA INDIVIDUAL\b",
    ]

    if any(any(re.search(p, txt) for p in padroes_empresariais) for txt in textos):
        score += 2
        evidencias.append("sufixo_empresarial")

    padroes_setoriais = [
        r"\bTRANSPORTES\b",
        r"\bLOGISTICA\b",
    ]

    if any(any(re.search(p, txt) for p in padroes_setoriais) for txt in textos):
        score += 1
        evidencias.append("termo_setorial_transporte")

    # -------------------------
    # penalidades
    # -------------------------
    if cnpj_empresa_norm and cnpjs:
        if cnpj_empresa_norm in cnpjs:
            score -= 5
            evidencias.append("cnpj_mesma_empresa")

    # -------------------------
    # classificação
    # -------------------------
    if score >= 7:
        classe = "PJ_EVIDENCIA_FORTE"
    elif score >= 4:
        classe = "PJ_EVIDENCIA_MEDIA"
    elif score >= 1:
        classe = "PJ_EVIDENCIA_FRACA"
    else:
        classe = "SEM_EVIDENCIA_PJ"

    return {
        "classe": classe,
        "score": score,
        "evidencias": evidencias,
        "cnpjs_detectados": cnpjs,
    }