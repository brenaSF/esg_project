import streamlit as st
import pandas as pd
import os
from datetime import datetime
import getpass

# Configuração da página para um visual moderno
st.set_page_config(
    page_title="ESG Curator Portal",
    layout="wide",
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)

# --- CSS Customizado para Estilização ---
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stExpander"] {
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        background-color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Sidebar (Filtros e Info) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3950/3950815.png", width=100) # Ícone ESG genérico
    st.title("ESG Control Panel")
    st.info(f"👤 **Usuário Ativo:** {getpass.getuser()}")
    st.divider()
    st.write("📅 **Data:**", datetime.now().strftime("%d/%m/%Y"))
    st.write("🚀 **Versão do Modelo:** GPT-4o-v1")

# --- Cabeçalho ---
st.title("🛡️ ESG Curator: Portal de Governança")
st.caption("Validação de dados extraídos por IA para relatórios de sustentabilidade")

# Definição de caminhos
CAMINHO_STAGING = "data/output/base_esg_processada_20251219_0953.csv"
CAMINHO_GOLD = "data/output/base_esg_FINAL_AUDITADA.csv"

if os.path.exists(CAMINHO_STAGING):
    df = pd.read_csv(CAMINHO_STAGING, sep=";")
    
    # --- Painel de Métricas Rápidas ---
    m1, m2, m3 = st.columns(3)

    # Verifica se o arquivo final auditado já existe para mudar o status visual
    base_auditada_existe = os.path.exists(CAMINHO_GOLD)

    with m1:
        st.metric("Total de Indicadores", len(df))
    with m2:
        st.metric("Categorias Encontradas", len(df['categoria'].unique()) if 'categoria' in df.columns else 1)
    with m3:
        # Lógica Dinâmica de Status
        if base_auditada_existe:
            st.metric("Status", "Finalizado", delta="Concluído", delta_color="normal")
        else:
            st.metric("Status", "Pendente", delta="Aguardando Revisão", delta_color="inverse")

    st.markdown("### 📋 Área de Auditoria")
    
    with st.expander("Expandir instruções de uso", expanded=False):
        st.write("""
            1. Verifique se os valores numéricos correspondem ao relatório PDF.
            2. Se houver erro de extração, clique na célula e corrija manualmente.
            3. Após validar todas as linhas, clique no botão **Aprovar Dados** no final da página.
        """)

    # --- Editor de Dados Profissional ---
    df_editado = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=True,
        column_config={
            "valor": st.column_config.NumberColumn("Valor Extraído", format="%.2f"),
            "unidade": st.column_config.TextColumn("Unidade"),
            "id_dashboard": st.column_config.SelectboxColumn("Indicador", options=["GRI 405-1", "GRI 305-1", "GRI 205-1"]),
            "categoria": st.column_config.TextColumn("Status", disabled=True)
        }
    )

    st.divider()

    # --- Ações de Finalização ---
    col1, col2, _ = st.columns([1, 1, 3])
    with col1:
        if st.button("✅ Aprovar Tudo", use_container_width=True, type="primary"):
            df_editado["status_validacao"] = "Auditado"
            df_editado["analista_responsavel"] = getpass.getuser()
            df_editado["data_aprovacao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df_editado.to_csv(CAMINHO_GOLD, index=False, sep=";", encoding="utf-8-sig")
            st.toast("Dados enviados para a Camada Gold!", icon="🚀")
            st.balloons()
            
    with col2:
        if st.button("🗑️ Rejeitar Lote", use_container_width=True):
            st.error("Lote enviado para re-processamento.")

else:
    st.container(border=True).success("🎉 **Tudo em dia!** Não há arquivos na fila de validação.")
    if st.button("🔄 Sincronizar Novos Dados"):
        st.rerun()