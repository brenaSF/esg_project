import pandas as pd
import plotly.express as px 
import streamlit as st
from dotenv import load_dotenv
import os
from src.services.diagnostic_service import (
    carregar_dados_para_diagnostico)


load_dotenv()

DIR_OUTPUT = os.getenv("DIR_OUTPUT")


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

    
    df["is_correto"] = df.apply(lambda linha: 0 if str(linha.get('Status_Auditoria', 'pendente')).lower() == 'inconsistente' else 1, axis=1)

    df_results = df.groupby("Empresa").agg(
        Total_Indicadores=("Valor", "size"),
        Acertos_Reais=("is_correto", "sum")
    ).reset_index()

    df_results["Acurácia (%)"] = (
        (df_results["Acertos_Reais"] / df_results["Total_Indicadores"]) * 100
    ).round(2)

    st.markdown("### Taxa de Acerto por Empresa (Métrica de Acurácia)")
    
    fig = px.bar(
        df_results, 
        x="Empresa", 
        y="Acurácia (%)", 
        text_auto='.1f',
        color="Acurácia (%)",
        color_continuous_scale="Viridis"
    )
    st.plotly_chart(fig, use_container_width=True)


    with st.expander("Ver Tabela Detalhada"):
        st.dataframe(
            df_results.sort_values(by="Acurácia (%)", ascending=False),
            use_container_width=True,
            hide_index=True
        )