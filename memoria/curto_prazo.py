from collections import deque

LIMITE_MENSAGENS = 4
PAPEIS = ("usuario", "sirius")

# A caixa fica fora das funções: é uma só, compartilhada por todas elas.
caixa = deque(maxlen=LIMITE_MENSAGENS)


def adicionar(papel, texto):
    """Guarda uma mensagem. Se a caixa estiver cheia, a mais antiga sai."""
    if papel not in PAPEIS:
        raise ValueError(f"papel inválido: {papel!r} (use um de {PAPEIS})")
    caixa.append({"papel": papel, "texto": texto})


def ultimas():
    """Devolve as mensagens guardadas, da mais antiga para a mais nova."""
    return list(caixa)


def limpar():
    """Esvazia a caixa (por exemplo, ao começar uma conversa nova)."""
    caixa.clear()


if __name__ == "__main__":
    adicionar("usuario", "oi")
    adicionar("sirius", "olá")
    adicionar("usuario", "meu projeto é o Sirius")
    adicionar("sirius", "entendi")
    adicionar("usuario", "qual é o meu projeto?")
    adicionar("sirius", "Sirius")

    for mensagem in ultimas():
        print(f"{mensagem['papel']}: {mensagem['texto']}")
    print("Total guardado:", len(ultimas()))

    limpar()
    print("Depois de limpar:", len(ultimas()))

    try:
        adicionar("robo", "x")
    except ValueError as erro:
        print("Recusou:", erro)