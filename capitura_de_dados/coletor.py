from pathlib import Path
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request


PASTA_SAIDA = "dataset"
IDIOMAS = ["pt", "en"]
ARTIGOS_POR_IDIOMA = 300  # na hora de rodar dá para trocar: python coletor.py 5
MINIMO_CARACTERES = 3000  # artigo menor que isso (depois dos cortes) é esboço e é descartado
MINIMO_BYTES_PAGINA = 8000  # esboço descoberto ANTES de baixar o texto (tamanho da página)
RODADAS_POR_ARTIGO = 3  # sorteios de 20 páginas permitidos por artigo pedido
ERROS_SEGUIDOS_MAXIMOS = 8  # erros de rede seguidos antes de desistir
PAUSA = 1.0  # segundos de espera antes de cada pedido (a Wikipédia pede educação)
TENTATIVAS_POR_PEDIDO = 4  # quantas vezes repetir um pedido recusado com erro 429
ESPERA_INICIAL = 10  # segundos de espera depois do primeiro 429 (dobra a cada nova recusa)

# A Wikimedia pede que scripts se identifiquem com um contato. Escreva aqui o seu
# e-mail (ex.: "voce@exemplo.com"): sem contato o limite de pedidos costuma ser menor.
CONTATO = ""
USER_AGENT = "Sirius-LM/0.1 (projeto pessoal de estudo" + (f"; {CONTATO}" if CONTATO else "") + ")"

# Seções do fim do artigo: só listas de links e de livros, sem texto corrido
SECOES_FINAIS = {
    "referências", "referência", "notas", "notas e referências", "ver também",
    "ligações externas", "links externos", "bibliografia", "fontes",
    "leitura adicional", "leituras adicionais",
    "references", "notes", "notes and references", "see also", "external links",
    "bibliography", "sources", "further reading", "footnotes", "citations",
    "works cited",
}
TITULOS_IGNORADOS = ("lista de", "listas de", "list of", "lists of")

# Só estes caracteres entram: letras acentuadas comuns e pontuação. Nomes em russo,
# chinês, árabe etc. trariam centenas de caracteres raros e inchariam o vocabulário.
LETRAS_PERMITIDAS = "áàâãäåçéèêëíìîïñóòôõöúùûüýÿÁÀÂÃÄÅÇÉÈÊËÍÌÎÏÑÓÒÔÕÖÚÙÛÜÝß"
SIMBOLOS_PERMITIDOS = "–—‘’“”«»…°ºª€£"
# letras que não se decompõem em letra + acento, trocadas à mão
LETRAS_TROCADAS = {
    "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
    "ı": "i", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE",
}


class LimiteDeUso(Exception):
    pass


# a pausa cresce sozinha quando a Wikipédia pede para ir mais devagar
estado = {"pausa": PAUSA, "pedidos": 0}


# Pedidos
def pedir(idioma, parametros):
    url = f"https://{idioma}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(parametros)
    pedido = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    espera = ESPERA_INICIAL

    for tentativa in range(TENTATIVAS_POR_PEDIDO):
        time.sleep(estado["pausa"])
        estado["pedidos"] += 1

        try:
            with urllib.request.urlopen(pedido, timeout=30) as resposta:
                return json.loads(resposta.read().decode("utf-8"))
        except urllib.error.HTTPError as erro:
            if erro.code not in (429, 503):
                raise

            # 429 = "muitos pedidos". Se o servidor disse quanto esperar, vale o que ele disse.
            pedida = erro.headers.get("Retry-After", "") if erro.headers else ""
            if pedida.isdigit():
                espera = min(int(pedida), 120)

            estado["pausa"] = min(estado["pausa"] * 2, 10)

            if tentativa < TENTATIVAS_POR_PEDIDO - 1:
                print(idioma, f"-> a Wikipédia pediu para ir mais devagar (erro {erro.code}); esperando {espera} s")
                time.sleep(espera)
                espera = min(espera * 2, 120)

    raise LimiteDeUso("a Wikipédia continua recusando os pedidos (limite de uso).")


def lista_de_paginas(dados):
    paginas = dados["query"]["pages"]
    if isinstance(paginas, dict):
        paginas = list(paginas.values())
    return paginas


def sortear_candidatos(idioma):
    # um pedido só traz 20 páginas sorteadas com o tamanho de cada uma (sem o texto)
    dados = pedir(idioma, {
        "action": "query",
        "generator": "random",
        "grnnamespace": 0,  # só artigos (nada de páginas de discussão, usuários...)
        "grnlimit": 20,
        "prop": "info",
        "format": "json",
        "formatversion": 2,
    })

    candidatos = []
    for pagina in lista_de_paginas(dados):
        tamanho = pagina.get("length", MINIMO_BYTES_PAGINA)
        candidatos.append((pagina["pageid"], pagina["title"], tamanho))
    return candidatos


def buscar_texto(idioma, pagina_id):
    # texto completo só vem um artigo por pedido, por isso só pedimos os que valem a pena
    dados = pedir(idioma, {
        "action": "query",
        "pageids": pagina_id,
        "prop": "extracts",
        "explaintext": 1,  # texto puro, sem HTML
        "exsectionformat": "wiki",  # títulos de seção viram "== Título =="
        "format": "json",
        "formatversion": 2,
    })
    return lista_de_paginas(dados)[0].get("extract", "")


