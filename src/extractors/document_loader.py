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
        """
        Extrai texto ignorando as bordas (menus laterais e cabeçalhos).
        """
        largura = page.width
        altura = page.height
        
        # CROP: Ignora 80px da esquerda (menu), 40px do topo e 40px do rodapé
        # Formato: (x0, top, x1, bottom)
        area_util = page.within_bbox((55, 40, largura - 40, altura - 40)) 
        
        words = area_util.extract_words(x_tolerance=self.x_tolerance, y_tolerance=self.y_tolerance)
        if not words: return ""

        # Ordenação e agrupamento por colunas
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
                        linhas[r_y].append(w)
                        found = True
                        break
                if not found: 
                    linhas[y] = [w]
            
            texto_col = [" ".join([w['text'] for w in sorted(linhas[y], key=lambda x: x['x0'])]) 
                         for y in sorted(linhas.keys())]
            texto_final.append("\n".join(texto_col))

        return "\n\n[QUEBRA_DE_COLUNA]\n\n".join(texto_final)

    def _extract_tables_fast(self, page):
        """
        Extração de tabelas nativa do pdfplumber (Alta Performance).
        """
        try:
            tables = page.extract_tables()
            if not tables:
                return ""
            
            texto_tabelas = ""
            for table in tables:
                # Remove linhas totalmente vazias (None ou string vazia)
                linhas_limpas = [linha for linha in table if any(celula for celula in linha)]
                
                # Formata cada linha separando colunas por " | "
                linhas_str = [
                    " | ".join([str(celula).replace('\n', ' ') if celula else "---" for celula in linha]) 
                    for linha in linhas_limpas
                ]
                texto_tabelas += "\n\n[TABELA_DATA]\n" + "\n".join(linhas_str) + "\n"
            return texto_tabelas
        except Exception as e:
            print(f"Erro rápido na tabela: {e}")
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
                texto_tabelas = ""
                if any(k in texto_pag.lower() for k in self.keywords_esg):
                    texto_tabelas = self._extract_tables_fast(page)
                
                # 3. Consolidação do Chunk
                chunk = {
                    "indicador_id": "RAW_TEXT",
                    "chave": f"pg_{num_pagina}",
                    "valor": None,
                    "contexto": (texto_pag + texto_tabelas).strip(),
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