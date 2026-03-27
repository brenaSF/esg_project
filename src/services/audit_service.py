import os
import pandas as pd
import shutil

DIR_OUTPUT = "data/output"
DIR_CSV = os.path.join(DIR_OUTPUT, "resultado_csv")
DIR_AUDITADOS = os.path.join(DIR_OUTPUT, "auditados")
DIR_EXCLUIDOS = os.path.join(DIR_OUTPUT, "excluidos")
CAMINHO_GOLD = os.path.join(DIR_OUTPUT, "base_consolidada_esg.csv")

def carregar_dados_para_auditoria(arquivo_nome):
    caminho = os.path.join(DIR_CSV, arquivo_nome)
    if os.path.exists(caminho):
        return pd.read_csv(caminho, sep=";")
    return None

def consolidar_e_limpar(df_editado, arquivo_nome):
    """Salva na base final e remove o arquivo da pasta de pendentes."""
    if os.path.exists(CAMINHO_GOLD):
        base_gold = pd.read_csv(CAMINHO_GOLD, sep=";")
        df_final = pd.concat([base_gold, df_editado], ignore_index=True)
    else:
        df_final = df_editado
    
    df_final.to_csv(CAMINHO_GOLD, index=False, sep=";", encoding="utf-8-sig")
    
    caminho_pendente = os.path.join(DIR_CSV, arquivo_nome)
    if os.path.exists(caminho_pendente):
        os.remove(caminho_pendente)
    return True

def descartar_relatorio(arquivo_nome):
    caminho_origem = os.path.join(DIR_CSV, arquivo_nome)
    os.makedirs(DIR_EXCLUIDOS, exist_ok=True)
    if os.path.exists(caminho_origem):
        shutil.move(caminho_origem, os.path.join(DIR_EXCLUIDOS, arquivo_nome))