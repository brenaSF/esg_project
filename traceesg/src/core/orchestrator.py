import os
import pandas as pd
import json
import chromadb
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma
from src.core.extractor import ESGDocumentLoader
from src.core.ai_processor import ESGMetricProcessor
from dotenv import load_dotenv
import asyncio
load_dotenv()  # Carrega variáveis de ambiente do arquivo .env

DIR_OUTPUT = os.getenv("DIR_OUTPUT")
DIR_CSV = os.getenv("DIR_CSV")
class ESGAutomationOrchestrator:
    def __init__(self, pdf_path, empresa, ano):
        self.pdf_path = pdf_path
        self.empresa = empresa
        self.ano = ano
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        # Centralizando caminhos
        self.dir_output = DIR_OUTPUT
        self.dir_csv = DIR_CSV
        os.makedirs(self.dir_csv, exist_ok=True)

        # Inicialização dos componentes de IA
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=self.api_key)
        self.loader = ESGDocumentLoader()
        self.processor = ESGMetricProcessor()
        
        # Configuração ChromaDB
        self.collection_name = "esg_documents_v1"
        self.chroma_client = chromadb.PersistentClient(path=os.path.join(self.dir_output, "vectorstore"))
        self.vector_store = Chroma(
            client=self.chroma_client,
            collection_name=self.collection_name, 
            embedding_function=self.embeddings 
        )

    async def run_pipeline(self):
        # 1. Extração (Pre-processing do KDD)
        raw_data = self.loader.extract_all_text(self.pdf_path, self.empresa, self.ano)
        if not raw_data or not raw_data.get("chunks"):
            return False
        
        # 2. Persistência de Auditoria
        self._save_json_chunks(raw_data)

        #3. Deletar vetores antigos da mesma empresa e ano para evitar contaminação
        try:
            # Busca os IDs dos documentos que coincidem com os metadados
            existing_docs = self.vector_store.get(
                where={
                    "$and": [
                        {"empresa": self.empresa},
                        {"ano": int(self.ano)}
                    ]
                }
            )
            
            if existing_docs and existing_docs['ids']:
                self.vector_store.delete(ids=existing_docs['ids'])
                print(f"✅ {len(existing_docs['ids'])} vetores antigos para {self.empresa} - {self.ano} deletados.")
            else:
                print(f"ℹ️ Nenhum vetor antigo encontrado para {self.empresa} - {self.ano}.")
                
        except Exception as e:
            print(f"⚠️ Erro ao tentar limpar o ChromaDB: {e}")

        # 4. Transformação e Mineração (Vector Indexing + RAG)
        self._index_to_vector_db(raw_data)
        
        #5. Processamento LLM com RAG
        resultado_llm = await self.processor._extrair_com_rag(
            vector_store = self.vector_store,
            empresa=self.empresa,
            ano=self.ano
        )
        
        # 6. Exportação (Evaluation do KDD)
        return self._export_final_csv(resultado_llm)

    def _index_to_vector_db(self, raw_data):
        """Indexar os chunks extraídos no ChromaDB, associando metadados de empresa, ano e página."""
        documents = [
            Document(
                page_content=chunk.get("document", ""),
                metadata=chunk.get("metadata", {})
            ) for chunk in raw_data["chunks"] if chunk.get("document")
        ]
        if documents:
            self.vector_store.add_documents(documents)
        else:
            print(f"Aviso: Nenhum embedding gerado para {self.empresa}. Verifique a extração.")

    def _export_final_csv(self, dados_llm):
        try:
            df = pd.DataFrame(dados_llm)
            csv_path = os.path.join(self.dir_csv, f"resultado_{self.empresa}_{self.ano}.csv")
            df.to_csv(csv_path, index=False, sep=";", encoding="utf-8-sig")
            return True
        except Exception as e:
            print(f"Erro ao exportar CSV: {e}")
        return False

    def _save_json_chunks(self, raw_data):
        try:
            chunks_dir = os.path.join(self.dir_output, "chunks")
            os.makedirs(chunks_dir, exist_ok=True)
            path = os.path.join(chunks_dir, f"chunks_{self.empresa}_{self.ano}.json")
            with open(path, "w", encoding="utf-8") as f:

                json.dump(raw_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar JSON: {e}")
            return False