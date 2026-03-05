
import os
import pandas as pd
import json
import shutil
from datetime import datetime
from src.extractors.document_loader import ESGDocumentLoader
from src.agents.ai_processor import ESGMetricProcessor
import dotenv
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

import chromadb
from chromadb.utils import embedding_functions

dotenv.load_dotenv()

# Configuração de Diretórios
DIR_RAW = "./data/raw"
DIR_PROCESSED = "./data/processed"
DIR_OUTPUT = "./data/output"

# Criar pastas caso não existam
for folder in [DIR_RAW, DIR_PROCESSED, DIR_OUTPUT]:
    os.makedirs(folder, exist_ok=True)


def carregar_configuracao():
    caminho_config = "src/utils/esg_indicadores.json"
    with open(caminho_config, "r", encoding="utf-8") as f:
        return json.load(f)

CONFIG_ESG = carregar_configuracao()

class ESGAutomationOrchestrator:
    def __init__(self, pdf_path, empresa, ano):
        self.pdf_path = pdf_path
        self.filename = os.path.basename(pdf_path)
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.empresa = empresa
        self.ano = ano
        self.output_dir = DIR_OUTPUT 
        
        self.loader = ESGDocumentLoader(CONFIG_ESG)
        self.processor = ESGMetricProcessor(self.api_key)

        # --- Configuração do ChromaDB ---
        # Persistência local no diretório de saída
        self.chroma_client = chromadb.PersistentClient(path=os.path.join(DIR_OUTPUT, "chroma_db"))
        
        # Usando modelo default (all-MiniLM-L6-v2) ou OpenAI se preferir
        self.emb_fn = embedding_functions.DefaultEmbeddingFunction()
        
        # Criar ou obter a coleção
        self.collection = self.chroma_client.get_or_create_collection(
            name="esg_documents",
            embedding_function=self.emb_fn
        )

    def run_pipeline(self):
        print(f"\n{'-'*50}\n🚀 Processando arquivo: {self.filename}")
        
        # Etapa 1: Extração de conteúdo do PDF
        raw_data = self.loader.extract_all_text(self.pdf_path, empresa=self.empresa, ano=self.ano)

        print(raw_data)
        
        if not raw_data or not raw_data.get("chunks"):
            print(f" {self.filename}: Nenhum conteúdo relevante.")
            return False
   
        # Etapa 2: Salvar o JSON específico desta empresa/arquivo
        json_path = self._save_json_chunks(raw_data)

        # --- NOVO: Etapa 3: Indexar no Banco Vetorial ---
        print(f"🧠 Indexando no ChromaDB...")
        self._index_to_vector_db(raw_data)
     
        print(f"📖 Lendo dados a partir do JSON: {os.path.basename(json_path)}")
        with open(json_path, "r", encoding="utf-8") as f:
            dados_para_processar = json.load(f)
        
        print(f"⌛ Etapa 4: Analisando chunks via LLM...")
        # Etapa 4: Análise LLM para extração de métricas
        resultado_llm = self.processor._extrair_texto_estruturado_csv(dados_para_processar["metadata"],dados_para_processar["chunks"])
        
        self._export_final_csv(resultado_llm)
        return True
    
    def _index_to_vector_db(self, raw_data):
        """Insere os chunks de texto e metadados no ChromaDB."""
        documents = []
        metadatas = []
        ids = []

        for i, chunk in enumerate(raw_data["chunks"]):
            documents.append(chunk["contexto"])

            texto = chunk["contexto"]
            print(f"DEBUG: Indexando ID {i} | Caracteres: {len(texto)} | Começo: {texto[:50]}... | Fim: {texto[-50:]}")

            print(chunk['contexto'])
            
            metadatas.append({
                "empresa": self.empresa,
                "ano": self.ano,
                "pagina": chunk.get("page", 0),
                "source": self.filename
            })
            
            ids.append(f"{self.empresa}_{self.ano}_{i}")

        self.collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"✅ {len(ids)} fragmentos indexados no banco vetorial.")


    def _save_json_chunks(self, raw_data):
       
        json_filename = f"chunks_{self.empresa}_{self.ano}.json"

        chunks_dir = os.path.join(self.output_dir, "chunks")
    
        os.makedirs(chunks_dir, exist_ok=True)
        
        path = os.path.join(chunks_dir, json_filename)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=4, ensure_ascii=False)
        print(f"📂 JSON de auditoria criado com sucesso.")
        return path 

    def _export_final_csv(self, dados_llm):
        # 1. Cria o DataFrame com os dados retornados pelo LLM
        df = pd.DataFrame(dados_llm)

        # 3. Reordenar colunas (incluindo as novas colunas injetadas)
        cols_priority = ["Empresa", "Ano", "Dado Extraído", "Valor", "Fonte (Texto Original)", "Página"]
        
        # Filtra apenas colunas que realmente existem no DF
        existentes = [c for c in cols_priority if c in df.columns]
        outras = [c for c in df.columns if c not in cols_priority]
        df = df[existentes + outras]

        # 4. Configurar caminhos e salvar
        csv_filename = f"resultado_{self.empresa}_{self.ano}.csv"
        csv_dir = os.path.join(self.output_dir, "resultado_csv")
        os.makedirs(csv_dir, exist_ok=True)
        csv_path = os.path.join(csv_dir, csv_filename)

        # 5. Salvamento com encoding para Excel
        df.to_csv(csv_path, index=False, sep=";", encoding="utf-8-sig")
        print(f"✅ Tabela de auditoria salva: {csv_filename}")


app = FastAPI(title="ESG Extractor API")

class FilePayload(BaseModel):
    filename: str
    empresa: str
    ano: int

def executar_processamento(arquivo: str, empresa: str , ano: int ):
    """Lógica central de processamento de arquivos."""
    caminho_completo = os.path.join(DIR_RAW, arquivo)
    
    if not os.path.exists(caminho_completo):
        return {"status": "not_found", "message": "Arquivo não existe no DIR_RAW"}

    try:
        orchestrator = ESGAutomationOrchestrator(caminho_completo,empresa, ano)
        sucesso = orchestrator.run_pipeline()

        if sucesso:
            destino = os.path.join(DIR_PROCESSED, arquivo)
            shutil.move(caminho_completo, destino)
            return {"status": "processed", "message": f"Movido para {DIR_PROCESSED}"}
        else:
            return {"status": "skipped", "message": "Nenhum conteúdo relevante"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/process-all")
def process_all():
    """Processa todos os arquivos .pdf presentes em DIR_RAW e retorna um resumo do processamento."""
    arquivos = [f for f in os.listdir(DIR_RAW) if f.lower().endswith(".pdf")]
    if not arquivos:
        return {"processed": 0, "details": {}}

    details = {}
    for arquivo in arquivos:
        details[arquivo] = executar_processamento(arquivo)
    return {"processed": len([v for v in details.values() if v["status"] == "processed"]), "details": details}

@app.post("/process-file")
def process_file(payload: FilePayload):
    arquivo = payload.filename
    
    if not arquivo.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos .pdf são aceitos")
    
    result = executar_processamento(arquivo, payload.empresa, payload.ano)
    
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail=result["message"])
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
        
    return result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)