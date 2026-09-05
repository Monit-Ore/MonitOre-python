import csv
import os
import time
import psutil

from datetime import datetime


# Nome do arquivo que receberá as capturas.
# O arquivo será criado na mesma pasta do programa.
ARQUIVO_CSV = "./captura_resumo.csv"


def classificar_uso(valor):
    """
    Classifica o percentual de utilização da métrica.

    NORMAL:
    uso abaixo de 50%.

    ATENCAO:
    uso entre 50% e 79.99%.

    ALTO:
    uso entre 80% e 89.99%.

    CRITICO:
    uso igual ou superior a 90%.
    """

    if valor < 50:
        return "NORMAL"

    elif valor < 80:
        return "ATENCAO"

    elif valor < 90:
        return "ALTO"

    else:
        return "CRITICO"


def arquivo_precisa_cabecalho(caminho):
    """
    Verifica se o cabeçalho precisa ser criado.

    O cabeçalho será criado quando:
    - o arquivo ainda não existir;
    - ou o arquivo existir, mas estiver vazio.
    """

    return (
        not os.path.exists(caminho)
        or os.path.getsize(caminho) == 0
    )


# Obtém a quantidade de processadores disponíveis.
#
# logical=False:
# retorna a quantidade de processadores físicos.
#
# logical=True:
# retorna a quantidade de processadores virtuais.
processadores_fisicos = psutil.cpu_count(logical=False)
processadores_virtuais = psutil.cpu_count(logical=True)


# Define as colunas do arquivo CSV.
cabecalho = [
    "data",
    "hora",
    "cpu_total_percentual",
    "cpu_total_status",
    "ram_percentual",
    "ram_status",
    "disco_percentual",
    "disco_status",
    "cpu_maior_uso",
    "maior_uso_cpu_percentual",
    "processadores_fisicos",
    "processadores_virtuais"
]


# Verifica antes de abrir o arquivo se ele precisa
# receber o cabeçalho.
precisa_cabecalho = arquivo_precisa_cabecalho(
    ARQUIVO_CSV
)


print("=" * 50)
print("MONITORAMENTO DE RECURSOS")
print("=" * 50)
print(f"Processadores físicos: {processadores_fisicos}")
print(f"Processadores virtuais: {processadores_virtuais}")
print("Captura iniciada.")
print("Pressione Ctrl + C para encerrar.")
print("=" * 50)


try:
    # O modo "a" adiciona as novas capturas
    # sem apagar o histórico existente.
    with open(
        ARQUIVO_CSV,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as arquivo_csv:

        # O ponto e vírgula facilita a separação
        # das colunas no Excel em português.
        escritor = csv.writer(
            arquivo_csv,
            delimiter=";"
        )

        # Adiciona o cabeçalho somente na
        # primeira criação do arquivo.
        if precisa_cabecalho:
            escritor.writerow(cabecalho)
            arquivo_csv.flush()

        # Mantém a captura funcionando continuamente.
        # O programa será encerrado somente quando
        # o usuário pressionar Ctrl + C.
        while True:

            # Aguarda 1 segundo enquanto mede o uso
            # de cada processador virtual.
            uso_processadores = psutil.cpu_percent(
                interval=1,
                percpu=True
            )

            # Calcula a média de utilização de todos
            # os processadores virtuais.
            cpu_total = (
                sum(uso_processadores)
                / len(uso_processadores)
            )

            # Obtém o percentual de utilização da RAM.
            ram = psutil.virtual_memory().percent

            # Identifica o disco principal do sistema.
            raiz_disco = os.path.abspath(os.sep)

            # Obtém o percentual de utilização do disco.
            disco = psutil.disk_usage(
                raiz_disco
            ).percent

            # Obtém a data e a hora da captura.
            agora = datetime.now()

            data = agora.strftime("%d/%m/%Y")
            hora = agora.strftime("%H:%M:%S")

            # Encontra o maior percentual entre
            # todos os processadores virtuais.
            maior_uso_cpu = max(uso_processadores)

            # Descobre qual CPU virtual apresentou
            # o maior percentual de utilização.
            numero_cpu_maior_uso = (
                uso_processadores.index(
                    maior_uso_cpu
                )
            )

            # Organiza todos os dados que serão
            # adicionados em uma linha do arquivo.
            linha = [
                data,
                hora,
                round(cpu_total, 2),
                classificar_uso(cpu_total),
                round(ram, 2),
                classificar_uso(ram),
                round(disco, 2),
                classificar_uso(disco),
                numero_cpu_maior_uso,
                round(maior_uso_cpu, 2),
                processadores_fisicos,
                processadores_virtuais
            ]

            # Adiciona a captura no arquivo CSV.
            escritor.writerow(linha)

            # Garante que os dados sejam salvos
            # imediatamente no arquivo.
            arquivo_csv.flush()

            # Exibe no terminal um resumo da captura.
            print()
            print("-" * 50)
            print(f"CAPTURA — {data} às {hora}")
            print("-" * 50)

            print(
                f"CPU total : {cpu_total:6.2f}% "
                f"[{classificar_uso(cpu_total)}]"
            )

            print(
                f"RAM       : {ram:6.2f}% "
                f"[{classificar_uso(ram)}]"
            )

            print(
                f"Disco     : {disco:6.2f}% "
                f"[{classificar_uso(disco)}]"
            )

            print(
                f"Maior CPU : CPU {numero_cpu_maior_uso} "
                f"com {maior_uso_cpu:.2f}% "
                f"[{classificar_uso(maior_uso_cpu)}]"
            )

            print()
            print("Próxima captura em aproximadamente 10 segundos...")

            # A medição da CPU já demora 1 segundo.
            # A pausa de 9 segundos completa aproximadamente
            # 10 segundos entre o início de cada captura.
            time.sleep(9)


# O Ctrl + C gera uma interrupção do tipo
# KeyboardInterrupt, encerrando o ciclo infinito.
except KeyboardInterrupt:
    print()
    print("=" * 50)
    print("Captura encerrada pelo usuário.")
    print("=" * 50)