# Limpeza
def remover_formulas(texto):
    # fórmulas aparecem como "{\displaystyle ...}", com chaves dentro de chaves
    while True:
        inicio = texto.find("{\\displaystyle")
        if inicio < 0:
            return texto

        fim_linha = texto.find("\n", inicio)
        if fim_linha < 0:
            fim_linha = len(texto)

        nivel = 0
        fim = fim_linha  # se as chaves não fecharem, apaga só até o fim da linha
        for i in range(inicio, fim_linha):
            if texto[i] == "{":
                nivel += 1
            elif texto[i] == "}":
                nivel -= 1
                if nivel == 0:
                    fim = i + 1
                    break

        texto = texto[:inicio] + texto[fim:]


def cortar_secoes_finais(texto):
    linhas = []

    for linha in texto.split("\n"):
        titulo = re.fullmatch(r"=+\s*(.*?)\s*=+", linha.strip())

        if titulo:
            if titulo.group(1).casefold() in SECOES_FINAIS:
                break  # daqui para baixo é só lista de links e referências
            linha = titulo.group(1)  # "== História ==" vira "História"

        linhas.append(linha)

    return "\n".join(linhas)


def caractere_permitido(caractere):
    if caractere.isascii():
        return caractere.isprintable()
    return caractere in LETRAS_PERMITIDAS or caractere in SIMBOLOS_PERMITIDOS


def limpar_caracteres(texto):
    saida = []

    for caractere in unicodedata.normalize("NFC", texto):
        if caractere == "\n":
            saida.append(caractere)
        elif caractere.isspace():  # espaço sem quebra, tab etc. viram espaço comum
            saida.append(" ")
        elif caractere_permitido(caractere):
            saida.append(caractere)
        elif caractere in LETRAS_TROCADAS:
            saida.append(LETRAS_TROCADAS[caractere])
        else:
            # letra rara com acento (ř, ğ, ş...): vira a letra sem acento; o resto é apagado
            sem_acento = unicodedata.normalize("NFKD", caractere)
            sem_acento = "".join(c for c in sem_acento if c.isascii() and c.isalpha())
            if len(sem_acento) == 1:
                saida.append(sem_acento)

    texto = "".join(saida)
    # parênteses que ficaram vazios porque o nome em outro alfabeto foi apagado:
    # "( )", "(; )" e "(em russo: )"
    texto = re.sub(r"\(\s*[;,:.\-–]*\s*\)", "", texto)
    texto = re.sub(r"\([^()]*[:;,]\s*\)", "", texto)
    texto = re.sub(r"([:;,])\s*[;,]", r"\1", texto)  # "russo: , Kyiv" -> "russo: Kyiv"
    texto = re.sub(r" {2,}", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def preparar_texto(titulo, extrato):
    corpo = remover_formulas(extrato)
    corpo = cortar_secoes_finais(corpo)
    corpo = limpar_caracteres(corpo)
    return limpar_caracteres(titulo), corpo


# Coleta
def coletar(idioma, quantidade, pasta):
    aceitos = 0
    rodadas = 0
    caracteres = 0
    erros_seguidos = 0
    limitado = False
    pedidos_antes = estado["pedidos"]

    while aceitos < quantidade and rodadas < quantidade * RODADAS_POR_ARTIGO:
        rodadas += 1

        try:
            for pagina_id, titulo, tamanho in sortear_candidatos(idioma):
                if aceitos >= quantidade:
                    break
                if tamanho < MINIMO_BYTES_PAGINA:
                    continue
                if titulo.casefold().startswith(TITULOS_IGNORADOS):
                    continue

                arquivo = pasta / f"wiki_{idioma}_{pagina_id}.txt"
                if arquivo.exists():  # o sorteio repetiu um artigo que já temos
                    continue

                titulo, corpo = preparar_texto(titulo, buscar_texto(idioma, pagina_id))
                if len(corpo) < MINIMO_CARACTERES:
                    continue

                arquivo.write_text(titulo + "\n\n" + corpo, encoding="utf-8")
                aceitos += 1
                caracteres += len(corpo)
                print(f"{idioma} {aceitos}/{quantidade}: {titulo} ({len(corpo)} caracteres)")

            erros_seguidos = 0
        except LimiteDeUso as erro:
            print(idioma, "->", erro)
            limitado = True
            break
        except Exception as erro:
            erros_seguidos += 1
            print(idioma, "-> erro no pedido:", erro)
            if erros_seguidos >= ERROS_SEGUIDOS_MAXIMOS:
                print(idioma, "-> muitos erros seguidos, parando. Confira a internet.")
                break

    return aceitos, estado["pedidos"] - pedidos_antes, caracteres, limitado


def main():
    quantidade = ARTIGOS_POR_IDIOMA
    if len(sys.argv) > 1:
        try:
            quantidade = int(sys.argv[1])
        except ValueError:
            print("Use um número inteiro, por exemplo: python coletor.py 5")
            return

    pasta = Path(PASTA_SAIDA)
    if not pasta.exists():
        print("Pasta de saída não encontrada:", pasta)
        print("Rode de dentro da pasta capitura_de_dados.")
        return

    resumo = []
    limitado = False
    for idioma in IDIOMAS:
        aceitos, pedidos, caracteres, limitado = coletar(idioma, quantidade, pasta)
        resumo.append((idioma, aceitos, pedidos, caracteres))
        if limitado:
            break  # o limite vale para todos os idiomas: não adianta insistir no próximo

    print()
    for idioma, aceitos, pedidos, caracteres in resumo:
        print(idioma, ":", aceitos, "artigos salvos,", caracteres, "caracteres,", pedidos, "pedidos")

    if limitado:
        print("O que já foi baixado ficou salvo. Espere alguns minutos e rode de novo")
        print("(artigos que já existem são pulados). Veja também a constante CONTATO no topo.")
    elif sum(r[1] for r in resumo) > 0:
        print("Agora rode pipeline.py, tokenizer.py e, na pasta sirius, treinar.py.")


if __name__ == "__main__":
    main()