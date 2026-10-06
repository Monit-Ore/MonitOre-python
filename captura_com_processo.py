import csv
import os
import time
from datetime import datetime
import psutil

ARQUIVO_CSV = "./captura_mas_com_processos.csv"

IDENTIFICADOR_TORRE = "TORRE-001"
IDENTIFICADOR_SERVIDOR = "SERVIDOR-001"

# Definição do cabeçalho focado em processos e CPU (sem status)
CABECALHO = [
    "identificador_torre",
    "identificador_servidor",
    "data",
    "hora",
    "pid",
    "nome_processo",
    "cpu_processo_percentual",
    "cpu_classificacao"
]


def classificar_uso(valor):
    """
    Classifica o percentual de utilização de CPU do processo.
    """
    if valor < 20:
        return "NORMAL"
    elif valor < 50:
        return "ATENCAO"
    elif valor < 80:
        return "ALTO"
    else:
        return "CRITICO"


def arquivo_precisa_cabecalho(caminho):
    """
    Verifica se o arquivo CSV precisa de cabeçalho.
    """
    return (
        not os.path.exists(caminho)
        or os.path.getsize(caminho) == 0
    )


precisa_cabecalho = arquivo_precisa_cabecalho(ARQUIVO_CSV)
cpu_count = psutil.cpu_count() or 1

print("=" * 70)
print("MONITOR DE PROCESSOS — FOCO EM CPU")
print("=" * 70)
print(f"Torre     : {IDENTIFICADOR_TORRE}")
print(f"Servidor  : {IDENTIFICADOR_SERVIDOR}")
print(f"Arquivo   : {ARQUIVO_CSV}")
print("Captura iniciada. Pressione CTRL+C para encerrar.")
print("=" * 70)

#  chamada sem intervalo 
for p in psutil.process_iter(['pid']):
    try:
        p.cpu_percent(interval=None)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

try:
    with open(
        ARQUIVO_CSV,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as arquivo_csv:

        escritor = csv.writer(arquivo_csv, delimiter=";")

        if precisa_cabecalho:
            escritor.writerow(CABECALHO)
            arquivo_csv.flush()
            precisa_cabecalho = False

        while True:
            # Aguarda 2 segundos para calcular a variação de CPU dos processos
            time.sleep(2)

            agora = datetime.now()
            data = agora.strftime("%d/%m/%Y")
            hora = agora.strftime("%H:%M:%S")

            lista_processos = []

            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    # Mede o uso de CPU desde a última chamada normalizado pelo número de CPUs
                    cpu_uso = proc.cpu_percent(interval=None) / cpu_count

                    lista_processos.append({
                        "pid": proc.info['pid'],
                        "nome": proc.info['name'] or "desconhecido",
                        "cpu": cpu_uso,
                        "classificacao": classificar_uso(cpu_uso)
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            # Ordena os processos pelos que mais utilizam CPU
            lista_processos.sort(key=lambda x: x["cpu"], reverse=True)

            # Grava todos os processos capturados no CSV
            for p in lista_processos:
                escritor.writerow([
                    IDENTIFICADOR_TORRE,
                    IDENTIFICADOR_SERVIDOR,
                    data,
                    hora,
                    p["pid"],
                    p["nome"],
                    f"{p['cpu']:.2f}",
                    p["classificacao"]
                ])

            arquivo_csv.flush()

            # Exibição no console: Resumo com os 5 processos que mais consomem CPU no momento
            print("\n" + "-" * 70)
            print(f"CAPTURA — {data} às {hora} | Total de processos: {len(lista_processos)}")
            print("-" * 70)
            print(f"{'PID':<8} {'PROCESSO':<35} {'CPU (%)':<10} {'CLASSIFICAÇÃO'}")
            print("-" * 70)

            for p in lista_processos[:5]:
                print(
                    f"{p['pid']:<8} "
                    f"{p['nome'][:33]:<35} "
                    f"{p['cpu']:>6.2f}%    "
                    f"[{p['classificacao']}]"
                )

            print("-" * 70)
            print("Próxima coleta em 5 segundos...")
            time.sleep(5)

except KeyboardInterrupt:
    print("\n" + "=" * 70)
    print("Captura de processos encerrada pelo usuário.")
    print("=" * 70)