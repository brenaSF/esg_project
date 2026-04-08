import os
import pandas as pd
import shutil
import os
from dotenv import load_dotenv
import streamlit as st
load_dotenv()

DIR_OUTPUT = os.getenv("DIR_OUTPUT")
DIR_CSV = os.getenv("DIR_CSV")
DIR_AUDITADOS = os.getenv("DIR_AUDITADOS")
DIR_EXCLUIDOS = os.getenv("DIR_EXCLUIDOS")

def carregar_dados_para_auditoria(arquivo_nome):
    caminho = os.path.join(DIR_CSV, arquivo_nome)
    if os.path.exists(caminho):
        return pd.read_csv(caminho, sep=";")
    return None

def salvar_dados_auditados(df_editado, arquivo_nome):
    os.makedirs(DIR_AUDITADOS, exist_ok=True)
    
    caminho_origem = os.path.join(DIR_CSV, arquivo_nome)
    caminho_destino = os.path.join(DIR_AUDITADOS, arquivo_nome)

    try:
        # 1. Limpa e salva o DataFrame no diretório de destino
        df_to_save = df_editado.copy()
        df_to_save = df_to_save.loc[:, ~df_to_save.columns.str.match(r"^Unnamed")]
        df_to_save.to_csv(caminho_destino, index=False, sep=";", encoding="utf-8-sig")

        # 2. Verifica se o arquivo foi criado com sucesso antes de deletar a origem
        if os.path.exists(caminho_destino):
            if os.path.exists(caminho_origem):
                os.remove(caminho_origem)
            return True
        
        return False
    except Exception as e:
        st.error(f"Erro ao processar arquivos: {e}")
        return False
    
def descartar_relatorio(arquivo_nome):
    caminho_origem = os.path.join(DIR_CSV, arquivo_nome)
    os.makedirs(DIR_EXCLUIDOS, exist_ok=True)
    if os.path.exists(caminho_origem):
        shutil.move(caminho_origem, os.path.join(DIR_EXCLUIDOS, arquivo_nome))



def obter_arquivos_pendentes():
    if not os.path.exists(DIR_CSV): return []
    return [f for f in os.listdir(DIR_CSV) if f.endswith(".csv")]

def calcular_progresso(dir_auditados):
    pendentes = len(obter_arquivos_pendentes())
    concluidos = len([f for f in os.listdir(dir_auditados) if f.endswith(".csv")])
    total = pendentes + concluidos
    percentual = concluidos / total if total > 0 else 0
    return pendentes, concluidos, total, percentual