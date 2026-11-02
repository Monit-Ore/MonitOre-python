import csv
import os
import glob
import unicodedata
from datetime import datetime
from getpass import getpass

import mysql.connector

PASTA_ENTRADA = "."
PASTA_SAIDA = "."

CONFIG_BANCO = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "me.nogue.201207!"),
    "database": os.getenv("DB_NAME", "monitore"),
    "port": int(os.getenv("DB_PORT", "3306")),
}


COMPONENTES = {
    "CPU": {
        "coluna": "CPU_TOTAL_PCT",
        "aliases": ["cpu", "processador"],
    },
    "RAM": {
        "coluna": "RAM_TOTAL_PCT",
        "aliases": ["ram", "memoria", "memoriaram"],
    },
    "DISCO": {
        "coluna": "DISCO_TOTAL_PCT",
        "aliases": ["disco", "armazenamento", "hd", "ssd"],
    },
}

def ler_csv(caminho):
    if not os.path.exists(caminho):
        raise FileNotFoundError(
            f"arquivo nao encontrado: {caminho}"
        )

    with open(
        caminho,
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=";")

        if not leitor.fieldnames:
            return []

        dados = []

        for linha in leitor:
            registro = {}

            for coluna, valor in linha.items():
                if coluna is not None:
                    registro[coluna.strip()] = (
                        valor.strip() if valor is not None else ""
                    )

            dados.append(registro)

        return dados


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


# CONVERSAO

def numero(valor):
    if valor is None:
        return None

    texto = str(valor).strip()

    if texto.upper() in ("", "NA", "N/A", "NONE"):
        return None

    try:
        return float(texto.replace(",", "."))
    except (ValueError, TypeError):
        return None


def normalizar_nome(valor):
    texto = str(valor).strip().lower()

    texto = unicodedata.normalize("NFD", texto)

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    return "".join(
        caractere
        for caractere in texto
        if caractere.isalnum()
    )


def identificar_componente(nome):
    nome_normalizado = normalizar_nome(nome)

    for componente, configuracao in COMPONENTES.items():
        for alias in configuracao["aliases"]:
            if alias in nome_normalizado:
                return componente

    return None


# CONSULTA AO MYSQL

def carregar_dados_banco():
    conexao = mysql.connector.connect(**CONFIG_BANCO)

    try:
        cursor = conexao.cursor(dictionary=True)

        # identifica o PC, a torre e a mineradora
        sql_pcs = """
            SELECT
                pc.id_pc_industrial,
                pc.hostname,
                pc.status_operacional,
                pc.fk_torre,
                t.codigo AS codigo_torre,
                t.nome AS nome_torre,
                t.fk_mineradora,
                e.razao_social AS mineradora
            FROM PC_Industrial pc
            INNER JOIN torre t
                ON t.id_torre = pc.fk_torre
            INNER JOIN empresa e
                ON e.id_empresa = t.fk_mineradora
        """

        cursor.execute(sql_pcs)
        registros_pcs = cursor.fetchall()

        # busca os limites de cada componente
        sql_limites = """
            SELECT
                la.fk_pc_industrial,
                c.nome AS componente,
                la.atencao,
                la.critico
            FROM limite_alerta la
            INNER JOIN componente c
                ON c.id_componente = la.fk_componente
        """

        cursor.execute(sql_limites)
        registros_limites = cursor.fetchall()

        return registros_pcs, registros_limites

    finally:
        conexao.close()



# IDENTIFICACAO DOS PCS E LIMITES


def montar_mapa_pcs(registros_pcs):
    # organiza os pc em um dicionário
    mapa = {}

    for pc in registros_pcs:
        hostname = pc.get("hostname")

        if hostname:
            mapa[str(hostname).strip()] = pc

    return mapa


