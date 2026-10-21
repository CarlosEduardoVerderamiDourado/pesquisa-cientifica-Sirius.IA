from collections import Counter
from pathlib import Path
import random
import re
import unicodedata

import pymupdf


PASTA_ENTRADA = "dataset"
PASTA_SAIDA = "dataset_saida"
ARQUIVO_TREINO = "train.txt"
ARQUIVO_VALIDACAO = "validation.txt"
LIMITE_SUSPEITO = 0.10
PROPORCAO_VALIDACAO = 0.10
SEMENTE = 42
LINHAS_NUMERO_PAGINA = 3  # número de página: só nas 3 primeiras/últimas linhas da página
LINHAS_CABECALHO = 4  # cabeçalho/rodapé: quantas linhas do topo e do pé são comparadas
MINIMO_REPETICOES = 4  # quantas páginas precisam repetir a linha para ser cabeçalho/rodapé
MINIMO_CARACTERES_LINHA = 8  # linhas com menos caracteres (sem contar espaços) não são avaliadas
LIMITE_LETRAS = 0.5  # linha com menos letras que isso (fórmula, tabela de números) é removida
INICIO_DOCUMENTO = "<BOS>"
FIM_DOCUMENTO = "<EOS>"

palavras_comuns = {
    "de", "a", "o", "que", "e", "do", "da", "em", "um", "para",
    "com", "não", "uma", "os", "no", "se", "na", "por", "mais", "as",
    "dos", "como", "mas", "ao", "das", "ou",
    "the", "of", "and", "to", "in", "is", "that", "for", "it",
    "with", "was", "on", "are", "by", "this", "be", "or", "from", "an", "at",
}

# Ligaduras: o PDF devolve "fi", "fl"... como uma letra só (chr(0xFB01) é a de "fi").
LIGADURAS = {
    chr(0xFB00): "ff",
    chr(0xFB01): "fi",
    chr(0xFB02): "fl",
    chr(0xFB03): "ffi",
    chr(0xFB04): "ffl",
    chr(0xFB05): "st",
    chr(0xFB06): "st",
}

# Acentos que o PDF devolve como caractere separado, antes da letra.
# (escritos com \u para o editor não trocar o símbolo por engano)
ACENTOS_SOLTOS = {
    "\u00b4": ("\u0301", "aeiouAEIOU"),  # ´  -> á é í ó ú
    "\u02c6": ("\u0302", "aeoAEO"),      # ˆ  -> â ê ô
    "\u02dc": ("\u0303", "aoAO"),        # ˜  -> ã õ
    "\u00a8": ("\u0308", "uU"),          # ¨  -> ü
}


# Extração
def extrair_pdf(caminho):
    # "\f" marca onde uma página termina; a limpeza de cabeçalho/rodapé usa isso
    with pymupdf.open(caminho) as leitor:
        return "\f".join(pagina.get_text() for pagina in leitor)


def extrair_txt(caminho):
    return caminho.read_text(encoding="utf-8", errors="replace")


def extrair_texto(caminho):
    tipo = caminho.suffix.lower()

    if tipo == ".pdf":
        return extrair_pdf(caminho)
    if tipo == ".txt":
        return extrair_txt(caminho)

    print("Formato não suportado, pulando:", caminho.name)
    return None


# 1. Limpeza
def linha_para_comparar(linha):
    # "Vol. 12, p. 776" e "Vol. 12, p. 777" viram a mesma coisa: "Vol. #, p. #"
    return re.sub(r"\d+", "#", linha.strip())


def indices_das_bordas(linhas, profundidade):
    cheias = [i for i, linha in enumerate(linhas) if linha.strip()]
    return set(cheias[:profundidade] + cheias[-profundidade:])


