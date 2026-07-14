from app.db.models.efd_registro import EfdRegistro
from app.db.models.efd_revisao import EfdRevisao
from app.db.models.efd_versao import EfdVersao

from app.utils.numbers import q2,dec_any
from app.legacy_service.versao_overlay_service import carregar_linhas_logicas_com_revisoes_e_insert
from app.sped.blocoC.c100_utils import patch_c100_totais_imposto
from app.sped.blocoC.c170_utils import _parse_linha_sped_to_reg_dados, _parse_sped_float
from typing import Any, Dict, Optional, List, Tuple
from sqlalchemy.orm import Session
import os
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func,or_
import re
import logging

from app.utils.sped import preview_linha_sped

logger = logging.getLogger(__name__)

CPF_RE = re.compile(r"^\d{11}$")


PF_DEBUG = os.getenv("PF_DEBUG", "0").strip() == "1"

# para liga no power shell set PF_DEBUG=1

def pfdbg(msg: str) -> None:
        if PF_DEBUG:
            print(msg)

def _to_decimal(self, s):
    if not s:
        return None
    txt = str(s).replace(".", "").replace(",", ".")
    try:
        return Decimal(txt)
    except:
        return None

def _dec_sped(raw: object) -> Decimal:
    s = str(raw or "").strip()
    if not s:
        return Decimal("0")
    # padrão sped pt-BR -> Decimal
    s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")

def _q2(v: Decimal) -> Decimal:
    return (v or Decimal("0")).quantize(Decimal("0.01"), ROUND_HALF_UP)

def _s(v: Any) -> str:
    return str(v or "").strip()

