import streamlit as st
import boto3
import hashlib
import uuid
import pytz
from datetime import datetime

# ====== CONFIGURACIÓN INICIAL ======
st.set_page_config(page_title="NEXUS", page_icon="⚡", layout="wide")

# ====== 1. CSS FUTURISTA ======
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

/* FORZAR BLANCO EN TODO */
.stTextInput > label,.stSelectbox > label,.stTextInput > div > div > input {
    color: white!important;
}

.stTextInput > div > div > input {
    background: rgba(255, 255, 255, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 10px;
}

.stTextInput > div > div > input::placeholder {
    color: rgba(255, 255, 255, 0.7)!important;
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
        response = table.get_item(
            Key={'usuario_id': usuario_id}
        )
        if 'Item' not in response:
            return False, "ID de usuario no existe"

        user = response['Item']
        if user['password_hash'] == password_hash and user.get('activo', True):
            return True, user
        else:
            return False, "Contraseña incorrecta"
    except Exception as e:
        return False, f"Error: {e}"
# ====== 3.5. FUNCIONES DE REGISTRO ======
def generar_id_dueno():
    table = get_dynamodb_table('NEXUS_CONTADORES')
    response = table.update_item(
        Key={'tipo': 'dueno'},
        UpdateExpression='ADD contador :inc',
        ExpressionAttributeValues={':inc': 1},
        ReturnValues='UPDATED_NEW'
    )
    nuevo_contador = int(response['Attributes']['contador'])
    return f"DUENO-{nuevo_contador:03d}"

def generar_id_empleado():
    table = get_dynamodb_table('NEXUS_CONTADORES')
    response = table.update_item(
        Key={'tipo': 'empleado'},
        UpdateExpression='ADD contador :inc',
        ExpressionAttributeValues={':inc': 1},
        ReturnValues='UPDATED_NEW'
    )
    nuevo_contador = int(response['Attributes']['contador'])
    return f"EMP-{nuevo_contador:03d}"

def registrar_local(nombre_local, email, password):
    table_usuarios = get_dynamodb_table('NEXUS_USUARIOS')
    table_duenos = get_dynamodb_table('NEXUS_DUENOS')
    
    id_dueno = generar_id_dueno()      # DUENO-001
    id_empleado = generar_id_empleado() # EMP-001
    usuario_id = f"DUENO{nombre_local[:3].upper()}"
    
    table_usuarios.put_item(Item={
        'usuario_id': usuario_id,
        'nombre': nombre_local,
        'rol': 'dueño',
        'email': email,
        'password_hash': hash_password(password),
        'id_del_dueno': id_dueno,
        'id_del_empleado': id_empleado,
        'activo': True,
        'fecha_creacion': datetime.now(pytz.timezone('America/Lima')).isoformat()
    })
    
    table_duenos.put_item(Item={
        'id_del_dueno': id_dueno,
        'nombre_local': nombre_local
    })
    
    return usuario_id, id_dueno, id_empleado        
def cambiar_clave_usuario(usuario_id, nueva_clave):
    table = get_dynamodb_table('NEXUS_USUARIOS')
    hash_nuevo = hash_password(nueva_clave)
    try:
        table.update_item(
            Key={'usuario_id': usuario_id},
            UpdateExpression='SET password_hash = :h',
            ExpressionAttributeValues={':h': hash_nuevo}
        )
        return True, "Clave actualizada"
    except Exception as e:
        return False, f"Error: {e}"

def mostrar_panel_admin():
    st.markdown('<h3 style="color: white;">🔧 Panel Admin - Cambiar Claves</h3>', unsafe_allow_html=True)
    
    usuario_id = st.text_input("ID del Usuario", placeholder="DUENOCHA", key="admin_user")
    nueva_clave = st.text_input("Nueva Clave Temporal", type="password", key="admin_pass")
    
    if st.button("Actualizar Clave", use_container_width=True, key="btn_admin"):
        if usuario_id and nueva_clave:
            success, msg = cambiar_clave_usuario(usuario_id, nueva_clave)
            if success:
                st.success(f"Listo. Dile al cliente: usuario `{usuario_id}` clave `{nueva_clave}`")
                st.info("Que la cambie cuando entre")
            else:
                st.error(msg)
        else:
            st.warning("Completa ambos campos")
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
        tab1, tab2 = st.tabs(["🔐 Iniciar Sesión", "🆕 Registrar Local"])
        
        with tab1:
            st.markdown('<h3 style="color: white; text-align: center; margin-bottom: 1.5rem;">Iniciar Sesión</h3>', unsafe_allow_html=True)
            usuario_id = st.text_input("ID de Usuario", placeholder="Ej: DUENOCHA, EMPCHA", key="login_user")
            password = st.text_input("Contraseña", type="password", key="login_pass")
            if st.button("Iniciar Sesión", use_container_width=True, key="btn_login"):
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
        
        with tab2:
            st.markdown('<h3 style="color: white; text-align: center; margin-bottom: 1.5rem;">Registrar Nuevo Local</h3>', unsafe_allow_html=True)
            nombre_local = st.text_input("Nombre del Local", placeholder="Ej: Tienda La Chamba", key="reg_local")
            email = st.text_input("Email", placeholder="tu@correo.com", key="reg_email")
            password = st.text_input("Contraseña", type="password", key="reg_pass")
            if st.button("Registrar", use_container_width=True, key="btn_reg"):
                if nombre_local and email and password:
                    try:
                        usuario_id, id_dueno, id_empleado = registrar_local(nombre_local, email, password)
                        st.success(f"¡Listo! Tu usuario es: {usuario_id}")
                        st.info(f"ID del local: {id_dueno} - El cliente no lo ve")
                        st.info("Ahora ve a Iniciar Sesión")
                    except Exception as e:
                        st.error(f"Error: {e}")
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
        menu = st.selectbox("Menú", ["📊 Dashboard", "📦 Productos", "💰 Ventas", "👥 Usuarios", "🔧 Admin"])
    elif user['rol'] == 'admin':  # ← ESTE ERES TÚ
        menu = st.selectbox("Menú", ["🔧 Admin", "📊 Dashboard"])
    else:
        menu = st.selectbox("Menú", ["📦 Productos", "💰 Ventas"])

    if menu == "🔧 Admin":
        mostrar_panel_admin()
    else:
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
