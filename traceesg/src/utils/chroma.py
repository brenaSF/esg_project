import chromadb
import os

# O caminho onde o arquivo de 45MB reside
path_correto = "/home/brena/Documentos/GitHub/esg_project/data/output/vectorstore"

if os.path.exists(path_correto):
    # Conectamos na pasta PAI do arquivo chroma.sqlite3
    client = chromadb.PersistentClient(path=path_correto)
    cols = client.list_collections()
    
    print(f"--- Banco de Dados Real Encontrado (45MB) ---")
    print(f"Coleções: {[c.name for c in cols]}")
    
    for col in cols:
        count = col.count()
        print(f"Coleção '{col.name}': {count} chunks")
        
        # Se quiser ver um exemplo de chunk desta coleção:
        if count > 0:
            exemplo = col.peek(1)
            print(f"  Exemplo de texto: {exemplo['documents'][0][:100]}...")
else:
    print("Caminho não encontrado. Verifique se a pasta 'data' está na raiz do projeto.")