def montar_mapa_limites(registros_limites):
    # organiza os limites para cada ipc
    mapa = {}

    for registro in registros_limites:
        id_pc = registro["fk_pc_industrial"]

        componente = identificar_componente(
            registro.get("componente", "")
        )

        if componente is None:
            print(
                "AVISO: componente nao reconhecido no banco:",
                registro.get("componente"),
            )
            continue

        mapa[(id_pc, componente)] = {
            "atencao": numero(registro.get("atencao")),
            "critico": numero(registro.get("critico")),
        }

    return mapa


def componentes_configurados(limites, id_pc):
    # quais conponentes estão configurados para cada computador
    return {
        componente
        for (pc_id, componente) in limites
        if pc_id == id_pc
    }


def buscar_limite(limites, id_pc, componente):
    return limites.get(
        (id_pc, componente),
        {
            "atencao": None,
            "critico": None,
        },
    )


# CLASSIFICACAO DE ALERTAS

def classificar_alerta(valor, limite):
    if valor is None:
        return "Sem dados"

    atencao = limite["atencao"]
    critico = limite["critico"]

    if atencao is None and critico is None:
        return "Sem limite"

    if critico is not None and valor >= critico:
        return "Crítico"

    if atencao is not None and valor >= atencao:
        return "Atenção"

    if atencao is None and critico is not None:
        return "Normal"

    return "Normal"



# TRATAMENTO DO HARDWARE

