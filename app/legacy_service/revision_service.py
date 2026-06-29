from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.db.models import EfdVersao, EfdRegistro, EfdApontamento
from app.db.models.efd_revisao import EfdRevisao
from sqlalchemy import func
from app.sped.renderer import render_from_registro, _sha1

import logging
from collections import Counter

logger = logging.getLogger(__name__)

class RevisionService:
    """
    Fluxo:
      - versão original: retifica_de_versao_id = NULL (imutável)
      - versão revisada: retifica_de_versao_id = <id da original>
      - efd_revisao: alterações aplicadas sobre registros da original
    """

    @staticmethod
    def get_or_create_versao_revisada(
        db: Session,
        *,
        versao_origem_id: int,
        status_revisada: str = "EM_REVISAO",
    ) -> EfdVersao:
        origem = db.get(EfdVersao, int(versao_origem_id))
        if not origem:
            raise ValueError("Versão de origem não encontrada")

        # Se a origem já for revisada, normaliza para a raiz (original)
        raiz_id = int(origem.retifica_de_versao_id) if origem.retifica_de_versao_id else int(origem.id)

        # Já existe revisada para essa raiz?
        revisada = (
            db.query(EfdVersao)
            .filter(EfdVersao.retifica_de_versao_id == raiz_id)
            .order_by(EfdVersao.id.desc())
            .first()
        )
        if revisada:
            return revisada

        # cria nova revisada
        nova = EfdVersao(
            arquivo_id=int(origem.arquivo_id),
            numero=int(origem.numero) + 1,  # simples; se você já controla sequência de outro jeito, ajusta
            data_geracao=datetime.utcnow(),
            status=status_revisada,
            retifica_de_versao_id=raiz_id,
        )
        db.add(nova)
        db.flush()  # pega id

        return nova

    @staticmethod
    def criar_revisao_replace_line(
            db: Session,
            *,
            versao_id: int,
            apontamento_id: int,
            linha_nova: str,
            motivo_codigo: Optional[str] = None,
    ):
        ap = db.get(EfdApontamento, int(apontamento_id))
        if not ap:
            raise ValueError("Apontamento não encontrado")

        # 🔒 valida contexto
        if int(ap.versao_id) != int(versao_id):
            raise ValueError(
                f"Apontamento {apontamento_id} não pertence à versão {versao_id}"
            )

        regrow = db.get(EfdRegistro, int(ap.registro_id))
        if not regrow:
            raise ValueError("Registro do apontamento não encontrado")

        versao_revisada = RevisionService.get_or_create_versao_revisada(
            db, versao_origem_id=int(versao_id)
        )

        rev = EfdRevisao(
            versao_origem_id=int(versao_id),
            versao_revisada_id=None,  # opção 2
            registro_id=int(regrow.id),  # ok manter (origem)
            reg=str(regrow.reg),
            acao="REPLACE_LINE",
            revisao_json={
                "linha_referencia": int(regrow.linha),
                "linha_nova": linha_nova,
            },
            motivo_codigo=motivo_codigo or ap.codigo,
            apontamento_id=int(ap.id),
        )

        ap.resolvido = True

        db.add(rev)  # o apontamento (ap) já está no session
        db.flush()

        return rev



def _parse_sped_line_to_reg_dados(linha_nova: str) -> Tuple[str, List[str]]:
    """
    |C190|051|1102|...|  ->  ("C190", ["051","1102",...])
    """
    s = (linha_nova or "").strip()
    if not s:
        raise ValueError("linha_nova vazia")

    if not s.startswith("|"):
        s = "|" + s
    if not s.endswith("|"):
        s = s + "|"

    partes = s.split("|")
    if len(partes) < 3 or not partes[1].strip():
        raise ValueError("linha_nova inválida (REG ausente)")

    reg = partes[1].strip()
    dados = partes[2:-1]  # remove o último "" do pipe final
    return reg, dados


