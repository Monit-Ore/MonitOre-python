import csv
import os

ARQUIVO_CSV = "./CAPTURA_FINALIZADA.csv"


def analisar_capturas(caminho_arquivo):
    if not os.path.exists(caminho_arquivo):
        print(f"arquivo '{caminho_arquivo}' nao encontrado.")
        return

    with open(caminho_arquivo, "r", encoding="utf-8-sig") as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=";")

        rodadas = {}

        # agrupamento das linhas por rodada
        for linha in leitor:
            if not linha or not linha.get("RODADA"):
                continue

            rodada_id = linha["RODADA"]
            if rodada_id not in rodadas:
                rodadas[rodada_id] = {
                    "info": {
                        "torre": linha["TORRE"],
                        "servidor": linha["SERVIDOR"],
                        "data": linha["DATA"],
                        "hora": linha["HORA"],
                        "cpu_total": float(linha["CPU_TOTAL_PCT"]),
                        "ram_total": float(linha["RAM_TOTAL_PCT"]),
                        "ram_mb": float(linha.get("RAM_TOTAL_MB", 0)),
                        "disco_total": float(linha["DISCO_TOTAL_PCT"]),
                    },
                    "processos": [],
                }

            rodadas[rodada_id]["processos"].append(
                {
                    "pid": linha["PID"],
                    "nome": linha["PROCESSO"],
                    "cpu_global": float(linha.get("PROC_CPU_GLOBAL_PCT", 0)),
                    "ram_pct": float(linha.get("PROC_RAM_PCT", 0)),
                    "ram_mb": float(linha.get("PROC_RAM_MB", 0)),
                }
            )

        # exibicao estruturada com top 5 de impacto
        for rodada_id, dados in rodadas.items():
            info = dados["info"]
            print("=" * 78)
            print(
                f"RODADA #{rodada_id} — {info['data']} as {info['hora']} | TORRE: {info['torre']} | SERVIDOR: {info['servidor']}"
            )
            print(
                f"USO GLOBAL: CPU: {info['cpu_total']:.2f}% | RAM: {info['ram_total']:.2f}% (Total: {info['ram_mb']:.0f} MB) | DISCO: {info['disco_total']:.2f}%"
            )
            print("-" * 78)
            print(
                f"{'PID':<8} {'PROCESSO':<24} {'USO CPU TOTAL':<16} {'RAM (%)':<10} {'RAM (MB)':<10}"
            )
            print("-" * 78)

            # ordena os processos pelo maior impacto real na cpu
            top_processos = sorted(
                dados["processos"], key=lambda p: p["cpu_global"], reverse=True
            )[:5]

            for proc in top_processos:
                print(
                    f"{proc['pid']:<8} "
                    f"{proc['nome'][:23]:<24} "
                    f"{proc['cpu_global']:>6.2f}%         "
                    f"{proc['ram_pct']:>6.2f}%   "
                    f"{proc['ram_mb']:>8.1f} MB"
                )
            print("=" * 78 + "\n")


if __name__ == "__main__":
    analisar_capturas(ARQUIVO_CSV)