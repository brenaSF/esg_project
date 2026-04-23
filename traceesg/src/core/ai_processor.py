import re
import os
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.documents import Document
from src.core.parsers import formatar_para_numero
from src.core.config import Config
from src.core.prompt400 import DISCOVERY_PROMPT_TEMPLATE_400
from src.core.prompt300 import DISCOVERY_PROMPT_TEMPLATE_300
import json 
import time
import asyncio
from dotenv import load_dotenv
from langchain_classic.retrievers import MultiQueryRetriever
load_dotenv() 
import pandas as pd
VALOR_PADRAO = os.getenv("VALOR_PADRAO", "GRI_400") 

ADAPTIVE_QUERY_PROMPT = PromptTemplate(
    input_variables=["empresa", "ano"],
    template="""Com base nas métricas GRI 400 (Diversidade, Raça, Faixa Etária e Pessoal), 
    gere 5 buscas específicas para o relatório da {empresa} em {ano}.
    Exemplos de termos de busca:
    1. "Tabela de empregados por gênero e idade GRI 2-7 {ano}"
    2. "Quadro de colaboradores por raça e etnia {ano}"
    3. "Composição da alta governança e liderança {ano}"
    4. "Número total de empregados período integral e parcial"
    """
)


class ESGMetricProcessor:
    def __init__(self):
        self.model = ChatOpenAI(
            model_name=Config.MODEL_NAME, 
            temperature=0, 
            api_key=Config.OPENAI_API_KEY
        )
        self.embeddings = OpenAIEmbeddings(
            api_key=Config.OPENAI_API_KEY, 
            model=Config.EMBEDDING_MODEL
        )
        self.parser = JsonOutputParser()
        self.semaphore = asyncio.Semaphore(5)


    def _rerank_documents(self, query, docs_e_scores):
        """
        Reavalia os documentos trazidos pelo ChromaDB usando uma nota de 0 a 10.
        """
        reranked_docs = []
        
        # Ajustamos o prompt para pedir uma nota numérica
        rerank_prompt = PromptTemplate.from_template(
            "Como um auditor ESG, avalie de 0 a 10 a utilidade do trecho para responder: '{query}'\n"
            "Considere se há números, tabelas ou menções diretas aos indicadores.\n"
            "Responda APENAS o número da nota.\n\n"
            "Trecho: {context}"
        )
        
        chain = rerank_prompt | self.model
        
        for doc, score in docs_e_scores:
            try:
                # A LLM analisa o conteúdo e retorna uma nota
                veredicto = chain.invoke({"query": query, "context": doc.page_content}).content
                
                # Extrai o número da resposta (ex: "Nota: 8" vira 8.0)
                match = re.search(r'\d+', veredicto)
                if match:
                    score_relevancia = float(match.group())
                    
                    # Filtro de corte: só passa o que for relevante (nota >= 5)
                    if score_relevancia >= 5:
                        # O novo score combina a similaridade do Chroma com a "inteligência" da LLM
                        novo_score = score + (score_relevancia / 10)
                        reranked_docs.append((doc, novo_score))
            except Exception as e:
                print(f"Erro no re-ranking de um trecho: {e}")
                continue
                
        # Reordena pela nova pontuação combinada
        reranked_docs.sort(key=lambda x: x[1], reverse=True)
        return reranked_docs  
    
    async def convert_text_to_markdown_tables(self,raw_text: str) -> str:
        """
        Recebe o texto bruto extraído do PDF e utiliza o LLM para 
        reconstruir as tabelas em formato Markdown limpo.
        """
        llm = ChatOpenAI(temperature=0, model_name=self.model_name)
        
        template = """
        Você é um especialista em engenharia de dados ESG. Sua tarefa é converter o texto bruto extraído de um PDF 
        em tabelas Markdown organizadas. 
        
        Regras:
        1. Identifique se há múltiplas tabelas misturadas e separe-as com títulos (H3).
        2. Recupere a estrutura lógica (Linhas vs Colunas) mesmo que o texto esteja desalinhado.
        3. Preserve os valores exatos e os nomes das métricas (GRI, Categorias, anos).
        4. Se um dado parecer truncado ou ilegível, mantenha-o como está, mas tente organizar a linha.

        Texto Bruto:
        {text}

        Tabelas em Markdown:
        """
        
        prompt = PromptTemplate(template=template, input_variables=["text"])
        chain = prompt | llm
        
        response = await chain.ainvoke({"text": raw_text})
        return response.content


    def _salvar_log_discovery(self, empresa, ano, dados):
        nome_arquivo = f"discovery_{empresa}_{ano}_{int(time.time())}.json"
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
        print(f"✅ Log de descoberta salvo: {nome_arquivo}")


    def _detectar_tabela_no_texto(self,text: str) -> bool:
        """
        Detecta padrões que indicam que o texto bruto é uma tabela desalinhada.
        """
        padroes = [
            r"\d{4}\s+\d+",                 # Anos seguidos de números
            r"GRI\s+\d+",                   # GRI seguido de número
            r"\d+[.,]\d+%\s+\d+[.,]\d+%",   # Porcentagens lado a lado
            r"(Homens|Mulheres|Gênero|Raça|PCD|Até \d+ anos)", # Palavras-chave ESG
            r"\d{2,}\s+\d{2,}\s+\d{2,}",    # Sequência de pelo menos 3 números
            r"Total\s+\d+"                  # Palavra Total seguida de valor
        ]
        
        for p in padroes:
            if re.search(p, text, re.IGNORECASE | re.MULTILINE):
                return True
        return False


    def visualizar_chunks_busca(self, docs_recuperados, empresa, ano):
        """
        Exibe de forma organizada os chunks recuperados pelo retriever.
        Útil para validar se o MultiQuery está encontrando as tabelas GRI.
        """
        print(f"\n{'='*80}")
        print(f"📊 RELATÓRIO DE CHUNKS RECUPERADOS - {empresa} ({ano})")
        print(f"Total de chunks encontrados: {len(docs_recuperados)}")

        dados_para_exibicao = []

        for i, doc in enumerate(docs_recuperados):
            # Extraindo metadados (ajuste as chaves conforme seu parser/vectorstore)
            pagina = doc.metadata.get('page', 'N/A')
            fonte = doc.metadata.get('source', 'Documento')
            
            # Limpa o texto para visualização rápida (primeiros 200 caracteres)
            preview_texto = doc.page_content.replace('\n', ' ').strip()[:200] + "..."
            
            dados_para_exibicao.append({
                "ID": i + 1,
                "Página": pagina,
                "Conteúdo": preview_texto
            })

            # Print detalhado no console
            print(f"🔍 [Chunk {i+1}] | Página: {pagina}")
            print(f"Texto: {doc.page_content.strip()}")
            print("-" * 50)

        # Opcional: Retornar como DataFrame para melhor visualização em Notebooks
        df_chunks = pd.DataFrame(dados_para_exibicao)
        return df_chunks

    
    async def _processar_metrica_individual(self, metrica, dados, retriever, discovery_prompt, empresa, ano):
        """
        Função assíncrona para processar uma única métrica.
        """
        async with self.semaphore:
            try:
                # Lógica de Refinamento (Precise Extraction)
                if dados.get("valor") is None or "Omissão" in str(dados.get("status")):
                    query_focada = f"Valor numérico exato e tabela para a métrica {metrica} da {empresa} em {ano}"
                    
                    # O retriever.ainvoke é a versão assíncrona do invoke
                    docs_especificos = await retriever.ainvoke(query_focada)
                    
                    contextos_processados = []
                    for doc in docs_especificos:
                        conteudo_chunk = doc.page_content
                        if self._detectar_tabela_no_texto(conteudo_chunk):
                            # Chamada assíncrona para estruturação de tabela
                            #conteudo_chunk = await self.convert_text_to_markdown_tables(conteudo_chunk)
                            print("-----------------------")
                            print(conteudo_chunk)
                        contextos_processados.append(conteudo_chunk)
                    
                    contexto_focado = "\n\n".join(contextos_processados)
                    
                    # Executa a extração refinada
                    dados_refinados = await (discovery_prompt | self.model | self.parser).ainvoke({
                        "context": contexto_focado, 
                        "empresa": empresa, 
                        "ano": ano
                    })
                    
                    if metrica in dados_refinados:
                        dados = dados_refinados[metrica]

                # Formatação do resultado
                valor_final = dados.get("valor")
                return {
                    "Empresa": empresa,
                    "Ano": ano,
                    "Metrica": metrica,
                    "Valor": valor_final,
                    "Unidade": "Percentual (%)" if "%" in str(valor_final) else "Absoluto",
                    "Evidencia": dados.get("evidencia_texto", ""),
                    "Página": str(dados.get("página", "Não encontrada")),
                    "Status_Auditoria": "Pendente"
                }
            except Exception as e:
                print(f"❌ Erro na métrica {metrica}: {e}")
                return None

    async def _extrair_com_rag(self, vector_store, empresa, ano):
        # --- FASE 1: PLANEJAMENTO (O LLM define o que buscar com base no Prompt 400) ---
        print(f"📡 Fase 1: Planejando busca técnica para {empresa}...")
        
        # Seleção do Template base
        template_texto = DISCOVERY_PROMPT_TEMPLATE_400 if VALOR_PADRAO == "GRI_400" else DISCOVERY_PROMPT_TEMPLATE_300
        
        # O LLM analisa o seu prompt principal para saber o que procurar no VectorDB
        chain_planejamento = ADAPTIVE_QUERY_PROMPT | self.model
        plano_de_busca = await chain_planejamento.ainvoke({
            "template": template_texto,
            "empresa": empresa,
            "ano": ano
        })
        
        # --- FASE 2: EXECUÇÃO (Multi-Query baseada no plano) ---
        print(f"🔍 Fase 2: Executando Multi-Query orientado a métricas...")
        
        base_retriever = vector_store.as_retriever(
            search_kwargs={
                "k": 12, 
                "filter": {
                    "$and": [
                        {"empresa": {"$eq": empresa}},
                        {"ano": {"$eq": int(ano)}}
                    ]
                }
            }
        )

        # O MultiQuery agora usa o plano gerado na Fase 1
        docs_recuperados = await base_retriever.ainvoke(plano_de_busca.content)
        
        # Remove duplicatas (Caso queries diferentes tragam a mesma página)
        vistos = set()
        docs_unicos = []
        for d in docs_recuperados:
            content_hash = hash(d.page_content)
            if content_hash not in vistos:
                vistos.add(content_hash)
                docs_unicos.append(d)

        self.visualizar_chunks_busca(docs_unicos, empresa, ano)
        contexto_consolidado = "\n\n".join([doc.page_content for doc in docs_unicos])

        # --- FASE 3: EXTRAÇÃO (O Discovery Prompt final) ---
        print(f"🧠 Fase 3: Extraindo métricas do contexto filtrado...")
        
        discovery_prompt = PromptTemplate(
            template=template_texto,
            input_variables=["context", "ano", "empresa"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )

        metricas_preliminares = await (discovery_prompt | self.model | self.parser).ainvoke({
            "context": contexto_consolidado,
            "empresa": empresa,
            "ano": ano
        })

        # --- FASE DE REFINAMENTO (Seu Passo 5 original permanece igual) ---
        print(f"📊 Refinando {len(metricas_preliminares)} métricas...")
        tarefas = [
            self._processar_metrica_individual(metrica, dados, base_retriever, discovery_prompt, empresa, ano)
            for metrica, dados in metricas_preliminares.items()
        ]

        tabela_auditoria = await asyncio.gather(*tarefas, return_exceptions=True)
        tabela_auditoria = [linha for linha in tabela_auditoria if isinstance(linha, dict)]

        if tabela_auditoria:
            self._salvar_log_discovery(empresa, ano, tabela_auditoria)
        
        return tabela_auditoria