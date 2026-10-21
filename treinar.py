import shutil
import time
from pathlib import Path

import torch

from arquitetura import (
    ARQUIVO_MODELO,
    PASTA,
    TAMANHO_BLOCO,
    VOCAB,
    SiriusLM,
    encode,
)

TAMANHO_LOTE = 64
PASSOS = 10000
AVALIAR_A_CADA = 250
TAXA_DE_APRENDIZADO = 0.001  # treino do zero (o modelo pequeno usava 0.002; o grande pede menos)
CONTINUAR = True  # True: parte do sirius_lm.pt salvo, se ele existir
TAXA_AO_CONTINUAR = 0.001  # o modelo já está treinado: recomeça com uma taxa menor

# "cuda" = placa de vídeo, se o torch enxergar uma; senão "cpu"
device = "cuda" if torch.cuda.is_available() else "cpu"

texto = (PASTA / "train.txt").read_text(encoding="utf-8", errors="replace")
texto_val = (PASTA / "validation.txt").read_text(encoding="utf-8", errors="replace")

# o texto inteiro mora no device: os lotes montados por pegar_lote já nascem lá
dados = torch.tensor(encode(texto), device=device)
dados_val = torch.tensor(encode(texto_val), device=device)


def pegar_lote(origem):
    inicios = torch.randint(0, len(origem) - TAMANHO_BLOCO, (TAMANHO_LOTE,))
    x_blocos = []
    y_blocos = []
    for i in inicios:
        x_blocos.append(origem[i : i + TAMANHO_BLOCO])
        y_blocos.append(origem[i + 1 : i + TAMANHO_BLOCO + 1])
    return torch.stack(x_blocos), torch.stack(y_blocos)


modelo = SiriusLM().to(device)

continuando = CONTINUAR and Path(ARQUIVO_MODELO).exists()
if continuando:
    modelo.load_state_dict(torch.load(ARQUIVO_MODELO, map_location=device))
    shutil.copy(ARQUIVO_MODELO, "sirius_lm_antes.pt")  # cópia de segurança do modelo antigo

taxa = TAXA_AO_CONTINUAR if continuando else TAXA_DE_APRENDIZADO
otimizador = torch.optim.Adam(modelo.parameters(), lr=taxa)
# a taxa de aprendizado cai aos poucos: começa em "taxa" e termina em "taxa / 10"
agenda = torch.optim.lr_scheduler.CosineAnnealingLR(
    otimizador, T_max=PASSOS, eta_min=taxa / 10
)


def medir_loss(origem, repeticoes=50):
    modelo.eval()
    total = 0.0
    with torch.no_grad():
        for _ in range(repeticoes):
            x_lote, y_lote = pegar_lote(origem)
            notas = modelo(x_lote)
            loss = torch.nn.functional.cross_entropy(
                notas.reshape(-1, VOCAB), y_lote.reshape(-1)
            )
            total += loss.item()
    modelo.train()
    return total / repeticoes


print("Ids de treino:", len(dados), "| ids de validação:", len(dados_val))
print("Parâmetros:", sum(p.numel() for p in modelo.parameters()))
print("Dispositivo:", device)

melhor_val = float("inf")
if continuando:
    # só salva de novo se ficar melhor que o modelo carregado (200 lotes: menos ruído)
    melhor_val = medir_loss(dados_val, repeticoes=200)
    print(f"Continuando de {ARQUIVO_MODELO} | validação dele: {melhor_val:.4f}")

inicio = time.time()

for passo in range(PASSOS):
    x_lote, y_lote = pegar_lote(dados)

    notas = modelo(x_lote)
    loss = torch.nn.functional.cross_entropy(
        notas.reshape(-1, VOCAB), y_lote.reshape(-1)
    )

    otimizador.zero_grad()
    loss.backward()
    otimizador.step()
    agenda.step()

    if passo == 0 or (passo + 1) % AVALIAR_A_CADA == 0:
        loss_treino = medir_loss(dados)
        loss_val = medir_loss(dados_val)
        marca = ""
        if loss_val < melhor_val:
            melhor_val = loss_val
            torch.save(modelo.state_dict(), ARQUIVO_MODELO)
            marca = "  <- melhor até agora, salvo"
        print(
            f"Passo: {passo + 1:04d} | "
            f"Treino: {loss_treino:.4f} | "
            f"Validação: {loss_val:.4f} | "
            f"Taxa: {agenda.get_last_lr()[0]:.5f} | "
            f"Tempo: {time.time() - inicio:.0f}s{marca}"
        )

print(f"Melhor validação: {melhor_val:.4f} (modelo salvo em {ARQUIVO_MODELO})")