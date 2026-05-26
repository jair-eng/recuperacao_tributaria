from __future__ import annotations

import csv
from io import StringIO
from sqlalchemy.orm import Session
from sqlalchemy import case
from app.db.models import EfdApontamento, EfdRegistro


class ApontamentosExportService:
    @staticmethod
    def exportar_csv(db: Session, *, versao_id: int) -> str:
        """
        Gera CSV dos apontamentos da versão.
        Retorna CSV como string (o endpoint converte pra bytes com utf-8-sig).
        """

        rows = (
            db.query(EfdApontamento, EfdRegistro)
            .outerjoin(EfdRegistro, EfdRegistro.id == EfdApontamento.registro_id)
            .filter(EfdApontamento.versao_id == versao_id)
            .order_by(
                case((EfdRegistro.linha.is_(None), 1), else_=0).asc(),
                EfdRegistro.linha.asc(),
                EfdApontamento.id.asc(),
            )
            .all()
        )

        output = StringIO()
        writer = csv.writer(
            output,
            delimiter=";",
            quoting=csv.QUOTE_ALL,
            lineterminator="\n",
        )

        writer.writerow([
            "linha",
            "reg_sped",
            "registro_id",
            "item_fiscal_consolidado_id",
            "origem",
            "status_cruzamento",
            "tipo",
            "codigo",
            "descricao",
            "impacto_financeiro",
            "resolvido",
        ])

        for a, r in rows:
            meta = a.meta_json or {}

            linha = r.linha if r else ""
            reg_sped = r.reg if r else ""

            registro_id = a.registro_id if a.registro_id is not None else ""

            item_fiscal_id = (
                a.item_fiscal_consolidado_id
                if getattr(a, "item_fiscal_consolidado_id", None) is not None
                else meta.get("item_fiscal_consolidado_id", "")
            )

            origem = meta.get("origem", "")
            status_cruzamento = meta.get("status_cruzamento", "")

            desc = (a.descricao or "")
            desc = desc.replace("\r", " ").replace("\n", " ").strip()

            impacto = ""
            if a.impacto_financeiro is not None:
                impacto = f"{float(a.impacto_financeiro):.2f}".replace(".", ",")

            writer.writerow([
                linha,
                reg_sped,
                registro_id,
                item_fiscal_id,
                origem,
                status_cruzamento,
                a.tipo or "",
                a.codigo or "",
                desc,
                impacto,
                "SIM" if a.resolvido else "NAO",
            ])

        return output.getvalue()