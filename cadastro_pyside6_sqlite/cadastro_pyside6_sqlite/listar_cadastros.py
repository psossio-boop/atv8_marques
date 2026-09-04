import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent / "cadastro.db"

if not db.exists():
    print("O banco ainda não existe. Execute primeiro: python main.py")
    raise SystemExit

conexao = sqlite3.connect(db)
cursor = conexao.execute("""
    SELECT id, nome, tipo_documento, documento, email, celular, cidade, estado
    FROM pessoas
    ORDER BY id DESC
""")

registros = cursor.fetchall()

if not registros:
    print("Nenhum cadastro encontrado.")
else:
    for registro in registros:
        print(registro)

conexao.close()
