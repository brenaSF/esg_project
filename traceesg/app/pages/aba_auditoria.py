import streamlit as st # library in order to create the interface of the audit page
import os # library to handle file paths and operations
from src.services.audit_service import (
    carregar_dados_para_auditoria, 
    salvar_dados_auditados, 
    descartar_relatorio,
 
)

from dotenv import load_dotenv # library to load environment variables from a .env file

load_dotenv()

DIR_OUTPUT = os.getenv("DIR_OUTPUT")
DIR_AUDITADOS = os.getenv("DIR_AUDITADOS")



def render_auditoria(arquivo_selecionado): 
    """Renders the audit page where users can review and edit extracted ESG metrics before consolidating them into the final database."""
    
    st.markdown("""
        <div class="main-card">
            <h2>Auditoria de Dados Extraídos pela IA</h2>
            <p>Análise os dados extraídos e informe se é "Consistente" ou "Inconsistente".</p>
        </div>
    """, unsafe_allow_html=True)
    

    if arquivo_selecionado:

        df = carregar_dados_para_auditoria(arquivo_selecionado)

        if df is not None:
        
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
            
        
            df['Página'] = df['Página'].astype(str)

            if 'Status_Auditoria' not in df.columns:
                df['Status_Auditoria'] = "🟡 Pendente"
            
            # 2. Converter tudo para string para evitar conflito com NaT/NaN do Pandas
            df['Status_Auditoria'] = df['Status_Auditoria'].astype(str).replace(['nan', 'None', ''], "🟡 Pendente")
            
            # 3. Limpar espaços extras que podem quebrar a correspondência com as 'options'
            df['Status_Auditoria'] = df['Status_Auditoria'].str.strip()

            # Força o valor correto se o que vier do CSV não bater com as opções do Selectbox
            valid_options = ["🟡 Pendente", "🟢 Consistente", "🔴 Inconsistente"]
            df.loc[~df['Status_Auditoria'].isin(valid_options), 'Status_Auditoria'] = "🟡 Pendente"
 

            df_editado = st.data_editor(
                df,
                num_rows="dynamic",
                width="stretch",
                hide_index=True,
                column_config={
                    "Empresa": st.column_config.TextColumn("Empresa", disabled=True),
                    "Ano": st.column_config.NumberColumn("Ano", disabled=True),
                    "Metrica": st.column_config.TextColumn("Métrica", width="medium"),
                    "Valor": st.column_config.NumberColumn("Valor", format="%.6f"),
                    "Unidade": st.column_config.TextColumn("Unid.", width="small"),
                    "Evidencia": st.column_config.TextColumn("Evidência (RAG)", width="large"),
                    "Página": st.column_config.TextColumn("Pagina", width="medium"),
                    "Status_Auditoria": st.column_config.SelectboxColumn(
                    "Statis Auditoria",
                    help="Altere o status para atualizar a base de dados",
                    options=[
                        "🟡 Pendente", 
                        "🟢 Consistente", 
                        "🔴 Inconsistente"
                    ],
                    width="medium",
                    required=True,
                    default="🟡 Pendente"
                ),
                }
            )

            col1, col2, _ = st.columns([1, 1, 3])
            with col1:
                if st.button("✅ Aprovar e Consolidar", type="primary"):
                    salvar_dados_auditados(df_editado, arquivo_selecionado)
                    st.success("Dados movidos para a base consolidada!")
                    st.rerun()

            with col2:
                if st.button("🗑️ Descartar",type="secondary"):
                    descartar_relatorio(arquivo_selecionado)
                    st.success("Relatório descartado com sucesso!")
                    st.rerun()
        else:
            st.error("Erro ao carregar o arquivo.")
    else:
        st.info("Nenhum relatório pendente de auditoria.")

