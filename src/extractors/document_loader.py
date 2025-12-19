import pdfplumber
import pandas as pd
import re
import json


class ESGDocumentLoader:
    def __init__(self, configuracao, x_tolerance=3, y_tolerance=3):
        self.config = configuracao
        self.x_tolerance = x_tolerance
        self.y_tolerance = y_tolerance

    def _extrair_texto_estruturado(self, page):
        words = page.extract_words(x_tolerance=self.x_tolerance, y_tolerance=self.y_tolerance)
        if not words: return ""

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
            texto_final.append("\n".join(texto_col))

        return "\n\n[QUEBRA_DE_COLUNA]\n\n".join(texto_final)

    def extract_content(self,pdf_path, configuracao):
        dados_finais = {"metadata": {"empresa": "Bradesco", "ano": 2024}, "chunks": []}
        
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):

                texto_formatado = self._extrair_texto_estruturado(page)

                for gri_id, info in configuracao.items():
                    id_limpo = gri_id.replace("GRI ", "")
                    
                    if id_limpo in texto_formatado or any(k in texto_formatado.lower() for k in info["subtemas"]):
                        
  
                        pattern = r"(\d{1,3}(?:[\.,]\d+)?)\s*%"
                        matches = re.finditer(pattern, texto_formatado)
                        
                        for match in matches:
                  
                            janela = 70 
                            inicio = max(0, match.start() - janela)
                            fim = min(len(texto_formatado), match.end() + janela)
                            contexto = texto_formatado[inicio:fim].strip()

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
