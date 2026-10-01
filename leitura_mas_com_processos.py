import csv
import os
from collections import defaultdict

ARQUIVO_CSV = "./captura_mas_com_processos.csv"


def formatar_separador(caractere="=", tamanho=80):
    return caractere * tamanho


def ler_e_analisar_csv(caminho):
    if not os.path.exists(caminho):
        print(f"Erro: O arquivo '{caminho}' não foi encontrado.")
        print("Certifique-se de executar primeiro o script 'captura.py'.")
        return

    if os.path.getsize(caminho) == 0:
        print(f"Aviso: O arquivo '{caminho}' está vazio.")
        return

    total_registros = 0
    pids_unicos = set()
    processos_por_status = defaultdict(int)
    processos_por_alerta = defaultdict(int)
    maior_consumo = {
        "nome": "N/A",
        "pid": "N/A",
        "cpu": -1.0,
        "data": "",
        "hora": ""
    }

    ultimos_registros = []

    with open(caminho, mode="r", encoding="utf-8-sig") as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=";")

        # Validação do cabeçalho esperado
        campos_esperados = {"pid", "nome_processo", "cpu_processo_percentual", "cpu_classificacao", "status_processo"}
        if not campos_esperados.issubset(set(leitor.fieldnames or [])):
            print("Erro: O formato do cabeçalho no CSV não é compatível com o esperado.")
            return

        for linha in leitor:
            total_registros += 1
            pid = linha.get("pid", "")
            nome = linha.get("nome_processo", "desconhecido")
            status = linha.get("status_processo", "desconhecido")
            classificacao = linha.get("cpu_classificacao", "NORMAL")
            
            try:
                cpu = float(linha.get("cpu_processo_percentual", 0.0))
            except ValueError:
                cpu = 0.0

            pids_unicos.add(pid)
            processos_por_status[status] += 1
            processos_por_alerta[classificacao] += 1

            if cpu > maior_consumo["cpu"]:
                maior_consumo["cpu"] = cpu
                maior_consumo["nome"] = nome
                maior_consumo["pid"] = pid
                maior_consumo["data"] = linha.get("data", "")
                maior_consumo["hora"] = linha.get("hora", "")

            # Mantém em memória apenas os últimos 5 registros lidos
            ultimos_registros.append(linha)
            if len(ultimos_registros) > 5:
                ultimos_registros.pop(0)

    # Exibição do relatório consolidado
    print(formatar_separador())
    print("RELATÓRIO DE MONITORAMENTO DE PROCESSOS")
    print(f"Origem dos dados: {caminho}")
    print(formatar_separador())

    print(f"Total de amostras registradas: {total_registros}")
    print(f"Processos únicos identificados: {len(pids_unicos)}")

    print("\n" + formatar_separador("-"))
    print("DISTRIBUIÇÃO POR CLASSIFICAÇÃO DE CPU:")
    for status_alerta, qtd in sorted(processos_por_alerta.items(), key=lambda x: x[1], reverse=True):
        percentual = (qtd / total_registros) * 100 if total_registros else 0
        print(f" - {status_alerta:<12}: {qtd:>6} registros ({percentual:5.1f}%)")

    print("\n" + formatar_separador("-"))
    print("DISTRIBUIÇÃO POR STATUS DO PROCESSO:")
    for status_proc, qtd in sorted(processos_por_status.items(), key=lambda x: x[1], reverse=True):
        print(f" - {status_proc:<15}: {qtd:>6} ocorrências")

    print("\n" + formatar_separador("-"))
    print("PICO MÁXIMO DE CPU REGISTRADO:")
    if maior_consumo["cpu"] >= 0:
        print(f"Processo : {maior_consumo['nome']} (PID: {maior_consumo['pid']})")
        print(f"Consumo  : {maior_consumo['cpu']:.2f}%")
        print(f"Momento  : {maior_consumo['data']} às {maior_consumo['hora']}")
    else:
        print("Nenhum dado numérico válido para cálculo de pico.")

    print("\n" + formatar_separador("-"))
    print("ÚLTIMOS 5 REGISTROS DO ARQUIVO:")
    print(f"{'DATA/HORA':<20} {'PID':<8} {'PROCESSO':<25} {'CPU (%)':<10} {'STATUS'}")
    print(formatar_separador("-"))

    for reg in ultimos_registros:
        dh = f"{reg.get('data', '')} {reg.get('hora', '')}"
        pid = reg.get("pid", "")
        nome = reg.get("nome_processo", "")[:23]
        cpu = f"{reg.get('cpu_processo_percentual', '0')}%"
        alerta = reg.get("cpu_classificacao", "")
        print(f"{dh:<20} {pid:<8} {nome:<25} {cpu:<10} [{alerta}]")

    print(formatar_separador())


if __name__ == "__main__":
    ler_e_analisar_csv(ARQUIVO_CSV)