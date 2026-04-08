import pandas as pd
import plotly.express as px 
import streamlit as st
from app.pages.side_bar import render_sidebar
from src.services.diagnostic_service import (
    carregar_dados_para_diagnostico,
    detectar_dados_numericos)
from dotenv import load_dotenv
import os
load_dotenv()

DIR_OUTPUT = os.getenv("DIR_OUTPUT")

import re

def detectar_dados_numericos(valor):
    # Converte para string e remove espaços em branco
    v = str(valor).strip()
    
    # Regex para: 
    # - Números inteiros ou decimais (com ponto ou vírgula)
    # - Opcionalmente terminados em %
    padrao = r'^-?\d+([.,]\d+)?%?$'
    
    if re.match(padrao, v):
        return 1
    return 0

def render_diagnostico(arquivo_selecionado):
    st.title("Diagnóstico de Transparência ESG")
    
    if not arquivo_selecionado:
        st.info("Selecione um arquivo na barra lateral para começar.")
        return

    df = carregar_dados_para_diagnostico(arquivo_selecionado)

    
    if df is None or df.empty:
        st.error(f"Erro ao carregar ou arquivo vazio: {arquivo_selecionado}")
        return
    
    m1, m2, m3 = st.columns(3)
    with m1:
        nome_empresa = df['Empresa'].iloc[0] if 'Empresa' in df.columns else "N/A"
        st.metric("Empresa", nome_empresa)
    with m2:
        st.metric("Métricas", len(df))
    with m3:
        ano = df['Ano'].iloc[0] if 'Ano' in df.columns else "N/A"
        st.metric("Ano de Referência", ano)


    # --- PROCESSAMENTO ---
    
    # 1. Criamos flags binárias para facilitar a soma posterior
    df["is_numerico"] = df["Valor"].apply(detectar_dados_numericos)

    # 2. Agrupamento Consolidado
    # Contamos o tamanho do grupo (Total) e somamos as flags (Válidos)
    df_diag = df.groupby("Empresa").agg(
        Total_Indicadores=("Valor", "size"),
        Dados_Numericos=("is_numerico", "sum")
    ).reset_index()

    # 3. Cálculos Derivados
    df_diag["Omissões"] = df_diag["Total_Indicadores"] - df_diag["Dados_Numericos"]
    
    # Cálculo da porcentagem com tratamento para divisão por zero
    df_diag["Índice de Transparência (%)"] = (
        (df_diag["Dados_Numericos"] / df_diag["Total_Indicadores"]) * 100
    ).round(2)

    # --- VISUALIZAÇÃO ---
    
    # Métricas de destaque (KPIs)
    col1, col2 = st.columns(2)
    media_geral = df_diag["Índice de Transparência (%)"].mean()
    col1.metric("Média de Transparência", f"{media_geral:.1f}%")
    col2.metric("Total de Empresas", len(df_diag))

    st.markdown("### Índice de Transparência por Empresa")
    
    # Gráfico com Plotly
    fig = px.bar(
        df_diag.sort_values("Índice de Transparência (%)", ascending=False), 
        x="Empresa", 
        y="Índice de Transparência (%)", 
        color="Índice de Transparência (%)",
        range_y=[0, 100],
        color_continuous_scale="RdYlGn",
        text_auto='.1f' 
    )
    
    fig.update_layout(showlegend=False)

    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("Ver Tabela Detalhada"):
        st.dataframe(
            df_diag.sort_values(by="Índice de Transparência (%)", ascending=False),
            use_container_width=True,
            hide_index=True
        )