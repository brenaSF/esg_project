# Visão Geral da Arquitetura

O sistema utiliza uma arquitetura de RAG (Retrieval-Augmented Generation), separando a interface de usuário (Streamlit) do motor de processamento (FastAPI + LangChain).

---

## Etapas do Processo (Mapeamento KDD)

### 🟢 Fase 1 — Seleção e Coleta (Selection)
- **Entrada:** Arquivos PDF carregados via interface Streamlit.  
- **Armazenamento:** Arquivos movidos para `data/raw/` para aguardar processamento.  
- **Ação:** A API recebe o nome do arquivo, a empresa e o ano de referência, validando a existência do recurso.

### 🔵 Fase 2 — Pré-processamento e Limpeza (Preprocessing)
- Executada pela classe `ESGDocumentLoader`.  
- **Extração de Texto:** Conversão de PDF para texto bruto preservando a numeração de páginas.  
- **Fragmentação (Chunking):** O texto é dividido em blocos menores (chunks) para respeitar a janela de contexto da LLM e melhorar a recuperação.  
- **Persistência de Auditoria:** Um arquivo JSON com os chunks é gerado em `data/output/chunks/` para rastreio da origem dos dados.

### 🟡 Fase 3 — Transformação e Mineração (Transformation & Data Mining)
- Etapa central onde o orquestrador utiliza IA para extrair significado.  
- **Vetorização (Embeddings):** Uso do modelo `text-embedding-3-small` da OpenAI (vetores de 1536 dimensões).  
- **Indexação:** Armazenamento dos vetores no ChromaDB com metadatas (empresa, ano, página).  
- **Recuperação (Retrieval):** Consulta ao banco de vetores para obter trechos relevantes aos indicadores definidos em `esg_indicadores.json`.  
- **Geração (Generation):** A LLM (ex.: GPT-4o) analisa os trechos recuperados e estrutura a resposta final (Métrica, Valor, Unidade e Evidência).

### 🟠 Fase 4 — Avaliação e Interpretação (Evaluation)
- Executada na aba de Auditoria do Portal.  
- **Validação Humana:** O auditor revisa os dados extraídos pela IA, podendo corrigir valores ou validar a evidência (RAG).  
- **Consolidação:** Após aprovação, os dados saem do estado "Pendente" (CSV individual) e são integrados à Base Gold (`base_consolidada_esg.csv`), representando o conhecimento final descoberto.