def tratar_hardware(dados, mapa_pcs, limites):
    historico = []
    alertas = []
    status_pcs = []
    resumo_por_pc = {}

    for registro in dados:
        hostname = registro.get("PC_INDUSTRIAL", "").strip()

        if not hostname:
            continue

        pc = mapa_pcs.get(hostname)

        if pc is None:
            print(
                f"AVISO: hostname '{hostname}' nao encontrado "
                "no banco de dados."
            )
            continue

        id_pc = pc["id_pc_industrial"]

        configurados = componentes_configurados(
            limites,
            id_pc,
        )

        registro_tratado = dict(registro)

        registro_tratado.update({
            "ID_PC_INDUSTRIAL": id_pc,
            "ID_TORRE": pc["fk_torre"],
            "CODIGO_TORRE": pc.get("codigo_torre"),
            "NOME_TORRE": pc.get("nome_torre"),
            "MINERADORA": pc.get("mineradora"),
        })

        historico.append(registro_tratado)

        chave = (id_pc, hostname)

        if chave not in resumo_por_pc:
            resumo_por_pc[chave] = {
                "pc": pc,
                "registros": [],
                "componentes": configurados,
            }

        resumo_por_pc[chave]["registros"].append(registro)

        # verifica somente os componentes cadastrados para o PC
        for componente in configurados:
            coluna = COMPONENTES[componente]["coluna"]

            valor = numero(registro.get(coluna))

            limite = buscar_limite(
                limites,
                id_pc,
                componente,
            )

            classificacao = classificar_alerta(
                valor,
                limite,
            )

            if classificacao in ("Atenção", "Crítico"):
                alertas.append({
                    "DATA": registro.get("DATA"),
                    "HORA": registro.get("HORA"),
                    "PC_INDUSTRIAL": hostname,
                    "ID_PC_INDUSTRIAL": id_pc,
                    "CODIGO_TORRE": pc.get("codigo_torre"),
                    "NOME_TORRE": pc.get("nome_torre"),
                    "MINERADORA": pc.get("mineradora"),
                    "COMPONENTE": componente,
                    "VALOR": valor,
                    "LIMITE_ATENCAO": limite["atencao"],
                    "LIMITE_CRITICO": limite["critico"],
                    "TIPO_ALERTA": classificacao,
                })

    # gera um resumo por PC
    resumos = []

    for (id_pc, hostname), agrupamento in resumo_por_pc.items():
        pc = agrupamento["pc"]
        registros = agrupamento["registros"]
        configurados = agrupamento["componentes"]

        resumo = {
            "PC_INDUSTRIAL": hostname,
            "ID_PC_INDUSTRIAL": id_pc,
            "CODIGO_TORRE": pc.get("codigo_torre"),
            "NOME_TORRE": pc.get("nome_torre"),
            "MINERADORA": pc.get("mineradora"),
            "TOTAL_REGISTROS": len(registros),
        }

        for componente, configuracao in COMPONENTES.items():
            coluna = configuracao["coluna"]

            if componente not in configurados:
                resumo[f"{componente}_MEDIA_PCT"] = ""
                resumo[f"{componente}_MIN_PCT"] = ""
                resumo[f"{componente}_MAX_PCT"] = ""
                continue

            valores = [
                numero(registro.get(coluna))
                for registro in registros
            ]

            valores = [
                valor for valor in valores
                if valor is not None
            ]

            if valores:
                resumo[f"{componente}_MEDIA_PCT"] = round(
                    sum(valores) / len(valores), 2
                )

                resumo[f"{componente}_MIN_PCT"] = round(
                    min(valores), 2
                )

                resumo[f"{componente}_MAX_PCT"] = round(
                    max(valores), 2
                )
            else:
                resumo[f"{componente}_MEDIA_PCT"] = ""
                resumo[f"{componente}_MIN_PCT"] = ""
                resumo[f"{componente}_MAX_PCT"] = ""

        resumos.append(resumo)

    # calcula o status com base na ultima captura
    for (id_pc, hostname), agrupamento in resumo_por_pc.items():
        pc = agrupamento["pc"]
        registros = agrupamento["registros"]
        configurados = agrupamento["componentes"]

        ultimo = registros[-1]

        classificacoes = []

        for componente in configurados:
            coluna = COMPONENTES[componente]["coluna"]

            valor = numero(ultimo.get(coluna))

            limite = buscar_limite(
                limites,
                id_pc,
                componente,
            )

            classificacoes.append(
                classificar_alerta(valor, limite)
            )

        if "Crítico" in classificacoes:
            status = "Alerta"
            tipo_alerta = "Crítico"

        elif "Atenção" in classificacoes:
            status = "Alerta"
            tipo_alerta = "Atenção"

        elif not classificacoes or all(
            item in ("Sem dados", "Sem limite")
            for item in classificacoes
        ):
            status = "Offline"
            tipo_alerta = "Sem dados"

        else:
            status = "Online"
            tipo_alerta = "Normal"

        status_pcs.append({
            "PC_INDUSTRIAL": hostname,
            "ID_PC_INDUSTRIAL": id_pc,
            "CODIGO_TORRE": pc.get("codigo_torre"),
            "NOME_TORRE": pc.get("nome_torre"),
            "MINERADORA": pc.get("mineradora"),
            "STATUS_PC": status,
            "TIPO_ALERTA": tipo_alerta,
            "DATA_ULTIMA_CAPTURA": ultimo.get("DATA"),
            "HORA_ULTIMA_CAPTURA": ultimo.get("HORA"),
        })

    return historico, resumos, alertas, status_pcs


# TRATAMENTO DOS PROCESSOS

def tratar_processos(dados, mapa_pcs):
    historico = []

    for registro in dados:
        hostname = registro.get("PC_INDUSTRIAL", "").strip()

        if not hostname:
            continue

        pc = mapa_pcs.get(hostname)

        if pc is None:
            print(
                f"AVISO: hostname '{hostname}' nao encontrado "
                "no banco de dados."
            )
            continue

        registro_tratado = dict(registro)

        registro_tratado.update({
            "ID_PC_INDUSTRIAL": pc["id_pc_industrial"],
            "ID_TORRE": pc["fk_torre"],
            "CODIGO_TORRE": pc.get("codigo_torre"),
            "NOME_TORRE": pc.get("nome_torre"),
            "MINERADORA": pc.get("mineradora"),
        })

        historico.append(registro_tratado)

    return historico


# RESUMO GERENCIAL

