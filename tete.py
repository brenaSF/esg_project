import pdfplumber


with pdfplumber.open("NEOENERGIA_2022.pdf") as pdf:
    p = pdf.pages[6] # página 7
    # Imprime as coordenadas x0 (esquerda) de todas as palavras
    print([w['x0'] for w in p.extract_words()[:10]])