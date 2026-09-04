from pathlib import Path

pasta_sped =Path(r"C:\Sped\CONTRIB")
pasta_sped.mkdir(parents=True, exist_ok=True) # Cria a pasta se não existir



for arquivo in pasta_sped.iterdir():
    contagem = {}
    if arquivo.is_file() and arquivo.suffix == ".txt":
        with open(arquivo, "r", encoding="latin-1") as arquivo_aberto:
            for linha in arquivo_aberto:
                campos = linha.split("|")

                registro = campos[1]

                if registro in contagem:
                 contagem[registro] += 1
                else:
                    contagem[registro] = 1
                if registro == "9999":
                    break
            print(contagem)
