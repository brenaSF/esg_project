import pandas as pd
import plotly.express as px 
import streamlit as st
from dotenv import load_dotenv
import os
from src.services.diagnostic_service import (
    carregar_dados_para_diagnostico)
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy,context_precision,context_recall

from datasets import Dataset
from langchain_openai import ChatOpenAI

load_dotenv()
DIR_OUTPUT = os.getenv("DIR_OUTPUT")
llm_model = os.getenv("llm_model")
METRICAS_PDF = os.getenv("METRICAS_PDF")

color_map = {
    'Crítico': '#EF553B', 
    'Regular': '#FECB52',  
    'Bom': '#00CC96'      
}

def detectar_status(df):

    df["is_correto"] = df.apply(lambda linha: 0 if str(linha.get('Status_Auditoria', 'pendente')).lower() == 'inconsistente' else 1, axis=1)

    return df

def categorizar_status(valor):
    if valor < 70:
        return 'Crítico'
    elif valor < 80:
        return 'Regular'
    else:
        return 'Bom'

def calcular_acuracia(df):

    df_results = df.groupby("Empresa").agg(
        Total_Indicadores=("Valor", "size"),
        Acertos_Reais=("is_correto", "sum")
    ).reset_index()

    df_results["Acurácia (%)"] = (
        (df_results["Acertos_Reais"] / df_results["Total_Indicadores"]) * 100
    ).round(2)

    return df_results


@st.cache_data(show_spinner="Analisando fidelidade dos dados com Ragas...")
def obter_relatorio_ragas(dataframe):
    df_para_ragas = preparar_dataframe_para_ragas(dataframe)
    return executar_avaliacao_ragas(df_para_ragas)



def executar_avaliacao_ragas(df_preparado):
    evaluator_llm = ChatOpenAI(model="gpt-4o-mini")
    
    dataset = Dataset.from_dict(df_preparado[[
        "question", "answer", "contexts","ground_truth"
    ]].to_dict('list'))
    
   
    result = evaluate(
        dataset=dataset,
        metrics=[
            faithfulness,       
            answer_relevancy, 
            context_precision,
            context_recall
        ],
        llm=evaluator_llm
    )
    
    return result.to_pandas()

def preparar_dataframe_para_ragas(df):
    """
    Ajusta o DF vindo do diagnostic_service para o formato Ragas.
    """
    df_ragas = df.copy()
    

    df_ragas = df_ragas.rename(columns={
        "Metrica": "question",      
        "Valor": "answer",        
        "Evidencia": "contexts",   
        "Gabarito": "ground_truth"
    })
    
    df_ragas["contexts"] = df_ragas["contexts"].apply(lambda x: [str(x)] if pd.notnull(x) else [""])
    df_ragas["ground_truth"] = df_ragas["ground_truth"].fillna("").astype(str)
    
    df_ragas = df_ragas.fillna("N/A")
    
    return df_ragas

def processar_metricas_detalhadas(df):
    """
    Calcula Precisão, Recall e Acurácia corrigindo o erro de tipos.
    """
    df = df.copy()

   
    if 'Status_Auditoria' in df.columns:
        status_lower = df['Status_Auditoria'].astype(str).str.lower()
        df["is_correto"] = status_lower.str.contains('consistente') & ~status_lower.str.contains('inconsistente')
        df["is_correto"] = df["is_correto"].astype(int)
    else:
        df["is_correto"] = 0

    if 'Valor' in df.columns:
        df["is_tentativa"] = df['Valor'].notnull() & (df['Valor'].astype(str).str.strip() != "")
    else:
        df["is_tentativa"] = 0

    df_results = df.groupby("Empresa").agg(
        Total_Tentativas=("is_tentativa", "sum"),   
        Acertos_Totais=("is_correto", "sum")        
    ).reset_index()


    try:
        total_alvo = int(METRICAS_PDF)
    except:
        total_alvo = 17 
        
    df_results["Total_Gabarito"] = total_alvo
   
    df_results["Precisão (%)"] = (
        (df_results["Acertos_Totais"] / df_results["Total_Tentativas"].replace(0, 1)) * 100
    ).round(2)

    df_results["Recall (%)"] = (
        (df_results["Acertos_Totais"] / df_results["Total_Gabarito"].replace(0, 1)) * 100
    ).round(2)

   
    total_geral = df_results["Total_Tentativas"] + df_results["Total_Gabarito"] - df_results["Acertos_Totais"]
    df_results["Acurácia (%)"] = (
        (df_results["Acertos_Totais"] / total_geral.replace(0, 1)) * 100
    ).round(2)

    p = df_results["Precisão (%)"] / 100
    r = df_results["Recall (%)"] / 100
    df_results["F1-Score (%)"] = (
        (2 * (p * r) / (p + r).replace(0, 1)) * 100
    ).round(2)

    df_results['Status_Precisao'] = df_results['Precisão (%)'].apply(categorizar_status)
    df_results['Status_Recall'] = df_results['Recall (%)'].apply(categorizar_status)
    df_results['Status_Acuracia'] = df_results['Acurácia (%)'].apply(categorizar_status)
    df_results['Status_F1Score'] = df_results['F1-Score (%)'].apply(categorizar_status)


    return df_results

