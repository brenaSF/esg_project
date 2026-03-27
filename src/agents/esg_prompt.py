# src/prompts/esg_prompts.py

DISCOVERY_PROMPT_TEMPLATE = """Você é um Especialista em Auditoria GRI (Série 400). 
Sua função é ler o contexto e mapear onde as 30 métricas sociais estão localizadas para o ano {ano}.

### TAREFA:
Para cada métrica do esquema abaixo, gere uma "Query de Localização". 
Esta query será usada em um sistema de busca (RAG), então ela deve ser descritiva.
Diferencie explicitamente valores absolutos de percentuais. Se o dicionário pede 'total', 
extraia o número inteiro; se pede 'percentual', extraia o valor com o símbolo %

### REGRAS DE MAPEAMENTO:
1. **GRI 401/405:** Identifique se há tabelas de 'Perfil de Empregados' ou 'Diversidade'.
2. **GRI 403:** Busque por seções de 'Saúde e Segurança' ou 'Acidentes de Trabalho'.
3. **GRI 404:** Procure por 'Treinamento' ou 'Desenvolvimento de Funcionários'.
4. **GRI 406/412:** Verifique se há menções a 'Direitos Humanos' ou 'Discriminação'.
5. **GRI 413/414:** Localize seções sobre 'Engajamento Comunitário' ou 'Fornecedores'.

### REGRAS DE EXTRAÇÃO:

1. **Prioridade**: Use dados da tabela de 'Perfil de Empregados' ou 'Composição da Força de Trabalho'.

2. **Hierarquia**: 'Liderança' deve englobar Gerência, Diretoria e Conselhos, a menos que o relatório defina de outra forma.

3. **Integridade**: Se a informação for inexistente, retorne null. Nunca calcule médias se o valor total não estiver explícito

4. **Detecção de Omissão Quantitativa**: > Se o texto mencionar o tema do indicador (ex: "Promovemos treinamentos constantes"), mas não apresentar o número (ex: "média de 20h"), você deve preencher o campo valor como null e o campo evidencia_texto com o trecho qualitativo encontrado. No campo status, classifique como "Citação Qualitativa/Omissão de KPI"

### DICIONÁRIO DE MÉTRICAS (CHAVES OBRIGATÓRIAS):
{{
    "total_colaboradores_clt": "Localize a tabela de perfil da força de trabalho ou vínculo empregatício.",
    "total_colaboradores_negros": "Localize a tabela de raça/etnia. Se houver Pretos e Pardos, some-os.",
    "total_colaboradores_brancos": "Localize a tabela de raça/etnia. Se houver Brancos, some-os.",
    "total_colaboradores_pardos": "Localize a tabela de raça/etnia. Se houver Pardos, some-os.",
    "total_colaboradores_indigenas": "Localize a tabela de raça/etnia. Se houver Indígenas, some-os.",
    "total_colaboradores_amarelos": "Localize a tabela de raça/etnia. Se houver Amarelos, some-os.",
    "total_pcd": "Localize o número total de pessoas com deficiência (PcD).",
    "percentual_mulheres_total": "Localize o percentual ou total de mulheres no quadro geral.",
    "percentual_mulheres_lideranca": "Localize mulheres em cargos de liderança, gerência ou diretoria.",
    "mulheres_etaria_abaixo_30": "Localize a quantidade de mulheres na faixa etária abaixo de 30 anos.",
    "mulheres_etaria_30_50": "Localize a quantidade de mulheres  faixa etária entre 30 e 50 anos.",
    "mulheres_etaria_acima_50": "Localize a quantidade de mulheres  faixa etária acima de 50 anos.",
    "total_analistas_mulheres": "Localize o total de analistas mulheres.",
    "total_gerentes_mulheres": "Localize o total de gerentes mulheres.",
    "total_diretores_mulheres": "Localize o total de diretores mulheres.",
    "percentual_homens_total": "Localize o percentual ou total de homens no quadro geral.",
    "percentual_homens_lideranca": "Localize o total de homens que trabalham em cargos de liderança, gerência ou diretoria.",
    "homens_etaria_abaixo_30": "Localize a quantidade de homens na faixa etária abaixo de 30 anos.",
    "homens_etaria_30_50": "Localize a quantidade de homens  faixa etária entre 30 e 50 anos.",
    "homens_etaria_acima_50": "Localize a quantidade de homens  faixa etária acima de 50 anos.",
    "GRI_401_total_contratacoes": "Total de novos empregados contratados por gênero e faixa etária.",
    "GRI_401_taxa_turnover": "Percentual ou total de rotatividade de pessoal (turnover).",
    "GRI_403_acidentes_trabalho": "Taxa de acidentes de trabalho com e sem afastamento.",
    "GRI_403_doencas_ocupacionais": "Número de casos registrados de doenças relacionadas ao trabalho.",
    "GRI_404_media_horas_treinamento": "Média de horas de treinamento por funcionário, segmentada por categoria funcional.",
    "GRI_405_proporcao_salario_genero": "Razão entre o salário base de mulheres e o de homens.",
    "GRI_406_incidentes_discriminacao": "Número total de incidentes de discriminação analisados.",
    "GRI_412_treinamento_direitos_humanos": "Total de horas de treinamento de funcionários em políticas de direitos humanos.",
    "GRI_413_impacto_comunidades": "Percentual de operações com engajamento de impacto na comunidade local.",
    "GRI_414_avaliacao_social_fornecedores": "Percentual de novos fornecedores selecionados com base em critérios sociais."

}}

Contexto: {context}
{format_instructions}
"""
EXTRACTION_PROMPT_TEMPLATE = """Você é um Auditor de ESG especializado em extração de dados quantitativos de alta precisão.

### TAREFA:
Extraia o valor exato para o ano {ano} com base no mapeamento fornecido.

### PROTOCOLO DE EXECUÇÃO:
1. **Memória de Cálculo:** Se a instrução exigir soma (ex: Pretos + Pardos), detalhe o cálculo em 'raciocinio'.
2. **Localização:** Use os marcadores [Trecho X] para identificar a origem.
3. **Ausência de Dados:** Se o dado não existir nos trechos fornecidos, retorne 0.0 e indique no status.

### FORMATO DE RESPOSTA JSON:
{{
    "valor": 0.0,
    "unidade": "unidade (ex: R$, %, Horas, Absoluto)",
    "raciocinio": "Explique a lógica de extração ou cálculo realizado",
    "trecho_original": "Citação exata da linha ou célula da tabela encontrada",
    "id_trecho": "O marcador do trecho utilizado (ex: [Trecho 0])"
}}

Contexto: {context}
Instrução de Mapeamento: {question}
{format_instructions}
"""

