import csv
import os


ARQUIVO_HARDWARE = "CAPTURA_HARDWARE.csv"
ARQUIVO_PROCESSOS = "CAPTURA_PROCESSOS.csv"



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

        # Compatibilidade com arquivos antigos.
        if "SERVIDOR" in colunas and "PC_INDUSTRIAL" not in colunas:
            indice = colunas.index("SERVIDOR")
            colunas[indice] = "PC_INDUSTRIAL"

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

    # Campos essenciais para identificar cada registro.
    campos_obrigatorios = [
        "RODADA",
        "PC_INDUSTRIAL",
        "DATA",
        "HORA",
    ]

    for registro in dados:
        registro_valido = True

        # Verifica se as colunas obrigatórias existem e possuem valor.
        for campo in campos_obrigatorios:
            if campo not in colunas:
                continue

            valor = registro.get(campo, "")

            if valor is None or valor.strip().upper() in ("", "NA", "N/A"):
                registro_valido = False
                break

        if not registro_valido:
            continue

        # Remove registros completamente vazios ou inválidos.
        if not any(
            valor and valor.strip().upper() not in ("NA", "N/A")
            for valor in registro.values()
        ):
            continue

        dados_limpos.append(registro)

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



for arquivo_original in (
    ARQUIVO_HARDWARE,
    ARQUIVO_PROCESSOS,
):
    if not os.path.exists(arquivo_original):
        print("Arquivo nao encontrado:", arquivo_original)
        continue

    dados, colunas = ler_csv(arquivo_original)

    dados_limpos = limpar_dados(dados, colunas)

    nome, extensao = os.path.splitext(arquivo_original)
    arquivo_limpo = f"{nome}_LIMPO{extensao}"

    salvar_csv(
        arquivo_limpo,
        dados_limpos,
        colunas,
    )

    print("Arquivo limpo:", arquivo_limpo)
    print("Registros originais:", len(dados))
    print("Registros apos limpeza:", len(dados_limpos))
    print("Colunas:", ";".join(colunas))
    print("-" * 50)