import pyodbc
try:
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=DESKTOP-NTN\\SQLEXPRESS;'
        'DATABASE=LojaDB;'
        'UID=acessopython;'
        'Trusted_Connection=yes;'
    )

    print("✅ Conexão bem-sucedida!")
    conn.close()
except Exception as e:
    print("❌ Erro na conexão:")
    print(e)

# import pyodbc

# conn_str = (
#     "DRIVER={ODBC Driver 18 for SQL Server};"
#     "SERVER=DESKTOP-NTN\SQLEXPRESS;"
#     "DATABASE=LojaDB;"
#     "UID=DESKTOP-NTN;"
#     "PWD="
#     "TrustServerCertificate=yes;"
# )

# try:
#     conn = pyodbc.connect(conn_str)
#     print("Conectado com sucesso!")
#     conn.close()
# except Exception as e:
#     print("Erro na conexão:")
#     print(e)