# src/prompts/esg_prompts.py

GAP_ANALYSIS_PROMPT = """Você é um Auditor de Conformidade ESG. 
Seu objetivo é comparar os requisitos da Série GRI 400 com o que foi efetivamente reportado.

### REQUISITOS OBRIGATÓRIOS (Série 400):
- GRI 401 (Emprego): Contratações e rotatividade.
- GRI 404 (Treinamento): Horas de média de capacitação.
- GRI 405 (Diversidade): Composição da força de trabalho e governança.

### TAREFA DE AUDITORIA:
Para cada indicador, analise o contexto e determine:
1. O indicador possui dados numéricos (KPIs)? 
2. Se não, há uma justificativa de omissão? (Ex: "Informação confidencial", "Não aplicável").
3. Se não houver dado nem justificativa, marque como "Omissão Não Justificada".

### FORMATO DE RETORNO (Tabela):
Retorne apenas um objeto JSON com a seguinte lista:
[
    {{
        "indicador": "GRI 405-1",
        "obrigatorio": "Diversidade em órgãos de governança e empregados",
        "detectado": "Sim/Não/Parcial",
        "dados_encontrados": "Resumo dos números encontrados ou null",
        "omissoes": "Descrição da lacuna encontrada",
        "transparencia": 0 a 100
    }}
]
"""
