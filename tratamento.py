import csv
import os
from datetime import datetime
import mysql.connector

ARQUIVO_HARDWARE = "CAPTURA_HARDWARE_LIMPO.csv"
ARQUIVO_PROCESSOS = "CAPTURA_PROCESSOS_LIMPO.csv"

ARQUIVO_RESUMO_HARDWARE = "RESUMO_HARDWARE.csv"
ARQUIVO_HISTORICO_HARDWARE = "HISTORICO_HARDWARE.csv"
ARQUIVO_HISTORICO_PROCESSOS = "HISTORICO_PROCESSOS.csv"
ARQUIVO_STATUS_PCS = "STATUS_PCS.csv"
ARQUIVO_ALERTAS = "ALERTAS.csv"
ARQUIVO_RESUMO_GERENCIAL = "RESUMO_GERENCIAL.csv"


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
        "nome": "CPU",
    },
    "RAM": {
        "coluna": "RAM_TOTAL_PCT",
        "nome": "RAM",
    },
    "Disco": {
        "coluna": "DISCO_TOTAL_PCT",
        "nome": "Disco",
    },
}


def ler_csv(caminho):
    if not os.path.exists(caminho):
        raise FileNotFoundError(
            f"Arquivo nao encontrado: {caminho}"
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


def adicionar_historico(caminho, dados, colunas):
    """
    Acrescenta registros ao historico existente.
    Cria o arquivo com cabecalho caso ainda nao exista.
    """
    arquivo_novo = (
        not os.path.exists(caminho)
        or os.path.getsize(caminho) == 0
    )

    with open(
        caminho,
        "a",
        newline="",
        encoding="utf-8-sig",
    ) as arquivo:
        escritor = csv.DictWriter(
            arquivo,
            fieldnames=colunas,
            delimiter=";",
            extrasaction="ignore",
        )

        if arquivo_novo:
            escritor.writeheader()

        escritor.writerows(dados)


# ============================================================
# CONVERSAO DE VALORES
# ============================================================

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


def inteiro(valor):
    valor_convertido = numero(valor)

    if valor_convertido is None:
        return None

    return int(valor_convertido)


# ============================================================
# CONSULTA AO MYSQL
# ============================================================

def carregar_dados_banco():
    conexao = mysql.connector.connect(**CONFIG_BANCO)

    try:
        cursor = conexao.cursor(dictionary=True)

        # Identifica o PC, a torre e a mineradora.
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

        # Busca os limites de cada componente.
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


# ============================================================
# IDENTIFICACAO DOS PCS E LIMITES
# ============================================================

def montar_mapa_pcs(registros_pcs):
    mapa = {}

    for pc in registros_pcs:
        hostname = pc.get("hostname")

        if hostname:
            mapa[str(hostname).strip()] = pc

    return mapa


def montar_mapa_limites(registros_limites):
    mapa = {}

    for registro in registros_limites:
        chave_pc = registro["fk_pc_industrial"]
        componente = str(
            registro.get("componente", "")
        ).strip().lower()

        mapa[(chave_pc, componente)] = {
            "atencao": numero(registro.get("atencao")),
            "critico": numero(registro.get("critico")),
        }

    return mapa


def buscar_limite(limites, id_pc, componente):
    """
    Busca os limites cadastrados para um componente.
    """
    return limites.get(
        (id_pc, componente.lower()),
        {
            "atencao": None,
            "critico": None,
        },
    )


# ============================================================
# CLASSIFICACAO DE ALERTAS
# ============================================================

def classificar_alerta(valor, limite):
    if valor is None:
        return "Sem dados"

    atencao = limite["atencao"]
    critico = limite["critico"]

    if atencao is not None and valor >= atencao:
        if critico is not None and valor >= critico:
            return "Crítico"

        return "Atenção"

    # Se nao houver limite de atencao, utiliza o critico
    # como unico limite disponivel.
    if atencao is None and critico is not None:
        if valor >= critico:
            return "Crítico"

    return "Normal"


# ============================================================
# TRATAMENTO DO HARDWARE
# ============================================================

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
            }

        resumo_por_pc[chave]["registros"].append(registro)

        for componente, configuracao in COMPONENTES.items():
            coluna = configuracao["coluna"]
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

    # Gera um resumo por PC com base nas capturas processadas.
    resumos = []

    for (id_pc, hostname), agrupamento in resumo_por_pc.items():
        pc = agrupamento["pc"]
        registros = agrupamento["registros"]

        resumo = {
            "PC_INDUSTRIAL": hostname,
            "ID_PC_INDUSTRIAL": id_pc,
            "CODIGO_TORRE": pc.get("codigo_torre"),
            "NOME_TORRE": pc.get("nome_torre"),
            "MINERADORA": pc.get("mineradora"),
            "TOTAL_REGISTROS": len(registros),
        }

        for componente, configuracao in COMPONENTES.items():
            valores = [
                numero(r.get(configuracao["coluna"]))
                for r in registros
            ]

            valores = [
                valor for valor in valores
                if valor is not None
            ]

            if valores:
                resumo[f"{componente.upper()}_MEDIA_PCT"] = round(
                    sum(valores) / len(valores), 2
                )
                resumo[f"{componente.upper()}_MIN_PCT"] = round(
                    min(valores), 2
                )
                resumo[f"{componente.upper()}_MAX_PCT"] = round(
                    max(valores), 2
                )
            else:
                resumo[f"{componente.upper()}_MEDIA_PCT"] = ""
                resumo[f"{componente.upper()}_MIN_PCT"] = ""
                resumo[f"{componente.upper()}_MAX_PCT"] = ""

        resumos.append(resumo)

    # Status derivado das ultimas metricas capturadas por PC.
    for (id_pc, hostname), agrupamento in resumo_por_pc.items():
        pc = agrupamento["pc"]
        registros = agrupamento["registros"]
        ultimo = registros[-1]

        classificacoes = []

        for componente, configuracao in COMPONENTES.items():
            valor = numero(ultimo.get(configuracao["coluna"]))

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
        elif all(
            item == "Sem dados" for item in classificacoes
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


# ============================================================
# TRATAMENTO DOS PROCESSOS
# ============================================================

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


# ============================================================
# RESUMO GERENCIAL
# ============================================================

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


# ============================================================
# EXECUCAO PRINCIPAL
# ============================================================

def main():
    print("=" * 60)
    print("MONIT ORE - TRATAMENTO DOS DADOS")
    print("=" * 60)

    dados_hardware = ler_csv(ARQUIVO_HARDWARE)
    dados_processos = ler_csv(ARQUIVO_PROCESSOS)

    print("Registros de hardware:", len(dados_hardware))
    print("Registros de processos:", len(dados_processos))

    print("Consultando o banco de dados...")

    registros_pcs, registros_limites = carregar_dados_banco()

    mapa_pcs = montar_mapa_pcs(registros_pcs)
    limites = montar_mapa_limites(registros_limites)

    print("PCs encontrados no banco:", len(mapa_pcs))
    print("Limites carregados:", len(registros_limites))

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

    # Colunas adicionais dos arquivos tratados.
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

    salvar_csv(
        ARQUIVO_HISTORICO_HARDWARE,
        historico_hardware,
        colunas_hardware,
    )

    salvar_csv(
        ARQUIVO_HISTORICO_PROCESSOS,
        historico_processos,
        colunas_processos,
    )

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

    salvar_csv(
        ARQUIVO_RESUMO_HARDWARE,
        resumos_hardware,
        colunas_resumo,
    )

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

    salvar_csv(
        ARQUIVO_STATUS_PCS,
        status_pcs,
        colunas_status,
    )

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

    salvar_csv(
        ARQUIVO_ALERTAS,
        alertas,
        colunas_alertas,
    )

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
        ARQUIVO_RESUMO_GERENCIAL,
        resumo_gerencial,
        colunas_gerenciais,
    )

    print("-" * 60)
    print("Tratamento concluido.")
    print("Hardware tratado:", len(historico_hardware))
    print("Processos tratados:", len(historico_processos))
    print("Alertas identificados:", len(alertas))
    print("Arquivos gerados:")
    print("-", ARQUIVO_RESUMO_HARDWARE)
    print("-", ARQUIVO_HISTORICO_HARDWARE)
    print("-", ARQUIVO_HISTORICO_PROCESSOS)
    print("-", ARQUIVO_STATUS_PCS)
    print("-", ARQUIVO_ALERTAS)
    print("-", ARQUIVO_RESUMO_GERENCIAL)
    print("=" * 60)


if __name__ == "__main__":
    main()