def gerar_resumo_gerencial(status_pcs, alertas):
    total_pcs = len(status_pcs)

    online = sum(
        1 for pc in status_pcs
        if pc["STATUS_PC"] == "Online"
    )

    em_alerta = sum(
        1 for pc in status_pcs
        if pc["STATUS_PC"] == "Alerta"
    )

    offline = sum(
        1 for pc in status_pcs
        if pc["STATUS_PC"] == "Offline"
    )

    total_atencao = sum(
        1 for alerta in alertas
        if alerta["TIPO_ALERTA"] == "Atenção"
    )

    total_critico = sum(
        1 for alerta in alertas
        if alerta["TIPO_ALERTA"] == "Crítico"
    )

    return [{
        "DATA_PROCESSAMENTO": datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S"
        ),
        "TOTAL_PCS_COM_CAPTURA": total_pcs,
        "PCS_ONLINE": online,
        "PCS_EM_ALERTA": em_alerta,
        "PCS_OFFLINE": offline,
        "TOTAL_ALERTAS_ATENCAO": total_atencao,
        "TOTAL_ALERTAS_CRITICOS": total_critico,
    }]


# EXECUCAO PRINCIPAL

def processar_captura(arquivo_hardware, arquivo_processos, identificador):
    print("-" * 60)
    print("processando captura:", identificador)

    dados_hardware = ler_csv(arquivo_hardware)

    dados_processos = (
        ler_csv(arquivo_processos)
        if arquivo_processos
        else []
    )

    print("registros de hardware:", len(dados_hardware))
    print("registros de processos:", len(dados_processos))

    print("consultando o banco de dados...")

    registros_pcs, registros_limites = carregar_dados_banco()

    mapa_pcs = montar_mapa_pcs(registros_pcs)
    limites = montar_mapa_limites(registros_limites)

    print("PCs encontrados no banco:", len(mapa_pcs))
    print("limites carregados:", len(limites))

    (
        historico_hardware,
        resumos_hardware,
        alertas,
        status_pcs,
    ) = tratar_hardware(
        dados_hardware,
        mapa_pcs,
        limites,
    )

    historico_processos = tratar_processos(
        dados_processos,
        mapa_pcs,
    )

    resumo_gerencial = gerar_resumo_gerencial(
        status_pcs,
        alertas,
    )

    # define o nome dos arquivos da camada ouro
    arquivos_saida = {
        "historico_hardware": f"{identificador}_HISTORICO_HARDWARE.csv",
        "historico_processos": f"{identificador}_HISTORICO_PROCESSOS.csv",
        "resumo_hardware": f"{identificador}_RESUMO_HARDWARE.csv",
        "status_pcs": f"{identificador}_STATUS_PCS.csv",
        "alertas": f"{identificador}_ALERTAS.csv",
        "resumo_gerencial": f"{identificador}_RESUMO_GERENCIAL.csv",
    }

    colunas_hardware = list(dict.fromkeys(
        [
            *(
                list(dados_hardware[0].keys())
                if dados_hardware else []
            ),
            "ID_PC_INDUSTRIAL",
            "ID_TORRE",
            "CODIGO_TORRE",
            "NOME_TORRE",
            "MINERADORA",
        ]
    ))

    colunas_processos = list(dict.fromkeys(
        [
            *(
                list(dados_processos[0].keys())
                if dados_processos else []
            ),
            "ID_PC_INDUSTRIAL",
            "ID_TORRE",
            "CODIGO_TORRE",
            "NOME_TORRE",
            "MINERADORA",
        ]
    ))

    colunas_resumo = [
        "PC_INDUSTRIAL",
        "ID_PC_INDUSTRIAL",
        "CODIGO_TORRE",
        "NOME_TORRE",
        "MINERADORA",
        "TOTAL_REGISTROS",
        "CPU_MEDIA_PCT",
        "CPU_MIN_PCT",
        "CPU_MAX_PCT",
        "RAM_MEDIA_PCT",
        "RAM_MIN_PCT",
        "RAM_MAX_PCT",
        "DISCO_MEDIA_PCT",
        "DISCO_MIN_PCT",
        "DISCO_MAX_PCT",
    ]

    colunas_status = [
        "PC_INDUSTRIAL",
        "ID_PC_INDUSTRIAL",
        "CODIGO_TORRE",
        "NOME_TORRE",
        "MINERADORA",
        "STATUS_PC",
        "TIPO_ALERTA",
        "DATA_ULTIMA_CAPTURA",
        "HORA_ULTIMA_CAPTURA",
    ]

    colunas_alertas = [
        "DATA",
        "HORA",
        "PC_INDUSTRIAL",
        "ID_PC_INDUSTRIAL",
        "CODIGO_TORRE",
        "NOME_TORRE",
        "MINERADORA",
        "COMPONENTE",
        "VALOR",
        "LIMITE_ATENCAO",
        "LIMITE_CRITICO",
        "TIPO_ALERTA",
    ]

    colunas_gerenciais = [
        "DATA_PROCESSAMENTO",
        "TOTAL_PCS_COM_CAPTURA",
        "PCS_ONLINE",
        "PCS_EM_ALERTA",
        "PCS_OFFLINE",
        "TOTAL_ALERTAS_ATENCAO",
        "TOTAL_ALERTAS_CRITICOS",
    ]

    salvar_csv(
        os.path.join(PASTA_SAIDA, arquivos_saida["historico_hardware"]),
        historico_hardware,
        colunas_hardware,
    )

    salvar_csv(
        os.path.join(PASTA_SAIDA, arquivos_saida["historico_processos"]),
        historico_processos,
        colunas_processos,
    )

    salvar_csv(
        os.path.join(PASTA_SAIDA, arquivos_saida["resumo_hardware"]),
        resumos_hardware,
        colunas_resumo,
    )

    salvar_csv(
        os.path.join(PASTA_SAIDA, arquivos_saida["status_pcs"]),
        status_pcs,
        colunas_status,
    )

    salvar_csv(
        os.path.join(PASTA_SAIDA, arquivos_saida["alertas"]),
        alertas,
        colunas_alertas,
    )

    salvar_csv(
        os.path.join(PASTA_SAIDA, arquivos_saida["resumo_gerencial"]),
        resumo_gerencial,
        colunas_gerenciais,
    )

    print("tratamento concluido")
    print("hardware tratado:", len(historico_hardware))
    print("processos tratados:", len(historico_processos))
    print("alertas identificados:", len(alertas))
    print("arquivos gerados:")

    for arquivo in arquivos_saida.values():
        print("-", arquivo)


