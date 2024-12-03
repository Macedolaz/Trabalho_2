import sqlite3

conn = sqlite3.connect('usuarios.db')
c = conn.cursor()


c.execute('DELETE FROM usuarios')
c.execute('DELETE FROM arquivos')

conn.commit()
conn.close()

print("Dados da tabela usuarios foram removidos.")