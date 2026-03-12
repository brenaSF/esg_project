import pdfplumber
import re
from typing import Dict, List, Any

class ESGDocumentLoader:
    def __init__(self, configuracao, x_tolerance=3, y_tolerance=3):
        self.config = configuracao
        self.x_tolerance = x_tolerance
        self.y_tolerance = y_tolerance
        # Palavras-chave que indicam presença de dados quantitativos ou tabelas GRI
        self.keywords_esg = ["gri", "405-1", "quadro", "gênero", "raça", "pcd", 
                             "diversidade", "idade", "emissões", "escopo", "%"]

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
            tables = page.extract_tables({
                "vertical_strategy": "lines", 
                "horizontal_strategy": "lines",
                "intersection_y_tolerance": 5, # Ajuda a não quebrar linhas de tabelas ESG
            })
            if not tables: return ""
            
            output = []
            for table in tables:
                for row in table:
                    # Limpa None e substitui por "0" ou "N/A"
                    row_cleaned = [str(c).replace("\n", " ").strip() if c else "0" for c in row]
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
                
                # 1. Extrai o texto limpo (Sem menus laterais)
                texto_pag = self._extrair_texto_estruturado(page)
                
                # Se a página for vazia após o crop, pula
                if not texto_pag.strip():
                    continue

                # 2. Decisão de Extração de Tabela (Otimização de Velocidade)
                # Só roda o extrator de tabela se a página parecer ter dados relevantes
                #texto_tabelas = ""
                #if any(k in texto_pag.lower() for k in self.keywords_esg):
                #    texto_tabelas = self._extract_tables_fast(page)
                
                # 3. Consolidação do Chunk

                # 2. Extração de Tabela PRIORITÁRIA
                texto_tabelas = self._extract_tables_fast(page)

                # 3. Consolidação Inteligente
                # Se houver tabela, colocamos ela no topo do contexto do chunk
                if texto_tabelas:
                    contexto_final = f"{texto_tabelas}\n\n--- TEXTO DA PÁGINA ---\n\n{texto_pag}"
                else:
                    contexto_final = texto_pag

                chunk = {
                    "indicador_id": "RAW_TEXT",
                    "chave": f"pg_{num_pagina}",
                    "valor": None,
                    "contexto": contexto_final.strip(),
                    "pagina": num_pagina,
                    "empresa": empresa,
                    "ano": ano
                }

                
                dados_finais["chunks"].append(chunk)
                
                if num_pagina % 10 == 0:
                    print(f"Progress: {num_pagina}/{total_paginas} páginas concluídas...")

        return dados_finais

    def extract_content(self, pdf_path, configuracao, empresa, ano):
        """
        Método de extração baseada em RegEx (pode ser usado em conjunto com o pipeline de IA).
        """
        dados_finais = {"metadata": {"Empresa": empresa, "Ano": ano}, "chunks": []}
        
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                texto_formatado = self._extrair_texto_estruturado(page)
                
                for gri_id, info in configuracao.items():
                    id_limpo = gri_id.replace("GRI ", "")
                    
                    # Checagem de ID ou subtemas no texto
                    if id_limpo in texto_formatado or any(k in texto_formatado.lower() for k in info["subtemas"]):
                        # Busca padrões de percentual
                        pattern = r"(\d{1,3}(?:[\.,]\d+)?)\s*%"
                        matches = re.finditer(pattern, texto_formatado)
                        
                        for match in matches:
                            # Captura janela de contexto ao redor do número encontrado
                            janela = 100 
                            inicio = max(0, match.start() - janela)
                            fim = min(len(texto_formatado), match.end() + janela)
                            contexto_snippet = texto_formatado[inicio:fim].strip()

                            if id_limpo in contexto_snippet or any(k in contexto_snippet.lower() for k in info["subtemas"]):
                                try:
                                    valor_num = float(match.group(1).replace(".", "").replace(",", "."))
                                    
                                    chunk = {
                                        "indicador_id": gri_id,
                                        "chave": info["id_dashboard"],
                                        "valor": valor_num,
                                        "contexto": f"...{contexto_snippet}...",
                                        "pagina": i + 1
                                    }
                                    dados_finais["chunks"].append(chunk)
                                except ValueError:
                                    continue

        return dados_finais