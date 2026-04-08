import os
import dotenv
import chromadb
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

dotenv.load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
DB_PATH = "./data/output/chroma_db"
COLLECTION_NAME = "esg_documents_v1"

def quick_inspect(empresa: str, ano: int, pagina: int = None):
    """
    Consulta o ChromaDB para validar o armazenamento de uma empresa/ano/página.
    """
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=API_KEY)
    
    client = chromadb.PersistentClient(path=DB_PATH)
    
    vector_store = Chroma(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings
    )

    filtro = {
        "$and": [
            {"empresa": {"$eq": empresa}},
            {"ano": {"$eq": int(ano)}}
        ]
    }
    
    if pagina:
        filtro["$and"].append({"pagina": {"$eq": int(pagina)}})

    print(f"\n🔍 Buscando no Chroma: {empresa} | Ano: {ano} | Pág: {pagina if pagina else 'Todas'}")
    print("="*80)

    # Recupera os dados
    try:
        resultado = vector_store.get(where=filtro)
        
        if not resultado['documents']:
            print("❌ Nenhum dado encontrado com esses filtros.")
            return

        for i, (doc, meta) in enumerate(zip(resultado['documents'], resultado['metadatas'])):
            print(f"ID: {resultado['ids'][i]}")
            print(f"PÁGINA: {meta.get('pagina')}")
            print(f"TRECHO:\n{doc[:1500]}...") 
            print("-" * 40)
            
        print(f"\n✅ Total de fragmentos encontrados para este filtro: {len(resultado['documents'])}")

    except Exception as e:
        print(f"⚠️ Erro ao acessar o banco: {e}")

if __name__ == "__main__":
 
    quick_inspect(empresa="ENGIE_teste_15", ano=2024, pagina=136)