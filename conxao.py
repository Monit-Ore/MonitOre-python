import mysql.connector
from getpass import getpass

usuario = input("usuário do mysql: ")
senha = getpass("senha do mysql: ")

try:
    conexao = mysql.connector.connect(
        host="54.86.221.86",
        port=3306,
        user=usuario,
        password=senha,
        database="monitore"
    )

    if conexao.is_connected():
        print("conexão com o banco monitore realizada com sucesso")

    conexao.close()

except mysql.connector.Error as erro:
    print(f"erro na conexão: {erro}")