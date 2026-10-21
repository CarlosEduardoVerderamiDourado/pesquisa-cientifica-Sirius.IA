from pathlib import Path
import json

PASTA_ENTRADA = "dataset_saida"
ARQUIVO_TREINO = "train.txt"


def extrair_txt(caminho):
    return caminho.read_text(encoding="utf-8", errors="replace")


caminho = Path(PASTA_ENTRADA) / ARQUIVO_TREINO
texto = extrair_txt(caminho)

vocabulario = sorted(set(texto))

tokens = ["<PAD>", "<UNK>", "<BOS>", "<EOS>"] + vocabulario

caractere_para_id = {}
for numero, token in enumerate(tokens):
    caractere_para_id[token] = numero

id_para_caractere = {}
for token, numero in caractere_para_id.items():
    id_para_caractere[numero] = token


def encode(texto):
    ids = []
    for caractere in texto:
        ids.append(caractere_para_id.get(caractere, caractere_para_id["<UNK>"]))
    return ids


def decode(ids):
    caracteres = []
    for numero in ids:
        caracteres.append(id_para_caractere[numero])
    return "".join(caracteres)


arquivo_vocab = Path(PASTA_ENTRADA) / "vocab.json"
arquivo_vocab.write_text(json.dumps(caractere_para_id, ensure_ascii=False), encoding="utf-8")

print("Caracteres distintos:", len(vocabulario))
print("Total de tokens:", len(tokens))
print("PAD:", caractere_para_id["<PAD>"], "| a:", caractere_para_id["a"])
print(id_para_caractere[70])
print(id_para_caractere[0])
print(len(id_para_caractere))
print(decode(encode(texto)) == texto)

caminho_validacao = Path(PASTA_ENTRADA) / "validation.txt"
validacao = extrair_txt(caminho_validacao)
print(decode(encode(validacao)) == validacao)
print(encode(validacao).count(caractere_para_id["<UNK>"]))

texto_json = arquivo_vocab.read_text(encoding="utf-8")
vocab_carregado = json.loads(texto_json)
print(vocab_carregado == caractere_para_id)