def remover_cabecalhos_rodapes(texto):
    paginas = texto.split("\f")

    if len(paginas) < 2:  # .txt ou PDF de uma página: não há o que comparar
        return texto

    paginas = [pagina.split("\n") for pagina in paginas]
    minimo = max(MINIMO_REPETICOES, int(len(paginas) * 0.05))

    # em quantas páginas cada linha aparece no topo ou no pé
    repeticoes = Counter()
    for linhas in paginas:
        bordas = indices_das_bordas(linhas, LINHAS_CABECALHO)
        vistas = {linha_para_comparar(linhas[i]) for i in bordas}
        repeticoes.update(vistas)

    paginas_limpas = []
    for linhas in paginas:
        pontas = indices_das_bordas(linhas, LINHAS_NUMERO_PAGINA)
        bordas = indices_das_bordas(linhas, LINHAS_CABECALHO)
        mantidas = []

        for i, linha in enumerate(linhas):
            chave = linha_para_comparar(linha)
            tem_letras = len(re.findall(r"[^\W\d_]", linha)) >= 3

            if i in pontas and re.fullmatch(r"\d{1,4}", linha.strip()):  # número de página
                continue
            if i in bordas and tem_letras and repeticoes[chave] >= minimo:  # cabeçalho/rodapé
                continue

            mantidas.append(linha)

        paginas_limpas.append("\n".join(mantidas).strip("\n"))

    return "\n".join(paginas_limpas)


def juntar_hifenizacao(texto):
    # "aprendi-\nzado" -> "aprendizado" (só quando a próxima linha começa em minúscula)
    return re.sub(r"([^\W\d_])[-\u00ad]\n([a-zà-ú])", r"\1\2", texto)


def consertar_acentos(texto):
    for solto, (combinante, vogais) in ACENTOS_SOLTOS.items():
        for vogal in vogais:
            letra_certa = unicodedata.normalize("NFC", vogal + combinante)
            texto = texto.replace(solto + vogal, letra_certa)

    # o cedilha vem depois do c: "c¸" -> "ç"
    return texto.replace("c\u00b8", "ç").replace("C\u00b8", "Ç")


def trocar_ligaduras(texto):
    # PDFs guardam "fi", "fl"... como uma letra só; o modelo precisa ver as letras separadas
    for ligadura, letras in LIGADURAS.items():
        texto = texto.replace(ligadura, letras)
    return texto


def limpar_texto(texto):
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = "".join(
        caractere
        for caractere in texto
        if caractere in "\n\t" or not unicodedata.category(caractere).startswith("C")
    )
    return texto


def linha_de_sumario(linha):
    # "Introdução . . . . 12" e "Introdução.......12": 4 ou mais pontos seguidos
    # (com ou sem um espaço entre eles) é o pontilhado de sumário
    return re.search(r"(?:\.\s?){4,}", linha) is not None


def linha_sem_texto(linha):
    # fórmulas e tabelas de números: poucas letras entre os caracteres da linha
    caracteres = [c for c in linha if not c.isspace()]

    if len(caracteres) < MINIMO_CARACTERES_LINHA:
        return False

    letras = sum(c.isalpha() for c in caracteres)
    return letras / len(caracteres) < LIMITE_LETRAS


def remover_linhas_lixo(texto):
    mantidas = []
    removidas = 0

    for linha in texto.split("\n"):
        if linha_de_sumario(linha) or linha_sem_texto(linha):
            removidas += 1
        else:
            mantidas.append(linha)

    return "\n".join(mantidas), removidas


