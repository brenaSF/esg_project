import re
import os
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.documents import Document

class ESGMetricProcessor:
    def __init__(self, OPENAI_API_KEY):
        self.model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, api_key=OPENAI_API_KEY)
        self.embeddings = OpenAIEmbeddings(
            api_key=OPENAI_API_KEY, 
            model="text-embedding-3-small"
        )
        self.parser = JsonOutputParser()

    def formatar_para_numero(self, valor):
        if valor is None: return 0
        if isinstance(valor, dict):
            valor = next(iter(valor.values()), "0")
        
        texto = str(valor).replace(",", ".").strip()
        try:
            numeros = re.findall(r"[-+]?\d*\.\d+|\d+", texto)
            if not numeros: return 0
            num_final = float(numeros[0])
            if "%" in texto:
                return num_final / 100 if num_final > 1 else num_final
            return num_final
        except:
            return 0

    def _extrair_com_rag(self, chroma_client, collection_name, empresa, ano):
        # Conexão segura via LangChain usando o client persistente
        vector_store = Chroma(
            client=chroma_client,
            collection_name=collection_name,
            embedding_function=self.embeddings
        )

        # Filtro de metadados rigoroso para evitar vazamento de dados de outras empresas/anos
        retriever = vector_store.as_retriever(
            search_kwargs={
                "k": 10,
                "filter": {
                    "$and": [
                        {"empresa": {"$eq": empresa}},
                        {"ano": {"$eq": int(ano)}}
                    ]
                }
            }
        )

        discovery_prompt = PromptTemplate(
            template="""Você é um auditor sênior especialista em relatórios GRI (Global Reporting Initiative), focado na norma GRI 405-1.
            Sua tarefa é extrair exatamente 20 métricas quantitativas de Diversidade e Descarbonização do contexto abaixo.

            ### DIRETRIZES DE EXTRAÇÃO:
            1. **Precisão de Liderança:** Diferencie claramente 'quadro geral' de 'cargos de liderança/alta administração'.
            2. **Faixas Etárias:** Extraia separadamente as categorias (Ex: <30, 30-50, >50). Se houver uma tabela, foque no ano mais recente (2024).
            3. **Formato do Valor:** O valor no JSON deve ser uma PERGUNTA objetiva que, quando respondida, extraia apenas o número ou percentual específico. Caso seja um número : mostre o número inteiro (ex: 500 empregados com deficiência)
            4. **Filtro de Ruído:** Ignore cabeçalhos de tabelas ou sequências de números que não correspondam diretamente à métrica.
            5. No JSON, indique também em qual página (presente no contexto) você encontrou o valor específico.
            

            ### TEMAS PERMITIDOS:
            - Diversidade: Gênero, Raça/Etnia, PCD, Faixa Etária (Total e por Nível Hierárquico).

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

        extraction_prompt = PromptTemplate(
            template="""Você é um auditor sênior de ESG. Sua tarefa é extrair o valor quantitativo para o ano de {ano}.

            ### REGRAS CRÍTICAS:
            1. **Filtro de Ano:** O contexto contém dados históricos (2022, 2023, 2024). Ignore QUALQUER valor que não seja referente ao ano de {ano}.
            2. **Soma de Segmentos:** Se para o ano de {ano} existirem valores separados por gênero (Homens e Mulheres), você DEVE somá-los para compor o total da categoria.
            - Exemplo no contexto: "Até 29 anos 97 85". 
            - Ação: Somar 97 + 85 = 182.
            3. **Prioridade de Tabela:** Se houver uma estrutura de tabela, identifique a interseção correta entre a linha (métrica) e a coluna (ano/gênero).

            Responda em formato JSON:
            {{
                "valor": "o número encontrado",
                "unidade": "unidade de medida",
                "trecho_original": "a frase exata",
                "id_trecho": "o número do [Trecho X] de onde você extraiu a informação"
            }}
            Contexto: {context}
            Métrica: {question}
            {format_instructions}""",
            input_variables=["context", "question","ano"],
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
        for coluna, query in metricas_descobertas.items():
            try:
                docs_especificos = retriever.invoke(query)
                #contexto_focado = "\n".join([d.page_content for d in docs_especificos])
                #paginas = list(set([str(d.metadata.get("pagina", "N/A")) for d in docs_especificos]))

                fragmentos = []
                for i, d in enumerate(docs_especificos):
                    # Injetamos um marcador visual para o LLM (ex: [Doc 1])
                    fragmentos.append(f"[Trecho {i}]: {d.page_content}")

                contexto_focado = "\n\n".join(fragmentos)

                resultado = (extraction_prompt | self.model | self.parser).invoke({
                    "context": contexto_focado, "question": query, "ano": ano
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
                    "Valor": self.formatar_para_numero(resultado.get("valor")),
                    "Unidade": resultado.get("unidade"),
                    "Fonte (Texto Original)": resultado.get("trecho_original"),
                    "Página": str(pagina_exata) # <--- O SEGREDO ESTÁ AQUI: Forçar string
                })
            except Exception as e:
                print(f"Erro em {coluna}: {e}")

        return tabela_auditoria