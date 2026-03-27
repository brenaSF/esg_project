import requests
from requests.exceptions import ConnectionError, Timeout, RequestException
import os

def salvar_arquivo_upload(uploaded_file, destino_dir):
    """
    Salva o arquivo uploaded_file (Streamlit UploadedFile) em destino_dir e retorna o caminho completo.
    """
    os.makedirs(destino_dir, exist_ok=True)
    caminho = os.path.join(destino_dir, uploaded_file.name)
    with open(caminho, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return caminho

def processar_arquivo_na_api(api_url, filename, empresa, ano, timeout=300):
    """
    Envia um payload simples para a API e retorna (sucesso: bool, mensagem: str).
    Trata ConnectionError, Timeout e respostas com JSON inválido.
    """
    payload = {
        "filename": filename,
        "empresa": empresa,
        "ano": int(ano)
    }

    try:
        resp = requests.post(api_url, json=payload, timeout=timeout)
    except ConnectionError:
        return False, "🚨 Erro: API Offline. Inicie o backend (Uvicorn)."
    except Timeout:
        return False, "⏱️ Tempo de conexão esgotado com a API."
    except RequestException as e:
        return False, f"❌ Erro na requisição: {str(e)}"

    if resp.status_code == 200:
        return True, "✅ Processado com sucesso!"
    else:
        try:
            detalhe = resp.json().get("detail", None)
            if detalhe:
                return False, f"❌ {detalhe}"
        except ValueError:
            pass
        return False, f"❌ Resposta inválida do servidor (Status {resp.status_code})"
