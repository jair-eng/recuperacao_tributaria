# class Query:
#
#
#     def __init__(self):
#         self.resultado = []
#         self.ordenacao = None
#
#     def filter(self,filtro):
#         self.resultado.append(filtro)
#
#         return self
#
#     def order_by(self,campo):
#         self.ordenacao = campo
#         return self
#
#     def mostrar(self):
#         print(self.resultado)
#
#
#
# q = Query()
# q.filter("id = 10")
# q.filter("periodo = 202501")
# q.filter("empresa = 15")
#
# q.mostrar()



from pathlib import Path

from app.db.models import EfdRegistro, EfdRevisao, EfdApontamento
from app.domain.fiscal.bloco_F.f100_comparacao import carregar_contratos_extraidos, listar_contratos_nao_encontrados

# pasta_resultado = Path(
#     r"C:\Sped\LEITOR_CONTRATO\resultado"
# )
#
# contratos_extraidos = carregar_contratos_extraidos(
#     pasta_resultado,
#     ano="2021",
#     mes="01",
# )
#
# contratos_nao_encontrados = listar_contratos_nao_encontrados(
#     contratos_extraidos,
#     f100,
# )
#
# print(
#     "Contratos extraídos:",
#     len(contratos_extraidos)
# )
#
# print(
#     "Contratos não encontrados:",
#     contratos_nao_encontrados
# )

######################TESTE 0150######################
# from app.db.session import SessionLocal
# from app.domain.fiscal.frete_transp.f100_participantes import localizar_0150_por_documento_na_versao, \
#     resolver_cod_part_frete, montar_linha_0150_frete
# from app.domain.fiscal.frete_transp.mestres_fretes import localizar_0140_por_cnpj, localizar_0150_contratado
#
# db = SessionLocal()
#
# try:
#     versao_id = 124
#
#     # ---------------------------------------------------------
#     # CONTRATANTE / 0140 ALVO
#     # ---------------------------------------------------------
#     cnpj_contratante = "13248429000144"
#
#     contexto_0140 = localizar_0140_por_cnpj(
#         db,
#         versao_id=versao_id,
#         cnpj=cnpj_contratante,
#     )
#
#     print("\n" + "=" * 70)
#     print("0140 ALVO")
#     print("=" * 70)
#     print(contexto_0140)
#
#     if not contexto_0140:
#         raise RuntimeError(
#             "0140 do contratante não encontrado."
#         )
#
#     print(
#         "\nREGISTRO_ID ÂNCORA:",
#         contexto_0140["registro_id"]
#     )
#
#     # ---------------------------------------------------------
#     # TESTE 1
#     # PARTICIPANTE QUE JÁ EXISTE EM ALGUM 0150 DA VERSÃO
#     # ---------------------------------------------------------
#     documento_existente = "03196116719"
#
#     print("\n" + "=" * 70)
#     print("TESTE 1 - PARTICIPANTE EXISTENTE NA VERSÃO")
#     print("=" * 70)
#
#     participante_no_0140 = localizar_0150_contratado(
#         db,
#         versao_id=versao_id,
#         contexto_0140=contexto_0140,
#         documento=documento_existente,
#     )
#
#     print(
#         "\n0150 NO 0140 ALVO:",
#         participante_no_0140
#     )
#
#     participante_na_versao = (
#         localizar_0150_por_documento_na_versao(
#             db,
#             versao_id=versao_id,
#             documento=documento_existente,
#         )
#     )
#
#     print(
#         "\n0150 EM QUALQUER 0140:",
#         participante_na_versao
#     )
#
#     cod_part = resolver_cod_part_frete(
#         db,
#         versao_id=versao_id,
#         documento=documento_existente,
#     )
#
#     print(
#         "\nCOD_PART RESOLVIDO:",
#         cod_part
#     )
#
#     # ---------------------------------------------------------
#     # TESTE 2
#     # PARTICIPANTE QUE NÃO EXISTE
#     # ---------------------------------------------------------
#     documento_novo = "99999999999"
#
#     print("\n" + "=" * 70)
#     print("TESTE 2 - PARTICIPANTE NOVO")
#     print("=" * 70)
#
#     participante_novo = (
#         localizar_0150_por_documento_na_versao(
#             db,
#             versao_id=versao_id,
#             documento=documento_novo,
#         )
#     )
#
#     print(
#         "\nBUSCA NA VERSÃO:",
#         participante_novo
#     )
#
#     novo_cod_part = resolver_cod_part_frete(
#         db,
#         versao_id=versao_id,
#         documento=documento_novo,
#     )
#
#     print(
#         "\nNOVO COD_PART GERADO:",
#         novo_cod_part
#     )
#
#     # ---------------------------------------------------------
#     # SIMULAÇÃO DA ÂNCORA PARA INSERT AFTER
#     # ---------------------------------------------------------
#     print("\n" + "=" * 70)
#     print("SIMULAÇÃO INSERT 0150")
#     print("=" * 70)
#
#     registro_id_ancora = contexto_0140["registro_id"]
#
#     print(
#         "INSERT AFTER registro_id:",
#         registro_id_ancora
#     )
#
#     print(
#         "Âncora REG: 0140"
#     )
#
#     print(
#         "COD_PART a inserir:",
#         novo_cod_part
#     )
#
#     linha_0150 = montar_linha_0150_frete(
#         cod_part="32461",
#         nome="PARTICIPANTE TESTE",
#         documento="99999999999",
#         tipo_pessoa="PF",
#         cod_mun="3205200",
#         logradouro="RUA TESTE",
#         numero="100",
#         bairro="CENTRO",
#     )
#
#     print(linha_0150)
#     print(
#         "|" + "|".join(
#             "" if valor is None else str(valor)
#             for valor in linha_0150
#         ) + "|"
#     )
#
# finally:
#     db.close()

