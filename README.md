# TraceESG

O sistema utiliza **LLMs (GPT-4o-mini)** e **Busca Semântica (RAG)** para encontrar valores e retornar o texto original como evidência para auditoria humana.

## Interface auditoria

Ondevisualziar : https://esgproject-daqzi9ycjpgvxjqbimpfna.streamlit.app/

## 🚀 Funcionalidades do sistema

O sistema possui as seguintes funcionalidades:

1.  **Ingestão**: Leitura de PDFs e quebra em blocos de texto (chunks).
2.  **Vetorização**: Armazenamento dos chunks no ChromaDB para busca semântica.
3.  **Extração**: O LLM identifica métricas e busca o "Evidência" para cada valor.
4.  **Curadoria**: A Interface Streamlit permite a integração de todo o fluxo da aplicação.
5.  **Dianóstico**: Análise do desempenho do sistema: acurácia, precisão, f1-score. Comparação de métricas entre empresas e diferentes anos.


## 🛠️ Tecnologias Utilizadas

* **Python 3.10+**
* **LangChain**: Orquestração da IA e RAG.
* **OpenAI GPT-4o**: Modelo de linguagem para extração de alta precisão.
* **ChromaDB**: Banco de dados vetorial local.
* **Streamlit**: Portal de auditoria e interface de usuário.
* **Pandas**: Manipulação de dados e consolidação de bases.

## 📂 Estrutura do Projeto

```text
├── api 
│   └── server.py     # Rota de entrada para processamento de documentos
│
├── app
│   ├── pages/
│   └── static/
│
├── data/
│   ├── raw/          # PDFs originais para processamento
│   ├── processed/    # PDFs arquivados após processamento bem-sucedido
│   └── output/       # Saídas (CSVs individuais, JSONs de auditoria e Base Gold)
├── src/
│   ├── agents/       # ESGMetricProcessor (Lógica da IA)
│   ├── extractors/   # ESGDocumentLoader (Leitura de PDF)
│   └── utils/        # Configurações de métricas e indicadores JSON
├── main.py           # Aplicação WEB (Streamlit)
├── requirements.txt  # Bibliotecas necessárias para o funcionamento do sistema
└── .env              # Chaves de API e credenciais
```

## Como executar

1. Crie e ative um ambiente virtual:
```sh
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
```
2. Instale as dependências:
```sh
pip install -r requirements.txt
```

3. Entre na pasta traceesg
```sh
cd traceesg
```

4. Execute o app:
```sh
streamlit run main.py
```

5. Execute o servidor:
```sh
python -m api.server
```