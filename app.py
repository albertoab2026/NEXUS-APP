import streamlit as st
import boto3
import hashlib
import uuid
import pytz
from datetime import datetime

# ====== CONFIGURACIÓN INICIAL ======
st.set_page_config(page_title="NEXUS", page_icon="⚡", layout="wide")

# ====== 1. CSS FUTURISTA CORREGIDO ======
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
}

.stApp {
    background: linear-gradient(135deg, #0f172a, #1e293b, #334155, #1e293b);
    background-size: 400% 400%;
    animation: gradient 15s ease infinite;
}

@keyframes gradient {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

.main-header {
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    padding: 2rem;
    border-radius: 20px;
    text-align: center;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    margin-bottom: 2rem;
    animation: glow 2s ease-in-out infinite alternate;
}

@keyframes glow {
    0%, 100% { box-shadow: 0 0 20px rgba(99, 102, 241, 0.5); }
    50% { box-shadow: 0 0 40px rgba(99, 102, 241, 0.8); }
}

.main-header h1 {
    color: white;
    font-size: 3rem;
    font-weight: 700;
    margin: 0;
    text-shadow: 0 0 20px rgba(255,255,255,0.5);
}

.main-header p {
    color: rgba(255,255,255,0.9);
    font-size: 1.2rem;
    margin: 0.5rem 0 0 0;
}

.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    border: none;
    border-radius: 12px;
    padding: 0.75rem 2rem;
    font-weight: 600;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(99, 102, 241, 0.6);
}

/* CORREGIDO: TEXTO BLANCO PARA INPUTS */
.stTextInput > label {
    color: white!important;
    font-weight: 600;
}

.stTextInput > div > div > input {
    background: rgba(255, 255, 255, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 10px;
    color: white!important;
}

.stTextInput > div > div > input::placeholder {
    color: rgba(255, 255, 255, 0.7)!important;
}

/* CORREGIDO: TEXTO BLANCO PARA SELECTBOX */
.stSelectbox > label {
    color: white!important;
    font-weight: 600;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ====== 2. CONFIGURACIÓN AWS ======
def get_dynamodb_table(table_name):
    try:
        aws_access_key = st.secrets["AWS_ACCESS_KEY_ID"]
        aws_secret_key = st.secrets["AWS_SECRET_ACCESS_KEY"]
        region = st.secrets.get("AWS_DEFAULT_REGION", "us-east-1")

        dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=region
        )
        return dynamodb.Table(table_name)
    except Exception as e:
        st.error(f"Error conectando a DynamoDB: {e}")
        st.stop()

# ====== 3. FUNCIONES DE USUARIO ======
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_usuario(usuario_id, password):
    table = get_dynamodb_table('NEXUS_USUARIOS')
    password_hash = hash_password(password)

    try:
        response = table.query(
            IndexName='usuario_id-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('usuario_id').eq(usuario_id)
        )
        if not response['Items']:
            return False, "ID de usuario no existe"

        user = response['Items'][0]
        if user['password_hash'] == password_hash and user.get('activo', True):
            return True, user
        else:
            return False, "Contraseña incorrecta"
    except Exception as e:
        return False, f"Error: {e}"

# ====== 4. MANEJO DE SESIÓN ======
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_data' not in st.session_state:
    st.session_state.user_data = None

# ====== 5. PANTALLA LOGIN ======
def mostrar_login():
    st.markdown("""
    <div class="main-header">
        <h1>⚡ NEXUS</h1>
        <p>Sistema de Gestión Empresarial</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.subheader("🔐 Iniciar Sesión")
        usuario_id = st.text_input("ID de Usuario", placeholder="Ej: DUEÑO01, CAJA01")
        password = st.text_input("Contraseña", type="password")

        if st.button("Iniciar Sesión", use_container_width=True):
            if usuario_id and password:
                success, result = login_usuario(usuario_id, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.user_data = result
                    st.success("¡Bienvenido!")
                    st.rerun()
                else:
                    st.error(result)
            else:
                st.warning("Completa todos los campos")

# ====== 6. DASHBOARD ======
def mostrar_dashboard():
    user = st.session_state.user_data

    st.markdown(f"""
    <div class="main-header">
        <h1>Bienvenido, {user['nombre']}!</h1>
        <p>Rol: {user['rol'].upper()} | ID: {user['usuario_id']}</p>
    </div>
    """, unsafe_allow_html=True)

    if user['rol'] == 'dueño':
        menu = st.selectbox("Menú", ["📊 Dashboard", "📦 Productos", "💰 Ventas", "👥 Usuarios"])
    else:
        menu = st.selectbox("Menú", ["📦 Productos", "💰 Ventas"])

    st.info(f"Menú: {menu} - Aquí va el contenido")

    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_data = None
        st.rerun()

# ====== 7. ROUTER ======
if not st.session_state.logged_in:
    mostrar_login()
else:
    mostrar_dashboard()