###################################
# from app.db.session import SessionLocal
# from app.domain.fiscal.frete_transp.f100_participantes import montar_linha_0150_frete
# from app.domain.fiscal.frete_transp.insercao_frete import _criar_revisao_insert_0150_frete_v2
# from app.domain.fiscal.frete_transp.mestres_fretes import localizar_0140_por_cnpj
#
# from app.legacy_service.versao_overlay_service import (
#     carregar_linhas_logicas_com_revisoes_e_insert,
# )
#
#
# def linha_logica_para_texto(linha):
#
#     reg = str(
#         getattr(linha, "reg", "")
#         or ""
#     ).strip()
#
#     dados = (
#         getattr(linha, "dados", None)
#         or []
#     )
#
#     # Proteção caso dados já venha
#     # contendo o próprio REG.
#     if (
#         dados
#         and str(dados[0] or "").strip() == reg
#     ):
#         dados = dados[1:]
#
#     return (
#         "|"
#         + reg
#         + "|"
#         + "|".join(
#             ""
#             if valor is None
#             else str(valor)
#             for valor in dados
#         )
#         + "|"
#     )
#
#
# db = SessionLocal()
#
# try:
#
#     versao_id = 124
#
#     # =========================================================
#     # 1. LOCALIZA 0140
#     # =========================================================
#
#     contexto_0140 = localizar_0140_por_cnpj(
#         db,
#         versao_id=versao_id,
#         cnpj="13248429000144",
#     )
#
#     if not contexto_0140:
#         raise RuntimeError(
#             "0140 não encontrado."
#         )
#
#     print("\n" + "=" * 70)
#     print("0140 ÂNCORA")
#     print("=" * 70)
#
#     print(
#         "registro_id:",
#         contexto_0140["registro_id"]
#     )
#
#     print(
#         "linha:",
#         contexto_0140["linha_inicio"]
#     )
#
#     print(
#         "empresa:",
#         contexto_0140["nome"]
#     )
#
#     # =========================================================
#     # 2. MONTA 0150 TESTE
#     # =========================================================
#
#     linha_0150 = montar_linha_0150_frete(
#         cod_part="32461",
#         nome="PARTICIPANTE TESTE",
#         documento="99999999999",
#         tipo_pessoa="PF",
#         cod_mun="3205200",
#         logradouro="RUA TESTE",
#         numero="100",
#         bairro="CENTRO",
#     )
#
#     print("\n" + "=" * 70)
#     print("0150 A INSERIR")
#     print("=" * 70)
#
#     print(linha_0150)
#
#     # =========================================================
#     # 3. CRIA REVISÃO
#     # =========================================================
#
#     rv = _criar_revisao_insert_0150_frete_v2(
#         db,
#
#         versao_origem_id=versao_id,
#
#         registro_id_0140=(
#             contexto_0140["registro_id"]
#         ),
#
#         linha_0140=(
#             contexto_0140["linha_inicio"]
#         ),
#
#         linha_0150=linha_0150,
#
#         documento="99999999999",
#
#         cod_part="32461",
#     )
#
#     print("\n" + "=" * 70)
#     print("REVISÃO CRIADA")
#     print("=" * 70)
#
#     print("revisao_id:", rv.id)
#     print("acao:", rv.acao)
#     print("reg:", rv.reg)
#     print("registro_id ancora:", rv.registro_id)
#     print("revisao_json:", rv.revisao_json)
#
#     # =========================================================
#     # 4. RODA OVERLAY
#     # =========================================================
#
#     linhas = (
#         carregar_linhas_logicas_com_revisoes_e_insert(
#             db,
#             versao_origem_id=versao_id,
#         )
#     )
#
#     # =========================================================
#     # 5. LOCALIZA O 0150 QUE ACABAMOS DE INSERIR
#     # =========================================================
#
#     indice_inserido = None
#
#     for indice, linha in enumerate(linhas):
#
#         revisao_id = int(
#             getattr(
#                 linha,
#                 "revisao_id",
#                 0,
#             )
#             or 0
#         )
#
#         if revisao_id == int(rv.id):
#             indice_inserido = indice
#             break
#
#     print("\n" + "=" * 70)
#     print("OVERLAY")
#     print("=" * 70)
#
#     if indice_inserido is None:
#
#         print(
#             "ERRO: 0150 inserido não apareceu "
#             "no overlay."
#         )
#
#     else:
#
#         print(
#             "0150 ENCONTRADO NO OVERLAY!"
#         )
#
#         print(
#             "Índice lógico:",
#             indice_inserido
#         )
#
#         # -----------------------------------------------------
#         # Mostra algumas linhas antes e depois
#         # -----------------------------------------------------
#
#         inicio = max(
#             0,
#             indice_inserido - 3,
#         )
#
#         fim = min(
#             len(linhas),
#             indice_inserido + 4,
#         )
#
#         print("\nCONTEXTO:")
#
#         for linha in linhas[inicio:fim]:
#
#             marcador = ""
#
#             if int(
#                 getattr(
#                     linha,
#                     "revisao_id",
#                     0,
#                 )
#                 or 0
#             ) == int(rv.id):
#
#                 marcador = "  <<< NOVO 0150"
#
#             print(
#                 linha_logica_para_texto(
#                     linha
#                 ),
#                 marcador,
#             )
#
#     # =========================================================
#     # NÃO PERSISTE ESTE TESTE
#     # =========================================================
#
#     print("\n" + "=" * 70)
#     print("ROLLBACK DO TESTE")
#     print("=" * 70)
#
#     db.rollback()
#
#     print(
#         "Rollback realizado. "
#         "Nenhuma revisão do teste foi persistida."
#     )
#
# except Exception:
#
#     db.rollback()
#     raise
#
# finally:
#
#     db.close()



