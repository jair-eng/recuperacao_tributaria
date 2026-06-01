# app/teste/test_alertas_efd_omissao.py

from decimal import Decimal
from app.db.session import SessionLocal
from app.domain.ecd.ecd_gap_service import montar_contexto_gap_ecd_efd


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

        resumo = ctx["resumo"]

        ecd = Decimal(str(resumo.get("total_ecd_elegivel") or "0"))
        efd = Decimal(str(resumo.get("total_efd_declarada") or "0"))
        gap = Decimal(str(resumo.get("total_gap") or "0"))

        if ecd > 0:
            cobertura = ((efd / ecd) * Decimal("100")).quantize(Decimal("0.01"))
        else:
            cobertura = Decimal("0.00")

        alertas = []

        if ecd > 0 and efd <= 0:
            alertas.append({
                "tipo": "EFD_ZERADA_COM_DESPESA_ECD",
                "periodo": periodo,
                "despesa_ecd": ecd,
                "base_efd": efd,
                "gap": gap,
                "cobertura": cobertura,
            })

        elif ecd > 0 and efd > 0 and cobertura < Decimal("70.00"):
            alertas.append({
                "tipo": "EFD_COM_BAIXA_COBERTURA",
                "periodo": periodo,
                "despesa_ecd": ecd,
                "base_efd": efd,
                "gap": gap,
                "cobertura": cobertura,
            })

        print("\n========== ALERTAS EFD OMISSÃO ==========")

        if not alertas:
            print("Nenhum alerta crítico encontrado.")

        for alerta in alertas:
            print("-" * 80)
            print("Tipo:", alerta["tipo"])
            print("Ano-Mês:", alerta["periodo"])
            print("Despesa Elegível ECD:", fmt(alerta["despesa_ecd"]))
            print("Base Declarada EFD:", fmt(alerta["base_efd"]))
            print("Gap:", fmt(alerta["gap"]))
            print("% Cobertura:", f'{alerta["cobertura"]}%')
            print(
                "Motivo:",
                "ECD possui despesa elegível, mas a EFD declarou base insuficiente no Bloco M.",
            )

        print("\n========== DETALHE POR NATUREZA ==========")
        for nat, dados in sorted(ctx["por_natureza"].items()):
            if dados.get("status") in ("SEM_EFD", "PARCIAL"):
                print("-" * 80)
                print("NAT:", nat)
                print("Status:", dados.get("status"))
                print("ECD:", fmt(dados.get("valor_ecd")))
                print("EFD:", fmt(dados.get("valor_efd")))
                print("GAP:", fmt(dados.get("valor_gap")))
                print("Categorias:", dados.get("categorias"))

    finally:
        db.close()


if __name__ == "__main__":
    main()