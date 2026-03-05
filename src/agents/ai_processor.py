
import re
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.documents import Document


class ESGMetricProcessor:
    def __init__(self, OPENAI_API_KEY):
        self.model = ChatOpenAI(model_name="gpt-4o", temperature=0, api_key=OPENAI_API_KEY)
        self.embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)
        self.parser = JsonOutputParser()

    def create_vector_db(self, documents):
        # O ChromaDB agora conterá apenas páginas que passaram no filtro do Loader
        return Chroma.from_documents(documents, self.embeddings)
    
    def discover_relevant_context(self, query, retriever):
        prompt = PromptTemplate(
            template="""Você é um auditor especialista em GRI 405-1. Adcione um nome curto para cada métrica quantitativa relevante deste contexto. Retire pelo menos 30 métricas.
            Analise o contexto e identifique APENAS métricas quantitativas de diversidade (ex: % de mulheres, negros, PCDs, faixas etárias).
            Ignore outros temas como emissões ou corrupção.

            Retorne um JSON onde a CHAVE é o nome curto da métrica (snake_case) e o VALOR é a pergunta para extração.
            Contexto: {context}
            {format_instructions}""",
            input_variables=["context"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        discovery_chain = {"context": retriever} | prompt | self.model | self.parser
        return discovery_chain.invoke({"context": context})

    def extract_precise_value(self, query, context):
        prompt = PromptTemplate(
            template="""Você é um auditor de sustentabilidade. 
            Baseado no contexto abaixo, extraia o valor exato para a métrica: {question}
            Responda APENAS em JSON com a chave "valor".
            
            Contexto: {context}
            {format_instructions}""",
            input_variables=["question", "context"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        chain = prompt | self.model | self.parser
        return chain.invoke({"question": query, "context": context})
    
    def formatar_para_numero(self,valor):
        if valor is None: 
            return 0
        
        if isinstance(valor, dict):
            valor = next(iter(valor.values()), "0")
        
        texto = str(valor).replace(",", ".").strip()
        
        try:
            numeros = re.findall(r"[-+]?\d*\.\d+|\d+", texto)
            if not numeros:
                return 0
            
            num_final = float(numeros[0])
            
            if "%" in texto:
                return num_final / 100 if num_final > 1 else num_final
            
            return num_final
        except (ValueError, IndexError):
            return 0
    
    def _extrair_texto_estruturado_csv(self, metadata, chunks):
        documentos = [
            Document(page_content=c['contexto'], metadata={"pg": c.get('pagina', 'N/A')}) 
            for c in chunks
        ]

        retriever = self.create_vector_db(documentos).as_retriever(search_kwargs={"k": 5})

        discovery_prompt = PromptTemplate(
            template="""Você é um auditor sênior especialista em relatórios GRI (Global Reporting Initiative), focado na norma GRI 405-1.
            Sua tarefa é extrair exatamente 20 métricas quantitativas de Diversidade e Descarbonização do contexto abaixo.

            ### DIRETRIZES DE EXTRAÇÃO:
            1. **Precisão de Liderança:** Diferencie claramente 'quadro geral' de 'cargos de liderança/alta administração'.
            2. **Faixas Etárias:** Extraia separadamente as categorias (Ex: <30, 30-50, >50). Se houver uma tabela, foque no ano mais recente (2024).
            3. **Formato do Valor:** O valor no JSON deve ser uma PERGUNTA objetiva que, quando respondida, extraia apenas o número ou percentual específico. Caso seja um número : mostre o número inteiro (ex: 500 empregados com deficiência)
            4. **Filtro de Ruído:** Ignore cabeçalhos de tabelas ou sequências de números que não correspondam diretamente à métrica.

            ### TEMAS PERMITIDOS:
            - Diversidade: Gênero, Raça/Etnia, PCD, Faixa Etária (Total e por Nível Hierárquico).
            - Descarbonização: % Energia Renovável, % Redução de Emissões de Escopo 1, 2 ou 3.

            ### EXEMPLO DE SAÍDA ESPERADA:
            {{
                "percentual_mulheres_lideranca": "Qual o percentual de mulheres em cargos de liderança ou alta administração em 2024?",
                "percentual_pcd_total": "Qual o percentual total de pessoas com deficiência (PCD) no quadro de funcionários?",
                "quantidade_empregados_ate_30": "Qual a quantidade de empregados que possuem até 30 anos?",
            }}

            Contexto: {context}

            {format_instructions}""",
            input_variables=["context"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )

        # --- PROMPT COM FOCO EM EVIDÊNCIA ---
        extraction_prompt = PromptTemplate(
            template="""Extraia o valor numérico, a unidade de medida e o trecho comprobatório.
            Responda em formato JSON:
            {{
                "valor": "o número encontrado",
                "unidade": "a unidade de medida (ex: %, toneladas, absoluto)",
                "trecho_original": "a frase exata de onde tirou a informação"
            }}
            Contexto: {context}
            Métrica: {question}
            {format_instructions}""",
            input_variables=["context", "question"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )

        discovery_chain = {"context": retriever} | discovery_prompt | self.model | self.parser
        extraction_chain = extraction_prompt | self.model | self.parser

        metricas_descobertas = discovery_chain.invoke(
            "GRI 405-1: Diversidade de empregados, gênero, raça e pessoas com deficiência"
        )

        # --- NOVA ESTRUTURA: Lista de Auditoria ---
        tabela_auditoria = []

        for coluna, query in metricas_descobertas.items():
            try:
                print(f"🔍 Extraindo: {coluna}")
                docs_relacionados = retriever.invoke(query)
                
                paginas = list(set([str(d.metadata.get("pg", "N/A")) for d in docs_relacionados]))
                contexto_unido = "\n".join([d.page_content for d in docs_relacionados])
                
                resultado = extraction_chain.invoke({"context": contexto_unido, "question": query})
                
                # Criando a linha conforme sua solicitação
                linha_metrica = {

                    "Empresa" : metadata.get("empresa"),
                    "Ano" : metadata.get("ano"),
                    "Dado Extraído": coluna,
                    "Valor": self.formatar_para_numero(resultado.get("valor")),
                    "Unidade": resultado.get("unidade"),
                    "Fonte (Texto Original)": resultado.get("trecho_original"),
                    "Página": ", ".join(paginas)
                }
                
                tabela_auditoria.append(linha_metrica)
                print(f"✅ Sucesso: {coluna}")

            except Exception as e:
                print(f"❌ Erro em {coluna}: {e}")

        return tabela_auditoria # Retorna uma lista de linhas para o DataFrame