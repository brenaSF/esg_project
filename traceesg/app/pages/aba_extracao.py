
import streamlit as st
from src.services.storage_service import salvar_arquivo_upload, processar_arquivo_na_api
import os
import dotenv

dotenv.load_dotenv()  # Carrega variáveis de ambiente do arquivo .env

DIR_RAW = os.getenv("DIR_RAW")


API_URL = "http://localhost:8000/process-file"

def render_extracao() : 

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


