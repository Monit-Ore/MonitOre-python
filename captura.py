from getpass import getpass
import csv
import os
import socket
import time
import unicodedata
from datetime import datetime
import mysql.connector
import psutil

TOTAL_REGISTROS_LIMITE = 50
INTERVALO_SEGUNDOS = 10

# conexão com o mysql
CONFIG_BANCO = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD") or getpass("senha do mysql: "),
    "database": os.getenv("MYSQL_DATABASE", "monitore"),
}

CABECALHO_HARDWARE = [
    "RODADA",
    "PC_INDUSTRIAL",
    "DATA",
    "HORA",
    "CPU_TOTAL_PCT",
    "RAM_TOTAL_PCT",
    "RAM_TOTAL_MB",
    "DISCO_TOTAL_PCT",
    "QTD_PROCESSOS",
]

CABECALHO_PROCESSOS = [
    "RODADA",
    "PC_INDUSTRIAL",
    "DATA",
    "HORA",
    "PID",
    "PROCESSO",
    "PROC_CPU_ABSOLUTA_PCT",
    "PROC_CPU_GLOBAL_PCT",
    "PROC_RAM_PCT",
    "PROC_RAM_MB",
]


def normalizar_nome(nome):    
    # separa caracteres acentuados em duas partes, para remover o acento sem remover a letra
    nome = unicodedata.normalize("NFD", nome)
    # retira o acento e junta as letras
    nome = "".join(
        caractere for caractere in nome
        if unicodedata.category(caractere) != "Mn"
    )
    # strip() : remove espaços em branco
    # upper() : transforma todas as letras em maiúsculas
    return nome.strip().upper()


def identificar_componentes(componentes_banco):
    # identifica quais métricas estão configuradas para o ipc

    componentes = set()

    for nome in componentes_banco:
        nome = normalizar_nome(nome)

        if "CPU" in nome:
            componentes.add("CPU")

        elif "RAM" in nome:
            componentes.add("RAM")

        elif "DISCO" in nome:
            componentes.add("DISCO")

    return componentes


def consultar_configuracao_pc(hostname):

    # verificar se as configurações do bd estão preenchidas
    if not all([
        CONFIG_BANCO["host"],
        CONFIG_BANCO["user"],
        CONFIG_BANCO["password"],
    ]):
        raise ValueError(
            "configure MYSQL_HOST, MYSQL_USER e MYSQL_PASSWORD "
            "nas variaveis de ambiente"
        )

    # conectar o bd
    conexao = mysql.connector.connect(**CONFIG_BANCO)

    try:
        # resultados das consultas serão retornado como dicionários
        cursor = conexao.cursor(dictionary=True)

        # identifica o pc industrial pelo hostname
        cursor.execute(
            """
            SELECT
                id_pc_industrial,
                hostname
            FROM PC_Industrial
            WHERE hostname = %s
            """,
            (hostname,),
        )
        # armazena a consulta
        pc = cursor.fetchone()

        if pc is None:
            raise ValueError(
                f"hostname '{hostname}' nao encontrado "
                "na tabela PC_Industrial"
            )

        # consulta somente os componentes configurados para o pc
        cursor.execute(
            """
            SELECT
                c.nome
            FROM limite_alerta la
            INNER JOIN componente c
                ON c.id_componente = la.fk_componente
            WHERE la.fk_pc_industrial = %s
            """,
            (pc["id_pc_industrial"],),
        )

        componentes_banco = [
            registro["nome"]
            for registro in cursor.fetchall()
        ]

        cursor.close()

        componentes = identificar_componentes(componentes_banco)

        if not componentes:
            raise ValueError(
                "nenhum componente reconhecido esta configurado "
                "para este pc"
            )

        return pc, componentes, componentes_banco

    # fecha a conexão com o bd  
    finally:
        conexao.close()


def precisa_cabecalho(caminho):
    return (
        not os.path.exists(caminho)
        or os.path.getsize(caminho) == 0
    )


def obter_processos(
    numero_rodada,
    identificador_pc,
    data,
    hora,
    processadores_virtuais,
    componentes,
):
    linhas_processos = []

    for processo in psutil.process_iter([
        "pid",
        "name",
        "cpu_percent",
        "memory_info",
        "memory_percent",
    ]):
        try:
            info = processo.info

            pid = info["pid"]
            nome = info["name"] or "Desconhecido"

            # coleta cpu somente se estiver configurada
            if "CPU" in componentes:
                cpu_absoluta = info["cpu_percent"] or 0.0
                cpu_global = cpu_absoluta / processadores_virtuais

                cpu_absoluta = round(cpu_absoluta, 2)
                cpu_global = round(cpu_global, 2)
            else:
                cpu_absoluta = ""
                cpu_global = ""

            # coleta ram somente se estiver configurada
            if "RAM" in componentes:
                memoria = info["memory_info"]

                ram_mb = (
                    round(memoria.rss / (1024 * 1024), 2)
                    if memoria else 0.0
                )

                ram_pct = round(
                    info["memory_percent"] or 0.0,
                    2,
                )
            else:
                ram_mb = ""
                ram_pct = ""

            linhas_processos.append([
                numero_rodada,
                identificador_pc,
                data,
                hora,
                pid,
                nome,
                cpu_absoluta,
                cpu_global,
                ram_pct,
                ram_mb,
            ])

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    return linhas_processos


