from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from app.icms_ipi.icms_helpers import _parse_date_ddmmyyyy, _split_sped_line
from app.icms_ipi.parser_sped_icms import NfIcmsPreviewNota, NfIcmsItemPreview, ParticipanteIcms
from typing import Any
from app.sped.bloco_D.d100_layout import D100Layout


D100 = D100Layout()

def _campo(dados: list[Any], idx: int) -> str:
    if idx < 0 or idx >= len(dados):
        return ""
    return "" if dados[idx] is None else str(dados[idx]).strip()


def _campo_dec(dados: list[Any], idx: int) -> float:
    txt = _campo(dados, idx)
    if not txt:
        return 0.0

    s = str(txt).strip()
    try:
        if "," in s:
            # formato brasileiro: 6.504,00
            s = s.replace(".", "").replace(",", ".")
        else:
            # formato já normal: 6504.00
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        return 0.0

def _to_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return Decimal("0")


def parse_d100(dados: list[Any]) -> dict[str, Any]:
    return {
        "reg": "D100",
        "ind_oper": _campo(dados, D100.idx_ind_oper),
        "ind_emit": _campo(dados, D100.idx_ind_emit),
        "cod_part": _campo(dados, D100.idx_cod_part),
        "cod_mod": _campo(dados, D100.idx_cod_mod),
        "cod_sit": _campo(dados, D100.idx_cod_sit),
        "ser": _campo(dados, D100.idx_ser),
        "sub": _campo(dados, D100.idx_sub),
        "num_doc": _campo(dados, D100.idx_num_doc),
        "chv_cte": _campo(dados, D100.idx_chv_cte),
        "dt_doc": _campo(dados, D100.idx_dt_doc),
        "dt_a_p": _campo(dados, D100.idx_dt_a_p),
        "tp_cte": _campo(dados, D100.idx_tp_cte),
        "chv_cte_ref": _campo(dados, D100.idx_chv_cte_ref),
        "vl_doc": _campo_dec(dados, D100.idx_vl_doc),
        "vl_desc": _campo_dec(dados, D100.idx_vl_desc),
        "ind_frt": _campo(dados, D100.idx_ind_frt),
        "vl_serv": _campo_dec(dados, D100.idx_vl_serv),
        "vl_bc_icms": _campo_dec(dados, D100.idx_vl_bc_icms),
        "vl_icms": _campo_dec(dados, D100.idx_vl_icms),
        "vl_nt": _campo_dec(dados, D100.idx_vl_nt),
        "cod_inf": _campo(dados, D100.idx_cod_inf),
        "cod_cta": _campo(dados, D100.idx_cod_cta),
        "cod_mun_orig": _campo(dados, D100.idx_cod_mun_orig),
        "cod_mun_dest": _campo(dados, D100.idx_cod_mun_dest),
    }