#####################################

from app.db.session import SessionLocal
from app.domain.fiscal.frete_transp.insercao_frete import garantir_0150_frete
from app.domain.fiscal.frete_transp.mestres_fretes import _dados_registro, somente_digitos, localizar_0150_contratado, \
    localizar_0140_por_cnpj, _campo
from app.domain.workflow.corretiva_v2_service import aplicar_corretiva_apontamento_v2

from app.legacy_service.versao_overlay_service import (
    carregar_linhas_logicas_com_revisoes_e_insert,
)


VERSAO_ID = 124
CNPJ_0140_ALVO = "13248429000144"


def titulo(texto):
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


def localizar_participante_de_outro_0140(
    db,
    *,
    versao_id: int,
    contexto_0140: dict,
):
    """
    Procura automaticamente um 0150 que:

    - exista na versão;
    - esteja FORA do intervalo do 0140 alvo;
    - e não exista dentro do 0140 alvo pelo mesmo documento.

    Serve exclusivamente para encontrarmos um caso real
    do cenário 2.
    """

    linha_inicio = int(
        contexto_0140["linha_inicio"]
    )

    linha_fim = int(
        contexto_0140["linha_fim"]
    )

    registros = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(
                versao_id
            ),
            EfdRegistro.reg == "0150",
        )
        .order_by(
            EfdRegistro.linha.asc()
        )
        .all()
    )

    for registro in registros:

        linha = int(
            getattr(
                registro,
                "linha",
                0,
            )
            or 0
        )

        # ---------------------------------------------
        # Queremos um participante de OUTRO 0140.
        # ---------------------------------------------

        if linha_inicio <= linha <= linha_fim:
            continue

        dados = _dados_registro(
            registro
        )

        cnpj = somente_digitos(
            _campo(
                dados,
                3,
            )
        )

        cpf = somente_digitos(
            _campo(
                dados,
                4,
            )
        )

        documento = (
            cnpj
            or cpf
        )

        if not documento:
            continue

        # ---------------------------------------------
        # Confirma que ele realmente não existe
        # dentro do nosso 0140 alvo.
        # ---------------------------------------------

        participante_local = (
            localizar_0150_contratado(
                db,
                versao_id=versao_id,
                contexto_0140=contexto_0140,
                documento=documento,
            )
        )

        if participante_local:
            continue

        return {
            "documento": documento,

            "tipo_pessoa": (
                "PJ"
                if cnpj
                else "PF"
            ),

            "cod_part": _campo(
                dados,
                0,
            ),

            "nome": _campo(
                dados,
                1,
            ),

            "linha": linha,

            "registro_id": getattr(
                registro,
                "id",
                None,
            ),
        }

    return None


