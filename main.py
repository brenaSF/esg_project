import streamlit as st
import pandas as pd
import os
import getpass
import logging
import shutil
from src.utils.style import apply_vitality_style
from src.utils.audit import obter_arquivos_pendentes, calcular_progresso
from src.services.storage_service import salvar_arquivo_upload, processar_arquivo_na_api

from src.services.audit_service import (
    carregar_dados_para_auditoria, 
    consolidar_e_limpar, 
    descartar_relatorio
)

logging.getLogger("streamlit.runtime.scriptrunner.script_run_context").setLevel(logging.ERROR)

st.set_page_config(
    page_title="ESG Curator Portal",
    layout="wide",
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)
apply_vitality_style()


aba_principal, aba_extracao, aba_auditoria = st.tabs(["Principal","🚀 Nova Extração", "🛡️ Auditoria de Dados"])

with aba_principal:
    st.markdown("""
        <div class="main-card">
            <h1>Bem-vindo ao ESG Curator Portal</h1>
            <p>Gerencie a extração e auditoria de relatórios ESG com inteligência artificial.</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="white-card">
            <h2>Sobre o Portal</h2>
            <p>Este portal foi desenvolvido para facilitar a gestão de relatórios ESG, utilizando técnicas avançadas de inteligência artificial para extração e auditoria de dados.</p>
        </div>
    """, unsafe_allow_html=True)
    
with aba_extracao:
    DIR_RAW = "data/raw"
    
    API_URL = "http://localhost:8000/process-file"

    st.markdown("""
        <div class="main-card">
            <h2>Extração de Relatórios ESG</h2>
            <p>Carregue os PDFs para processamento via IA e geração de evidências.</p>
        </div>
    """, unsafe_allow_html=True)
    
    col_input, col_info = st.columns([1, 1])
    
    with col_input:
        with st.container(border=True):
            upload_files = st.file_uploader("Arraste os relatórios PDF aqui", type=["pdf"], accept_multiple_files=True)
            empresa_nome = st.text_input("Nome da Empresa")
            ano_ref = st.number_input("Ano de Referência", min_value=2000, max_value=2030, value=2024)
            
            if st.button("▶️ Iniciar Processamento", use_container_width=True):
                if upload_files and empresa_nome:
                    with st.spinner("Enviando documentos para processamento..."):
                        for uploaded_file in upload_files:
                            salvar_arquivo_upload(uploaded_file, DIR_RAW)

                            sucesso, mensagem = processar_arquivo_na_api(
                                API_URL, 
                                uploaded_file.name, 
                                empresa_nome, 
                                ano_ref
                            )
                            
                            if sucesso:
                                st.success(f"{uploaded_file.name}: {mensagem}")
                            else:
                                st.error(f"{uploaded_file.name}: {mensagem}")
                else:
                    st.error("Por favor, preencha o nome da empresa e suba os arquivos.")

with aba_auditoria:
    DIR_OUTPUT = "data/output"
    DIR_AUDITADOS = os.path.join(DIR_OUTPUT, "auditados")

    # --- Sidebar com Barra de Progresso ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3950/3950815.png", width=80)
        st.title("🛡️ ESG Control Panel")
        st.info(f"👤 **Usuário:** {getpass.getuser()}")
        st.divider()

        # Seção de Progresso
        n_pend, n_conc, n_total, pct = calcular_progresso(DIR_AUDITADOS)
        st.subheader("📈 Progresso da Auditoria")
        st.progress(pct)
        st.write(f"**{n_conc} de {n_total}** relatórios revisados")
        
        st.divider()
        
        # Seleção de Arquivo
        arquivos_lista = obter_arquivos_pendentes()
        if arquivos_lista:
            arquivo_selecionado = st.selectbox(
                "Selecione o relatório para auditar:",
                arquivos_lista,
                help="Arquivos aguardando revisão humana"
            )
        else:
            st.success("✅ Nenhum arquivo pendente!")
            arquivo_selecionado = None

    

    # --- Área Principal ---
    st.title("🛡️ Portal de Governança ESG")
    

    if arquivo_selecionado:

        df = carregar_dados_para_auditoria(arquivo_selecionado)

        if df is not None:
        
            # --- Painel de Métricas Rápidas ---
            m1, m2, m3 = st.columns(3)
            with m1:
                nome_empresa = df['Empresa'].iloc[0] if 'Empresa' in df.columns else "N/A"
                st.metric("Empresa", nome_empresa)
            with m2:
                st.metric("Métricas", len(df))
            with m3:
                ano = df['Ano'].iloc[0] if 'Ano' in df.columns else "N/A"
                st.metric("Ano de Referência", ano)

            st.markdown(f"### 📋 Editando: `{arquivo_selecionado}`")
            
            # Injeção de colunas de auditoria se não existirem
            #if 'status_auditoria' not in df.columns: df['status_auditoria'] = 'Pendente'
            #if 'notas_auditor' not in df.columns: df['notas_auditor'] = ''

            df['Página'] = df['Página'].astype(str)

            df_editado = st.data_editor(
                df,
                num_rows="dynamic",
                width="stretch",
                hide_index=True,
                column_config={
                    "status_auditoria": st.column_config.SelectboxColumn(
                        "Status", options=["Pendente", "Validado", "Corrigido", "Inconsistente"]
                    ),
                    "Empresa": st.column_config.TextColumn("Empresa", disabled=True),
                    "Ano": st.column_config.NumberColumn("Ano", disabled=True),
                    "Dado Extraído": st.column_config.TextColumn("Métrica IA", width="medium"),
                    "Valor": st.column_config.NumberColumn("Valor", format="%.6f"),
                    "Unidade": st.column_config.TextColumn("Unid.", width="small"),
                    "Fonte (Texto Original)": st.column_config.TextColumn("Evidência (RAG)", width="large"),
                    "Página": st.column_config.TextColumn("Pág", width="small")
                }
            )

            col1, col2, _ = st.columns([1, 1, 3])
            with col1:
                if st.button("✅ Aprovar e Consolidar", type="primary"):
                    consolidar_e_limpar(df_editado, arquivo_selecionado)
                    st.success("Dados movidos para a base consolidada!")
                    st.rerun()

            with col2:
                if st.button("🗑️ Descartar"):
                    descartar_relatorio(arquivo_selecionado)
                    st.success("Relatório descartado com sucesso!")
                    st.rerun()
        else:
            st.error("Erro ao carregar o arquivo.")
    else:
        st.info("Nenhum relatório pendente de auditoria.")