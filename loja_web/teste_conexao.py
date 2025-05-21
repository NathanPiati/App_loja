# import pyodbc
# try:
#     conn = pyodbc.connect(
#         'DRIVER={ODBC Driver 17 for SQL Server};'
#         'SERVER=DESKTOP-NTN\\SQLEXPRESS;'
#         'DATABASE=LojaDB;'
#         'UID=acessopython;'
#         'Trusted_Connection=yes;'
#     )

#     print("✅ Conexão bem-sucedida!")
#     conn.close()
# except Exception as e:
#     print("❌ Erro na conexão:")
#     print(e)


import mysql.connector

try:
    # Configuração da conexão
    conn = mysql.connector.connect(
        host="database-app.cfoi8wec06e3.us-east-1.rds.amazonaws.com",
        user="admin",
        password="Pakfat50",
        database="lojadb",
        port=3306
    )

    # Verificar se a conexão está ativa
    if conn.is_connected():
        print("Conexão com o MySQL estabelecida com sucesso!")
        print("Versão do servidor:", conn.get_server_info())
        
        # Obter o cursor apenas para verificar o banco de dados atual
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE()")
        db_name = cursor.fetchone()[0]
        print("Banco de dados conectado:", db_name)
        cursor.close()
    
    # Fechar a conexão
    conn.close()
    print("Conexão efetuada.")
    
except mysql.connector.Error as e:
    print("Erro na conexão com o MySQL:", e)

