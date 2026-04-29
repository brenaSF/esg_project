import pandas as pd
import plotly.express as px 
import streamlit as st
from dotenv import load_dotenv
import os
from src.services.diagnostic_service import (
    carregar_dados_para_diagnostico)


load_dotenv()

DIR_OUTPUT = os.getenv("DIR_OUTPUT")
METRICAS_PDF = os.getenv("METRICAS_PDF")

def detectar_status(df):

    df["is_correto"] = df.apply(lambda linha: 0 if str(linha.get('Status_Auditoria', 'pendente')).lower() == 'inconsistente' else 1, axis=1)

    return df

def calcular_acuracia(df):

    df_results = df.groupby("Empresa").agg(
        Total_Indicadores=("Valor", "size"),
        Acertos_Reais=("is_correto", "sum")
    ).reset_index()

    df_results["Acurácia (%)"] = (
        (df_results["Acertos_Reais"] / df_results["Total_Indicadores"]) * 100
    ).round(2)

    return df_results
def processar_metricas_detalhadas(df):
    """
    Calcula Precisão, Recall e Acurácia corrigindo o erro de tipos.
    """
    # Garantir que trabalhamos em uma cópia para não afetar o original
    df = df.copy()

    # 1. Identifica o que é acerto (não inconsistente)
    # Verificamos se a coluna existe para evitar erros
    if 'Status_Auditoria' in df.columns:
        df["is_correto"] = (df['Status_Auditoria'].astype(str).str.lower() != 'inconsistente').astype(int)
    else:
        df["is_correto"] = 0

    # 2. Identifica o que é uma tentativa da IA (Valor não nulo e não vazio)
    if 'Valor' in df.columns:
        df["is_tentativa"] = df['Valor'].notnull() & (df['Valor'].astype(str).str.strip() != "")
    else:
        df["is_tentativa"] = 0

    # 3. Agrupa por empresa para calcular as métricas
    df_results = df.groupby("Empresa").agg(
        Total_Gabarito=("is_correto", "size"),      
        Total_Tentativas=("is_tentativa", "sum"),   
        Acertos_Totais=("is_correto", "sum")        
    ).reset_index()

    # --- CÁLCULOS FINAIS ---
    
    # PRECISÃO: (Acertos / Tentativas) -> Foco em não alucinar
    # Se Total_Tentativas for 0, a precisão será 0.0
    df_results["Precisão (%)"] = df_results.apply(
        lambda row: (row["Acertos_Totais"] / row["Total_Tentativas"] * 100) 
        if row["Total_Tentativas"] > 0 else 0.0, axis=1
    ).round(2)

    # RECALL: (Acertos / Total esperado no Gabarito) -> Foco em não omitir
    df_results["Recall (%)"] = (
        (df_results["Acertos_Totais"] / df_results["Total_Gabarito"]) * 100
    ).round(2)

    # ACURÁCIA: Seguindo sua lógica anterior
    df_results["Acurácia (%)"] = df_results["Recall (%)"]

    return df_results

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

    # Processa as métricas corretamente agrupadas
    df_results = processar_metricas_detalhadas(df)

    # Métricas de topo (usando a primeira empresa da lista como exemplo)
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Empresa", df_results['Empresa'].iloc[0])
    with m2:
        st.metric("Total Gabarito", int(df_results['Total_Gabarito'].iloc[0]))
    with m3:
        st.metric("Tentativas IA", int(df_results['Total_Tentativas'].iloc[0]))

    # --- GRÁFICOS ---
    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### Precisão")
        st.plotly_chart(px.bar(df_results, x="Empresa", y="Precisão (%)", range_y=[0,105], text_auto=True, color_discrete_sequence=['#636EFA']), use_container_width=True)
    
    with c2:
        st.markdown("### Recall")
        st.plotly_chart(px.bar(df_results, x="Empresa", y="Recall (%)", range_y=[0,105], text_auto=True, color_discrete_sequence=['#00CC96']), use_container_width=True)

    with st.expander("Ver Tabela Detalhada"):
        st.dataframe(df_results, use_container_width=True, hide_index=True)