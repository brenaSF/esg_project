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
from datasets import Dataset
from ragas import evaluate

from ragas.metrics import faithfulness, context_recall
import nest_asyncio
nest_asyncio.apply()
VALOR_PADRAO = os.getenv("VALOR_PADRAO", "GRI_400") 
EVAL_RAGAS = False

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
        
        rerank_prompt = PromptTemplate.from_template(
            "Como um auditor ESG, avalie de 0 a 10 a utilidade do trecho para responder: '{query}'\n"
            "Considere se há números, tabelas ou menções diretas aos indicadores.\n"
            "Responda APENAS o número da nota.\n\n"
            "Trecho: {context}"
        )
        
        chain = rerank_prompt | self.model
        
        for doc, score in docs_e_scores:
            try:
                veredicto = chain.invoke({"query": query, "context": doc.page_content}).content
                
                match = re.search(r'\d+', veredicto)
                if match:
                    score_relevancia = float(match.group())
                    
                    if score_relevancia >= 5:
                        novo_score = score + (score_relevancia / 10)
                        reranked_docs.append((doc, novo_score))
            except Exception as e:
                print(f"Erro no re-ranking de um trecho: {e}")
                continue
                
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
        diretorio = "discovery"
        
        if not os.path.exists(diretorio):
            os.makedirs(diretorio)
        
        nome_arquivo = f"discovery_{empresa}_{ano}_{int(time.time())}.json"
        caminho_completo = os.path.join(diretorio, nome_arquivo)
        
        with open(caminho_completo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
            
        print(f"✅ Log de descoberta salvo em: {caminho_completo}")


    def _detectar_tabela_no_texto(self,text: str) -> bool:
        """
        Detecta padrões que indicam que o texto bruto é uma tabela desalinhada.
        """
        padroes = [
            r"\d{4}\s+\d+",                 
            r"GRI\s+\d+",                   
            r"\d+[.,]\d+%\s+\d+[.,]\d+%",   
            r"(Homens|Mulheres|Gênero|Raça|PCD|Até \d+ anos)", 
            r"\d{2,}\s+\d{2,}\s+\d{2,}",    
            r"Total\s+\d+"                  
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
            pagina = doc.metadata.get('page', 'N/A')
            fonte = doc.metadata.get('source', 'Documento')
            
            preview_texto = doc.page_content.replace('\n', ' ').strip()[:200] + "..."
            
            dados_para_exibicao.append({
                "ID": i + 1,
                "Página": pagina,
                "Conteúdo": preview_texto
            })

            print(f"🔍 [Chunk {i+1}] | Página: {pagina}")
            print(f"Texto: {doc.page_content.strip()}")
            print("-" * 50)

        df_chunks = pd.DataFrame(dados_para_exibicao)
        return df_chunks

    
    async def _processar_metrica_individual(self, metrica, dados, retriever, discovery_prompt, empresa, ano):
        """
        Função assíncrona para processar uma única métrica.
        """
        async with self.semaphore:
            try:
                if dados.get("valor") is None or "Omissão" in str(dados.get("status")):
                    query_focada = f"Valor numérico exato e tabela para a métrica {metrica} da {empresa} em {ano}"
                    
                    docs_especificos = await retriever.ainvoke(query_focada)
                    
                    contextos_processados = []
                    for doc in docs_especificos:
                        conteudo_chunk = doc.page_content
                        if self._detectar_tabela_no_texto(conteudo_chunk):
                            
                            print("-----------------------")
                            print(conteudo_chunk)
                        contextos_processados.append(conteudo_chunk)
                    
                    contexto_focado = "\n\n".join(contextos_processados)
                    
                    dados_refinados = await (discovery_prompt | self.model | self.parser).ainvoke({
                        "context": contexto_focado, 
                        "empresa": empresa, 
                        "ano": ano
                    })
                    
                    if metrica in dados_refinados:
                        dados = dados_refinados[metrica]

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

    async def _calcular_metricas_reais(self, tabela_auditoria, contextos_recuperados):
        if not tabela_auditoria:
            return {"faithfulness": 0.0, "context_recall": 0.0}

        data = {
            "question": [f"Qual o valor da métrica {m.get('Metrica', 'N/A')}?" for m in tabela_auditoria],
            "answer": [str(m.get('Valor', '')) for m in tabela_auditoria],
            "contexts": [contextos_recuperados for _ in tabela_auditoria],
            "ground_truth": [m.get('Evidencia', '') for m in tabela_auditoria]
        }

        def processar_ragas_sync(dataset_dict):
            from datasets import Dataset
            from ragas import evaluate
            
            dataset = Dataset.from_dict(dataset_dict)
            resultado = evaluate(
                dataset=dataset,
                metrics=[faithfulness, context_recall]
            )
            return resultado

        try:
            loop = asyncio.get_event_loop()
            resultado = await loop.run_in_executor(None, processar_ragas_sync, data)

            import pandas as pd
            df_scores = pd.DataFrame(resultado.scores)
            
            print("\n" + "="*50)
            print("📊 SCORES DETALHADOS DO RAGAS")
            print(df_scores) 
            print("="*50 + "\n")

            
            medias = df_scores.mean(numeric_only=True).to_dict()

            return {
                "faithfulness": round(medias.get("faithfulness", 0.0), 2),
                "context_recall": round(medias.get("context_recall", 0.0), 2)
            }
        except Exception as e:
            print(f"❌ Erro ao extrair scores do Ragas: {e}")
            if 'resultado' in locals():
                print(f"Estrutura do objeto resultado.scores: {type(resultado.scores)}")
                return {"faithfulness": 0.0, "context_recall": 0.0}

    async def _extrair_com_rag(self, vector_store, empresa, ano):
            start_time = time.time()
            
            print(f"📡 Fase 1: Planejando busca técnica para {empresa}...")
            template_texto = DISCOVERY_PROMPT_TEMPLATE_400 if VALOR_PADRAO == "GRI_400" else DISCOVERY_PROMPT_TEMPLATE_300
            chain_planejamento = ADAPTIVE_QUERY_PROMPT | self.model
            plano_de_busca = await chain_planejamento.ainvoke({
                "template": template_texto, "empresa": empresa, "ano": ano
            })
            
            print(f"🔍 Fase 2: Executando Multi-Query...")
            base_retriever = vector_store.as_retriever(
                search_kwargs={"k": 8, "filter": {"$and": [{"empresa": {"$eq": empresa}}, {"ano": {"$eq": int(ano)}}]}}
            )
            docs_recuperados = await base_retriever.ainvoke(plano_de_busca.content)
            
            vistos = set()
            docs_unicos = [d for d in docs_recuperados if not (hash(d.page_content) in vistos or vistos.add(hash(d.page_content)))]
            contexto_com_paginas = []
            for doc in docs_unicos:
                num_pagina = doc.metadata.get("source", "desconhecida")
                texto_formatado = f"[PÁGINA {num_pagina}]: {doc.page_content}"
                contexto_com_paginas.append(texto_formatado)

            contexto_consolidado = "\n\n".join(contexto_com_paginas)

            print(f"🧠 Fase 3: Extraindo métricas do contexto filtrado...")
            discovery_prompt = PromptTemplate(
                template=template_texto,
                input_variables=["context", "ano", "empresa"],
                partial_variables={"format_instructions": self.parser.get_format_instructions()}
            )

            metricas_finais = await (discovery_prompt | self.model | self.parser).ainvoke({
                "context": contexto_consolidado, "empresa": empresa, "ano": ano
            })

            faltantes = [m for m, d in metricas_finais.items() 
                        if d.get("valor") is None or "Omissão" in str(d.get("status"))]

            if faltantes:
                print(f"🔄 Tentativa de recuperação para: {len(faltantes)} métricas...")
                query_repescagem = f"Valores e detalhes sobre: {', '.join(faltantes)} - {empresa} {ano}"
                docs_repescagem = await base_retriever.ainvoke(query_repescagem)
                
                docs_unicos.extend(docs_repescagem)
                contexto_repescagem = "\n\n".join([d.page_content for d in docs_repescagem])

                metricas_recuperadas = await (discovery_prompt | self.model | self.parser).ainvoke({
                    "context": contexto_repescagem, "empresa": empresa, "ano": ano
                })

                for m in faltantes:
                    if m in metricas_recuperadas and metricas_recuperadas[m].get("valor") is not None:
                        metricas_finais[m] = metricas_recuperadas[m]

       
            tabela_auditoria = []
            for metrica, dados in metricas_finais.items():
                valor_raw = dados.get("valor")
                valor_final = str(valor_raw) if valor_raw is not None else "Não encontrado"
                
               
                pag_raw = str(dados.get("página") or dados.get("pagina") or dados.get("Página") or "N/A")
                
                pag_limpa = "".join(filter(str.isdigit, pag_raw)) if any(c.isdigit() for c in pag_raw) else pag_raw

                evidencia = dados.get("evidencia_texto") or dados.get("evidencia") or "Trecho não localizado"

                
                gabarito_usuario = dados.get("gabarito_editado", "") 

                valor_extraido = str(dados.get("valor") or "Não encontrado")
                
                if gabarito_usuario:
                    status_validacao = "✅ Consistente" if valor_extraido.strip() == gabarito_usuario.strip() else "❌ Inconsistente"
                else:
                    status_validacao = "Aguardando Gabarito"

                tabela_auditoria.append({
                    "Empresa": empresa,
                    "Ano": ano,
                    "Metrica": metrica,
                    "Valor": valor_final,
                    "Unidade": "Percentual (%)" if "%" in valor_final else "Absoluto",
                    "Evidencia": evidencia,
                    "Gabarito": gabarito_usuario,
                    "Página": pag_limpa,
                    "Status_Auditoria": dados.get("status") or ("Omissão" if valor_raw is None else "Coletado")
                })

            # --- AVALIAÇÃO RAGAS ---
            EVAL_RAGAS = False
            contextos_usados = [doc.page_content for doc in docs_unicos]
            
            if EVAL_RAGAS:
                scores_ragas = await self._calcular_metricas_reais(tabela_auditoria, contextos_usados)
            else:
                scores_ragas = {"faithfulness": 0.0, "context_recall": 0.0}

     
            if tabela_auditoria:
                self._salvar_log_discovery(empresa, ano, tabela_auditoria)

            return tabela_auditoria