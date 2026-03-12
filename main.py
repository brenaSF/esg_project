import streamlit as st
import pandas as pd
import os
from datetime import datetime
import getpass
import logging
import requests
import shutil
from src.utils.style import apply_vitality_style
from src.utils.audit import obter_arquivos_pendentes, calcular_progresso

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
    # Certifique-se de que a pasta existe antes de tentar salvar
    os.makedirs(DIR_RAW, exist_ok=True)
    
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
                            file_path = os.path.join(DIR_RAW, uploaded_file.name)
                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())

                            payload = {
                                "filename": uploaded_file.name,
                                "empresa": empresa_nome,
                                "ano": int(ano_ref)
                            }
                   
                            try:
                                response = requests.post(API_URL, json=payload, timeout=300) # Timeout longo para LLM
                                
                                if response.status_code == 200:
                                    st.success(f"✅ {uploaded_file.name} processado com sucesso!")
                                else:
                                    # CORREÇÃO DO JSONDECODEERROR:
                                    try:
                                        erro_info = response.json().get('detail', 'Erro interno no servidor')
                                    except:
                                        erro_info = f"Resposta inválida do servidor (Status {response.status_code})"
                                    
                                    st.error(f"❌ Falha ao processar {uploaded_file.name}: {erro_info}")
                            
                            except requests.exceptions.ConnectionError:
                                st.error("🚨 Erro: API Offline. Inicie o backend (Uvicorn).")
                else:
                    st.error("Por favor, preencha o nome da empresa e suba os arquivos.")

with aba_auditoria:
    DIR_OUTPUT = "data/output"
    DIR_AUDITADOS = os.path.join(DIR_OUTPUT, "auditados")
    DIR_CSV = os.path.join(DIR_OUTPUT, "resultado_csv")
    DIR_EXCLUIDOS = os.path.join(DIR_OUTPUT, "excluidos")
    CAMINHO_GOLD = os.path.join(DIR_OUTPUT, "base_consolidada_esg.csv")

    for pasta in [DIR_AUDITADOS, DIR_EXCLUIDOS,DIR_CSV]:
        os.makedirs(pasta, exist_ok=True)

  

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

        caminho_arquivo_atual = os.path.join(DIR_CSV, arquivo_selecionado)

        if not os.path.exists(caminho_arquivo_atual):
            st.error("Arquivo selecionado não encontrado. Por favor, sincronize os dados.")
            st.stop() 

        df = pd.read_csv(caminho_arquivo_atual, sep=";")
        
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
                "Valor": st.column_config.NumberColumn("Valor", format="%.2f"),
                "Unidade": st.column_config.TextColumn("Unid.", width="small"),
                "Fonte (Texto Original)": st.column_config.TextColumn("Evidência (RAG)", width="large"),
                "Página": st.column_config.TextColumn("Pág", width="small")
            }
        )

        col1, col2, _ = st.columns([1, 1, 3])
        with col1:
            if st.button("✅ Aprovar e Consolidar", type="primary"):
                if os.path.exists(CAMINHO_GOLD):
                    base_gold = pd.read_csv(CAMINHO_GOLD, sep=";")
                    df_final = pd.concat([base_gold, df_editado], ignore_index=True)
                else:
                    df_final = df_editado
                
                df_final.to_csv(CAMINHO_GOLD, index=False, sep=";", encoding="utf-8-sig")
                os.remove(caminho_arquivo_atual) # Remove dos pendentes após aprovar
                st.success("Dados movidos para a base consolidada!")
                st.rerun()

        with col2:
            if st.button("🗑️ Descartar"):
                shutil.move(caminho_arquivo_atual, os.path.join(DIR_EXCLUIDOS, arquivo_selecionado))
                st.rerun()
    else:
      st.info("Nenhum relatório pendente de auditoria.")