# styles.py
import streamlit as st

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