def main():
    # procura e organiza as arquivos (mesma captura) 
    print("=" * 60)
    print("MONITORE - TRATAMENTO DOS DADOS")
    print("=" * 60)

    arquivos_hardware = glob.glob(
        os.path.join(
            PASTA_ENTRADA,
            "*_LIMPEZA_HARDWARE.csv",
        )
    )

    arquivos_processos = glob.glob(
        os.path.join(
            PASTA_ENTRADA,
            "*_LIMPEZA_PROCESSOS.csv",
        )
    )

    mapa_processos = {
        os.path.basename(arquivo).replace(
            "_LIMPEZA_PROCESSOS.csv",
            "",
        ): arquivo
        for arquivo in arquivos_processos
    }

    if not arquivos_hardware:
        print("nenhum arquivo de hardware limpo encontrado")
        return

    for arquivo_hardware in sorted(arquivos_hardware):
        nome = os.path.basename(arquivo_hardware)

        identificador = nome.replace(
            "_LIMPEZA_HARDWARE.csv",
            "",
        )

        arquivo_processos = mapa_processos.get(identificador)

        if arquivo_processos is None:
            print(
                "AVISO: arquivo de processos nao encontrado para:",
                identificador,
            )

        processar_captura(
            arquivo_hardware,
            arquivo_processos,
            identificador,
        )

    print("=" * 60)
    print("processamento finalizado")
    print("=" * 60)


if __name__ == "__main__":
    main()