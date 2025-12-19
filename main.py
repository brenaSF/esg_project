
import os
import pandas as pd
import json
import shutil
from datetime import datetime
from src.extractors.document_loader import ESGDocumentLoader
from src.agents.ai_processor import ESGMetricProcessor
import dotenv
import json

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
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.filename = os.path.basename(pdf_path)
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        # DEFINIÇÃO FALTANTE:
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
        
        # --- ETAPA 1: Extração Bruta (PDF -> Memória) ---
        raw_data = self.loader.extract_content(self.pdf_path, CONFIG_ESG)
        
        if not raw_data or not raw_data.get("chunks"):
            print(f"⚠️ {self.filename}: Nenhum conteúdo relevante.")
            return False

        # --- ETAPA 2: Persistência (Salvamento do JSON) ---
        # Salvamos o arquivo no disco primeiro
        json_path = self._save_json_chunks(raw_data)
        
        # --- ETAPA 3: Leitura do JSON (Aqui a mágica acontece) ---
        # Agora o sistema lê o arquivo que acabou de salvar para processar
        print(f"📖 Lendo dados a partir do JSON: {os.path.basename(json_path)}")
        with open(json_path, "r", encoding="utf-8") as f:
            dados_para_processar = json.load(f)
        
        # --- ETAPA 4: Processamento LLM (Dados do JSON -> Dados Estruturados) ---
        print(f"⌛ Etapa 4: Analisando chunks via LLM...")
        # Enviamos os chunks vindos do ARQUIVO JSON, não da memória direta
        resultado_llm = self.processor._extrair_texto_estruturado_csv(dados_para_processar["chunks"])
        
        # --- ETAPA 5: Exportação Final ---
        self._export_final_csv(resultado_llm, dados_para_processar["metadata"])
        return True

    def _save_json_chunks(self, raw_data):
        nome_base = os.path.splitext(self.filename)[0].replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d")
        json_filename = f"chunks_empresa_{nome_base}_{timestamp}.json"
        path = os.path.join(self.output_dir, json_filename)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=4, ensure_ascii=False)
        print(f"📂 JSON de auditoria criado com sucesso.")
        return path # Retornamos o caminho para o run_pipeline poder ler

    def _export_final_csv(self, dados_llm, metadata):
        # 1. Determinar o nome da empresa
        empresa_detectada = metadata.get("empresa")
        if not empresa_detectada or empresa_detectada == "Bradesco":
            empresa_final = os.path.splitext(self.filename)[0].replace(" ", "_")
        else:
            empresa_final = empresa_detectada.replace(" ", "_")

        ano = metadata.get("ano", datetime.now().year)
        data_extracao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 2. Como dados_llm agora é uma LISTA de métricas, 
        # precisamos adicionar empresa/ano em cada item da lista
        for item in dados_llm:
            item["empresa"] = empresa_final
            item["ano_relatorio"] = ano
            item["data_extracao"] = data_extracao

        # 3. Criar DataFrame diretamente da lista
        df = pd.DataFrame(dados_llm)
        
        # 4. Reorganizar colunas para as mais importantes virem primeiro (opcional)
        cols_priority = ["empresa", "ano_relatorio", "Dado Extraído", "Valor", "Fonte (Texto Original)", "Página"]
        # Mantém as colunas existentes que batem com a prioridade
        cols = [c for c in cols_priority if c in df.columns] + [c for c in df.columns if c not in cols_priority]
        df = df[cols]

        # 5. Salvar
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"resultado_{empresa_final}_{ano}_{timestamp}.csv"
        csv_path = os.path.join(DIR_OUTPUT, csv_filename)

        df.to_csv(csv_path, index=False, sep=";", encoding="utf-8-sig")
        print(f"✅ Tabela de auditoria salva: {csv_filename}")

def main():
    # 1. Listar todos os PDFs na pasta RAW
    arquivos = [f for f in os.listdir(DIR_RAW) if f.lower().endswith(".pdf")]
    
    if not arquivos:
        print("📭 Ninguém para processar na pasta /data/raw")
        return

    print(f"📂 Encontrados {len(arquivos)} arquivos para processar.")

    for arquivo in arquivos:
        caminho_completo = os.path.join(DIR_RAW, arquivo)
        
        try:
            orchestrator = ESGAutomationOrchestrator(caminho_completo)
            sucesso = orchestrator.run_pipeline()
            
            if sucesso:
                # 2. Mover arquivo para PROCESSED após o sucesso
                destino = os.path.join(DIR_PROCESSED, arquivo)
                shutil.move(caminho_completo, destino)
                print(f"📦 Arquivo movido para: {DIR_PROCESSED}")
                
        except Exception as e:
            print(f"💥 Erro ao processar {arquivo}: {str(e)}")

if __name__ == "__main__":
    main()