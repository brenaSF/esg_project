import pdfplumber
import re
from typing import Dict, List, Any

class ESGDocumentLoader:
    def __init__(self, x_tolerance=3, y_tolerance=3):
        self.x_tolerance = x_tolerance
        self.y_tolerance = y_tolerance

        self.keywords_esg = ["gri", "405-1", "quadro", "gênero", "raça", "pcd", 
                             "diversidade", "idade", "%"]

    def _extrair_texto_estruturado(self, page):
        area_util = page.within_bbox((55, 40, page.width - 40, page.height - 40)) 
        # Em vez de ordenar por X primeiro, vamos ordenar por Y (linha)
        words = area_util.extract_words(x_tolerance=3, y_tolerance=3)
        
        if not words: return ""

        # Agrupar por linhas primeiro (eixo Y)
        linhas = {}
        for w in words:
            y = round(w['top'])
            encontrou_linha = False
            for r_y in linhas.keys():
                if abs(y - r_y) <= 3: # Tolerância para mesma linha
                    linhas[r_y].append(w)
                    encontrou_linha = True
                    break
            if not encontrou_linha:
                linhas[y] = [w]

        # Montar o texto linha por linha
        texto_final = []
        for y in sorted(linhas.keys()):
            # Ordena as palavras dentro da linha pelo X
            linha_ordenada = sorted(linhas[y], key=lambda x: x['x0'])
            texto_linha = " ".join([w['text'] for w in linha_ordenada])
            texto_final.append(texto_linha)

        return "\n".join(texto_final)
    
    def _extract_tables_fast(self, page):
        try:
            settings = {
                "vertical_strategy": "text",   # Detecta colunas pelo alinhamento do texto
                "horizontal_strategy": "text", # Detecta linhas pelo alinhamento do texto
                "snap_y_tolerance": 4,         # Tolerância para textos levemente desalinhados
                "intersection_x_tolerance": 10 # Evita que números muito próximos virem a mesma célula
            }

            tables = page.extract_tables(settings)
            if not tables: return ""
            
            output = []
            for table in tables:
                # Só considera tabela se tiver mais de 1 coluna e pelo menos uma célula com número
                if len(table[0]) > 1: 
                    for row in table:
                        row_cleaned = [str(c).strip() if c else "0" for c in row]
                        if any(char.isdigit() for char in "".join(row_cleaned)): # Filtra linhas sem dados
                            output.append("| " + " | ".join(row_cleaned) + " |")
            
            return "\n".join(output)
        except:
            return ""

    def extract_all_text(self, pdf_path, empresa, ano):
        """
        Processa o PDF inteiro de forma otimizada.
        """
        dados_finais = {
            "metadata": {"empresa": empresa, "ano": ano, "tipo_extracao": "full_text"}, 
            "chunks": []
        }
        
        with pdfplumber.open(pdf_path) as pdf:
            total_paginas = len(pdf.pages)
            
            for i, page in enumerate(pdf.pages):
                num_pagina = i + 1
                
                # 1. Extrai o texto limpo 
                texto_pag = self._extrair_texto_estruturado(page)
                
                if not texto_pag.strip():
                    continue

                texto_tabelas = self._extract_tables_fast(page)

                # 3. Consolidação 
                # Se houver tabela,ela fica no topo do contexto do chunk
                if texto_tabelas:
                    contexto_final = f"{texto_tabelas}\n\n--- TEXTO DA PÁGINA ---\n\n{texto_pag}"
                else:
                    contexto_final = texto_pag

                tem_tabela = "|" in contexto_final

                chunk = {
                    "id": f"{empresa}_{ano}_pg{num_pagina}_{i}", # ID único obrigatório
                    "document": contexto_final.strip(),          # O conteúdo textual
                    "metadata": {
                        "source": f"pg_{num_pagina}",
                        "empresa": empresa,
                        "ano": ano,
                        "setor": "Social",                          # Categoria para filtros
                        "tipo": "corpo_texto",
                        "tem_tabela": tem_tabela            
                             
                    }
                }

                
                dados_finais["chunks"].append(chunk)
                
                if num_pagina % 10 == 0:
                    print(f"Progress: {num_pagina}/{total_paginas} páginas concluídas...")

        return dados_finais
