# src/prompts/esg_prompts.py

DISCOVERY_PROMPT_TEMPLATE_300 = """Role: Você é um Engenheiro de Dados ESG especializado em métricas de impacto ambiental do Setor Elétrico (GRI 302, 303 e 305).
Objetivo: Extrair 9 valores quantitativos e identificar omissões técnicas nos relatórios para o ano {ano}.

### TAREFA:
Para cada métrica do esquema abaixo, gere uma "Query de Localização". 
Esta query será usada em um sistema de busca (RAG), então ela deve ser descritiva.
Diferencie explicitamente valores absolutos de percentuais. Se o dicionário pede 'total', 
extraia o número inteiro; se pede 'percentual', extraia o valor com o símbolo %.

### REGRAS DE EXTRAÇÃO:
1. **Especificidade de Gases**: Não aceite apenas "Emissões Totais". Priorize a quebra por tipo de gás ($SF_6$, $CH_4$, $N_2O$).
2. **Tratamento de Unidades**: Converta ou identifique claramente se o valor está em Toneladas (t) ou Toneladas de $CO_2$ equivalente ($tCO_2e$). 
3. **Métricas de Perda**: No setor elétrico, diferencie "Consumo Interno" de "Perdas na Distribuição/Transmissão". 
4. **Detecção de Vazio Técnico**: Se a empresa cita "mudanças climáticas" mas não apresenta a tabela de emissões de Escopo 1, 2 ou 3, marque como STATUS: OMISSÃO TÉCNICA CRÍTICA.
5.  Sempre conte as colunas a partir do cabeçalho. Se o cabeçalho tem 5 colunas (Indicador, Unidade, 2020, 2021, 2022), certifique-se de que o valor extraído pertence à 5ª coluna.
6.  As unidades de medida pra este escopo são (t/ano), Mil tCO2e, tCO2e/(R$ mil)

### DICIONÁRIO DE MÉTRICAS (CHAVES OBRIGATÓRIAS):
{{
    "emissoes_sf6": "Localize 'Emissões fugitivas de SF6' ou 'Hexafluoreto'. Extraia o valor da coluna do {ano}.",
    "emissoes_no_x": "Localize 'Emissões Totais de NOx' ou 'Óxidos de Nitrogênio'.",
    "emissoes_so_x": "Localize 'Emissões Totais de SOx' ou 'Óxidos de Enxofre'.",
    "material_particulado_mp": "Localize 'Emissões Totais de MP' ou 'Material Particulado'.",
    "escopo_2_sem_perdas": "Busque especificamente por 'Escopo 2 (sem perdas)' ou 'Escopo 2 líquido'.",
    "perdas_tecnicas_energia": "Localize o volume ou percentual de energia perdida na transmissão/distribuição (Métrica Setorial EU12).",
    "emissoes_totais_gee_rol": "Localize a relação de tCO2e emitida por cada Megawatt-hora (MWh) gerado ou distribuído.",
    "consumo_combustivel_fossil": "Total de combustíveis não renováveis consumidos (GRI 302-1) em Joules ou unidades de volume.",
    "emissoes_biogenicas_co2": "Localize emissões de CO2 provenientes de fontes biológicas (queima de biomassa)."
}}

### EXEMPLO DE SAÍDA ESPERADA:
{{
    "emissoes_sf6": {{
        "valor": 0.45,
        "unidade":Índice,
        "evidencia_texto": "Emissões fugitivas de SF6 em {ano} totalizaram 0,45 tCO2e",
        "status": "Encontrado"
    }},
    "emissoes_no_x": {{
        "valor": null,
        "unidade":(t/ano),
        "evidencia_texto": "Não foi encontrado dado numérico ou citação qualitativa.",
        "status": "Não Encontrado"
    }}
}}

Contexto: {context}
{format_instructions}
"""