def obter_falhas_extracao(df):
    """
    Retorna apenas as linhas onde o status contém a palavra 'inconsistente',
    ignorando emojis ou variações de maiúsculas/minúsculas.
    """
    # Usamos .str.contains para ignorar o emoji que acompanha a string
    mask_inconsistente = df['Status_Auditoria'].astype(str).str.lower().str.contains('inconsistente', na=False)
    
    df_falhas = df[mask_inconsistente].copy()
    
    colunas_uteis = ['Empresa', 'Metrica', 'Valor','Gabarito', 'Evidencia', 'Página']
    colunas_presentes = [c for c in colunas_uteis if c in df_falhas.columns]
    
    return df_falhas[colunas_presentes]

def render_acuracia_extracao(arquivo_selecionado):

    st.markdown("""
        <div class="main-card">
            <h2>Avaliação da qualidade da extração.</h2>
            <p>Analise a precisão e a confiabilidade dos dados processados.</p>
        </div>
    """, unsafe_allow_html=True)
    
    
    df = carregar_dados_para_diagnostico(arquivo_selecionado)
    if df.empty:
        st.warning("Dados não encontrados.")
        return

    df_results = processar_metricas_detalhadas(df)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Empresa", df_results['Empresa'].iloc[0])
    with m2:
        st.metric("Total Gabarito", int(df_results['Total_Gabarito'].iloc[0]))
    with m3:
        st.metric("Tentativas IA", int(df_results['Total_Tentativas'].iloc[0]))

    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### Precisão", help="Precisão: De tudo que a IA extraiu, quanto estava correto?")
        fig_prec = px.bar(
        df_results, 
        x="Empresa", 
        y="Precisão (%)", 
        range_y=[0, 110], 
        text_auto='.1f',
        color="Status_Precisao",
        color_discrete_map=color_map,
        category_orders={"Status_Precisao": ["Bom", "Regular", "Crítico"]}
        )

        fig_prec.update_layout(
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=False
        )
    
        st.plotly_chart(fig_prec, use_container_width=True)

    with c2:
        st.markdown("### Recall", help="Recall: De tudo que existia para extrair, quanto a IA conseguiu encontrar?")
        fig_rec = px.bar(
        df_results, 
        x="Empresa", 
        y="Recall (%)", 
        range_y=[0, 110], 
        text_auto='.1f',
        color="Status_Recall",
        color_discrete_map=color_map,
        category_orders={"Status_Recall": ["Bom", "Regular", "Crítico"]}
        )
    
        fig_rec.update_layout(
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=False
        )
        
        st.plotly_chart(fig_rec, use_container_width=True)

    c3, c4 = st.columns(2)

    with c3:
        st.markdown("### Acurácia", help="Recall: De tudo que existia para extrair, quanto a IA conseguiu encontrar?")
        fig_rec = px.bar(
        df_results, 
        x="Empresa", 
        y="Acurácia (%)", 
        range_y=[0, 110], 
        text_auto='.1f',
        color="Status_Acuracia",
        color_discrete_map=color_map,
        category_orders={"Status_Acuracia": ["Bom", "Regular", "Crítico"]}
        )
    
        fig_rec.update_layout(
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=False
        )
        
        st.plotly_chart(fig_rec, use_container_width=True)

    with c4:
        st.markdown("### Acurácia", help="Recall: De tudo que existia para extrair, quanto a IA conseguiu encontrar?")
        fig_rec = px.bar(
        df_results, 
        x="Empresa", 
        y="F1-Score (%)", 
        range_y=[0, 110], 
        text_auto='.1f',
        color="Status_F1Score",
        color_discrete_map=color_map,
        category_orders={"Status_F1Score": ["Bom", "Regular", "Crítico"]}
        )
    
        fig_rec.update_layout(
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=False
        )
        
        st.plotly_chart(fig_rec, use_container_width=True)

    st.markdown("### Diagnóstico de Falhas")
    
    col_btn, _ = st.columns([1, 2]) 
    
    with col_btn:
        with st.popover("🔍 Ver itens não extraídos (Falhas)"):
            st.write("Abaixo estão os indicadores que a IA não conseguiu capturar ou extraiu incorretamente:")
            
            df_falhas = obter_falhas_extracao(df) 
            
            if not df_falhas.empty:
                st.dataframe(df_falhas, use_container_width=True, hide_index=True)
                
                csv = df_falhas.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Baixar relatório de erros (.csv)",
                    data=csv,
                    file_name='falhas_extracao_esg.csv',
                    mime='text/csv',
                )
            else:
                st.success("Nenhuma falha crítica encontrada para este relatório!")
                
    st.markdown("### 🤖 Avaliação de IA (Ragas Framework)")
    
    if st.button("Gerar Relatório de Qualidade Ragas"):
        with st.spinner("Analisando fidelidade dos dados com GPT-4o-mini..."):
            df_para_ragas = preparar_dataframe_para_ragas(df)
            df_ragas_final = executar_avaliacao_ragas(df_para_ragas)
            
            cols = st.columns(4)
            cols[0].metric("Fidelidade", f"{df_ragas_final['faithfulness'].mean():.2f}")
            cols[1].metric("Relevância", f"{df_ragas_final['answer_relevancy'].mean():.2f}")
            cols[2].metric("Context Recall", f"{df_ragas_final['context_recall'].mean():.2f}")
            cols[3].metric("Context Precision", f"{df_ragas_final['context_precision'].mean():.2f}")
        
            
            st.dataframe(df_ragas_final, use_container_width=True)

    with st.expander("Ver Tabela Detalhada"):
        st.dataframe(df_results, use_container_width=True, hide_index=True)