db = SessionLocal()

try:

    # =========================================================
    # 0. LOCALIZA O 0140 ALVO
    # =========================================================

    contexto_0140 = localizar_0140_por_cnpj(
        db,
        versao_id=VERSAO_ID,
        cnpj=CNPJ_0140_ALVO,
    )

    if not contexto_0140:
        raise RuntimeError(
            "0140 alvo não encontrado."
        )

    titulo(
        "0140 ALVO"
    )

    print(
        "registro_id:",
        contexto_0140["registro_id"]
    )

    print(
        "linha_inicio:",
        contexto_0140["linha_inicio"]
    )

    print(
        "linha_fim:",
        contexto_0140["linha_fim"]
    )

    print(
        "empresa:",
        contexto_0140["nome"]
    )

    # =========================================================
    # CENÁRIO 1
    #
    # Participante já existe dentro do próprio 0140.
    #
    # ANDSON já foi validado no nosso teste anterior.
    # =========================================================

    titulo(
        "CENÁRIO 1 - 0150 JÁ EXISTE NO 0140 ALVO"
    )

    qtd_revisoes_antes = (
        db.query(EfdRevisao)
        .filter(
            EfdRevisao.versao_origem_id
            == VERSAO_ID
        )
        .count()
    )

    resultado_1 = garantir_0150_frete(
        db,

        versao_id=VERSAO_ID,

        contexto_0140=contexto_0140,

        documento="03196116719",

        # Esses dados nem deveriam ser necessários,
        # porque o participante já existe.
        nome="ANDSON SANTOS DAMACENO",

        tipo_pessoa="PF",
    )

    qtd_revisoes_depois = (
        db.query(EfdRevisao)
        .filter(
            EfdRevisao.versao_origem_id
            == VERSAO_ID
        )
        .count()
    )

    print(
        "RESULTADO:",
        resultado_1
    )

    print(
        "revisões antes:",
        qtd_revisoes_antes
    )

    print(
        "revisões depois:",
        qtd_revisoes_depois
    )

    assert (
        resultado_1["cod_part"]
        == "29510"
    )

    assert (
        resultado_1["criado"]
        is False
    )

    assert (
        resultado_1["origem"]
        == "0150_EXISTENTE_NO_0140"
    )

    assert (
        resultado_1["revisao_id"]
        is None
    )

    assert (
        qtd_revisoes_antes
        == qtd_revisoes_depois
    )

    print(
        "\nOK - nenhum 0150 foi criado."
    )

    # =========================================================
    # CENÁRIO 2
    #
    # Participante não existe nesse 0140,
    # mas existe em algum outro 0140.
    # =========================================================

    titulo(
        "PROCURANDO PARTICIPANTE PARA O CENÁRIO 2"
    )

    candidato = (
        localizar_participante_de_outro_0140(
            db,

            versao_id=VERSAO_ID,

            contexto_0140=contexto_0140,
        )
    )

    if not candidato:

        print(
            "Não encontramos automaticamente "
            "um participante adequado para o cenário 2."
        )

        resultado_2 = None

    else:

        print(
            "CANDIDATO:",
            candidato
        )

        titulo(
            "CENÁRIO 2 - 0150 EXISTE EM OUTRO 0140"
        )

        resultado_2 = garantir_0150_frete(
            db,

            versao_id=VERSAO_ID,

            contexto_0140=contexto_0140,

            documento=candidato[
                "documento"
            ],

            nome=candidato[
                "nome"
            ],

            tipo_pessoa=candidato[
                "tipo_pessoa"
            ],
        )

        print(
            "RESULTADO:",
            resultado_2
        )

        # ---------------------------------------------
        # O COD_PART precisa ser exatamente o mesmo
        # que já existia em outro estabelecimento.
        # ---------------------------------------------

        assert (
            resultado_2["cod_part"]
            == candidato["cod_part"]
        )

        assert (
            resultado_2["criado"]
            is True
        )

        assert (
            resultado_2["origem"]
            == "0150_REUTILIZADO_DA_VERSAO"
        )

        assert (
            resultado_2["revisao_id"]
            is not None
        )

        print(
            "\nOK - COD_PART reaproveitado:",
            resultado_2["cod_part"]
        )

        print(
            "revisao_id:",
            resultado_2["revisao_id"]
        )

    # =========================================================
    # CENÁRIO 3
    #
    # Participante totalmente novo.
    # =========================================================

    titulo(
        "CENÁRIO 3 - PARTICIPANTE NOVO"
    )

    resultado_3 = garantir_0150_frete(
        db,

        versao_id=VERSAO_ID,

        contexto_0140=contexto_0140,

        documento="99999999999",

        nome="PARTICIPANTE TESTE NOVO",

        tipo_pessoa="PF",

        cod_mun="3205200",

        logradouro="RUA TESTE",

        numero="100",

        bairro="CENTRO",
    )

    print(
        "RESULTADO:",
        resultado_3
    )

    assert (
        resultado_3["criado"]
        is True
    )

    assert (
        resultado_3["origem"]
        == "0150_NOVO"
    )

    assert (
        resultado_3["revisao_id"]
        is not None
    )

    print(
        "\nOK - novo COD_PART:",
        resultado_3["cod_part"]
    )

    # =========================================================
    # 4. TESTA OVERLAY
    #
    # Aqui queremos confirmar que as revisões criadas nos
    # cenários 2 e 3 realmente apareceram.
    # =========================================================

    titulo(
        "VALIDAÇÃO DO OVERLAY"
    )

    linhas = (
        carregar_linhas_logicas_com_revisoes_e_insert(
            db,

            versao_origem_id=VERSAO_ID,
        )
    )

    revisoes_esperadas = {
        int(
            resultado_3["revisao_id"]
        )
    }

    if (
        resultado_2
        and resultado_2.get(
            "revisao_id"
        )
    ):
        revisoes_esperadas.add(
            int(
                resultado_2[
                    "revisao_id"
                ]
            )
        )

    encontradas = set()

    for linha in linhas:

        revisao_id = int(
            getattr(
                linha,
                "revisao_id",
                0,
            )
            or 0
        )

        if (
            revisao_id
            not in revisoes_esperadas
        ):
            continue

        encontradas.add(
            revisao_id
        )

        print(
            "\nREVISÃO ENCONTRADA:",
            revisao_id
        )

        print(
            "reg:",
            getattr(
                linha,
                "reg",
                None,
            )
        )

        print(
            "linha lógica:",
            getattr(
                linha,
                "linha",
                None,
            )
        )

        print(
            "dados:",
            getattr(
                linha,
                "dados",
                None,
            )
        )

    titulo(
        "RESULTADO DO OVERLAY"
    )

    print(
        "esperadas:",
        revisoes_esperadas
    )

    print(
        "encontradas:",
        encontradas
    )

    assert (
        encontradas
        == revisoes_esperadas
    )

    print(
        "\nOK - todos os 0150 criados "
        "apareceram no overlay."
    )
    resultado = aplicar_corretiva_apontamento_v2(
        db=db,
        apontamento_id=62989,
    )

    print(f"Teste insercao pelo aplicar.{resultado}")

    # apontamento = (
    #     db.query(EfdApontamento)
    #     .filter(
    #         EfdApontamento.versao_id == 124,
    #         EfdApontamento.codigo == "F100_FRETE_AUSENTE_V2",
    #     )
    #     .order_by(EfdApontamento.id.desc())
    #     .first()
    # )
    #
    # print(f"Apontamento:{apontamento.id}")
    # =========================================================
    # 5. ROLLBACK
    # =========================================================

    titulo(
        "ROLLBACK"
    )

    db.rollback()

    print(
        "Rollback realizado."
    )

    print(
        "Nenhum 0150 de teste foi persistido."
    )

except Exception:

    db.rollback()
    raise

finally:

    db.close()