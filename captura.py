import csv
import os
import time
import psutil

from datetime import datetime


ARQUIVO_CSV = "./captura_resumo.csv"


IDENTIFICADOR_TORRE = "TORRE-001"
IDENTIFICADOR_SERVIDOR = "SERVIDOR-001"


def classificar_uso(valor):
    """
    Classifica o percentual de utilização da métrica.
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
    """

    return (
        not os.path.exists(caminho)
        or os.path.getsize(caminho) == 0
    )


# quantidade de processadores disponíveis.

# logical=False:quantidade de processadores físicos.

# logical=True: quantidade de processadores virtuais.
processadores_fisicos = psutil.cpu_count(logical=False)
processadores_virtuais = psutil.cpu_count(logical=True)


# Define as colunas do arquivo CSV.
cabecalho = [
    "identificador_torre",
    "identificador_servidor",
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


precisa_cabecalho = arquivo_precisa_cabecalho(
    ARQUIVO_CSV
)


# Apresenta a identificação do monitoramento.
print("=" * 60)
print("MONITOR ORE")
print("MONITORAMENTO DE RECURSOS")
print("=" * 60)
print(f"Torre      : {IDENTIFICADOR_TORRE}")
print(f"Servidor   : {IDENTIFICADOR_SERVIDOR}")
print(f"CPUs físicas  : {processadores_fisicos}")
print(f"CPUs virtuais : {processadores_virtuais}")
print("Captura iniciada.")
print("=" * 60)


try:
    # modo "a" = adiciona novas capturas sem apagar o histórico existente
    with open(
        ARQUIVO_CSV,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as arquivo_csv:


        escritor = csv.writer(
            arquivo_csv,
            delimiter=";"
        )

        # Adiciona o cabeçalho somente quando o arquivo é criado pela primeira vez
        if precisa_cabecalho:
            escritor.writerow(cabecalho)
            arquivo_csv.flush()

        # monitoramento em ciclos infinitos
        while True:

            # Mede o uso de cada processador virtual
            uso_processadores = psutil.cpu_percent(
                interval=1,
                percpu=True
            )

            # Calcula a média de utilização das CPUs
            cpu_total = (
                sum(uso_processadores)
                / len(uso_processadores)
            )

            # Obtém o percentual de utilização da RAM
            ram = psutil.virtual_memory().percent

            # Identifica o disco principal do sistema
            raiz_disco = os.path.abspath(os.sep)

            # Obtém o percentual de utilização do disco
            disco = psutil.disk_usage(
                raiz_disco
            ).percent

            # Obtém a data e a hora da captura
            agora = datetime.now()

            data = agora.strftime("%d/%m/%Y")
            hora = agora.strftime("%H:%M:%S")

            # Encontra o maior percentual de uso entre os processadores virtuais
            maior_uso_cpu = max(uso_processadores)

            # Identifica qual CPU apresentou o maior uso
            numero_cpu_maior_uso = (
                uso_processadores.index(
                    maior_uso_cpu
                )
            )

            # Organiza os dados que serão adicionados em uma nova linha do arquivo CSV
            linha = [
                IDENTIFICADOR_TORRE,
                IDENTIFICADOR_SERVIDOR,
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

            # Adiciona a captura no arquivo CSV
            escritor.writerow(linha)

            # Garante que os dados sejam gravados imediatamente no arquivo
            arquivo_csv.flush()

            # Exibe no terminal um resumo da captura
            print()
            print("-" * 60)
            print(f"CAPTURA — {data} às {hora}")
            print("-" * 60)

            print(f"Torre     : {IDENTIFICADOR_TORRE}")
            print(f"Servidor  : {IDENTIFICADOR_SERVIDOR}")

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
            print(
                "Próxima captura em aproximadamente "
                "10 segundos..."
            )

            # aproximadamente 10 segundos ( 1 da medição da CPU + 9)
            time.sleep(9)


except KeyboardInterrupt:
    print()
    print("=" * 60)
    print("Captura encerrada pelo usuário.")
    print("=" * 60)