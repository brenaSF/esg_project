import os
import shutil
import dotenv
import uvicorn
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import sys

# adiciona a pasta src ao sys.path (ajuste parents[n] se a estrutura for diferente)
SRC_DIR = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC_DIR))

from src.core.orchestrator import ESGAutomationOrchestrator

dotenv.load_dotenv()
app = FastAPI(title="ESG Curator API", description="Backend para extração RAG de relatórios sustentáveis")

for folder in ["data/raw", "data/processed", "data/output"]:
    os.makedirs(folder, exist_ok=True)



class FilePayload(BaseModel):
    filename: str
    empresa: str
    ano: int

@app.post("/process-file")
async def process_file(payload: FilePayload):
    """Endpoint para processar um arquivo PDF de relatório ESG."""
    caminho_origem = os.path.join(os.getenv("DIR_RAW"), payload.filename)

    if not os.path.exists(caminho_origem):
        raise HTTPException(status_code=404, detail=f"Arquivo {payload.filename} não encontrado no servidor.")
    
    try:
        orchestrator = ESGAutomationOrchestrator(caminho_origem, payload.empresa, payload.ano)
        
        if orchestrator.run_pipeline():
            caminho_destino = os.path.join("data/processed", payload.filename)
            shutil.move(caminho_origem, caminho_destino)
            return {"status": "success", "message": f"Relatório de {payload.empresa} processado."}
        
        return {"status": "error", "message": "Falha na extração de dados do PDF."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)