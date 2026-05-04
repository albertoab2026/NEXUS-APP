import streamlit as st
import boto3
import hashlib
import uuid
import pytz
from datetime import datetime
from decimal import Decimal
import os

# ====== CONFIGURACIÓN INICIAL ======
st.set_page_config(page_title="NEXUS", page_icon="⚡", layout="wide")

# ====== 1. CSS FUTURISTA ======
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
}

/* FONDO ANIMADO FUTURISTA - LIGERO */
.stApp {
    background: linear-gradient(-45deg, #0f172a, #1e293b, #334155, #1e293b);
    background-size: 400% 400%;
    animation: gradient 15s ease infinite;
}

@keyframes gradient {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* HEADER CON BRILLO */
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

/* BOTONES NEÓN */
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

/* INPUTS VIDRIO */
.stTextInput > div > div > input {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 10px;
    color: white;
    backdrop-filter: blur(10px);
}

.stTextInput > div > div > input::placeholder {
    color: rgba(255, 255, 255, 0.6);
}

/* CARDS VIDRIO */
.card {
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 1.5rem;
    margin: 1rem 0;
}

/* OCULTAR ELEMENTOS STREAMLIT */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
""")

# ====== 2. CONFIGURACIÓN AWS ======
def get_dynamodb_table():
    """Conecta a DynamoDB usando secrets o credenciales"""
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
        return dynamodb.Table('NEXUS_USUARIOS')
    except Exception as e:
        st.error(f"Error conectando a DynamoDB: {e}")
        st.stop()

# ====== 3. FUNCIONES DE USUARIO ======
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def crear_usuario(email, password, nombre):
    table = get_dynamodb_table()
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)
    
    try:
        table.put_item(
            Item={
                'email': email,
                'password_hash': password_hash,
                'nombre': nombre,
                'user_id': user_id,
                'fecha_registro': datetime.now(pytz.timezone('America/Lima')).isoformat(),
                'activo': True
            },
            ConditionExpression='attribute_not_exists(email)'
        )
        return True, "Usuario creado exitosamente"
    except boto3.exceptions.botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return False, "Este email ya está registrado"
        return False, f"Error: {e}"

def login_usuario(email, password):
    table = get_dynamodb_table()
    password_hash = hash_password(password)
    
    try:
        response = table.get_item(Key={'email': email})
        if 'Item' not in response:
            return False, "Email no registrado"
        
        user = response['Item']
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

# ====== 5. PANTALLA LOGIN/REGISTRO ======
def mostrar_login():
    st.markdown("""
    <div class="main-header">
        <h1>⚡ NEXUS</h1>
        <p>Sistema de Gestión Empresarial</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔐 Iniciar Sesión", "📝 Registrarse"])
    
    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        
        if st.button("Iniciar Sesión", use_container_width=True):
            if email and password:
                success, result = login_usuario(email, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.user_data = result
                    st.success("¡Bienvenido!")
                    st.rerun()
                else:
                    st.error(result)
            else:
                st.warning("Completa todos los campos")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        nombre = st.text_input("Nombre completo", key="reg_nombre")
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Contraseña", type="password", key="reg_pass")
        password2 = st.text_input("Confirmar contraseña", type="password", key="reg_pass2")
        
        if st.button("Crear Cuenta", use_container_width=True):
            if nombre and email and password and password2:
                if password == password2:
                    success, msg = crear_usuario(email, password, nombre)
                    if success:
                        st.success(msg)
                        st.info("Ahora inicia sesión")
                    else:
                        st.error(msg)
                else:
                    st.error("Las contraseñas no coinciden")
            else:
                st.warning("Completa todos los campos")
        st.markdown('</div>', unsafe_allow_html=True)

# ====== 6. DASHBOARD PRINCIPAL ======
def mostrar_dashboard():
    user = st.session_state.user_data
    
    st.markdown(f"""
    <div class="main-header">
        <h1>Bienvenido, {user['nombre']}!</h1>
        <p>Último acceso: {datetime.now(pytz.timezone('America/Lima')).strftime('%d/%m/%Y %H:%M')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.metric("Ventas Hoy", "S/ 0.00", "0%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.metric("Productos", "0", "0")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.metric("Clientes", "0", "0")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_data = None
        st.rerun()

# ====== 7. ROUTER PRINCIPAL ======
if not st.session_state.logged_in:
    mostrar_login()
else:
    mostrar_dashboard()
