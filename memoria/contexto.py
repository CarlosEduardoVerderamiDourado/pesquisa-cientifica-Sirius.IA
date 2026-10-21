from memoria.memoria import buscar_memorias
from memoria.curto_prazo import adicionar, ultimas

LIMITE_CONTEXTO = 120  # a janela do modelo é 128; a folga cobre o <BOS>


def formatar_memorias(memorias):
    # recebe a lista de dicionários (formato do buscar_memorias) e devolve um texto só,
    # com uma linha "chave: valor" por memória
    linhas = []
    for m in memorias:
        linhas.append(f"{m['chave']}: {m['valor']}")
    return "\n".join(linhas)  # lista vazia -> "" (texto vazio), sem tratar à parte


def formatar_mensagens(mensagens):
    # mesma ideia, para as mensagens da conversa: uma linha "papel: texto" por mensagem
    lista = []
    for m in mensagens:
        lista.append(f"{m['papel']}: {m['texto']}")
    return "\n".join(lista)


def juntar_partes(memorias, mensagens, pergunta):
    # monta o texto na ordem: memórias, mensagens recentes, pergunta nova.
    # termina com "sirius:" para o modelo continuar escrevendo a resposta
    partes = [
        formatar_memorias(memorias),
        formatar_mensagens(mensagens),
        f"usuario: {pergunta}",
        "sirius:",
    ]
    partes = [p for p in partes if p]  # tira as partes vazias (sem linha em branco)
    return "\n".join(partes)


def montar_contexto(memorias, mensagens, pergunta):
    mensagens = list(mensagens)# cópia: o pop abaixo não mexe na lista de quem chamou
    memorias = list(memorias)
    contexto = juntar_partes(memorias, mensagens, pergunta)

    # o limite é conferido aqui, uma vez, no TEXTO FINAL (len conta caracteres).
    # enquanto passar do limite e ainda houver mensagem, tira a mais antiga e remonta
    while len(contexto) > LIMITE_CONTEXTO and mensagens:
        mensagens.pop(0)  # posição 0 = a mensagem mais antiga
        contexto = juntar_partes(memorias, mensagens, pergunta)
    while len(contexto) > LIMITE_CONTEXTO and memorias:
        memorias.pop()
        contexto = juntar_partes(memorias, mensagens, pergunta)
    return contexto


def contexto_da_conversa(pergunta):
    # versão com dados reais: busca sozinha as memórias (banco) e as últimas mensagens (caixa)
    return montar_contexto(buscar_memorias(), ultimas(), pergunta)


if __name__ == "__main__":
    exemplo = [
        {"chave": "projeto_principal", "valor": "Sirius"},
        {"chave": "linguagem", "valor": "Python"},
    ]
    print(formatar_memorias(exemplo))
    print(repr(formatar_memorias([])))

    conversa = [
        {"papel": "usuario", "texto": "oi"},
        {"papel": "sirius", "texto": "olá"},
    ]
    print(formatar_mensagens(conversa))
    print("---")
    print(montar_contexto(exemplo, conversa, "qual é o meu projeto?"))
    print("---")
    print(montar_contexto([], [], "oi"))

    longa = [
        {"papel": "usuario", "texto": "oi"},
        {"papel": "sirius", "texto": "olá"},
        {"papel": "usuario", "texto": "meu projeto é o Sirius"},
        {"papel": "sirius", "texto": "entendi"},
    ]
    print("---")
    contexto = montar_contexto(exemplo, longa, "qual é o meu projeto?")
    print(contexto)
    print(len(contexto))

    print("--- dados reais ---")
    adicionar("usuario", "oi")
    adicionar("sirius", "olá")
    print(contexto_da_conversa("qual é o meu projeto?"))
    
    muitas = [{"chave": f"fato{i}", "valor": "a" * 20} for i in range(1, 6)]
    print("--- memórias demais ---")
    contexto = montar_contexto(muitas, [], "oi")
    print(contexto)
    print(len(contexto))