def norm(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s if s else None

def ensure_len(d: list, idx: int) -> None:
    # garante que existe d[idx]
    if len(d) <= idx:
        d.extend([""] * (idx + 1 - len(d)))


def obter_linha_final(db: Session, registro_id: int, linha_original: str, versao_id: int) -> str:
    """
    ESSA É A FUNÇÃO CHAVE: Usada pelo Writer e pelo Renderer.
    Ela garante que a tela e o arquivo final mostrem a mesma coisa.
    """
    revisao = db.query(EfdRevisao).filter(
        EfdRevisao.registro_id == registro_id,
        EfdRevisao.versao_origem_id == versao_id,
        EfdRevisao.versao_revisada_id.is_(None)
    ).first()

    if revisao and "linha_nova" in revisao.revisao_json:
        return revisao.revisao_json["linha_nova"]

    return linha_original

def calcular_totais_filhos(db: Session, versao_id: int, c100_id: int):
    """Soma PIS/COFINS dos C170 vinculados ao C100 via pai_id."""
    itens_c170 = db.query(EfdRegistro).filter(
        EfdRegistro.versao_id == versao_id,
        EfdRegistro.pai_id == c100_id,
        EfdRegistro.reg == "C170"
    ).all()

    t_pis = 0.0
    t_cofins = 0.0

    for item in itens_c170:
        # Usa obter_linha_final para considerar itens já revisados na soma
        linha = obter_linha_final(db, item.id, "", versao_id)
        if not linha:  # Se não houver revisão, pega o original
            dados = _get_dados(item)
        else:
            _, dados = _parse_linha_sped_to_reg_dados(linha)

        # C170
        # VL_PIS    -> índice 28
        # VL_COFINS -> índice 34
        if len(dados) > 34:
            t_pis += _parse_sped_float(dados[28])
            t_cofins += _parse_sped_float(dados[34])

    return t_pis, t_cofins

def calcular_totais_filhos_overlay(
    db,
    *,
    versao_origem_id: int,
    versao_final_id: int | None,
    c100_id: int,
) -> Tuple[Decimal, Decimal]:
    """
    Soma VL_PIS e VL_COFINS dos C170 filhos de um C100 considerando overlay
    (REPLACE_LINE + INSERT_AFTER/BEFORE).
    """
    linhas = carregar_linhas_logicas_com_revisoes_e_insert(
        db=db,
        versao_origem_id=int(versao_origem_id),
        versao_final_id=versao_final_id,
    )

    total_pis = Decimal("0.00")
    total_cofins = Decimal("0.00")

    for ln in linhas:
        if str(getattr(ln, "reg", "")).upper() != "C170":
            continue

        pai_id = int(getattr(ln, "pai_id", 0) or 0)
        if pai_id != int(c100_id):
            continue

        conteudo = obter_conteudo_final(ln) or ""
        if not conteudo.startswith("|C170|"):
            continue

        try:
            reg, dados = _parse_linha_sped_to_reg_dados(conteudo)
        except Exception:
            continue

        if reg != "C170":
            continue

        # índices do C170 sem o REG
        # 29 -> VL_PIS
        # 35 -> VL_COFINS
        vl_pis = Decimal("0.00")
        vl_cofins = Decimal("0.00")

        try:
            if len(dados) > 28:
                raw = str(dados[28] or "").strip().replace(".", "").replace(",", ".")
                vl_pis = Decimal(raw or "0")
        except Exception:
            vl_pis = Decimal("0.00")

        try:
            if len(dados) > 34:
                raw = str(dados[34] or "").strip().replace(".", "").replace(",", ".")
                vl_cofins = Decimal(raw or "0")
        except Exception:
            vl_cofins = Decimal("0.00")

        total_pis += _q2(vl_pis)
        total_cofins += _q2(vl_cofins)

    return _q2(total_pis), _q2(total_cofins)

#Usa a Revisao criada
def calcular_totais_filhos_overlay_por_revisao_c100(
    db: Session,
    *,
    versao_origem_id: int,
    versao_final_id: int | None,
    revisao_c100_id: int,
) -> Tuple[Decimal, Decimal]:
    """
    Soma VL_PIS/VL_COFINS dos C170 pertencentes a um C100 inserido por revisão.

    Estratégia:
    - carrega a visão final do overlay;
    - localiza a linha lógica do C100 pela revisao_id;
    - percorre as linhas seguintes;
    - soma os C170 consecutivos do bloco;
    - para ao encontrar o próximo C100 ou um delimitador forte de bloco.
    """
    linhas = carregar_linhas_logicas_com_revisoes_e_insert(
        db=db,
        versao_origem_id=int(versao_origem_id),
        versao_final_id=versao_final_id,
    )

    idx_c100: Optional[int] = None
    for i, ln in enumerate(linhas):
        if (
            str(getattr(ln, "reg", "")).upper() == "C100"
            and int(getattr(ln, "revisao_id", 0) or 0) == int(revisao_c100_id)
        ):
            idx_c100 = i
            break

    if idx_c100 is None:
        return Decimal("0.00"), Decimal("0.00")

    total_pis = Decimal("0")
    total_cofins = Decimal("0")

    # delimitadores de fim do bloco da nota
    regs_fim_bloco = {"C100", "C190", "C175", "C180", "C181", "C185", "C188", "C990"}

    for j in range(idx_c100 + 1, len(linhas)):
        ln = linhas[j]
        reg_ln = str(getattr(ln, "reg", "")).upper()

        if reg_ln in regs_fim_bloco:
            break

        if reg_ln != "C170":
            continue

        conteudo = obter_conteudo_final(ln) or ""
        if not conteudo.startswith("|C170|"):
            continue

        try:
            reg, dados = _parse_linha_sped_to_reg_dados(conteudo)
        except Exception:
            continue

        if reg != "C170":
            continue

        # dados sem o REG
        # 28 -> VL_PIS
        # 34 -> VL_COFINS
        vl_pis = _dec_sped(dados[28]) if len(dados) > 28 else Decimal("0")
        vl_cofins = _dec_sped(dados[34]) if len(dados) > 34 else Decimal("0")

        # soma bruto; arredonda só no final
        total_pis += vl_pis
        total_cofins += vl_cofins

    return _q2(total_pis), _q2(total_cofins)

# Usa Registro Id
def calcular_totais_filhos_overlay_por_registro_c100(
    db: Session,
    *,
    versao_origem_id: int,
    versao_final_id: int | None,
    registro_c100_id: int,
) -> Tuple[Decimal, Decimal]:
    linhas = carregar_linhas_logicas_com_revisoes_e_insert(
        db=db,
        versao_origem_id=int(versao_origem_id),
        versao_final_id=versao_final_id,
    )

    idx_c100: Optional[int] = None
    for i, ln in enumerate(linhas):
        if (
            str(getattr(ln, "reg", "")).upper() == "C100"
            and int(getattr(ln, "registro_id", 0) or 0) == int(registro_c100_id)
        ):
            idx_c100 = i
            break

    if idx_c100 is None:
        return Decimal("0.00"), Decimal("0.00")

    total_pis = Decimal("0")
    total_cofins = Decimal("0")
    regs_fim_bloco = {"C100", "C190", "C175", "C180", "C181", "C185", "C188", "C990"}

    for j in range(idx_c100 + 1, len(linhas)):
        ln = linhas[j]
        conteudo = obter_conteudo_final(ln) or ""
        if not conteudo.startswith("|"):
            continue

        try:
            reg, dados = _parse_linha_sped_to_reg_dados(conteudo)
        except Exception:
            continue

        reg = str(reg or "").upper()

        if reg in regs_fim_bloco:
            break

        if reg != "C170":
            continue

        vl_pis = _dec_sped(dados[28]) if len(dados) > 28 else Decimal("0")
        vl_cofins = _dec_sped(dados[34]) if len(dados) > 34 else Decimal("0")

        print(
            "[DBG C170 FILHO]",
            {
                "registro_c100_id": registro_c100_id,
                "j": j,
                "vl_pis": str(vl_pis),
                "vl_cofins": str(vl_cofins),
                "conteudo": conteudo,
            },
            flush=True,
        )

        total_pis += vl_pis
        total_cofins += vl_cofins

    print(
        "[DBG SOMA_C100]",
        {
            "registro_c100_id": registro_c100_id,
            "total_pis": str(total_pis),
            "total_cofins": str(total_cofins),
        },
        flush=True,
    )

    return _q2(total_pis), _q2(total_cofins)


def popular_pai_id(db: Session, versao_id: int):
    """
    Lógica Rígida: Vincula registros filhos (C170, C190, etc.) ao último C100
    encontrado acima deles no arquivo, garantindo a integridade hierárquica.
    """
    print(f"🔍 Iniciando vinculação hierárquica para a versão {versao_id}...")

    # Buscamos apenas os registros que participam da hierarquia do Bloco C
    # Ordenar pela 'linha' é OBRIGATÓRIO para a lógica sequencial funcionar
    registros = db.query(EfdRegistro).filter(
        EfdRegistro.versao_id == versao_id,
        EfdRegistro.reg.in_(['C100', 'C110', 'C170', 'C190'])
    ).order_by(EfdRegistro.linha.asc()).all()

    ultimo_c100_id = None
    vinculados_count = 0
    erros_count = 0

    for r in registros:
        if r.reg == "C100":
            # Novo cabeçalho encontrado: ele passa a ser o pai dos próximos registros
            ultimo_c100_id = r.id
        elif r.reg in ["C110", "C170", "C190"]:
            # Tenta vincular ao pai atual
            if ultimo_c100_id:
                r.pai_id = ultimo_c100_id
                vinculados_count += 1
            else:
                # Caso o arquivo tenha um item antes de qualquer nota (erro de estrutura)
                erros_count += 1
                print(f"⚠️ Alerta: Registro {r.reg} na linha {r.linha} não possui um C100 antecedente.")

    # Persiste as alterações no banco
    db.flush()

    print(f"✅ Vinculação concluída!")
    print(f"   - Sucesso: {vinculados_count} registros vinculados.")
    if erros_count > 0:
        print(f"   - Erros: {erros_count} registros órfãos encontrados.")

    return vinculados_count


def _reg_of(item) -> str:
    """Extrai o nome do registro com suporte a múltiplos formatos de objeto."""
    # 1. Se for string pura (Ex: |C100|...)
    if isinstance(item, str):
        parts = item.split("|")
        if len(parts) > 1 and parts[1].strip():
            return parts[1].strip().upper()
        return "IGNORAR"

    # 2. Se for um objeto com atributo 'reg' (O caso do seu Loader)
    reg = getattr(item, "reg", None)
    if reg:
        return str(reg).strip().upper()

    # 3. Se for um objeto com atributo 'dados' (Caso da LinhaSpedDinamica)
    if hasattr(item, "dados") and isinstance(item.dados, list) and len(item.dados) > 0:
        # Tenta inferir se for um objeto genérico
        return "IGNORAR"

    return "IGNORAR"

def _get_dados(r: EfdRegistro) -> list[Any]:
    cj: Dict[str, Any] = getattr(r, "conteudo_json", None) or {}
    dados_raw = cj.get("dados")

    if not isinstance(dados_raw, list):
        raise ValueError("Registro não possui dados em formato lista.")

    reg = (getattr(r, "reg", "") or "").strip().upper()

    # ✅ Normaliza QUALQUER registro no formato ["REG", [...]]
    if (
        len(dados_raw) == 2
        and isinstance(dados_raw[0], str)
        and isinstance(dados_raw[1], list)
        and (dados_raw[0] or "").strip().upper() == reg
    ):
        return list(dados_raw[1] or [])

    return list(dados_raw or [])



def aplicar_overlay_revisoes_c170(
    db,
    *,
    versao_id: int,
    items: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    if not items:
        return items, 0

    registro_ids = [int(it["registro_id"]) for it in items if it.get("registro_id")]
    if not registro_ids:
        return items, 0

    # Descobre se esta versão é revisada (retifica outra)
    versao = db.get(EfdVersao, int(versao_id))
    retifica_de = int(getattr(versao, "retifica_de_versao_id", 0) or 0) if versao else 0

    q = (
        db.query(EfdRevisao)
        .filter(EfdRevisao.reg == "C170")
        .filter(EfdRevisao.acao == "REPLACE_LINE")
        .filter(EfdRevisao.registro_id.in_(registro_ids))
    )

    if retifica_de:
        # ✅ estamos olhando a VERSÃO REVISADA (ex.: 63):
        # queremos as revisões "carimbadas" para essa versão revisada
        q = q.filter(EfdRevisao.versao_revisada_id == int(versao_id))
        # (opcional) se existir coluna versao_origem_id, pode restringir:
        # q = q.filter(EfdRevisao.versao_origem_id == retifica_de)
    else:
        # ✅ estamos olhando a VERSÃO ORIGEM (ex.: 62):
        # queremos revisões PENDENTES (ainda não carimbadas)
        q = q.filter(EfdRevisao.versao_origem_id == int(versao_id))
        q = q.filter(EfdRevisao.versao_revisada_id.is_(None))

    revs = q.order_by(EfdRevisao.created_at.desc(), EfdRevisao.id.desc()).all()

    by_registro: Dict[int, EfdRevisao] = {}
    for rev in revs:
        rid = int(rev.registro_id or 0)
        if rid and rid not in by_registro:
            by_registro[rid] = rev

    aplicadas = 0
    for it in items:
        rid = int(it.get("registro_id") or 0)
        rev = by_registro.get(rid)
        if not rev:
            continue

        rj = rev.revisao_json or {}
        linha_nova = rj.get("linha_nova")
        if not linha_nova:
            continue

        reg, dados = _parse_linha_sped_to_reg_dados(str(linha_nova))
        if (reg or "").strip().upper() != "C170":
            continue

        it["dados"] = dados
        it["alterado"] = True
        it["revisao_id"] = int(rev.id)
        aplicadas += 1

    return items, aplicadas



def obter_conteudo_final(r: Any) -> str:
    from app.sped.formatter import formatar_linha

    if isinstance(r, str):
        return r

    # 1) se já existir linha revisada pronta, ela tem prioridade
    if hasattr(r, "linha_revisada") and r.linha_revisada:
        return str(r.linha_revisada)

    # 2) depois tenta reg + dados
    reg_attr = getattr(r, "reg", None)
    dados_attr = getattr(r, "dados", None)
    if reg_attr and dados_attr is not None:
        return formatar_linha(str(reg_attr), list(dados_attr))

    # 3) render próprio
    if hasattr(r, "render_linha"):
        return r.render_linha()

    # 4) EfdRegistro bruto
    if hasattr(r, "conteudo_json") and r.conteudo_json:
        dados = r.conteudo_json.get("dados", [])
        return formatar_linha(getattr(r, "reg", ""), dados)

    return ""


def eh_pf_por_c100(db: Session, versao_id: int, registro_id: int) -> bool:


    def only_digits(x: object) -> str:
        return "".join(ch for ch in str(x or "") if ch.isdigit())

    def offset_if_reg_first(dados: list, reg: str) -> int:
        return 1 if dados and str(dados[0]).strip().upper() == reg else 0

    reg_atual = db.get(EfdRegistro, int(registro_id))
    if not reg_atual: return False

    # 1) Achar o C100
    reg_c100 = None
    if str(getattr(reg_atual, "reg", "")).upper() == "C100":
        reg_c100 = reg_atual
    else:
        pai_id = int(getattr(reg_atual, "pai_id", 0) or 0)
        if pai_id:
            pai = db.get(EfdRegistro, pai_id)
            if pai and str(getattr(pai, "reg", "")).upper() == "C100":
                reg_c100 = pai

    if not reg_c100: return False
    pfdbg(f"[PF] registro_id={registro_id} reg_atual={getattr(reg_atual, 'reg', None)}")
    pfdbg(f"[PF] C100 id={reg_c100.id}")

    dados_c100 = _get_dados(reg_c100)
    off_c100 = offset_if_reg_first(dados_c100, "C100")

    cod_part = str(dados_c100[2 + off_c100]).strip()
    chave = only_digits(dados_c100[7 + off_c100])
    pfdbg(f"[PF] cod_part={cod_part}")
    pfdbg(f"[PF] chave={chave}")

    # 2) Identificar o Estabelecimento (0140) dono deste C100
    # Pegamos o CNPJ da filial na chave (posições 7 a 20)
    cnpj_filial_na_chave = chave[6:20] if len(chave) == 44 else None

    # 3) Localizar o 0140 que precede este C100 ou que tenha o CNPJ da chave
    # IMPORTANTE: No SPED, os participantes de uma filial ficam após o 0140 dela.
    # 0140 do bloco (sempre por linha)
    target_0140 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == versao_id,
            EfdRegistro.reg == "0140",
            EfdRegistro.linha < reg_c100.linha
        )
        .order_by(EfdRegistro.linha.desc())
        .first()
    )
    if not target_0140:
        return False

    # 4) Buscar o 0150 que está DEPOIS desse 0140 específico
    # mas ANTES do próximo 0140 (para não vazar participante de outra filial)
    prox_0140 = db.query(EfdRegistro).filter(
        EfdRegistro.versao_id == versao_id,
        EfdRegistro.reg == "0140",
        EfdRegistro.linha > target_0140.linha
    ).order_by(EfdRegistro.linha.asc()).first()

    limite_linha = prox_0140.linha if prox_0140 else 10 ** 18

    reg_0150 = db.query(EfdRegistro).filter(
        EfdRegistro.versao_id == versao_id,
        EfdRegistro.reg == "0150",
        EfdRegistro.linha > target_0140.linha,
        EfdRegistro.linha < limite_linha
    ).filter(
        or_(
            func.json_unquote(func.json_extract(EfdRegistro.conteudo_json, "$.dados[0]")) == cod_part,
            func.json_unquote(func.json_extract(EfdRegistro.conteudo_json, "$.dados[1]")) == cod_part
        )
    ).first()
    if not reg_0150: return False
    pfdbg(f"[PF] 0150 id={getattr(reg_0150, 'id', None)}")

    # 5) Análise final do 0150 encontrado
    d_0150 = _get_dados(reg_0150)
    off_0150 = offset_if_reg_first(d_0150, "0150")

    cnpj_0150 = only_digits(d_0150[3 + off_0150])
    cpf_0150 = only_digits(d_0150[4 + off_0150])

    # Regra de Ouro: Se tem CNPJ preenchido, é PJ. Se CNPJ vazio e tem CPF, é PF.
    if cnpj_0150:
        return False  # É PJ

    if len(cpf_0150) == 11:
        return True  # É PF

    pfdbg(f"[PF] cnpj_0150={cnpj_0150} cpf_0150={cpf_0150}")
    pfdbg(f"[PF] RESULTADO is_pf={bool(len(cpf_0150) == 11 and not cnpj_0150)}")

    return False

