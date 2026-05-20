from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.vectorstores import Qdrant

from langchain_openai import OpenAI, ChatOpenAI, OpenAIEmbeddings
from langchain.retrievers.multi_query import MultiQueryRetriever
from dotenv import load_dotenv

load_dotenv() 


# 1. Configuração dos Modelos (Usando ChatOpenAI para melhor suporte a ferramentas/chains)
llm_model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
embeddings = OpenAIEmbeddings(model='text-embedding-3-large')

# 2. Documentos de Teste (Dados fictícios para testar a recuperação)
docs = [
    Document(page_content="O Pix automático será lançado em 2025 pelo Banco Central para facilitar cobranças recorrentes."),
    Document(page_content="O Drex é a moeda digital brasileira (CBDC) focada em transações financeiras e contratos inteligentes."),
    Document(page_content="A inteligência artificial generativa está transformando o desenvolvimento de software em 2026.")
]

# 3. Inicialização e Alimentação do Vector Store (Qdrant em memória)
vector_store = Qdrant.from_documents(
    documents=docs,       # Note que na versão antiga o parâmetro é 'documents'
    embedding=embeddings,  # E aqui é 'embedding' no singular
    location=":memory:",
    collection_name="teste_rag"
)

# 4. Configuração dos Retrievers
base_retriever = vector_store.as_retriever(search_kwargs={"k": 1})

# Corrigido: Atribuindo o MultiQueryRetriever à variável correta
retriever_multi = MultiQueryRetriever.from_llm(
    retriever=base_retriever, 
    llm=llm_model
)

# 5. Criação do Prompt e da Chain de RAG
prompt_template = """Você é um assistente prestativo. Use os seguintes pedaços de contexto para responder à pergunta no final. Se você não sabe a resposta, apenas diga que não sabe.

Contexto:
{context}

Pergunta: {question}
Resposta:"""

prompt = ChatPromptTemplate.from_template(prompt_template)

# Função para formatar os documentos recuperados em uma string única
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# Chain padrão do LangChain (LCEL)
rag_chain_base = (
    {"context": base_retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm_model
    | StrOutputParser()
)

rag_chain_multi = (
    {"context": retriever_multi | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm_model
    | StrOutputParser()
)

# 6. Execução do Teste Comparativo
# Uma pergunta com sinônimos ou termos diferentes ajuda a ver o poder do MultiQuery
query = "Me explique sobre as cobranças recorrentes que o BC vai lançar"

print("--- EXECUTANDO TESTE ---")
print(f"Pergunta original: {query}\n")

# Teste 1: RAG Normal
print("========= RAG NORMAL =========")
# Se você quiser ver apenas o que ele recuperou:
docs_normal = base_retriever.invoke(query)
print(f"Documentos recuperados ({len(docs_normal)}): {[d.page_content for d in docs_normal]}")
# Resposta final do LLM
resposta_normal = rag_chain_base.invoke(query)
print(f"Resposta Final: {resposta_normal}\n")

# Teste 2: RAG Multi Query
print("========= RAG MULTI QUERY =========")
# Se você quiser ver apenas o que ele recuperou (o MultiQuery vai gerar variações da pergunta antes):
docs_multi = retriever_multi.invoke(query)
print(f"Documentos recuperados ({len(docs_multi)}): {[d.page_content for d in docs_multi]}")
# Resposta final do LLM
resposta_multi = rag_chain_multi.invoke(query)
print(f"Resposta Final: {resposta_multi}\n")