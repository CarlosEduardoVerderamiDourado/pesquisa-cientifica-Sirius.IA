import torch

ids = torch.tensor([0, 1, 2, 3])
alvos = torch.tensor([1, 2, 3, 4])

modelo = torch.nn.Sequential(
    torch.nn.Embedding(5, 3),
    torch.nn.Linear(3, 5),
)

otimizador = torch.optim.SGD(modelo.parameters(), lr=0.5)

for epoca in range(200):
    notas = modelo(ids)
    loss = torch.nn.functional.cross_entropy(notas, alvos)

    otimizador.zero_grad()
    loss.backward()
    otimizador.step()

    if (epoca + 1) % 20 == 0:
        print(f"Época: {epoca + 1:03d} | Loss: {loss.item():.4f}")

palpites = modelo(ids).argmax(dim=1)
print("Alvos:   ", alvos)
print("Palpites:", palpites)