import re
from datetime import datetime


def hora_atual():
    # datetime.now() = o momento atual do relógio do PC; strftime vira texto por um padrão:
    # %H = hora (00-23), %M = minutos; o ":" aparece como está
    return datetime.now().strftime("%H:%M")


def data_atual():
    # %d = dia, %m = mês, %Y = ano com 4 dígitos
    return datetime.now().strftime("%d/%m/%Y")


# nome -> função. Sem parênteses de propósito: guarda a função, não o resultado dela
FERRAMENTAS = {"hora": hora_atual, "data": data_atual}

# frase que o usuário escreve -> nome da ferramenta que o programa executa sozinho.
# frases (e não palavras soltas) para pegar menos coisa errada: "hora" pegaria "horário"
GATILHOS = {
    "que horas": "hora",
    "qual a hora": "hora",
    "que dia": "data",
    "qual a data": "data",
}


def executar_ferramenta(nome):
    if nome not in FERRAMENTAS:
        raise ValueError(f"ferramenta desconhecida: {nome!r} (use uma de {list(FERRAMENTAS)})")
    return FERRAMENTAS[nome]()  # busca a função pelo nome e chama


def achar_pedido(texto):
    # procura "[ferramenta: nome]" em qualquer lugar do texto.
    # \[ e \] = colchetes de verdade; \s* = zero ou mais espaços;
    # (\w+) = o nome (letras/números/_), que o group(1) recupera
    resultado = re.search(r"\[ferramenta:\s*(\w+)\]", texto)
    if resultado is None:
        return None  # não há pedido no texto
    return resultado.group(1)


def resolver_pedido(texto):
    # o ciclo inteiro: acha o pedido, executa e devolve uma linha pronta para o contexto.
    # sem pedido -> None. A mensagem de erro é curta de propósito: o contexto só tem 120 caracteres
    nome = achar_pedido(texto)
    if nome is None:
        return None
    try:
        valor = executar_ferramenta(nome)
        return f"[resultado: {valor}]"
    except ValueError:
        # um modelo pequeno vai pedir ferramentas que não existem; o erro vira texto
        # em vez de derrubar o programa
        return "[erro: ferramenta desconhecida]"


def detectar_gatilho(pergunta):
    # o PROGRAMA lê a pergunta do usuário; se ela contém uma frase de GATILHOS, já executa
    # a ferramenta e devolve a linha pronta para o contexto (sem esperar o modelo pedir)
    pergunta = pergunta.lower()  # "Que horas" e "que horas" passam a ser iguais
    for frase, nome in GATILHOS.items():
        if frase in pergunta:  # "in" entre textos: a frase aparece em qualquer lugar da pergunta
            return f"[resultado: {executar_ferramenta(nome)}]"
    return None  # nenhum gatilho: a pergunta segue só para o modelo


def responder(contexto, gerar, maximo_voltas=3):
    # gerar = qualquer função que recebe o contexto e devolve texto (o modelo, ou um falso).
    # maximo_voltas é a trava: sem ela, um modelo que pede ferramenta sem parar travaria tudo
    texto = gerar(contexto)
    for _ in range(maximo_voltas):
        resultado = resolver_pedido(texto)
        if resultado is None:
            return texto  # sem pedido: a resposta está pronta
        # devolve ao modelo: contexto antigo + o que ele escreveu + o resultado + novo "sirius:"
        contexto = contexto + " " + texto + "\n" + resultado + "\nsirius:"
        texto = gerar(contexto)
    return texto  # estourou a trava: devolve o último texto como está


if __name__ == "__main__":
    print(executar_ferramenta("hora"))
    print(executar_ferramenta("data"))
    try:
        executar_ferramenta("xpto")
    except ValueError as erro:
        print("Recusou:", erro)

    print(achar_pedido("vou ver [ferramenta: hora] agora"))
    print(achar_pedido("[ferramenta:data]"))
    print(achar_pedido("sem pedido nenhum"))

    print(resolver_pedido("vou ver [ferramenta: hora] agora"))
    print(resolver_pedido("sem pedido nenhum"))
    print(resolver_pedido("[ferramenta: xpto]"))

    def gerar_falso(contexto):
        # finge ser o modelo: pede a hora; quando já vê o resultado no contexto, responde
        if "[resultado:" in contexto:
            return "agora sei a hora"
        return "vou ver [ferramenta: hora]"

    def gerar_sempre_pede(contexto):
        # finge ser um modelo que pede ferramenta em toda volta (para testar a trava)
        return "[ferramenta: hora]"

    print(responder("usuario: que horas são?\nsirius:", gerar_falso))
    print(responder("usuario: oi\nsirius:", gerar_sempre_pede))

    print(detectar_gatilho("Que horas são?"))
    print(detectar_gatilho("qual a data de hoje?"))
    print(detectar_gatilho("me conte uma história"))