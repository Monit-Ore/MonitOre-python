
import csv
import os
import glob


PASTA_CAPTURA = "."
PASTA_LIMPEZA = "."


def ler_csv(caminho):
    with open(
        caminho,
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=";")

        colunas_originais = leitor.fieldnames or []

        colunas = [
            coluna.strip() if coluna else coluna
            for coluna in colunas_originais
        ]

        dados = []

        for linha in leitor:
            registro = {}

            for coluna_original, coluna_nova in zip(
                colunas_originais,
                colunas,
            ):
                valor = linha.get(coluna_original)

                registro[coluna_nova] = (
                    valor.strip() if valor is not None else ""
                )

            dados.append(registro)

        return dados, colunas


def limpar_dados(dados, colunas):
    dados_limpos = []

    campos_obrigatorios = [
        "RODADA",
        "PC_INDUSTRIAL",
        "DATA",
        "HORA",
    ]

    for registro in dados:
        registro_valido = True

        for campo in campos_obrigatorios:
            if campo not in colunas:
                registro_valido = False
                break

            valor = registro.get(campo, "")

            if valor.upper() in ("", "NA", "N/A"):
                registro_valido = False
                break

        if not registro_valido:
            continue

        if not any(
            valor and valor.upper() not in ("NA", "N/A")
            for valor in registro.values()
        ):
            continue

        dados_limpos.append(registro)

    # retorna uma lista contendo somente dados válidos
    return dados_limpos


def salvar_csv(caminho, dados, colunas):
    with open(
        caminho,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as arquivo:
        escritor = csv.DictWriter(
            arquivo,
            fieldnames=colunas,
            delimiter=";",
            extrasaction="ignore",
        )

        escritor.writeheader()
        escritor.writerows(dados)


def processar_arquivo(arquivo_original, tipo):
    dados, colunas = ler_csv(arquivo_original)

    dados_limpos = limpar_dados(dados, colunas)

    nome_arquivo = os.path.basename(arquivo_original)

    # mantém a data e o horário da captura no nome
    identificador = nome_arquivo.replace(
        f"_CAPTURA_{tipo}.csv",
        "",
    )

    arquivo_limpo = os.path.join(
        PASTA_LIMPEZA,
        f"{identificador}_LIMPEZA_{tipo}.csv",
    )

    salvar_csv(
        arquivo_limpo,
        dados_limpos,
        colunas,
    )

    print("Arquivo limpo:", arquivo_limpo)
    print("-" * 50)


def main():
    print("=" * 60)
    print("MONITORE - LIMPEZA DE DADOS")
    print("=" * 60)

                    # procurar arquivos
    arquivos_hardware = glob.glob(
        os.path.join(PASTA_CAPTURA, "*_CAPTURA_HARDWARE.csv")
    )

    arquivos_processos = glob.glob(
        os.path.join(PASTA_CAPTURA, "*_CAPTURA_PROCESSOS.csv")
    )

    arquivos = (
        [(arquivo, "HARDWARE") for arquivo in arquivos_hardware]
        + [(arquivo, "PROCESSOS") for arquivo in arquivos_processos]
    )

    if not arquivos:
        print("Nenhum arquivo de captura encontrado")
        return

    for arquivo, tipo in sorted(arquivos):
        processar_arquivo(arquivo, tipo)


if __name__ == "__main__":
    main()