def materializar_versao_revisada(*, db: Session, versao_origem_id: int) -> int:
    """
    Materializa versão revisada de forma mais leve:
      - cria/reutiliza versão revisada
      - vincula revisões pendentes
      - apaga registros anteriores da revisada, se existirem
      - recria a versão revisada em memória a partir da origem
      - aplica REPLACE_LINE e INSERT_AFTER durante a cópia
      - evita UPDATE linha = linha + 1 em massa
    """

    import time
    t0 = time.perf_counter()

    logger.info("## [MAT v%s] INICIO ##", versao_origem_id)

    origem = db.get(EfdVersao, int(versao_origem_id))
    if not origem:
        raise ValueError("Versão origem não encontrada")

    # 1) Reutiliza ou cria versão revisada
    revisada = None

    if getattr(origem, "versao_revisada_id", None):
        revisada = db.get(EfdVersao, int(origem.versao_revisada_id))

    if revisada is None:
        revisada = (
            db.query(EfdVersao)
            .filter(EfdVersao.retifica_de_versao_id == int(versao_origem_id))
            .order_by(EfdVersao.id.desc())
            .first()
        )

    if revisada is None:
        max_num = (
            db.query(func.max(EfdVersao.numero))
            .filter(EfdVersao.arquivo_id == origem.arquivo_id)
            .scalar()
        ) or 0

        empresa_id = (
            getattr(origem, "empresa_id", None)
            or getattr(getattr(origem, "arquivo", None), "empresa_id", None)
        )

        if not empresa_id:
            raise ValueError(
                f"empresa_id não encontrado para versao_origem_id={origem.id}"
            )

        revisada = EfdVersao(
            arquivo_id=int(origem.arquivo_id),
            empresa_id=int(empresa_id),
            periodo=getattr(origem, "periodo", None),
            tipo_arquivo=getattr(origem, "tipo_arquivo", None),
            dominio=getattr(origem, "dominio", None),
            numero=int(max_num) + 1,
            status="EM_REVISAO",
            retifica_de_versao_id=int(versao_origem_id),
            observacao="Versão revisada (materializada)",
        )
        db.add(revisada)
        db.flush()

        logger.info(
            "## [MAT v%s] criou revisada id=%s em %.3fs ##",
            versao_origem_id,
            revisada.id,
            time.perf_counter() - t0,
        )

    versao_revisada_id = int(revisada.id)

    if getattr(origem, "versao_revisada_id", None) != versao_revisada_id:
        origem.versao_revisada_id = versao_revisada_id
        db.add(origem)
        db.flush()

    logger.info(
        "## [MAT v%s] revisada_id=%s preparada em %.3fs ##",
        versao_origem_id,
        versao_revisada_id,
        time.perf_counter() - t0,
    )

    # 2) Vincula revisões pendentes
    qtd_vinculadas = (
        db.query(EfdRevisao)
        .filter(
            EfdRevisao.versao_origem_id == int(versao_origem_id),
            EfdRevisao.versao_revisada_id.is_(None),
        )
        .update(
            {EfdRevisao.versao_revisada_id: versao_revisada_id},
            synchronize_session=False,
        )
    )
    db.flush()

    logger.info(
        "## [MAT v%s] revisoes pendentes vinculadas=%s em %.3fs ##",
        versao_origem_id,
        qtd_vinculadas,
        time.perf_counter() - t0,
    )

    # 3) Carrega revisões da versão
    revisoes: List[EfdRevisao] = (
        db.query(EfdRevisao)
        .filter(EfdRevisao.versao_origem_id == int(versao_origem_id))
        .filter(EfdRevisao.versao_revisada_id == versao_revisada_id)
        .order_by(EfdRevisao.id.asc())
        .all()
    )

    cnt_acoes = Counter(str(r.acao or "").strip().upper() for r in revisoes)

    logger.info(
        "## [MAT v%s] revisoes=%s por_acao=%s em %.3fs ##",
        versao_origem_id,
        len(revisoes),
        dict(cnt_acoes),
        time.perf_counter() - t0,
    )

    # 4) Mapa registro origem -> linha
    origem_reg_to_linha: Dict[int, int] = dict(
        db.query(EfdRegistro.id, EfdRegistro.linha)
        .filter(EfdRegistro.versao_id == int(versao_origem_id))
        .all()
    )

    inserts_por_linha: dict[int, list[str]] = {}
    replaces_por_linha: dict[int, str] = {}

    for rev in revisoes:
        payload = dict(rev.revisao_json or {})
        linha_nova = (payload.get("linha_nova") or "").strip()

        # AJUSTE_M e revisões sem linha_nova ficam fora da materialização física de linhas
        if not linha_nova:
            continue

        linha = payload.get("linha_referencia")
        linha = int(linha) if linha is not None else None

        if linha is None and rev.registro_id is not None:
            linha = origem_reg_to_linha.get(int(rev.registro_id))

        if linha is None:
            logger.warning(
                "## [MAT v%s] revisao sem linha resolvida | rev_id=%s acao=%s ##",
                versao_origem_id,
                rev.id,
                rev.acao,
            )
            continue

        acao = str(rev.acao or "").strip().upper()

        if acao == "REPLACE_LINE":
            replaces_por_linha[int(linha)] = linha_nova

        elif acao == "INSERT_AFTER":
            inserts_por_linha.setdefault(int(linha), []).append(linha_nova)

    logger.info(
        "## [MAT v%s] mapas prontos | replaces=%s inserts=%s em %.3fs ##",
        versao_origem_id,
        len(replaces_por_linha),
        sum(len(v) for v in inserts_por_linha.values()),
        time.perf_counter() - t0,
    )

    # 5) Apaga registros existentes da revisada em lotes
    total_apagados = 0

    while True:
        ids = [
            x[0]
            for x in (
                db.query(EfdRegistro.id)
                .filter(EfdRegistro.versao_id == versao_revisada_id)
                .order_by(EfdRegistro.id.asc())
                .limit(1000)
                .all()
            )
        ]

        if not ids:
            break

        apagados = (
            db.query(EfdRegistro)
            .filter(EfdRegistro.id.in_(ids))
            .delete(synchronize_session=False)
        )
        total_apagados += int(apagados or 0)
        db.flush()

    logger.info(
        "## [MAT v%s] registros revisados antigos apagados=%s em %.3fs ##",
        versao_origem_id,
        total_apagados,
        time.perf_counter() - t0,
    )

    # 6) Carrega origem e recria revisada já aplicando revisões
    regs_origem: List[EfdRegistro] = (
        db.query(EfdRegistro)
        .filter(EfdRegistro.versao_id == int(versao_origem_id))
        .order_by(EfdRegistro.linha.asc(), EfdRegistro.id.asc())
        .all()
    )

    if not regs_origem:
        raise ValueError("Versão origem não possui registros")

    logger.info(
        "## [MAT v%s] origem carregada registros=%s em %.3fs ##",
        versao_origem_id,
        len(regs_origem),
        time.perf_counter() - t0,
    )

    novos: list[EfdRegistro] = []
    nova_linha = 1

    for r in regs_origem:
        linha_original = int(r.linha)

        if linha_original in replaces_por_linha:
            linha_render = replaces_por_linha[linha_original]
            reg_novo, dados_novos = _parse_sped_line_to_reg_dados(linha_render)

            novos.append(
                EfdRegistro(
                    versao_id=versao_revisada_id,
                    linha=nova_linha,
                    reg=reg_novo,
                    conteudo_json={"dados": dados_novos},
                    alterado=True,
                    base_credito=getattr(r, "base_credito", None),
                    valor_credito=getattr(r, "valor_credito", None),
                    tipo_credito=getattr(r, "tipo_credito", None),
                )
            )
        else:
            novos.append(
                EfdRegistro(
                    versao_id=versao_revisada_id,
                    linha=nova_linha,
                    reg=str(r.reg),
                    conteudo_json=dict(r.conteudo_json or {}),
                    alterado=False,
                    base_credito=getattr(r, "base_credito", None),
                    valor_credito=getattr(r, "valor_credito", None),
                    tipo_credito=getattr(r, "tipo_credito", None),
                )
            )

        nova_linha += 1

        for linha_insert in inserts_por_linha.get(linha_original, []):
            reg_ins, dados_ins = _parse_sped_line_to_reg_dados(linha_insert)

            novos.append(
                EfdRegistro(
                    versao_id=versao_revisada_id,
                    linha=nova_linha,
                    reg=reg_ins,
                    conteudo_json={"dados": dados_ins},
                    alterado=True,
                )
            )
            nova_linha += 1

    logger.info(
        "## [MAT v%s] novos registros montados=%s em %.3fs ##",
        versao_origem_id,
        len(novos),
        time.perf_counter() - t0,
    )

    if novos:
        db.bulk_save_objects(novos)
        db.flush()

    logger.info(
        "## [MAT v%s] FIM | revisada_id=%s | registros_final=%s | tempo=%.3fs ##",
        versao_origem_id,
        versao_revisada_id,
        len(novos),
        time.perf_counter() - t0,
    )

    return versao_revisada_id