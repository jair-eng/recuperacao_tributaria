# app/teste/test_integracao_ecd_gap_apontamentos.py

from decimal import Decimal
from pprint import pprint

from app.db.session import SessionLocal
from app.db.models import EfdApontamento
from app.domain.ecd.ecd_gap_service import (
    carregar_linhas_ecd_com_natureza_real,
    gerar_diagnostico_gap_ecd_efd_por_versao,
    montar_contexto_gap_ecd_efd,
)
from app.domain.fiscal.enquadramento.enquadramento_repository import buscar_enquadramento_por_cenario
from app.domain.workflow.gerar_apontamentos_service import gerar_apontamentos_por_contexto

VERSAO_ID = 4
EMPRESA_ID = 1
PERIODO = "202211"


def assert_decimal_igual(valor, esperado):
    assert Decimal(str(valor)) == Decimal(str(esperado)), f"{valor} != {esperado}"


def main():
    db = SessionLocal()

    try:
        print("=" * 80)
        print("1) ECD COM NATUREZA REAL")
        print("=" * 80)

        linhas_ecd = carregar_linhas_ecd_com_natureza_real(
            db=db,
            empresa_id=EMPRESA_ID,
            periodo=PERIODO,
        )

        print("TOTAL ECD:", len(linhas_ecd))
        for linha in linhas_ecd:
            pprint(linha)

        assert len(linhas_ecd) == 4

        por_cod = {x["cod_cta"]: x for x in linhas_ecd}

        assert_decimal_igual(por_cod["292"]["valor"], "4500.00")
        assert_decimal_igual(por_cod["325"]["valor"], "396.00")
        assert_decimal_igual(por_cod["362"]["valor"], "242.00")
        assert_decimal_igual(por_cod["354"]["valor"], "20.37")

        assert por_cod["292"]["nat_bc_cred"] == "02"
        assert por_cod["325"]["nat_bc_cred"] == "03"
        assert por_cod["362"]["nat_bc_cred"] == "03"
        assert por_cod["354"]["nat_bc_cred"] == "04"

        print("OK ECD")

        print("=" * 80)
        print("2) DIAGNÓSTICO GAP ECD x EFD")
        print("=" * 80)

        diag_gap = gerar_diagnostico_gap_ecd_efd_por_versao(
            db=db,
            versao_id=VERSAO_ID,
            periodo=PERIODO,
            linhas_ecd_classificadas=linhas_ecd,
        )

        pprint(diag_gap["resumo"])
        pprint(diag_gap["comparativo"])

        resumo = diag_gap["resumo"]

        assert_decimal_igual(resumo["total_ecd_elegivel"], "5158.37")
        assert_decimal_igual(resumo["total_efd_declarada"], "2500.00")
        assert_decimal_igual(resumo["total_gap"], "2658.37")
        assert resumo["total_naturezas"] == 4

        comp = diag_gap["comparativo"][PERIODO]

        assert_decimal_igual(comp["01"]["base_efd_declarada"], "2500.00")
        assert comp["01"]["status"] == "SEM_ECD"

        assert_decimal_igual(comp["02"]["valor_ecd_elegivel"], "4500.00")
        assert comp["02"]["status"] == "SEM_EFD"

        assert_decimal_igual(comp["03"]["valor_ecd_elegivel"], "638.00")
        assert comp["03"]["status"] == "SEM_EFD"

        assert_decimal_igual(comp["04"]["valor_ecd_elegivel"], "20.37")
        assert comp["04"]["status"] == "SEM_EFD"

        print("OK GAP")

        print("=" * 80)
        print("3) CONTEXTO GAP PARA DIAGNÓSTICAS")
        print("=" * 80)

        contexto_gap = montar_contexto_gap_ecd_efd(
            db=db,
            empresa_id=EMPRESA_ID,
            versao_id=VERSAO_ID,
            periodo=PERIODO,
        )

        pprint(contexto_gap)

        assert contexto_gap["periodo"] == PERIODO
        assert "por_natureza" in contexto_gap

        assert contexto_gap["por_natureza"]["02"]["tem_gap"] is True
        assert_decimal_igual(contexto_gap["por_natureza"]["02"]["valor_gap"], "4500.00")

        assert contexto_gap["por_natureza"]["03"]["tem_gap"] is True
        assert_decimal_igual(contexto_gap["por_natureza"]["03"]["valor_gap"], "638.00")

        assert contexto_gap["por_natureza"]["04"]["tem_gap"] is True
        assert_decimal_igual(contexto_gap["por_natureza"]["04"]["valor_gap"], "20.37")

        print("OK CONTEXTO GAP")

        print("=" * 80)
        print("4) ENQUADRAMENTO")
        print("=" * 80)

        enq = buscar_enquadramento_por_cenario(
            db,
            "POSTO_CREDITO_NORMAL_LUBRIFICANTE",
        )

        pprint(enq)

        assert enq
        assert enq["cod_cred"] == enq["tipo_credito_codigo"]
        assert enq["nat_bc_cred"] == enq["base_credito_codigo"]
        assert enq["cst_pis_destino"] == "50"
        assert enq["cst_cofins_destino"] == "50"

        print("OK ENQUADRAMENTO")

        print("=" * 80)
        print("5) GERAR APONTAMENTOS POR CONTEXTO")
        print("=" * 80)

        res = gerar_apontamentos_por_contexto(
            db=db,
            versao_id=VERSAO_ID,
        )

        pprint(res)

        assert res["ok"] is True
        assert res["versao_id"] == VERSAO_ID

        apontamentos = (
            db.query(EfdApontamento)
            .filter(EfdApontamento.versao_id == VERSAO_ID)
            .filter(EfdApontamento.codigo.like("%_V2"))
            .all()
        )

        print("TOTAL APONTAMENTOS V2:", len(apontamentos))

        for ap in apontamentos[:20]:
            print("-" * 80)
            print("ID:", ap.id)
            print("CODIGO:", ap.codigo)
            print("PRIORIDADE:", ap.prioridade)
            meta = ap.meta_json or {}

            print("cenario:", meta.get("codigo_cenario") or meta.get("cenario"))
            print("status_cruzamento:", meta.get("status_cruzamento"))
            print("enquadramento:")
            pprint(meta.get("enquadramento"))
            print("ecd_gap:")
            pprint(meta.get("ecd_gap"))

            enq_meta = meta.get("enquadramento") or {}

            assert "cod_cred" in enq_meta
            assert "nat_bc_cred" in enq_meta

            # ecd_gap pode ser None se a natureza do item não tiver GAP.
            # Mas se existir, precisa vir estruturado.
            if meta.get("ecd_gap"):
                gap = meta["ecd_gap"]
                assert "nat_bc_cred" in gap
                assert "valor_gap" in gap
                assert "status" in gap

        print("=" * 80)
        print("TESTE FINALIZADO COM SUCESSO")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    main()