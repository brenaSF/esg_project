# src/audit.py
import os
import pandas as pd

DIR_OUTPUT = "data/output"
DIR_CSV = os.path.join(DIR_OUTPUT, "resultado_csv")

def obter_arquivos_pendentes():
    if not os.path.exists(DIR_CSV): return []
    return [f for f in os.listdir(DIR_CSV) if f.endswith(".csv")]

def calcular_progresso(dir_auditados):
    pendentes = len(obter_arquivos_pendentes())
    concluidos = len([f for f in os.listdir(dir_auditados) if f.endswith(".csv")])
    total = pendentes + concluidos
    percentual = concluidos / total if total > 0 else 0
    return pendentes, concluidos, total, percentual