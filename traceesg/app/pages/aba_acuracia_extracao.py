import pandas as pd
import plotly.express as px 
import streamlit as st
from dotenv import load_dotenv
import os
from src.services.diagnostic_service import (
    carregar_dados_para_diagnostico)


load_dotenv()

DIR_OUTPUT = os.getenv("DIR_OUTPUT")

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

def render_acuracia_extracao(arquivo_selecionado):
    """Renderiza a aba de avaliação de acurácia da extração, mostrando a taxa de acerto por empresa."""
    st.title("Avaliação de Acurácia da Extração")
    
    df = carregar_dados_para_diagnostico(arquivo_selecionado)

    m1, m2, m3 = st.columns(3)
    with m1:
        nome_empresa = df['Empresa'].iloc[0] if 'Empresa' in df.columns else "N/A"
        st.metric("Empresa", nome_empresa)
    with m2:
        st.metric("Métricas", len(df))
    with m3:
        ano = df['Ano'].iloc[0] if 'Ano' in df.columns else "N/A"
        st.metric("Ano de Referência", ano)    

    df_status = detectar_status(df)

    # Calcular a acurácia por empresa
    df_results = calcular_acuracia(df_status)


    tentativas_da_ia = df[df['Valor'].notnull()] 

    acertos = tentativas_da_ia["is_correto"].sum() 
    total_tentativas = len(tentativas_da_ia) 

    precisao = (acertos / total_tentativas) * 100

    df_results["Precisão (%)"] = precisao.round(2)

    # recall
    # 1. Total de métricas que REALMENTE estavam no PDF (Gabarito)
    # No seu exemplo, eram 14 métricas presentes na página.
    metricas_existentes_no_pdf = 20 

    # 2. Total que o extrator acertou (Status Consistente)
    acertos = df["is_correto"].sum() 

    # 3. Cálculo do Recall
    # Se ele acertou as 14 que existiam: 14 / 14 = 1.0 (100%)
    # Se ele tivesse 'esquecido' 2, seriam 12 acertos: 12 / 14 = 0.85 (85%)
    recall = (acertos / metricas_existentes_no_pdf) * 100

    df_results["Recall (%)"] = recall.round(2)


    st.markdown("### Métrica de Acurácia")
    
    fig = px.bar(
        df_results, 
        x="Empresa", 
        y="Acurácia (%)", 
        text_auto='.1f',
        color="Acurácia (%)",
        color_continuous_scale="Viridis"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Métrica de Precisão")

    fig2 = px.bar(
        df_results, 
        x="Empresa", 
        y="Precisão (%)", 
        text_auto='.1f',
        color="Precisão (%)",
        color_continuous_scale="Cividis"
    )
    st.plotly_chart(fig2, use_container_width=True)
    fig3 = px.bar(
        df_results, 
        x="Empresa", 
        y="Recall (%)", 
        text_auto='.1f',
        color="Recall (%)",
        color_continuous_scale="Plasma" 
    )
    st.plotly_chart(fig3, use_container_width=True)


    with st.expander("Ver Tabela Detalhada"):
        st.dataframe(
            df_results.sort_values(by="Acurácia (%)", ascending=False),
            use_container_width=True,
            hide_index=True
        )