import pdfplumber
import pandas as pd
import re
import json

# 1. Configuração do Mapeamento (Dicionário de Contextos/Indicadores)
# Isso permite que o dashboard use chaves fixas independentemente do texto do PDF
CONFIG_ESG = {
    "GRI 405-1": {
        "id_dashboard": "DIVERSIDADE_QUADRO_SOCIAL",
        "categoria": "Social",
        "subtemas": ["mulheres", "gênero", "raça", "etnia", "idade", "pcd"],
        "unidade": "percentual"
    },
    "GRI 305-1": {
        "id_dashboard": "EMISSOES_ESCOPO_1",
        "categoria": "Ambiental",
        "subtemas": ["co2", "emissões", "gases", "efeito estufa"],
        "unidade": "tCO2e"
    },
       "GRI 205-1": {
        "id_dashboard": "ANTICORRUPCAO_OPERACOES",
        "categoria": "Governança",
        "subtemas": ["corrupção", "suborno", "integridade", "operações"],
        "unidade": "percentual"
    }
}

def extrair_texto_estruturado(page):
    words = page.extract_words(x_tolerance=3, y_tolerance=3)
    if not words: return ""

    # Clusterização por colunas (gap de 40px)
    words_sorted = sorted(words, key=lambda x: x['x0'])
    colunas = []
    if words_sorted:
        curr_col = [words_sorted[0]]
        for i in range(1, len(words_sorted)):
            if words_sorted[i]['x0'] - words_sorted[i-1]['x1'] > 20:
                colunas.append(curr_col)
                curr_col = []
            curr_col.append(words_sorted[i])
        colunas.append(curr_col)

    texto_final = []
    for col in colunas:
        linhas = {}
        for w in col:
            y = round(w['top'])
            found = False
            for r_y in linhas.keys():
                if abs(y - r_y) <= 3:
                    linhas[r_y].append(w); found = True; break
            if not found: linhas[y] = [w]
        
        texto_col = [" ".join([w['text'] for w in sorted(linhas[y], key=lambda x: x['x0'])]) 
                     for y in sorted(linhas.keys())]
        # O marcador abaixo impede que o contexto de uma coluna sangre para a outra
        texto_final.append("\n".join(texto_col))

    return "\n\n[QUEBRA_DE_COLUNA]\n\n".join(texto_final)

def processar_relatorio_esg_v2(pdf_path, configuracao):
    dados_finais = {"metadata": {"empresa": "Bradesco", "ano": 2024}, "chunks": []}
    
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            # NOVIDADE: Extração que respeita colunas melhor que o .extract_text() padrão
            texto_formatado = extrair_texto_estruturado(page)

            for gri_id, info in configuracao.items():
                # Busca flexível para IDs (ex: "205-1" ou "GRI 205")
                id_limpo = gri_id.replace("GRI ", "")
                
                # Se o indicador ou palavras-chave estão no texto da página
                if id_limpo in texto_formatado or any(k in texto_formatado.lower() for k in info["subtemas"]):
                    
                    # Regex para capturar o valor próximo ao contexto
                    # Ajustada para pegar números com vírgula ou ponto
                    pattern = r"(\d{1,3}(?:[\.,]\d+)?)\s*%"
                    matches = re.finditer(pattern, texto_formatado)
                    
                    for match in matches:
                        # Pegamos uma janela de texto MENOR e mais PRECISA para evitar misturar colunas
                        # Aqui você define o 'offset' de caracteres
                        janela = 70 
                        inicio = max(0, match.start() - janela)
                        fim = min(len(texto_formatado), match.end() + janela)
                        contexto = texto_formatado[inicio:fim].strip()

                        # Validação: Só salva se o indicador/tema estiver REALMENTE perto do número
                        if id_limpo in contexto or any(k in contexto.lower() for k in info["subtemas"]):
                            valor_num = float(match.group(1).replace(".", "").replace(",", "."))
                            
                            chunk = {
                                "indicador_id": gri_id,
                                "chave": info["id_dashboard"],
                                "valor": valor_num,
                                "contexto": f"...{contexto}...",
                                "pagina": i + 1
                            }
                            dados_finais["chunks"].append(chunk)

    return dados_finais





# --- Execução ---
pdf_path = "bradesco-relatorio-ESG-2024.pdf"

try:
    resultados = processar_relatorio_esg_v2(pdf_path, CONFIG_ESG)

    # CORREÇÃO 1: Criar o DataFrame apontando para a lista de chunks
    if resultados["chunks"]:
        df_final = pd.DataFrame(resultados["chunks"])
        
        # Adiciona a empresa e o ano do metadado como colunas (opcional, para facilitar no BI)
        df_final["empresa"] = resultados["metadata"]["empresa"]
        df_final["ano_relatorio"] = resultados["metadata"]["ano"]

        # CORREÇÃO 2: Salvar o JSON (isso geralmente já funciona, mas garantimos aqui)
        with open("data_chunks_esg_v2.json", "w", encoding="utf-8") as f:
            json.dump(resultados, f, indent=4, ensure_ascii=False)

        # CORREÇÃO 3: Salvar o Excel (usando o DataFrame correto)
        df_final.to_excel("dashboard_esg_mapeado_v2.xlsx", index=False)

        print(f"Sucesso! {len(df_final)} chunks de dados extraídos e mapeados.")
        
        # Ajuste no Print para as novas chaves
        print(df_final[["indicador_id", "valor", "pagina"]].head())
    else:
        print("Nenhum dado foi encontrado com os critérios atuais.")

except Exception as e:
    print(f"Erro no processamento: {e}")