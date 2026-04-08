import streamlit as st
import logging
from app.style import apply_vitality_style
from app.pages.aba_extracao import render_extracao
from app.pages.aba_auditoria import render_auditoria
from app.pages.aba_diagnostico import render_diagnostico
from app.pages.aba_acuracia_extracao import render_acuracia_extracao
from app.pages.side_bar import render_sidebar
logging.getLogger("streamlit.runtime.scriptrunner.script_run_context").setLevel(logging.ERROR)

st.set_page_config(
    page_title="TraceESG - Auditoria e Diagnóstico ESG",
    layout="wide",
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)
apply_vitality_style()


aba_principal, aba_extracao, aba_auditoria, aba_diagnostico , aba_acuracia_extracao = st.tabs(["Principal","🚀 Nova Extração", "🛡️ Auditoria de Dados", "Diagnóstico de Conformidade", "Acurácia da Extração"])

arquivo_selecionado, arquivo_auditado = render_sidebar()

with aba_extracao:
    render_extracao() 

with aba_auditoria:
    render_auditoria(arquivo_selecionado)
    pass


with aba_acuracia_extracao:
    if arquivo_auditado:
        render_acuracia_extracao(arquivo_auditado)
    else:
        st.warning("📊 Nenhuma métrica disponível. Selecione um arquivo na seção 'Relatórios Auditados'.")