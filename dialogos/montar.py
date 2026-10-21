from pathlib import Path

from arquitetura import TAMANHO_BLOCO, caractere_para_id, encode

# os arquivos ficam ao lado deste, na pasta dialogos, de onde quer que o programa rode
PASTA = Path(__file__).parent
ENTRADA = PASTA / "exemplos.txt"
SAIDA = PASTA / "dialogos.txt"
ID_DESCONHECIDO = caractere_para_id["<UNK>"]


def ler_exemplos():
    # o arquivo tem um exemplo por bloco, separados por uma linha em branco
    texto = ENTRADA.read_text(encoding="utf-8")
    return texto.strip().split("\n\n")


def marcar(exemplo):
    # <BOS> no começo; a última linha termina com quebra de linha (o sinal de "acabou a
    # resposta", em que o gerar_resposta para); depois vem o <EOS>
    return "<BOS>" + exemplo + "\n<EOS>"


def main():
    documentos = []
    total_ids = 0
    total_desconhecidos = 0

    for numero, exemplo in enumerate(ler_exemplos(), start=1):
        documento = marcar(exemplo)
        ids = encode(documento)
        desconhecidos = ids.count(ID_DESCONHECIDO)

        avisos = []
        if len(ids) > TAMANHO_BLOCO:
            avisos.append(f"maior que a janela de {TAMANHO_BLOCO}")
        if desconhecidos > 0:
            avisos.append(f"{desconhecidos} caractere(s) desconhecido(s)")
        print(f"Exemplo {numero}: {len(ids)} ids" + (" <- " + "; ".join(avisos) if avisos else ""))

        documentos.append(documento)
        total_ids += len(ids)
        total_desconhecidos += desconhecidos

    # os documentos ficam colados, sem nada entre o <EOS> de um e o <BOS> do próximo
    # (igual ao train.txt do pipeline). newline="\n" evita que o Windows troque por \r\n
    SAIDA.write_text("".join(documentos), encoding="utf-8", newline="\n")

    print(f"\n{len(documentos)} exemplos, {total_ids} ids, {total_desconhecidos} desconhecidos")
    print("Escrito em:", SAIDA)


if __name__ == "__main__":
    main()