def _eh_item_cafe_match(item: Dict[str, Any]) -> bool:
    ncm = _s(item.get("ncm"))
    descricao = _s(item.get("descricao")).upper()
    cod_item = _s(item.get("cod_item")).upper()

    if ncm.startswith("0901"):
        return True

    texto = f"{descricao} {cod_item}"
    return "CAFE" in texto or "CAFÉ" in texto


def consolidar_totais_no_proprio_c100_inserido(
    db: Session,
    *,
    versao_origem_id: int,
    versao_final_id: int | None,
    revisao_c100_id: int,
) -> int | None:
    """
    Atualiza o próprio INSERT do C100 (rv_c100.revisao_json['linha_nova'])
    com a soma dos C170 do bloco.
    Retorna o id da revisão atualizada, ou None.
    """
    rv_c100 = db.query(EfdRevisao).filter(EfdRevisao.id == int(revisao_c100_id)).first()
    if not rv_c100:
        return None

    revisao_json = dict(rv_c100.revisao_json or {})

    if "linha_nova" in revisao_json:

        linha_nova = revisao_json["linha_nova"]
        formato = "ANTIGO"
    elif "linhas_novas" in revisao_json:

        linhas = list(revisao_json["linhas_novas"] or [])
        if not linhas:
            return None

        linha_nova = linhas[0]
        formato = "NOVO"

    else:
        return None
    if not linha_nova.startswith("|C100|"):
        return None

    total_pis, total_cofins = calcular_totais_filhos_overlay_por_revisao_c100(
        db,
        versao_origem_id=int(versao_origem_id),
        versao_final_id=versao_final_id,
        revisao_c100_id=int(revisao_c100_id),
    )
    logger.warning(
        "[C100_CONSOLIDA] revisao=%s pis=%s cofins=%s",
        revisao_c100_id,
        total_pis,
        total_cofins,
    )

    reg, dados_c100 = _parse_linha_sped_to_reg_dados(linha_nova)
    if reg != "C100":
        return None
    ###testar antes
    total_vl_merc = Decimal("0.00")

    if formato == "NOVO":
        for linha_filho in linhas[1:]:
            reg_filho, dados_filho = _parse_linha_sped_to_reg_dados(
                str(linha_filho or "")
            )

            if reg_filho != "C170":
                continue

            total_vl_merc += dec_any(
                dados_filho[5] if len(dados_filho) > 5 else None
            )

        total_vl_merc = q2(total_vl_merc)

        logger.warning(
            "[C100_CONSOLIDA][VL_MERC] "
            "revisao=%s formato=%s "
            "vl_merc_antes=%s vl_merc_soma_c170=%s",
            revisao_c100_id,
            formato,
            dados_c100[14] if len(dados_c100) > 14 else None,
            total_vl_merc,
        )

        dados_c100[14] = str(total_vl_merc).replace(".", ",")

    ####


    campos_atualizados = patch_c100_totais_imposto(
        dados_c100,
        total_pis,
        total_cofins,
    )
    if len(campos_atualizados) != 28:
        raise ValueError(f"C100 inválido após patch: esperado 28 dados, veio {len(campos_atualizados)}")

    nova_linha = "|" + "|".join(["C100"] + campos_atualizados) + "|"

    if formato == "NOVO":
        linhas[0] = nova_linha
        revisao_json["linhas_novas"] = linhas
    else:
        revisao_json["linha_nova"] = nova_linha
        revisao_json["totais_consolidados_auto"] = {
            "vl_pis": str(total_pis),
            "vl_cofins": str(total_cofins),
            "origem": "soma_c170_overlay_por_revisao_c100",
        }
    logger.warning(
        "[C100_CONSOLIDA] revisao=%s formato=%s pis=%s cofins=%s",
        revisao_c100_id,
        formato,
        total_pis,
        total_cofins,
    )
    rv_c100.revisao_json = revisao_json
    db.add(rv_c100)
    db.flush()

    return int(rv_c100.id)
