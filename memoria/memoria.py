import sqlite3
from pathlib import Path

# o banco fica ao lado deste arquivo (na pasta memoria), de onde quer que o programa rode
ARQUIVO_BANCO = Path(__file__).parent / "memoria.db"
CATEGORIAS = ("fato", "preferencia", "experiencia")


def conectar():
    # abre o banco; se o arquivo memoria.db não existir, ele é criado aqui
    return sqlite3.connect(ARQUIVO_BANCO)


def criar_tabela():
    conexao = conectar()
    # IF NOT EXISTS: só cria se ainda não existir, então pode rodar sempre sem erro
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS memorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            chave TEXT NOT NULL,
            valor TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conexao.commit()  # sem o commit a mudança some quando a conexão fecha
    conexao.close()


def salvar_memoria(categoria, chave, valor):
    if categoria not in CATEGORIAS:
        raise ValueError(f"categoria inválida: {categoria!r} (use uma de {CATEGORIAS})")

    chave = chave.strip()
    valor = valor.strip()
    if chave == "" or valor == "":
        raise ValueError("chave e valor não podem ser vazios")

    criar_tabela()  # garante que a tabela existe, mesmo na primeira vez
    conexao = conectar()
    # os "?" são preenchidos com a tupla: o banco trata chave e valor só como texto,
    # nunca como comando (por isso não se monta o SQL juntando strings)
    cursor = conexao.execute(
        "INSERT INTO memorias (categoria, chave, valor) VALUES (?, ?, ?)",
        (categoria, chave, valor),
    )
    conexao.commit()
    novo_id = cursor.lastrowid  # o id que o banco acabou de gerar
    conexao.close()
    return novo_id


def apagar_memoria(id_memoria):
    criar_tabela()
    conexao = conectar()
    # o WHERE limita o DELETE a uma linha; sem ele, a tabela inteira seria apagada.
    # (id_memoria,) tem vírgula de propósito: é uma tupla de um elemento só
    cursor = conexao.execute(
        "DELETE FROM memorias WHERE id = ?",
        (id_memoria,),
    )
    conexao.commit()
    apagadas = cursor.rowcount  # quantas linhas o DELETE removeu (0 = o id não existia)
    conexao.close()
    return apagadas > 0


def atualizar_memoria(id_memoria, novo_valor):
    novo_valor = novo_valor.strip()  # strip é método do texto: tira espaços das pontas
    if novo_valor == "":
        raise ValueError("valor não pode ser vazio")

    criar_tabela()
    conexao = conectar()
    # UPDATE tabela SET coluna = ? WHERE ...  (sem FROM). Dois "?" = dois valores na tupla,
    # na MESMA ordem: primeiro o novo valor, depois o id
    cursor = conexao.execute(
        "UPDATE memorias SET valor = ? WHERE id = ?",
        (novo_valor, id_memoria),
    )
    conexao.commit()
    atualizadas = cursor.rowcount  # 0 = o id não existia
    conexao.close()
    return atualizadas > 0


def buscar_memorias(categoria=None, chave=None):
    sql = "SELECT id, categoria, chave, valor, criado_em FROM memorias"
    filtros = []
    parametros = []

    if categoria is not None:
        filtros.append("categoria = ?")
        parametros.append(categoria)
    if chave is not None:
        filtros.append("chave = ?")
        parametros.append(chave)

    if filtros:
        sql += " WHERE " + " AND ".join(filtros)
    sql += " ORDER BY id DESC"  # as mais recentes primeiro

    criar_tabela()
    conexao = conectar()
    conexao.row_factory = sqlite3.Row  # cada linha vira algo que aceita linha["valor"]
    linhas = conexao.execute(sql, parametros).fetchall()
    conexao.close()
    return [dict(linha) for linha in linhas]


if __name__ == "__main__":
    criar_tabela()

    # confere o que foi criado: PRAGMA table_info devolve uma linha por coluna
    conexao = conectar()
    colunas = conexao.execute("PRAGMA table_info(memorias)").fetchall()
    conexao.close()

    print("Banco:", ARQUIVO_BANCO)
    print("Colunas da tabela memorias:")
    for _, nome, tipo, *_ in colunas:
        print(f"  {nome} ({tipo})")
    print("Memórias salvas:", len(buscar_memorias()))
    
    