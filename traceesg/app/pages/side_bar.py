# --- Sidebar com Barra de Progresso ---
import streamlit as st
import os
import getpass
from src.services.audit_service import (
    obter_arquivos_pendentes,
    calcular_progresso
)
from dotenv import load_dotenv

load_dotenv()

DIR_OUTPUT = os.getenv("DIR_OUTPUT")
DIR_AUDITADOS = os.getenv("DIR_AUDITADOS")

def render_sidebar():

    with st.sidebar:
        # --- Área Lateral ---  
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

        # Seleção de Arquivo - CSVs pendentes
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

        #Seleção de Arquivo - CSVs auditados (para aba de acurácia)
        st.divider()
        st.subheader("📊 Relatórios Auditados")
        arquivos_auditados = [f for f in os.listdir(DIR_AUDITADOS) if f.endswith('.csv')]
        if arquivos_auditados:
            arquivo_auditado = st.selectbox(
                "Selecione um relatório auditado para análise de acurácia:",
                arquivos_auditados,
                help="Arquivos já revisados e prontos para diagnóstico"
            )
        else:
            st.info("Aguardando conclusão de auditorias para gerar métricas de acurácia.")
            arquivo_auditado = None

        return arquivo_selecionado, arquivo_auditado