from app.db.models import EfdRegistro
from sqlalchemy.orm import Session
from typing import Optional


def _resolver_ancora_f100_em_f010(
    db: Session,
    *,
    versao_origem_id: int,
    linha_fim_f010: int,
) -> tuple[Optional[int], int, str]:
    """
    Resolve a âncora para inserção de um novo registro F100
    dentro de um estabelecimento F010 já existente.

    Regra de posicionamento:

    1. Procura o próximo registro F010 existente após o término
       do F010 atual.
       - Se encontrado, utiliza esse próximo F010 como âncora.
       - A ação será INSERT_BEFORE, garantindo que o novo F100
         permaneça dentro do F010 ao qual pertence.

    2. Caso o F010 atual seja o último estabelecimento do Bloco F,
       não haverá outro F010 posterior.
       - Nesse caso, procura o registro F990, encerramento do Bloco F.
       - O F990 será utilizado como âncora com INSERT_BEFORE.

    Exemplo com próximo F010:

        |F010|CNPJ_A|
        |F100|...|
        |F100|NOVO|       <- inserir aqui
        |F010|CNPJ_B|     <- âncora / INSERT_BEFORE

    Exemplo quando o F010 é o último do bloco:

        |F010|CNPJ_A|
        |F100|...|
        |F100|NOVO|       <- inserir aqui
        |F990|...|         <- âncora / INSERT_BEFORE

    A linha final do intervalo do F010 atual (`linha_fim_f010`)
    é utilizada como referência para procurar somente registros
    posteriores ao estabelecimento que está sendo tratado.

    Se não for encontrado nem um próximo F010 nem o F990,
    a função não deve escolher uma posição arbitrária para a
    inserção. Essa situação deve ser tratada pela corretiva como
    uma inconsistência estrutural do arquivo.

    Retorno:
        tuple[Optional[int], int, str]:
            - registro_id da âncora;
            - número da linha da âncora;
            - ação de inserção ("INSERT_BEFORE").
    """

    proximo_f010 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "F010",
            EfdRegistro.linha > int(linha_fim_f010),
        )
        .order_by(EfdRegistro.linha.asc())
        .first()
    )

    if proximo_f010:
        return (
            int(proximo_f010.id),
            int(proximo_f010.linha or 0),
            "INSERT_BEFORE",
        )

    reg_f990 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "F990",
        )
        .order_by(EfdRegistro.linha.asc())
        .first()
    )

    if reg_f990:
        return (
            int(reg_f990.id),
            int(reg_f990.linha or 0),
            "INSERT_BEFORE",
        )

    return None, 0, "INSERT_AFTER"