# 2. Normalização
def normalizar_texto(texto):
    texto = unicodedata.normalize("NFC", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


# 3. Remoção de duplicados
def chave_duplicidade(texto):
    return " ".join(texto.casefold().split())


# 4. Detecção de lixo
def proporcao_comuns(texto):
    palavras = re.findall(r"[^\W\d_]+", texto.casefold(), flags=re.UNICODE)

    if not palavras:
        return 0.0

    quantidade_comuns = sum(palavra in palavras_comuns for palavra in palavras)
    return quantidade_comuns / len(palavras)


def documento_suspeito(texto):
    return proporcao_comuns(texto) < LIMITE_SUSPEITO


# 6. Separação dos documentos entre treino e validação
def separar_documentos(documentos):
    documentos = documentos.copy()
    random.Random(SEMENTE).shuffle(documentos)

    if len(documentos) >= 2:
        quantidade_validacao = max(
            1, round(len(documentos) * PROPORCAO_VALIDACAO)
        )
        quantidade_validacao = min(quantidade_validacao, len(documentos) - 1)
        validacao = documentos[:quantidade_validacao]
        treino = documentos[quantidade_validacao:]
        return treino, validacao

    if len(documentos) == 1:
        palavras = documentos[0].split()
        ponto_corte = max(1, min(len(palavras) - 1, round(len(palavras) * 0.9)))

        if len(palavras) >= 2:
            return [" ".join(palavras[:ponto_corte])], [
                " ".join(palavras[ponto_corte:])
            ]

    return documentos, []


def marcar_documento(texto):
    # o tokenizer transforma <BOS> e <EOS> nos ids especiais (ver encode)
    return INICIO_DOCUMENTO + texto + FIM_DOCUMENTO


def salvar_texto(caminho, documentos):
    conteudo = "".join(marcar_documento(documento) for documento in documentos)
    Path(caminho).write_text(conteudo, encoding="utf-8")


def main():
    documentos = []
    chaves_vistas = set()
    suspeitos = 0
    duplicados = 0
    erros = 0
    linhas_removidas = 0

    pasta = Path(PASTA_ENTRADA)
    pasta_saida = Path(PASTA_SAIDA)

    if not pasta.exists():
        print("Pasta de entrada não encontrada:", pasta)
        return

    for caminho in sorted(pasta.rglob("*")):
        if not caminho.is_file():
            continue

        try:
            texto = extrair_texto(caminho)
        except Exception as erro:
            erros += 1
            print(caminho.name, "-> erro ao ler, pulando:", erro)
            continue

        if texto is None:
            continue

        texto = remover_cabecalhos_rodapes(texto)
        texto = juntar_hifenizacao(texto)
        texto = consertar_acentos(texto)
        texto = trocar_ligaduras(texto)
        texto = limpar_texto(texto)
        texto, removidas = remover_linhas_lixo(texto)
        texto = normalizar_texto(texto)
        linhas_removidas += removidas
        proporcao = proporcao_comuns(texto)

        print(
            caminho.name,
            "->",
            len(texto),
            "caracteres |",
            round(proporcao * 100, 1),
            "% palavras comuns |",
            removidas,
            "linhas de lixo removidas",
        )

        if documento_suspeito(texto):
            suspeitos += 1
            print("   suspeito, não entra no corpus")
            continue

        chave = chave_duplicidade(texto)
        if chave in chaves_vistas:
            duplicados += 1
            print("   duplicado, ignorado")
            continue

        chaves_vistas.add(chave)
        documentos.append(texto)

    # 5. Junção do corpus e geração dos arquivos
    treino, validacao = separar_documentos(documentos)

    pasta_saida.mkdir(parents=True, exist_ok=True)
    salvar_texto(pasta_saida / ARQUIVO_TREINO, treino)
    salvar_texto(pasta_saida / ARQUIVO_VALIDACAO, validacao)

    print()
    print("Aprovados:", len(documentos))
    print("Duplicados:", duplicados)
    print("Suspeitos:", suspeitos)
    print("Com erro de leitura:", erros)
    print("Linhas de lixo removidas:", linhas_removidas)
    print("Documentos de treino:", len(treino))
    print("Documentos de validação:", len(validacao))
    print("Arquivos gerados em", pasta_saida, ":", ARQUIVO_TREINO, "e", ARQUIVO_VALIDACAO)


if __name__ == "__main__":
    main()