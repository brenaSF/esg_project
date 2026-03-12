# Inteligência Artificial para Auditoria GRI 405-1

O sistema utiliza **LLMs (GPT-4o)** e **Busca Semântica (RAG)** para encontrar valores e, crucialmente, retornar o texto original como evidência para auditoria humana.

## 🚀 Arquitetura do Sistema

O fluxo de dados segue o padrão RAG (Retrieval-Augmented Generation):

1.  **Ingestão**: Leitura de PDFs e quebra em blocos de texto (chunks).
2.  **Vetorização**: Armazenamento dos chunks no ChromaDB para busca semântica.
3.  **Extração**: O LLM identifica métricas e busca o "Texto de Suporte" para cada valor.
4.  **Curadoria**: Interface Streamlit para validação humana.


## 🛠️ Tecnologias Utilizadas

* **Python 3.10+**
* **LangChain**: Orquestração da IA e RAG.
* **OpenAI GPT-4o**: Modelo de linguagem para extração de alta precisão.
* **ChromaDB**: Banco de dados vetorial local.
* **Streamlit**: Portal de auditoria e interface de usuário.
* **Pandas**: Manipulação de dados e consolidação de bases.

## 📂 Estrutura do Projeto

```text
├── data/
│   ├── raw/          # PDFs originais para processamento
│   ├── processed/    # PDFs arquivados após processamento bem-sucedido
│   └── output/       # Saídas (CSVs individuais, JSONs de auditoria e Base Gold)
├── src/
│   ├── agents/       # ESGMetricProcessor (Lógica da IA)
│   ├── extractors/   # ESGDocumentLoader (Leitura de PDF)
│   └── utils/        # Configurações de métricas e indicadores JSON
├── main.py           # Portal de Curadoria (Streamlit)
├── api.py            # API de extração e busca semântica
└── .env              # Chaves de API e credenciais

## Interface auditoria

Ondevisualziar : https://esgproject-daqzi9ycjpgvxjqbimpfna.streamlit.app/
