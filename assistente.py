from memoria.contexto import contexto_da_conversa
from memoria.curto_prazo import adicionar, ultimas
from ferramentas.ferramentas import detectar_gatilho, responder


def conversar(pergunta, gerar):
    # o caminho inteiro de uma pergunta até a resposta.
    # gerar = a função que gera texto a partir do contexto (hoje um modelo falso, depois o Sirius-LM)

    # 1. o programa vê se a pergunta dispara uma ferramenta (ex.: "que horas são?")
    resultado = detectar_gatilho(pergunta)

    # 2. se disparou, o resultado vai colado logo depois da pergunta, em outra linha
    pergunta_completa = pergunta
    if resultado is not None:
        pergunta_completa = pergunta + "\n" + resultado

    # 3. monta o contexto: memórias do banco + conversa recente + pergunta (cortado em 120)
    contexto = contexto_da_conversa(pergunta_completa)

    # 4. gera a resposta; se o modelo pedir uma ferramenta, o responder resolve
    resposta = responder(contexto, gerar)

    # 5. só AGORA guarda na memória de curto prazo. Se guardasse antes, a pergunta
    # apareceria duas vezes no contexto (a caixa já a traria, e o contexto a junta de novo).
    # vai a pergunta original, sem o "[resultado: ...]" colado
    adicionar("usuario", pergunta)
    adicionar("sirius", resposta)
    return resposta


if __name__ == "__main__":
    vistos = []

    def gerar_falso(contexto):
        vistos.append(contexto)  # guarda o que o "modelo" recebeu, para conferir depois
        if "[resultado:" in contexto:
            return "obrigado, já tenho a informação"
        return "não sei"

    print(conversar("oi", gerar_falso))
    print(conversar("que horas são?", gerar_falso))
    print(len(ultimas()))
    print(repr(vistos[1]))