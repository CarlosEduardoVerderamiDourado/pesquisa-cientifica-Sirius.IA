from pathlib import Path
import json
import re
import torch

PASTA = Path("capitura_de_dados") / "dataset_saida"
ARQUIVO_MODELO = "sirius_lm.pt"

# Tamanho do modelo. Treino e geração precisam usar os mesmos valores,
# porque o arquivo salvo (sirius_lm.pt) só serve para esta arquitetura.
TAMANHO_BLOCO = 32
DIM = 64
CABECAS = 4
N_BLOCOS = 3
DROPOUT = 0.2
TAM_CABECA = DIM // CABECAS

caractere_para_id = json.loads((PASTA / "vocab.json").read_text(encoding="utf-8"))

id_para_caractere = {}
for token, numero in caractere_para_id.items():
    id_para_caractere[numero] = token

VOCAB = len(caractere_para_id)


def encode(texto):
    ids = []
    # "<BOS>" e "<EOS>" viram um id só; o resto do texto, um id por caractere
    for pedaco in re.split(r"(<BOS>|<EOS>)", texto):
        if pedaco == "<BOS>" or pedaco == "<EOS>":
            ids.append(caractere_para_id[pedaco])
        else:
            for caractere in pedaco:
                ids.append(caractere_para_id.get(caractere, caractere_para_id["<UNK>"]))
    return ids


class Atencao(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.consulta = torch.nn.Linear(DIM, DIM, bias=False)
        self.chave = torch.nn.Linear(DIM, DIM, bias=False)
        self.valor = torch.nn.Linear(DIM, DIM, bias=False)
        self.projecao = torch.nn.Linear(DIM, DIM)
        self.descarta_pesos = torch.nn.Dropout(DROPOUT)
        self.descarta_saida = torch.nn.Dropout(DROPOUT)

    def forward(self, x):
        B, T, C = x.shape

        q = self.consulta(x).view(B, T, CABECAS, TAM_CABECA).transpose(1, 2)
        k = self.chave(x).view(B, T, CABECAS, TAM_CABECA).transpose(1, 2)
        v = self.valor(x).view(B, T, CABECAS, TAM_CABECA).transpose(1, 2)

        pesos = q @ k.transpose(-2, -1) / TAM_CABECA ** 0.5
        mascara = torch.tril(torch.ones(T, T))
        pesos = pesos.masked_fill(mascara == 0, float("-inf"))
        pesos = torch.softmax(pesos, dim=-1)
        pesos = self.descarta_pesos(pesos)

        saida = (pesos @ v).transpose(1, 2).reshape(B, T, C)
        return self.descarta_saida(self.projecao(saida))


class Bloco(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.norma1 = torch.nn.LayerNorm(DIM)
        self.atencao = Atencao()
        self.norma2 = torch.nn.LayerNorm(DIM)
        self.rede = torch.nn.Sequential(
            torch.nn.Linear(DIM, 4 * DIM),
            torch.nn.ReLU(),
            torch.nn.Linear(4 * DIM, DIM),
            torch.nn.Dropout(DROPOUT),
        )

    def forward(self, x):
        x = x + self.atencao(self.norma1(x))
        x = x + self.rede(self.norma2(x))
        return x


class SiriusLM(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.tabela_tokens = torch.nn.Embedding(VOCAB, DIM)
        self.tabela_posicoes = torch.nn.Embedding(TAMANHO_BLOCO, DIM)
        blocos = []
        for _ in range(N_BLOCOS):
            blocos.append(Bloco())
        self.blocos = torch.nn.ModuleList(blocos)
        self.norma_final = torch.nn.LayerNorm(DIM)
        self.saida = torch.nn.Linear(DIM, VOCAB)

    def forward(self, ids):
        T = ids.shape[1]
        x = self.tabela_tokens(ids) + self.tabela_posicoes(torch.arange(T))
        for bloco in self.blocos:
            x = bloco(x)
        x = self.norma_final(x)
        return self.saida(x)