def parse_sped_icms_d100_preview(arquivo_path: str) -> dict[str, Any]:
    path = Path(arquivo_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {arquivo_path}")

    periodo: str | None = None
    dt_ini: date | None = None
    dt_fin: date | None = None

    empresa_cnpj: str | None = None
    empresa_nome: str | None = None
    empresa_uf: str | None = None

    participantes: dict[str, ParticipanteIcms] = {}
    infos_0460: dict[str, str] = {}

    notas: list[NfIcmsPreviewNota] = []
    itens: list[NfIcmsItemPreview] = []

    nota_atual: NfIcmsPreviewNota | None = None
    codigos_0460_atual: list[str] = []
    evidencias_0460_atual: list[str] = []

    def flush_nota() -> None:

        nonlocal nota_atual, codigos_0460_atual, evidencias_0460_atual
        print(
            "[DBG FLUSH D100 ANTES]",
            "num_doc=", getattr(nota_atual, "num_doc", None),
            "cods=", codigos_0460_atual,
            "evids=", evidencias_0460_atual,
            flush=True,
        )
        if nota_atual:
            notas.append(nota_atual)

        nota_atual = None
        codigos_0460_atual = []
        evidencias_0460_atual = []
        print(
            "[DBG FLUSH D100]",
            "nota_atual=", getattr(nota_atual, "num_doc", None),
            "cods_antes=", codigos_0460_atual,
            "evids_antes=", evidencias_0460_atual,
            flush=True,
        )

    with path.open("r", encoding="latin1") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            reg, fields = _split_sped_line(line)
            if not reg:
                continue

            if reg == "0000":
                dt_ini = _parse_date_ddmmyyyy(fields[2] if len(fields) > 2 else "")
                dt_fin = _parse_date_ddmmyyyy(fields[3] if len(fields) > 3 else "")
                empresa_nome = fields[4] if len(fields) > 4 else None
                empresa_cnpj = fields[5] if len(fields) > 5 else None
                empresa_uf = fields[7] if len(fields) > 7 else None
                if dt_ini:
                    periodo = dt_ini.strftime("%Y%m")

            elif reg == "0150":
                cod_part = fields[0] if len(fields) > 0 else ""
                if cod_part:
                    participantes[cod_part] = ParticipanteIcms(
                        cod_part=cod_part,
                        nome=fields[1] if len(fields) > 1 else None,
                        cod_pais=fields[2] if len(fields) > 2 else None,
                        cnpj=fields[3] if len(fields) > 3 else None,
                        cpf=fields[4] if len(fields) > 4 else None,
                        ie=fields[5] if len(fields) > 5 else None,
                        cod_mun=fields[6] if len(fields) > 6 else None,
                        suframa=fields[7] if len(fields) > 7 else None,
                        end=fields[8] if len(fields) > 8 else None,
                        num=fields[9] if len(fields) > 9 else None,
                        compl=fields[10] if len(fields) > 10 else None,
                        bairro=fields[11] if len(fields) > 11 else None,
                    )
            elif reg == "0460":
                cod_obs = fields[0] if len(fields) > 0 else ""
                txt_obs = fields[1] if len(fields) > 1 else ""
                if cod_obs:
                    infos_0460[cod_obs] = txt_obs

            elif reg == "D100":
                flush_nota()

                d = parse_d100(fields)
                cod_part = d.get("cod_part")
                part = participantes.get(cod_part or "")

                nota_atual = NfIcmsPreviewNota(
                    chave_nfe=d.get("chv_cte") or "",
                    num_doc=d.get("num_doc"),
                    serie=d.get("ser"),
                    dt_doc=_parse_date_ddmmyyyy(d.get("dt_doc") or ""),
                    dt_es=_parse_date_ddmmyyyy(d.get("dt_a_p") or ""),
                    vl_doc=_to_decimal(d.get("vl_doc")),
                    vl_icms=_to_decimal(d.get("vl_icms")),
                    modelo=d.get("cod_mod"),
                    cod_part=cod_part,
                    participante_nome=part.nome if part else None,
                    participante_cod_pais=part.cod_pais if part else None,
                    participante_cnpj=part.cnpj if part else None,
                    participante_cpf=part.cpf if part else None,
                    participante_ie=part.ie if part else None,
                    participante_cod_mun=part.cod_mun if part else None,
                    participante_suframa=part.suframa if part else None,
                    participante_end=part.end if part else None,
                    participante_num=part.num if part else None,
                    participante_compl=part.compl if part else None,
                    participante_bairro=part.bairro if part else None,
                    ind_oper=d.get("ind_oper"),
                    cod_sit=d.get("cod_sit"),
                    cod_mod=d.get("cod_mod"),
                    nome_arquivo=path.name,
                    codigos_0460=[],
                    evidencias_0460=[],
                )

            elif reg == "D190" and nota_atual:
                cst_icms = fields[0] if len(fields) > 0 else None
                cfop = fields[1] if len(fields) > 1 else None
                aliq_icms = fields[2] if len(fields) > 2 else "0"
                vl_opr = fields[3] if len(fields) > 3 else "0"
                vl_bc_icms = fields[4] if len(fields) > 4 else "0"
                vl_icms = fields[5] if len(fields) > 5 else "0"

                itens.append(
                    NfIcmsItemPreview(
                        chave_nfe=nota_atual.chave_nfe,
                        num_doc=nota_atual.num_doc,
                        serie=nota_atual.serie,
                        dt_doc=nota_atual.dt_doc,
                        cod_part=nota_atual.cod_part,
                        participante_nome=nota_atual.participante_nome,
                        participante_cnpj=nota_atual.participante_cnpj,
                        num_item=None,
                        cod_item=None,
                        cod_item_norm=None,
                        descricao="SERVICO_TRANSPORTE",
                        ncm=None,
                        cfop=cfop,
                        qtd=Decimal("0"),
                        unid=None,
                        cst_icms=cst_icms,
                        aliq_icms=_to_decimal(aliq_icms),
                        vl_item=_to_decimal(vl_opr),
                        vl_desc=Decimal("0"),
                        vl_bc_icms=_to_decimal(vl_bc_icms),
                        vl_icms=_to_decimal(vl_icms),
                        vl_ipi=Decimal("0"),
                        origem_item="D190_FALLBACK",
                        nome_arquivo=path.name,
                    )
                )
            elif reg == "D195" and nota_atual:
                cod_obs = fields[0] if len(fields) > 0 else ""
                if cod_obs:
                    codigos_0460_atual.append(cod_obs)

                    txt_obs = infos_0460.get(cod_obs)
                    if txt_obs:
                        evidencias_0460_atual.append(txt_obs)

                    # mantém espelhado na nota atual
                    setattr(nota_atual, "codigos_0460", list(codigos_0460_atual))
                    setattr(nota_atual, "evidencias_0460", list(evidencias_0460_atual))
    print(
        "[DBG FLUSH D100 POS]",
        "qtd_notas_depois=", len(notas),
        flush=True,
    )
    flush_nota()

    total_notas = len(notas)
    total_itens = len(itens)
    total_vl_doc = sum((n.vl_doc for n in notas), Decimal("0"))
    total_vl_item = sum((i.vl_item for i in itens), Decimal("0"))
    total_vl_icms = sum((n.vl_icms for n in notas), Decimal("0"))

    return {
        "arquivo": path.name,
        "fonte": "EFD_ICMS_IPI",
        "periodo": periodo,
        "dt_ini": dt_ini,
        "dt_fin": dt_fin,
        "empresa": {
            "cnpj": empresa_cnpj,
            "nome": empresa_nome,
            "uf": empresa_uf,
        },
        "total_notas": total_notas,
        "total_itens": total_itens,
        "total_vl_doc": total_vl_doc,
        "total_vl_item": total_vl_item,
        "total_vl_icms": total_vl_icms,
        "participantes_count": len(participantes),
        "produtos_count": 0,
        "notas_preview": [asdict(n) for n in notas[:20]],
        "itens_preview": [asdict(i) for i in itens[:50]],
        "notas": notas,
        "itens": itens,
        "participantes": participantes,
        "produtos": {},
    }