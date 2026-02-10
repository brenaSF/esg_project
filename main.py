
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

# Agora, em vez de definir o dicionário manualmente, você faz:
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

    # def run_pipeline(self):
    #     print(f"\n{'-'*50}\n🚀 Processando arquivo: {self.filename}")
    #     
    #     raw_data = self.loader.extract_content(self.pdf_path, CONFIG_ESG)
    #     
    #     if not raw_data or not raw_data.get("chunks"):
    #         print(f"⚠️ {self.filename}: Nenhum conteúdo relevante.")
    #         return False
    #
    #     # --- NOVA LÓGICA: Salva o JSON específico desta empresa/arquivo ---
    #     self._save_json_chunks(raw_data)
    #     
    #     # Extração LLM
    #     resultado_llm = self.processor._extrair_texto_estruturado_csv(raw_data["chunks"])
    #     
    #     # Exportação Personalizada
    #     self._export_final_csv(resultado_llm, raw_data["metadata"])
    #     return True
    #
    # def _save_json_chunks(self, raw_data):
    #     """Salva o JSON com os textos brutos de cada empresa separadamente"""
    #     # Pega o nome do arquivo sem a extensão .pdf
    #     nome_base = os.path.splitext(self.filename)[0].replace(" ", "_")
    #     
    #     # Cria um nome único: chunks_natura_20251219.json
    #     timestamp = datetime.now().strftime("%Y%m%d")
    #     json_filename = f"chunks_{nome_base}_{timestamp}.json"
    #     path = os.path.join(self.output_dir, json_filename)
    #     
    #     with open(path, "w", encoding="utf-8") as f:
    #         json.dump(raw_data, f, indent=4, ensure_ascii=False)
    #     print(f"📂 JSON de auditoria salvo: {json_filename}")

    def run_pipeline(self):
        print(f"\n{'-'*50}\n🚀 Processando arquivo: {self.filename}")
        
        # Etapa 1: Extração de conteúdo do PDF
        raw_data = self.loader.extract_content(self.pdf_path, CONFIG_ESG, empresa=self.empresa, ano=self.ano)
        
        if not raw_data or not raw_data.get("chunks"):
            print(f"⚠️ {self.filename}: Nenhum conteúdo relevante.")
            return False
   
        # Etapa 2: Salvar o JSON específico desta empresa/arquivo
        json_path = self._save_json_chunks(raw_data)
     
        print(f"📖 Lendo dados a partir do JSON: {os.path.basename(json_path)}")
        #Etapa 3: Ler o JSON salvo para garantir que a análise LLM seja feita a partir do arquivo persistido
        with open(json_path, "r", encoding="utf-8") as f:
            dados_para_processar = json.load(f)
        
        print(f"⌛ Etapa 4: Analisando chunks via LLM...")
        # Etapa 4: Análise LLM para extração de métricas
        resultado_llm = self.processor._extrair_texto_estruturado_csv(dados_para_processar["chunks"])
        
        self._export_final_csv(resultado_llm, dados_para_processar["metadata"])
        return True

    def _save_json_chunks(self, raw_data):
       
        json_filename = f"chunks_{self.empresa}_{self.ano}.json"

        chunks_dir = os.path.join(self.output_dir, "chunks")
    
        os.makedirs(chunks_dir, exist_ok=True)
        
        path = os.path.join(chunks_dir, json_filename)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=4, ensure_ascii=False)
        print(f"📂 JSON de auditoria criado com sucesso.")
        return path # Retornamos o caminho para o run_pipeline poder ler

    def _export_final_csv(self, dados_llm, metadata):
        #criar tabela
        df = pd.DataFrame(dados_llm)

        #reordenar
        cols_priority = ["empresa", "ano_relatorio", "Dado Extraído", "Valor", "Fonte (Texto Original)", "Página"]
        cols = [c for c in cols_priority if c in df.columns] + [c for c in df.columns if c not in cols_priority]
        df = df[cols]

        #nomear
        csv_filename = f"resultado_{self.empresa}_{self.ano}.csv"

        #salvar
        csv_dir = os.path.join(self.output_dir, "resultado_csv")
        os.makedirs(csv_dir, exist_ok=True)
        csv_path = os.path.join(csv_dir, csv_filename)

        # Salvamento com separador ';' e encoding UTF-8 com BOM para Excel
        df.to_csv(csv_path, index=False, sep=";", encoding="utf-8-sig")
        print(f"✅ Tabela de auditoria salva: {csv_filename}")


app = FastAPI(title="ESG Extractor API")

class FilePayload(BaseModel):
    filename: str
    empresa: str
    ano: int

def executar_processamento(arquivo: str, empresa: str = None, ano: int = None):
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