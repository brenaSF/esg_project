import re
import os
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.documents import Document
from src.core.parsers import formatar_para_numero
from src.core.config import Config
from src.core.esg_prompt import DISCOVERY_PROMPT_TEMPLATE_400
from src.core.prompt300 import DISCOVERY_PROMPT_TEMPLATE_300
import json 
import time

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

    def _extrair_com_rag(self,vector_store,empresa, ano):
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
        
        # retriever com filtro para empresa e ano, garantindo que só busque documentos relevantes para o contexto específico
        retriever = vector_store.as_retriever(
            search_kwargs={
                "k": 8,
                "filter": {
                    "$and": [
                        {"empresa": {"$eq": empresa}},
                        {"ano": {"$eq": int(ano)}}
                    ]
                }
            }
        )

        discovery_prompt = PromptTemplate(
            template=DISCOVERY_PROMPT_TEMPLATE_300,
            input_variables=["context"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )

        
        # 1. Discovery
        docs_iniciais = retriever.invoke(f"Indicadores de diversidade e emissões de {empresa} {ano}")
        contexto_inicial = "\n".join([d.page_content for d in docs_iniciais])
        
        metricas_descobertas = (discovery_prompt | self.model | self.parser).invoke({
            "context": contexto_inicial, "empresa": empresa, "ano": ano
        })

        nome_arquivo = f"discovery_{empresa}_{ano}_{int(time.time())}.json"
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(metricas_descobertas, f, ensure_ascii=False, indent=4)

        print(f"✅ Mapeamento de descoberta salvo em: {nome_arquivo}")

            
        # 2. Precise Extraction
        tabela_auditoria = []

        print(metricas_descobertas)

        total = len(metricas_descobertas)
        print(f"📊 Processando {total} métricas encontradas...")

        for metrica, dados in metricas_descobertas.items():
            try:
                valor_original = dados.get("valor")
                unidade = "Percentual (%)" if dados.get("status") == "Percentual" or "%" in str(valor_original) else "Absoluto"
              
                pagina = str(dados.get("pagina", "Não informada"))

                linha = {
                    "Empresa": empresa,
                    "Ano": ano,
                    "Metrica": metrica,
                    "Valor": valor_original,
                    "Unidade": unidade,
                    "Evidencia": dados.get("evidencia_texto", ""),
                    "Página": pagina ,
                    "Status_Auditoria": "Pendente"  
                }
                
                tabela_auditoria.append(linha)
                
            except Exception as e:
                print(f"Erro ao estruturar métrica {metrica}: {e}")

        # Retorna a lista de dicionários (pronta para pd.DataFrame(tabela_para_csv))
        return tabela_auditoria