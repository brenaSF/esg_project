import streamlit as st
import pandas as pd
import os
from datetime import datetime
import getpass

def apply_vitality_style():
    st.markdown("""
    <style>
        /* Fundo principal em tom pastel frio */
        .stApp {
            background-color: #E6F7F8; 
        }

        /* Sidebar com o gradiente da imagem Vitality */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #78D1D2 0%, #4FA5D7 100%);
            border-radius: 0 40px 40px 0;
            margin-right: 10px;
        }

        /* Títulos e textos da Sidebar */
        [data-testid="stSidebar"] h2, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
            color: white !important;
        }

        /* Card Principal (Gradiente Turquesa) */
        .main-card {
            background: linear-gradient(135deg, #78D1D2 0%, #5AB9BE 100%);
            padding: 30px;
            border-radius: 35px;
            color: white;
            box-shadow: 0 10px 20px rgba(0,0,0,0.05);
            margin-bottom: 25px;
        }

        /* Card Branco (Como o de calorias/Burn calories) */
        .white-card {
            background-color: white;
            padding: 25px;
            border-radius: 35px;
            box-shadow: 0 10px 20px rgba(0,0,0,0.02);
            color: #4A4A4A;
        }

        /* Botões Arredondados estilo 'Pill' */
        .stButton>button {
            border-radius: 50px;
            background-color: #78D1D2 !important;
            color: white !important;
            border: none;
            padding: 10px 25px;
            font-weight: bold;
        }

        /* Inputs e Selectbox */
        .stSelectbox div[data-baseweb="select"] {
            border-radius: 20px;
        }

        /* Esconder bordas padrão do Streamlit para um look clean */
        [data-testid="stHeader"] {background: rgba(0,0,0,0);}
    </style>
    """, unsafe_allow_html=True)


# Configuração da página para um visual moderno
st.set_page_config(
    page_title="ESG Curator Portal",
    layout="wide",
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)
apply_vitality_style()


# --- Configuração de Caminhos ---
DIR_OUTPUT = "data/output"
DIR_PROCESSADOS = os.path.join(DIR_OUTPUT, "processados")
CAMINHO_GOLD = os.path.join(DIR_OUTPUT, "base_esg_FINAL_AUDITADA.csv")

# Garantir que as pastas existam
for pasta in [DIR_OUTPUT, DIR_PROCESSADOS]:
    os.makedirs(pasta, exist_ok=True)

# --- Funções de Apoio e Estatísticas ---
def obter_arquivos_pendentes():
    if not os.path.exists(DIR_OUTPUT):
        return []
    return [f for f in os.listdir(DIR_OUTPUT) if f.startswith("resultado_") and f.endswith(".csv")]

def calcular_progresso():
    pendentes = len(obter_arquivos_pendentes())
    concluidos = len([f for f in os.listdir(DIR_PROCESSADOS) if f.endswith(".csv")])
    total = pendentes + concluidos
    percentual = concluidos / total if total > 0 else 0
    return pendentes, concluidos, total, percentual

# --- Sidebar com Barra de Progresso ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3950/3950815.png", width=80)
    st.title("🛡️ ESG Control Panel")
    st.info(f"👤 **Usuário:** {getpass.getuser()}")
    st.divider()

    # Seção de Progresso
    n_pend, n_conc, n_total, pct = calcular_progresso()
    st.subheader("📈 Progresso da Auditoria")
    st.progress(pct)
    st.write(f"**{n_conc} de {n_total}** relatórios revisados")
    
    st.divider()
    
    # Seleção de Arquivo
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

# --- Área Principal ---
st.title("🛡️ Portal de Governança ESG")
st.caption("Validação de evidências e consolidação de métricas auditadas")

if arquivo_selecionado:
    caminho_completo = os.path.join(DIR_OUTPUT, arquivo_selecionado)
    df = pd.read_csv(caminho_completo, sep=";")
    
    # --- Painel de Métricas Rápidas ---
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Empresa", df['empresa'].iloc[0] if 'empresa' in df.columns else "N/A")
    with m2:
        st.metric("Indicadores", len(df))
    with m3:
        st.metric("Ano", df['ano_relatorio'].iloc[0] if 'ano_relatorio' in df.columns else "N/A")

    st.markdown(f"### 📋 Editando: `{arquivo_selecionado}`")
    
    # --- Editor de Dados ---
    df_editado = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=True,
        column_config={
            "valor": st.column_config.NumberColumn("Valor IA", format="%.4f"),
            "contexto": st.column_config.TextColumn("Evidência do PDF", width="large"),
            "id_dashboard": st.column_config.TextColumn("Métrica", disabled=True),
            "pagina": st.column_config.TextColumn("Pág", width="small")
        }
    )

    # --- Ações de Auditoria ---
    st.divider()
    col1, col2, _ = st.columns([1, 1, 3])
    
    with col1:
        if st.button("✅ Aprovar e Consolidar", use_container_width=True, type="primary"):
            # Metadados de Governança
            df_editado["auditado_por"] = getpass.getuser()
            df_editado["data_auditoria"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df_editado["arquivo_origem"] = arquivo_selecionado
            
            # Consolidação na base GOLD
            if os.path.exists(CAMINHO_GOLD):
                df_gold = pd.read_csv(CAMINHO_GOLD, sep=";")
                df_final = pd.concat([df_gold, df_editado], ignore_index=True)
            else:
                df_final = df_editado
            
            df_final.to_csv(CAMINHO_GOLD, index=False, sep=";", encoding="utf-8-sig")
            
            # Arquivamento (Mover arquivo para 'processados')
            os.rename(caminho_completo, os.path.join(DIR_PROCESSADOS, arquivo_selecionado))
            
            st.toast(f"Relatório {arquivo_selecionado} aprovado!", icon="🚀")
            st.balloons()
            st.rerun()
            
    with col2:
        
        if st.button("🗑️ Descartar", use_container_width=True):
            os.remove(caminho_completo)
            st.warning("Relatório removido da fila.")
            st.rerun()

    

else:
    st.container(border=True).success("🎉 **Excelente!** Todos os relatórios foram auditados.")
    if st.button("🔄 Sincronizar Novos Dados"):
        st.rerun()