import csv
import os


ARQUIVO_CSV = "./captura_resumo.csv"


def mostrar_alerta(metrica, percentual, status):
    """
    Exibe uma mensagem diferente quando uma métrica estiver em nível alto ou crítico
    """

    if status == "CRITICO":
        print(
            f"ALERTA CRÍTICO: {metrica} está em "
            f"{percentual}% de utilização!"
        )

    elif status == "ALTO":
        print(
            f"ALERTA: {metrica} está em "
            f"{percentual}% de utilização."
        )


# Verifica se o arquivo existe antes de tentar abri-lo
if not os.path.exists(ARQUIVO_CSV):
    print("=" * 60)
    print("ERRO NA LEITURA")
    print("=" * 60)
    print(f"O arquivo {ARQUIVO_CSV} não foi encontrado.")
    print("Execute primeiro o arquivo captura.py.")
    print("=" * 60)

else:
    try:
        # Abre o arquivo no modo "r"(leitura)
        with open(
            ARQUIVO_CSV,
            "r",
            newline="",
            encoding="utf-8-sig"
        ) as arquivo_csv:

            # O DictReader utiliza os nomes presentes no cabeçalho para acessar cada coluna
            leitor = csv.DictReader(
                arquivo_csv,
                delimiter=";"
            )

            quantidade_capturas = 0

            print("=" * 60)
            print("HISTÓRICO DE CAPTURAS — MONITOR ORE")
            print("=" * 60)

            # Percorre todas as capturas armazenadas
            for captura in leitor:
                quantidade_capturas += 1

                print()
                print("-" * 60)
                print(f"CAPTURA {quantidade_capturas}")
                print("-" * 60)

                # Exibe a origem da captura
                print(
                    f"Torre            : "
                    f"{captura['identificador_torre']}"
                )

                print(
                    f"Servidor         : "
                    f"{captura['identificador_servidor']}"
                )

                print(
                    f"Data e hora      : "
                    f"{captura['data']} às {captura['hora']}"
                )

                print(
                    f"CPU total        : "
                    f"{captura['cpu_total_percentual']}% "
                    f"[{captura['cpu_total_status']}]"
                )

                print(
                    f"RAM              : "
                    f"{captura['ram_percentual']}% "
                    f"[{captura['ram_status']}]"
                )

                print(
                    f"Disco            : "
                    f"{captura['disco_percentual']}% "
                    f"[{captura['disco_status']}]"
                )

                print(
                    f"CPU de maior uso : "
                    f"CPU {captura['cpu_maior_uso']} com "
                    f"{captura['maior_uso_cpu_percentual']}%"
                )

                print(
                    f"CPUs físicas     : "
                    f"{captura['processadores_fisicos']}"
                )

                print(
                    f"CPUs virtuais    : "
                    f"{captura['processadores_virtuais']}"
                )

                # Verifica se alguma métrica apresentou
                # utilização alta ou crítica.
                mostrar_alerta(
                    "CPU",
                    captura["cpu_total_percentual"],
                    captura["cpu_total_status"]
                )

                mostrar_alerta(
                    "RAM",
                    captura["ram_percentual"],
                    captura["ram_status"]
                )

                mostrar_alerta(
                    "Disco",
                    captura["disco_percentual"],
                    captura["disco_status"]
                )

            print()
            print("=" * 60)

            # Informa quando ainda não existem capturas
            if quantidade_capturas == 0:
                print(
                    "Nenhuma captura foi encontrada "
                    "no arquivo."
                )

            else:
                print(
                    f"Total de capturas lidas: "
                    f"{quantidade_capturas}"
                )

            print("=" * 60)

    except KeyError as erro:
        # Este erro acontece quando uma coluna esperada não está presente no arquivo
        print("=" * 60)
        print("ERRO NO FORMATO DO ARQUIVO")
        print("=" * 60)
        print(f"Coluna não encontrada: {erro}")
        print(
            "Apague o captura_resumo.csv antigo e execute "
            "novamente o captura.py."
        )
        print("=" * 60)
