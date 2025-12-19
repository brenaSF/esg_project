import streamlit as st
import pandas as pd
import os
from datetime import datetime
import getpass

# Configuração da página
st.set_page_config(
    page_title="ESG Curator Portal",
    layout="wide",
    page_icon="🛡️",
)

# --- Configuração de Caminhos ---
DIR_OUTPUT = "data/output"
CAMINHO_GOLD = os.path.join(DIR_OUTPUT, "base_esg_FINAL_AUDITADA.csv")

# --- Funções de Apoio ---
def listar_arquivos_pendentes():
    # Lista todos os arquivos que começam com 'resultado_' e terminam em '.csv'
    if not os.path.exists(DIR_OUTPUT):
        return []
    arquivos = [f for f in os.listdir(DIR_OUTPUT) if f.startswith("resultado_") and f.endswith(".csv")]
    return arquivos

# --- Cabeçalho e Sidebar ---
with st.sidebar:
    st.title("🛡️ ESG Control Panel")
    st.info(f"👤 **Usuário:** {getpass.getuser()}")
    
    arquivos_pendentes = listar_arquivos_pendentes()
    
    st.subheader("📂 Seleção de Arquivo")
    if arquivos_pendentes:
        arquivo_selecionado = st.selectbox(
            "Selecione o relatório para auditar:",
            arquivos_pendentes,
            help="Estes são os arquivos gerados pelo pipeline de IA"
        )
    else:
        st.warning("Nenhum arquivo pendente.")
        arquivo_selecionado = None

# --- Área Principal ---
st.title("🛡️ Portal de Governança ESG")

if arquivo_selecionado:
    caminho_completo = os.path.join(DIR_OUTPUT, arquivo_selecionado)
    df = pd.read_csv(caminho_completo, sep=";")
    
    # --- Painel de Métricas ---
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Empresa", df['empresa'].iloc[0] if 'empresa' in df.columns else "N/A")
    with m2:
        st.metric("Indicadores", len(df))
    with m3:
        st.metric("Ano Referência", df['ano_relatorio'].iloc[0] if 'ano_relatorio' in df.columns else "N/A")

    st.markdown(f"### 📋 Auditando: `{arquivo_selecionado}`")
    
    # --- Editor de Dados ---
    # O editor agora mostra o Valor e a Fonte que a IA extraiu
    df_editado = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=True,
        column_config={
            "Valor": st.column_config.NumberColumn("Valor IA", format="%.4f"),
            "Fonte (Texto Original)": st.column_config.TextColumn("Evidência do PDF", width="large"),
            "Dado Extraído": st.column_config.TextColumn("Métrica", disabled=True),
            "Página": st.column_config.TextColumn("Pág", width="small")
        }
    )

    # --- Ações ---
    col1, col2, _ = st.columns([1, 1, 3])
    
    with col1:
        if st.button("✅ Aprovar e Consolidar", use_container_width=True, type="primary"):
            # Adiciona metadados de auditoria
            df_editado["auditado_por"] = getpass.getuser()
            df_editado["data_auditoria"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df_editado["arquivo_origem"] = arquivo_selecionado
            
            # Se a base GOLD já existir, concatena. Se não, cria.
            if os.path.exists(CAMINHO_GOLD):
                df_gold = pd.read_csv(CAMINHO_GOLD, sep=";")
                df_final = pd.concat([df_gold, df_editado], ignore_index=True)
            else:
                df_final = df_editado
            
            # Salva na base consolidada
            df_final.to_csv(CAMINHO_GOLD, index=False, sep=";", encoding="utf-8-sig")
            
            # Move o arquivo original para uma pasta 'archive' ou deleta para sair da fila
            os.makedirs(os.path.join(DIR_OUTPUT, "processados"), exist_ok=True)
            os.rename(caminho_completo, os.path.join(DIR_OUTPUT, "processados", arquivo_selecionado))
            
            st.success(f"Dados de {arquivo_selecionado} movidos para a base consolidada!")
            st.balloons()
            st.rerun()
            
    with col2:
        if st.button("🗑️ Descartar", use_container_width=True):
            os.remove(caminho_completo)
            st.warning("Arquivo removido da fila.")
            st.rerun()

else:
    st.container(border=True).success("🎉 **Tudo em dia!** Não há novos relatórios para validar.")
    if st.button("🔄 Buscar Novos Arquivos"):
        st.rerun()