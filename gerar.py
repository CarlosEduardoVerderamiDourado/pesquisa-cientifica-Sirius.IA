import torch

from arquitetura import (
    ARQUIVO_MODELO,
    TAMANHO_BLOCO,
    SiriusLM,
    encode,
    id_para_caractere,
)

# Ajustes de amostragem. Mude aqui ou durante a execução (digite /ajuda).
CONFIG = {
    "temperatura": 0.7,  # 0 = greedy (sempre o caractere mais provável)
    "topk": 0,  # só os k mais prováveis podem ser sorteados (0 = desligado)
    "topp": 0.9,  # só os mais prováveis que somam p entram no sorteio (1 = desligado)
    "tamanho": 300,  # quantos caracteres gerar
}
TIPOS = {"temperatura": float, "topk": int, "topp": float, "tamanho": int}
LIMITES = {"temperatura": (0, 5), "topk": (0, 1000), "topp": (0.01, 1.0), "tamanho": (1, 5000)}
AJUDA = """Comandos (digite no lugar do começo do texto):
  /config              mostra os ajustes atuais
  /temperatura 0.6     0 = greedy; menor = mais seguro e mais repetitivo
  /topk 10             0 = desligado
  /topp 0.9            1 = desligado
  /tamanho 500         caracteres gerados"""

modelo = SiriusLM()
modelo.load_state_dict(torch.load(ARQUIVO_MODELO, map_location="cpu"))
modelo.eval()


def filtrar_topk(notas, k):
    k = min(k, notas.shape[-1])
    maiores, _ = torch.topk(notas, k)
    return notas.masked_fill(notas < maiores[:, -1:], float("-inf"))


def filtrar_topp(notas, p):
    ordenadas, indices = torch.sort(notas, descending=True, dim=-1)
    probabilidades = torch.softmax(ordenadas, dim=-1)
    acumulada = torch.cumsum(probabilidades, dim=-1)
    # tira quem só entraria depois de a soma já ter passado de p
    tirar = acumulada - probabilidades > p
    ordenadas = ordenadas.masked_fill(tirar, float("-inf"))
    # devolve as notas para a ordem original dos caracteres
    return torch.full_like(notas, float("-inf")).scatter(-1, indices, ordenadas)


def escolher(notas):
    # notas: as pontuações do próximo caractere, no formato (1, VOCAB)
    if CONFIG["temperatura"] <= 0:
        return notas.argmax(dim=-1, keepdim=True)  # greedy

    notas = notas / CONFIG["temperatura"]
    if CONFIG["topk"] > 0:
        notas = filtrar_topk(notas, CONFIG["topk"])
    if CONFIG["topp"] < 1.0:
        notas = filtrar_topp(notas, CONFIG["topp"])

    probabilidades = torch.softmax(notas, dim=-1)
    return torch.multinomial(probabilidades, num_samples=1)


def gerar(prompt, parar_em_linha=False):
    # devolve o prompt + o texto novo. parar_em_linha=True: para na primeira quebra de linha
    # (o terminal usa o padrão False e continua igual)
    # o treino viu cada documento começando em <BOS>, então o texto começa com ele
    contexto = torch.tensor([encode("<BOS>" + prompt)])
    texto_gerado = [prompt]

    with torch.no_grad():
        for _ in range(CONFIG["tamanho"]):
            janela = contexto[:, -TAMANHO_BLOCO:]
            notas = modelo(janela)[:, -1, :]

            proximo = escolher(notas)
            contexto = torch.cat([contexto, proximo], dim=1)

            caractere = id_para_caractere[proximo.item()]
            if caractere == "<EOS>":  # o modelo decidiu que o documento acabou
                break
            if parar_em_linha and caractere == "\n":  # acabou a linha da resposta
                break
            texto_gerado.append(caractere)

    return "".join(texto_gerado)


def gerar_resposta(contexto):
    # a função que o assistente usa: devolve só o que o modelo escreveu, sem o contexto.
    # gerar devolve contexto + texto novo; [len(contexto):] pula o contexto e fica o novo
    texto = gerar(contexto, parar_em_linha=True)
    return texto[len(contexto):].strip()


def mudar_ajuste(comando):
    partes = comando[1:].split()

    if partes == ["config"]:
        print("Ajustes:", CONFIG)
        return
    if len(partes) != 2 or partes[0] not in TIPOS:
        print(AJUDA)
        return

    nome = partes[0]
    try:
        valor = TIPOS[nome](partes[1])
    except ValueError:
        print("Valor inválido:", partes[1])
        return

    minimo, maximo = LIMITES[nome]
    if not minimo <= valor <= maximo:
        print(f"{nome} precisa estar entre {minimo} e {maximo}")
        return

    CONFIG[nome] = valor
    print("Ajustes:", CONFIG)


if __name__ == "__main__":
    # só roda quando você executa o gerar.py direto (python gerar.py);
    # quando outro arquivo faz "import gerar", o terminal interativo não abre
    print(f"Modelo carregado de {ARQUIVO_MODELO}. Digite /ajuda para ver como mudar os ajustes.")
    print("Ajustes:", CONFIG)

    while True:
        # lstrip: espaços colados antes do texto ou do comando (ao copiar e colar) são ignorados
        prompt = input("\nComeço do texto (Enter vazio para sair): ").lstrip()
        if prompt == "":
            break
        if prompt.startswith("/"):
            mudar_ajuste(prompt)
            continue
        print("\n" + gerar(prompt))