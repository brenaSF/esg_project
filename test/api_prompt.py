import os
import json
import pandas as pd
import re
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import JsonOutputParser

# --- 1. SETUP E PARSER ---
# Certifique-se de ter a OPENAI_API_KEY no seu ambiente
model = ChatOpenAI(model_name="gpt-4o", temperature=0)
parser = JsonOutputParser()

# --- 2. FUNÇÃO DE LIMPEZA (CORRIGIDA) ---
def formatar_para_numero(valor):
    if valor is None: 
        return 0
    
    # Se o valor vier como dicionário (comum no JsonOutputParser), extrai o conteúdo
    if isinstance(valor, dict):
        valor = next(iter(valor.values()), "0")
    
    # Força conversão para string e normaliza separador decimal
    texto = str(valor).replace(",", ".").strip()
    
    try:
        # Busca todos os números (inteiros ou decimais)
        numeros = re.findall(r"[-+]?\d*\.\d+|\d+", texto)
        if not numeros:
            return 0
        
        num_final = float(numeros[0])
        
        # Trata percentuais: se houver '%' ou se o modelo retornou 0.XX
        if "%" in texto:
            # Se o número já for decimal (ex: 0.52), não divide por 100 novamente
            return num_final / 100 if num_final > 1 else num_final
        
        return num_final
    except (ValueError, IndexError):
        return 0

# --- 3. CARREGAMENTO DE DADOS E VECTOR DB ---
with open("data_chunks_esg_v2.json", "r", encoding="utf-8") as f:
    dados = json.load(f)
chunks = dados.get("chunks", [])

documentos = [
    Document(page_content=c['contexto'], metadata={"pg": c.get('pagina', 'N/A')}) 
    for c in chunks
]

vector_db = Chroma.from_documents(documentos, OpenAIEmbeddings())
retriever = vector_db.as_retriever(search_kwargs={"k": 5})

# --- 4. DEFINIÇÃO DOS PROMPTS ---

discovery_prompt = PromptTemplate(
    template="""Você é um auditor especialista em GRI 405-1. Adcione um nome curto para cada métrica quantitativa relevante deste contexto. Retire pelo menos 20 métricas.
    Analise o contexto e identifique APENAS métricas quantitativas de diversidade (ex: % de mulheres, negros, PCDs, faixas etárias).
    Ignore outros temas como emissões ou corrupção.
    
    Retorne um JSON onde a CHAVE é o nome curto da métrica (snake_case) e o VALOR é a pergunta para extração.
    Contexto: {context}
    {format_instructions}""",
    input_variables=["context"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

extraction_prompt = PromptTemplate(
    template="""Extraia o valor numérico da métrica solicitada com base no contexto.
    Responda em formato JSON contendo uma chave "valor".
    Contexto: {context}
    Pergunta: {question}
    {format_instructions}""",
    input_variables=["context", "question"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

# --- 5. CHAINS ---
# Nota: O discovery usa o retriever para entender o que existe no documento
discovery_chain = {"context": retriever} | discovery_prompt | model | parser
extraction_chain = extraction_prompt | model | parser

# --- 6. EXECUÇÃO DINÂMICA ---
print("🔍 Analisando documento para identificar métricas GRI 405-1...")

metricas_descobertas = discovery_chain.invoke(
    "GRI 405-1: Diversidade de empregados, gênero, raça, idade e composição do conselho"
)

registro_unico = {"empresa": "Bradesco", "ano": 2024}

for coluna, query in metricas_descobertas.items():
    try:
        print(f"\n{'='*60}")
        print(f"📊 Métrica Identificada: {coluna}")
        
        # 1. Busca chunks relevantes
        docs_relacionados = retriever.invoke(query)
        
        # 2. Organiza metadados
       # paginas = sorted(list(set([str(d.metadata.get('pg', 'N/A')) for d in docs_relacionados])))
        contexto_unido = "\n".join([d.page_content for d in docs_relacionados])
        
        # 3. Extração com o LLM
        resultado = extraction_chain.invoke({"context": contexto_unido, "question": query})
        
        # 4. Limpeza robusta do valor
        valor_limpo = formatar_para_numero(resultado)
        
        # 5. Salva no dicionário de registro
        registro_unico[coluna] = valor_limpo
        #registro_unico[f"{coluna}_pag"] = ", ".join(paginas)
        
        #print(f"📄 Fonte: Pág(s) {', '.join(paginas)}")
        print(f"✅ Valor Extraído: {valor_limpo}")

    except Exception as e:
        print(f"❌ Erro ao processar {coluna}: {str(e)}")
        registro_unico[coluna] = 0

# --- 7. EXPORTAÇÃO ---
df_esg = pd.DataFrame([registro_unico])
# Ordena colunas para que as páginas fiquem ao lado dos valores
df_esg = df_esg.reindex(columns=sorted(df_esg.columns))
df_esg.to_csv("base_esg_final.csv", index=False, sep=";", encoding="utf-8-sig")

print(f"\n{'='*60}")
print(f"--- PROCESSO CONCLUÍDO: {len(metricas_descobertas)} métricas processadas ---")