import re
import os
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.documents import Document
from src.utils.parsers import formatar_para_numero
from src.config import Config
from src.agents.esg_prompt import DISCOVERY_PROMPT_TEMPLATE, EXTRACTION_PROMPT_TEMPLATE
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

    def _extrair_com_rag(self, chroma_client, collection_name, empresa, ano):
        """Função principal que executa o processo de extração usando RAG.
         1. Discovery: Identifica quais métricas estão presentes e gera perguntas específicas.
         2. Precise Extraction: Para cada métrica, busca os trechos mais relevantes e extrai o valor quantitativo.
        
        Args:
            chroma_client: Cliente do ChromaDB para acesso à base de dados vetorial.
            collection_name: Nome da coleção no ChromaDB onde os documentos estão armazenados.
            empresa: Nome da empresa alvo da extração.
            ano: Ano específico para o qual os dados devem ser extraídos.

        Returns:
            Uma tabela de auditoria contendo as métricas extraídas, seus valores, unidades, scores de relevância e evidências textuais.

        """
        
        vector_store = Chroma(
            client=chroma_client,
            collection_name=collection_name,
            embedding_function=self.embeddings
        )

        # retriever com filtro para empresa e ano, garantindo que só busque documentos relevantes para o contexto específico
        retriever = vector_store.as_retriever(
            search_kwargs={
                "k": 15,
                "filter": {
                    "$and": [
                        {"empresa": {"$eq": empresa}},
                        {"ano": {"$eq": int(ano)}}
                    ]
                }
            }
        )

        discovery_prompt = PromptTemplate(
            template=DISCOVERY_PROMPT_TEMPLATE,
            input_variables=["context"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )

        extraction_prompt = PromptTemplate(
            template=EXTRACTION_PROMPT_TEMPLATE,
            input_variables=["context", "question", "ano"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )

        
        # 1. Discovery
        docs_iniciais = retriever.invoke(f"Indicadores de diversidade e emissões de {empresa} {ano}")
        contexto_inicial = "\n".join([d.page_content for d in docs_iniciais])
        
        metricas_descobertas = (discovery_prompt | self.model | self.parser).invoke({
            "context": contexto_inicial, "empresa": empresa, "ano": ano
        })

       
        # 2. Precise Extraction
        tabela_auditoria = []

        print(f"\nMétricas Descobertas para {empresa} {ano}:")
        print(metricas_descobertas)

        for coluna, info_metrica in metricas_descobertas.items():
            try:

                query_busca = info_metrica.get("query_localizacao") if isinstance(info_metrica, dict) else info_metrica
        
                if not query_busca:
                    query_busca = f"Dados sobre {coluna} no ano {ano}"

                docs_especificos = retriever.invoke(query_busca)
                #contexto_focado = "\n".join([d.page_content for d in docs_especificos])
                #paginas = list(set([str(d.metadata.get("pagina", "N/A")) for d in docs_especificos]))

                print(f"\n--- EXPLORANDO CHUNKS PARA: {coluna} ---")
                for i, doc in enumerate(docs_especificos):
                    # Mostra o índice, os metadados (página, empresa) e o início do conteúdo
                    origem = doc.metadata.get('source', 'Desconhecido')
                    pagina = doc.metadata.get('pagina', 'N/A')
                    
                    print(f"ID: {i} | Página: {pagina} | Fonte: {origem}")
                    print(f"Conteúdo: {doc.page_content[:200]}...") # Primeiros 200 caracteres
                    print("-" * 30)

                fragmentos = []
                for i, d in enumerate(docs_especificos):
                    # Injetamos um marcador visual para o LLM (ex: [Doc 1])
                    fragmentos.append(f"[Trecho {i}]: {d.page_content}")

                contexto_focado = "\n\n".join(fragmentos)

                resultado = (extraction_prompt | self.model | self.parser).invoke({
                    "context": contexto_focado, "question": query_busca, "ano": ano
                })

                try:
                    # Tenta pegar o ID que o LLM retornou
                    id_str = str(resultado.get("id_trecho", "0"))
                    id_usado = int(re.search(r'\d+', id_str).group())
                    # Garante que o índice existe nos documentos retornados
                    if id_usado < len(docs_especificos):
                        pagina_exata = str(docs_especificos[id_usado].metadata.get("pagina", "N/A"))
                    else:
                        pagina_exata = "N/A"
                except:
                    pagina_exata = "Não identificada"

                tabela_auditoria.append({
                    "Empresa": empresa,
                    "Ano": ano,
                    "Dado Extraído": coluna,
                    "Valor": formatar_para_numero(resultado.get("valor")),
                    "Unidade": resultado.get("unidade"),
                    "Fonte (Texto Original)": resultado.get("trecho_original"),
                    "Página": str(pagina_exata) # <--- O SEGREDO ESTÁ AQUI: Forçar string
                })
            except Exception as e:
                print(f"Erro em {coluna}: {e}")

        return tabela_auditoria