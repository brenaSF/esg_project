import re

def formatar_para_numero(valor):
    """Converte strings e formatos variados da IA em float puro."""
    if valor is None: return 0
    if isinstance(valor, dict):
        valor = next(iter(valor.values()), "0")
    
    texto = str(valor).replace(",", ".").strip()
    try:
        numeros = re.findall(r"[-+]?\d*\.\d+|\d+", texto)
        if not numeros: return 0
        num_final = float(numeros[0])
        if "%" in texto:
            return num_final / 100 if num_final > 1 else num_final
        return num_final
    except Exception:
        return 0