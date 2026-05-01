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

color_map = {
    'Crítico': '#EF553B',  # Vermelho
    'Regular': '#FECB52',  # Amarelo/Laranja
    'Bom': '#00CC96'       # Verde
}

def detectar_status(df):

    df["is_correto"] = df.apply(lambda linha: 0 if str(linha.get('Status_Auditoria', 'pendente')).lower() == 'inconsistente' else 1, axis=1)

    return df

def categorizar_status(valor):
    if valor < 70:
        return 'Crítico'
    elif valor < 90:
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

    df_results["Precisão (%)"] = (
        (df_results["Acertos_Totais"] / df_results["Total_Tentativas"].replace(0, 1)) * 100
    ).where(df_results["Total_Tentativas"] > 0, 0.0).round(2)

    df_results["Recall (%)"] = (
        (df_results["Acertos_Totais"] / df_results["Total_Gabarito"].replace(0, 1)) * 100
    ).where(df_results["Total_Gabarito"] > 0, 0.0).round(2)

    # 4. Enriquecimento de UI (Design Semântico)
    df_results['Status_Precisao'] = df_results['Precisão (%)'].apply(categorizar_status)
    df_results['Status_Recall'] = df_results['Recall (%)'].apply(categorizar_status)
    
    # Acurácia em RAG/Extração costuma ser o Recall ou F1-Score
    df_results["Acurácia (%)"] = df_results["Recall (%)"]

    return df_results

def obter_falhas_extracao(df):
    """
    Retorna apenas as linhas onde o gabarito esperava um dado, 
    mas a IA falhou ou errou.
    """
    # Filtra onde houve erro (is_correto == 0) mas era uma linha do gabarito
    df_falhas = df[df['Status_Auditoria'].astype(str).str.lower() == 'inconsistente'].copy()
    
    # Selecionamos apenas colunas úteis para o auditor não se perder
    colunas_uteis = ['Empresa', 'Metrica', 'Valor', 'Evidencia', 'Página']
    
    # Garante que só retornamos colunas que existem no seu DF
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

    # --- ABAIXO DOS GRÁFICOS ---
    st.markdown("### Diagnóstico de Falhas")
    
    col_btn, _ = st.columns([1, 2]) # Alinha o botão à esquerda
    
    with col_btn:
        with st.popover("🔍 Ver itens não extraídos (Falhas)"):
            st.write("Abaixo estão os indicadores que a IA não conseguiu capturar ou extraiu incorretamente:")
            
            # 'df' é o dataframe original carregado antes de processar as métricas
            df_falhas = obter_falhas_extracao(df) 
            
            if not df_falhas.empty:
                st.dataframe(df_falhas, use_container_width=True, hide_index=True)
                
                # Botão opcional para exportar essas falhas para análise posterior
                csv = df_falhas.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Baixar relatório de erros (.csv)",
                    data=csv,
                    file_name='falhas_extracao_esg.csv',
                    mime='text/csv',
                )
            else:
                st.success("Nenhuma falha crítica encontrada para este relatório!")

    with st.expander("Ver Tabela Detalhada"):
        st.dataframe(df_results, use_container_width=True, hide_index=True)