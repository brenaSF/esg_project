import pdfplumber
import re
import tabula
import camelot

from typing import Dict, List, Any

class ESGDocumentLoader:
    def __init__(self, configuracao, x_tolerance=3, y_tolerance=3):
        self.config = configuracao
        self.x_tolerance = x_tolerance
        self.y_tolerance = y_tolerance
    
    def _extract_tables_per_page(
        self, 
        pdf_path: str, 
        page_number: int
    ) -> List[Dict[str, Any]]: # Mudamos para retornar apenas a lista daquela página
        """
        Extrai tabelas de UMA página específica. 
        Isso evita o pico de processamento (CPU) e uso de memória.
        """
        tables_list = []

        try:
            # Importante: pages=str(page_number) foca a CPU apenas no que importa agora
            # flavor="stream" é muito mais leve que "lattice", use se o PDF permitir
            cam_tables = camelot.read_pdf(
                pdf_path, 
                pages=str(page_number), 
                flavor="lattice"
            )
            
            for t in cam_tables:
                tables_list.append({
                    "source": "camelot_lattice",
                    "data": t.df.values.tolist(),
                })
                
        except Exception as e:
            print(f"Erro na extração de tabelas da pág {page_number}: {e}")
        
        return tables_list

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
    
    def extract_all_text(self, pdf_path, empresa, ano):
        dados_finais = {
            "metadata": {"empresa": empresa, "ano": ano, "tipo_extracao": "full_text"}, 
            "chunks": []
        }
        
        with pdfplumber.open(pdf_path) as pdf:
            # REMOVIDO: a chamada fora do loop que processava tudo de uma vez
            
            for i, page in enumerate(pdf.pages):
                num_pagina = i + 1
                print(f"Processando página {num_pagina}...")
                
                # 1. Extrai o texto estruturado da página (pdfplumber)
                texto_pag = self._extrair_texto_estruturado(page)
                
                # 2. Extrai as tabelas APENAS desta página (Camelot)
                # Retorna uma lista simples: [ {"source":..., "data":...}, ... ]
                tabelas_da_pagina = self._extract_tables_per_page(pdf_path, num_pagina)
                
                # 3. Formata as tabelas para texto
                texto_tabelas = ""
                if tabelas_da_pagina:
                    for tab in tabelas_da_pagina:
                        # tab["data"] já é a lista de listas (linhas da tabela)
                        linhas_tab = [" | ".join(map(str, linha)) for linha in tab["data"]]
                        texto_tabelas += "\n[TABELA_DATA]\n" + "\n".join(linhas_tab)

                # 4. Cria o chunk
                chunk = {
                    "indicador_id": "RAW_TEXT",
                    "chave": f"pg_{num_pagina}",
                    "valor": None,
                    "contexto": (texto_pag + texto_tabelas).strip(),
                    "pagina": num_pagina
                }
                
                dados_finais["chunks"].append(chunk)

        return dados_finais

    def extract_content(self,pdf_path, configuracao, empresa, ano):
        dados_finais = {"metadata": {"Empresa": empresa, "Ano": ano}, "chunks": []}
        
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
