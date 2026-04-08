import pandas as pd
import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

DIR_CSV = os.getenv("DIR_CSV")
DIR_AUDITADOS = os.getenv("DIR_AUDITADOS")


def carregar_dados_para_diagnostico(arquivo_auditado):
    if arquivo_auditado is None:
        return None
    caminho = os.path.join(DIR_AUDITADOS, arquivo_auditado)
    if os.path.exists(caminho):
        return pd.read_csv(caminho, sep=";")
    return None




def detectar_dados_numericos(valor):
    """Verifica se um valor individual é numérico e diferente de zero."""
    if isinstance(valor, (int, float)):
        return 1 if valor != 0 else 0
    if isinstance(valor, str):
        valor_limpo = valor.replace(",", ".").strip()
        try:
            num = float(valor_limpo)
            return 1 if num != 0 else 0
        except ValueError:
            return 0
    return 0

def calcular_indice_transparencia(df_grupo):
    """
    Calcula a média de transparência para uma empresa.
    Baseado na proporção de campos numéricos preenchidos.
    """
    total = len(df_grupo)
    preenchidos = df_grupo["Detectados com Dados Numéricos"].sum()
    return round((preenchidos / total) * 100, 2) if total > 0 else 0