def obter_uso_disco():
    # calcula o percentual de ocupacao total dos discos locais

    total_bytes = 0
    usado_bytes = 0
    dispositivos_vistos = set()

    for particao in psutil.disk_partitions(all=False):
        dispositivo = particao.device

        if dispositivo in dispositivos_vistos:
            continue

        dispositivos_vistos.add(dispositivo)

        try:
            uso = psutil.disk_usage(particao.mountpoint)
            total_bytes += uso.total
            usado_bytes += uso.used

        except (PermissionError, OSError):
            continue

    if total_bytes == 0:
        return 0.0

    return round((usado_bytes / total_bytes) * 100, 2)


def main():
    print("=" * 60)
    print("MONIT ORE - CAPTURA DE HARDWARE E PROCESSOS")
    print("=" * 60)

    identificador_pc = socket.gethostname().strip()

    if not identificador_pc:
        raise ValueError("nao foi possivel identificar o hostname")

    print(f"hostname local: {identificador_pc}")

    # consulta o banco antes de iniciar a captura
    pc, componentes, nomes_banco = consultar_configuracao_pc(
        identificador_pc
    )

    print(f"pc industrial: {pc['id_pc_industrial']}")
    print(f"componentes encontrados: {nomes_banco}")
    print(f"componentes reconhecidos: {sorted(componentes)}")

    # cria um identificador unico para os dois arquivos
    identificador_data = datetime.now().strftime(
        "%d-%m-%Y_%H-%M-%S"
    )

    arquivo_hardware = (
        f"{identificador_data}_CAPTURA_HARDWARE.csv"
    )

    arquivo_processos = (
        f"{identificador_data}_CAPTURA_PROCESSOS.csv"
    )

    processadores_virtuais = psutil.cpu_count(logical=True) or 1

    escrever_cabecalho_hw = precisa_cabecalho(arquivo_hardware)
    escrever_cabecalho_proc = precisa_cabecalho(arquivo_processos)

    try:
        with open(
            arquivo_hardware,
            "a",
            newline="",
            encoding="utf-8-sig",
        ) as arquivo_hw, open(
            arquivo_processos,
            "a",
            newline="",
            encoding="utf-8-sig",
        ) as arquivo_proc:

            escritor_hw = csv.writer(arquivo_hw, delimiter=";")
            escritor_proc = csv.writer(arquivo_proc, delimiter=";")

            if escrever_cabecalho_hw:
                escritor_hw.writerow(CABECALHO_HARDWARE)

            if escrever_cabecalho_proc:
                escritor_proc.writerow(CABECALHO_PROCESSOS)

            for numero_rodada in range(
                1,
                TOTAL_REGISTROS_LIMITE + 1,
            ):
                agora = datetime.now()

                data = agora.strftime("%d/%m/%Y")
                hora = agora.strftime("%H:%M:%S")

                # coleta somente os componentes cadastrados
                if "CPU" in componentes:
                    cpu_total_pct = psutil.cpu_percent(interval=1)
                else:
                    cpu_total_pct = ""
                    time.sleep(1)

                if "RAM" in componentes:
                    memoria = psutil.virtual_memory()
                    ram_total_pct = round(memoria.percent, 2)
                    ram_total_mb = round(
                        memoria.total / (1024 * 1024), 2
                    )
                else:
                    ram_total_pct = ""
                    ram_total_mb = ""

                if "DISCO" in componentes:
                    disco_total_pct = obter_uso_disco()
                else:
                    disco_total_pct = ""

                # coleta processos quando cpu ou ram estiver configurada
                if componentes.intersection({"CPU", "RAM"}):
                    linhas_processos = obter_processos(
                        numero_rodada,
                        identificador_pc,
                        data,
                        hora,
                        processadores_virtuais,
                        componentes,
                    )
                    qtd_processos = len(linhas_processos)
                else:
                    linhas_processos = []
                    qtd_processos = ""

                linha_hardware = [
                    numero_rodada,
                    identificador_pc,
                    data,
                    hora,
                    round(cpu_total_pct, 2) if cpu_total_pct != "" else "",
                    ram_total_pct,
                    ram_total_mb,
                    disco_total_pct,
                    qtd_processos,
                ]

                escritor_hw.writerow(linha_hardware)
                escritor_proc.writerows(linhas_processos)

                arquivo_hw.flush()
                arquivo_proc.flush()

                print(
                    f"rodada {numero_rodada}/"
                    f"{TOTAL_REGISTROS_LIMITE} | "
                    f"cpu: {cpu_total_pct if cpu_total_pct != '' else 'nao configurada'} | "
                    f"ram: {ram_total_pct if ram_total_pct != '' else 'nao configurada'} | "
                    f"disco: {disco_total_pct if disco_total_pct != '' else 'nao configurado'} | "
                    f"processos: {qtd_processos}"
                )

                if numero_rodada < TOTAL_REGISTROS_LIMITE:
                    time.sleep(INTERVALO_SEGUNDOS)

    except KeyboardInterrupt:
        print("\ncaptura interrompida manualmente")

    print("=" * 60)
    print("captura finalizada")
    print(f"hardware: {arquivo_hardware}")
    print(f"processos: {arquivo_processos}")
    print("=" * 60)


if __name__ == "__main__":
    main()