import random
from datetime import date, timedelta

from ferramentas.ferramentas import GATILHOS

# igual ao TAMANHO_BLOCO do arquitetura.py: o modelo só enxerga os últimos 128 caracteres
TAMANHO_JANELA = 128

# as 4 primeiras disparam um gatilho (têm "que horas" ou "qual a hora"); as outras não,
# então nelas o Sirius precisa PEDIR a ferramenta
PERGUNTAS_HORA = [
    "que horas são?",
    "Que horas são agora?",
    "qual a hora?",
    "qual a hora agora?",
    "me diz o horário",
    "qual é o horário agora?",
    "qual é a hora?",
    "pode me dizer as horas?",
    "horas, por favor",
]
# {valor} é trocado pelo resultado da ferramenta, com .format (a f-string não serve aqui,
# porque o modelo de resposta é sorteado de uma lista, depois de o texto já existir).
# {valor} serve para qualquer ferramenta, por isso montar_exemplo é uma função só
RESPOSTAS_HORA = ["são {valor}.", "agora são {valor}.", "{valor}.", "no momento são {valor}."]

# as 5 primeiras disparam gatilho ("que dia", "qual a data"); as outras 5 não
PERGUNTAS_DATA = [
    "que dia é hoje?",
    "Que dia é hoje?",
    "qual a data?",
    "qual a data de hoje?",
    "em que dia estamos?",
    "qual é a data?",
    "me diz a data de hoje",
    "que data é hoje?",
    "pode me dizer a data?",
    "data de hoje, por favor",
]
RESPOSTAS_DATA = ["hoje é {valor}.", "{valor}.", "estamos em {valor}.", "a data de hoje é {valor}."]

# fatos que o Sirius pode ter guardado na memória. Os valores são inventados de propósito:
# o modelo precisa aprender a COPIAR o valor da linha de memória, não a decorar um
FATOS = {
    "nome": {
        "perguntas": ["qual é o meu nome?", "como eu me chamo?", "você sabe o meu nome?"],
        "respostas": ["o seu nome é {valor}.", "você se chama {valor}.", "{valor}."],
        "valores": ["Ana", "Bruno", "Carla", "Diego", "Marina", "Pedro", "Lucas", "Julia"],
    },
    "cidade": {
        "perguntas": ["onde eu moro?", "qual é a minha cidade?", "em que cidade eu moro?"],
        "respostas": ["você mora em {valor}.", "a sua cidade é {valor}.", "{valor}."],
        "valores": ["Recife", "Curitiba", "Salvador", "Belém", "Manaus", "Goiânia", "Natal", "Santos"],
    },
    "curso": {
        "perguntas": ["qual é o meu curso?", "o que eu estudo?", "em que curso eu estou?"],
        "respostas": ["o seu curso é {valor}.", "você estuda {valor}.", "{valor}."],
        "valores": ["Direito", "Medicina", "Engenharia", "Letras", "Física", "Computação", "Biologia", "Química"],
    },
    "linguagem": {
        "perguntas": ["qual linguagem eu uso?", "qual é a minha linguagem?", "que linguagem eu programo?"],
        "respostas": ["você usa {valor}.", "a sua linguagem é {valor}.", "{valor}."],
        "valores": ["Python", "Java", "Rust", "Go", "C", "Kotlin", "Ruby", "Julia"],
    },
    "projeto_principal": {
        "perguntas": ["qual é o meu projeto?", "qual é o meu projeto principal?", "em que projeto eu trabalho?"],
        "respostas": ["o seu projeto é {valor}.", "o projeto principal é {valor}.", "{valor}."],
        "valores": ["Sirius", "Atlas", "Orion", "Vega", "Lyra", "Polaris", "Nova", "Aurora"],
    },
}


def montar_exemplo(nome, perguntas, respostas, valor):
    # a parte comum a todas as ferramentas: nome = "hora" ou "data"; valor = o que a
    # ferramenta devolveria (ex.: "09:05")
    pergunta = random.choice(perguntas)
    resposta = random.choice(respostas).format(valor=valor)

    # o caminho não é escolhido na mão: é o mesmo teste que o detectar_gatilho faz.
    # any(...) = True se pelo menos uma frase de GATILHOS aparece na pergunta
    gatilho = any(frase in pergunta.lower() for frase in GATILHOS)

    if gatilho:
        # o programa já colocou o resultado depois da pergunta; o Sirius só lê
        linhas = [
            "usuario: " + pergunta,
            f"[resultado: {valor}]",
            "sirius: " + resposta,
        ]
    else:
        # sem gatilho, o Sirius pede a ferramenta e só depois recebe o resultado
        linhas = [
            "usuario: " + pergunta,
            f"sirius: [ferramenta: {nome}]",
            f"[resultado: {valor}]",
            "sirius: " + resposta,
        ]
    return "\n".join(linhas)


def exemplo_hora():
    # f"{n:02d}" escreve com 2 dígitos, completando com zero: 5 vira "05"
    hora = f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}"
    return montar_exemplo("hora", PERGUNTAS_HORA, RESPOSTAS_HORA, hora)


def exemplo_data():
    # data inicial + um número sorteado de dias: nunca dá uma data que não existe
    # (30 de fevereiro, por exemplo). 2555 dias cobrem de 2024 a 2030
    sorteada = date(2024, 1, 1) + timedelta(days=random.randint(0, 2555))
    data = sorteada.strftime("%d/%m/%Y")
    return montar_exemplo("data", PERGUNTAS_DATA, RESPOSTAS_DATA, data)


def exemplo_memoria():
    # o valor a copiar vem de uma linha de memória no começo do contexto, não de uma ferramenta.
    # while True: sorteia de novo até o exemplo caber na janela do modelo (descarta o que passa)
    while True:
        chave = random.choice(list(FATOS))
        fato = FATOS[chave]
        valor = random.choice(fato["valores"])
        pergunta = random.choice(fato["perguntas"])
        resposta = random.choice(fato["respostas"]).format(valor=valor)

        # de 0 a 2 memórias "distratoras" (outros assuntos): o modelo aprende a ESCOLHER a
        # linha da chave perguntada, não a copiar "a primeira linha"
        outras = [c for c in FATOS if c != chave]
        distratores = random.sample(outras, random.randint(0, 2))

        memorias = [f"{chave}: {valor}"]
        for c in distratores:
            memorias.append(f"{c}: {random.choice(FATOS[c]['valores'])}")
        random.shuffle(memorias)  # embaralha no lugar (devolve None); a certa não fica sempre em 1º

        exemplo = "\n".join(memorias + ["usuario: " + pergunta, "sirius: " + resposta])
        # +3 ids além do texto: o <BOS>, a quebra de linha final e o <EOS>
        if len(exemplo) + 3 <= TAMANHO_JANELA:
            return exemplo


if __name__ == "__main__":
    for _ in range(3):
        print(exemplo_hora())
        print()
    for _ in range(3):
        print(exemplo_data())
        print()
    for _ in range(3):
        print(exemplo_memoria())
        print()