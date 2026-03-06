import chromadb
import pandas as pd

# Conecta ao banco
client = chromadb.PersistentClient(path="./data/output/chroma_db")
collection = client.get_collection(name="esg_documents")

# Puxa os dados
data = collection.get()

# Organiza em um DataFrame do Pandas
if data['ids']:
    df = pd.DataFrame({
        "ID": data['ids'],
        "Texto": [doc[:100] + "..." for doc in data['documents']], # Resumo do texto
        "Metadados": data['metadatas']
    })
    
    # Expande os metadados em colunas separadas
    df_meta = pd.json_normalize(df['Metadados'])
    df_final = pd.concat([df[['ID', 'Texto']], df_meta], axis=1)
    
    print(f"\nTotal de registros: {len(df_final)}")
    print(df_final.head(10)) # Mostra as 10 primeiras linhas
    
    # Opcional: Salvar para CSV para abrir no Excel
    df_final.to_csv("inspecao_chroma.csv", index=False, encoding='utf-8-sig')
    print("\n✅ Arquivo 'inspecao_chroma.csv' gerado para visualização no Excel!")
else:
    print("O banco de dados está vazio.")