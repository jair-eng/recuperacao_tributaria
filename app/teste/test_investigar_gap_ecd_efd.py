# app/teste/test_investigar_gap_ecd_efd.py

from decimal import Decimal
from app.db.session import SessionLocal
from app.domain.ecd.ecd_gap_service import (
    montar_contexto_gap_ecd_efd,
    carregar_linhas_ecd_com_natureza_real,
)


def fmt(v):
    if v is None:
        return "0,00"
    if not isinstance(v, Decimal):
        v = Decimal(str(v or "0"))
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    db = SessionLocal()

    try:
        empresa_id = 1
        versao_id = 4
        periodo = "202211"

        ctx = montar_contexto_gap_ecd_efd(
            db,
            empresa_id=empresa_id,
            versao_id=versao_id,
            periodo=periodo,
        )

        investigacoes = []

        for nat, dados in sorted(ctx["por_natureza"].items()):
            status = dados.get("status")
            valor_gap = Decimal(str(dados.get("valor_gap") or "0"))

            if status == "SEM_EFD":
                investigacoes.append({
                    "tipo": "ECD_SEM_BASE_EFD",
                    "prioridade": "ALTA",
                    "nat": nat,
                    "status": status,
                    "gap": valor_gap,
                    "acao_sugerida": "Verificar se a natureza deveria ter sido declarada na EFD/Bloco M.",
                    "categorias": dados.get("categorias") or [],
                    "contas": dados.get("contas_ecd") or [],
                    "fundamentos": dados.get("fundamentos") or [],
                })

            elif status == "SEM_ECD":
                investigacoes.append({
                    "tipo": "EFD_SEM_LASTRO_ECD",
                    "prioridade": "MEDIA",
                    "nat": nat,
                    "status": status,
                    "gap": valor_gap,
                    "acao_sugerida": "Investigar se existe conta contábil não classificada ou classificação ECD ausente para esta natureza.",
                    "categorias": dados.get("categorias") or [],
                    "contas": dados.get("contas_ecd") or [],
                    "fundamentos": dados.get("fundamentos") or [],
                })

            elif status == "PARCIAL":
                investigacoes.append({
                    "tipo": "COBERTURA_PARCIAL",
                    "prioridade": "MEDIA",
                    "nat": nat,
                    "status": status,
                    "gap": valor_gap,
                    "acao_sugerida": "Comparar contas ECD com bases declaradas para identificar diferença parcial.",
                    "categorias": dados.get("categorias") or [],
                    "contas": dados.get("contas_ecd") or [],
                    "fundamentos": dados.get("fundamentos") or [],
                })

        print("\n========== INVESTIGAR ==========")

        for item in investigacoes:
            print("-" * 80)
            print("Tipo:", item["tipo"])
            print("Prioridade:", item["prioridade"])
            print("NAT:", item["nat"])
            print("Status:", item["status"])
            print("GAP:", fmt(item["gap"]))
            print("Categorias:", item["categorias"])
            print("Contas:", item["contas"])
            print("Fundamentos:", item["fundamentos"])
            print("Ação sugerida:", item["acao_sugerida"])

        print("\n========== RESUMO INVESTIGAÇÃO ==========")
        print("Total itens para investigar:", len(investigacoes))

        por_tipo = {}
        for item in investigacoes:
            por_tipo[item["tipo"]] = por_tipo.get(item["tipo"], 0) + 1

        for tipo, qtd in sorted(por_tipo.items()):
            print(tipo + ":", qtd)

    finally:
        db.close()


if __name__ == "__main__":
    main()