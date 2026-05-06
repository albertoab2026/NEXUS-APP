import streamlit as st
import boto3
import hashlib
import uuid
import pytz
from datetime import datetime, timedelta # AGREGUÉ timedelta
from boto3.dynamodb.conditions import Attr, Key # AGREGUÉ ESTA LÍNEA

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
        response = table.get_item(Key={'usuario_id': usuario_id})
        if 'Item' not in response:
            return False, "ID de usuario no existe"

        user = response['Item']
        if user['password_hash']!= password_hash:
            return False, "Contraseña incorrecta"

        # VERIFICAR TRIAL VENCIDO
        if user.get('plan') == 'trial':
            fecha_fin = datetime.fromisoformat(user['fecha_trial_fin'])
            hoy = datetime.now(pytz.timezone('America/Lima'))
            if hoy > fecha_fin:
                codigo = f"ACT-{user['dni']}"
                return False, f"TRIAL_VENCIDO|{codigo}"

        # VERIFICAR PREMIUM VENCIDO
        if user.get('plan') == 'premium' and 'fecha_vencimiento' in user:
            fecha_venc = datetime.fromisoformat(user['fecha_vencimiento'])
            hoy = datetime.now(pytz.timezone('America/Lima'))
            if hoy > fecha_venc:
                table.update_item(
                    Key={'usuario_id': usuario_id},
                    UpdateExpression='SET plan = :p',
                    ExpressionAttributeValues={':p': 'trial'}
                )
                codigo = f"ACT-{user['dni']}"
                return False, f"TRIAL_VENCIDO|{codigo}"

        if not user.get('activo', True):
            return False, "Usuario desactivado"

        return True, user
    except Exception as e:
        return False, f"Error: {e}"

# ====== 3.5. FUNCIONES DE REGISTRO NEXUS 5.0 - ZERO SCAN ======
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

def verificar_trial_usado(tipo, valor):
    """ZERO SCAN: Verifica si DNI, CEL o EMAIL ya usó trial"""
    table = get_dynamodb_table('NEXUS_TRIAL_USADOS')
    response = table.get_item(Key={'tipo_id': f'{tipo}-{valor}'})
    return 'Item' in response

def guardar_trial_usado(tipo, valor):
    """ZERO SCAN: Guarda DNI, CEL, EMAIL para bloquear futuros trials"""
    table = get_dynamodb_table('NEXUS_TRIAL_USADOS')
    table.put_item(Item={
        'tipo_id': f'{tipo}-{valor}',
        'fecha': datetime.now(pytz.timezone('America/Lima')).isoformat()
    })

def registrar_local(nombre_local, dni, celular, email, password):
    table_usuarios = get_dynamodb_table('NEXUS_USUARIOS')
    table_duenos = get_dynamodb_table('NEXUS_DUENOS')

    # ANTI-VIVOS ZERO SCAN: Verificar triple con get_item
    if verificar_trial_usado('DNI', dni):
        raise Exception("Este DNI ya usó su prueba gratis")
    if verificar_trial_usado('CEL', celular):
        raise Exception("Este WhatsApp ya usó su prueba gratis")
    if email and verificar_trial_usado('EMAIL', email):
        raise Exception("Este Email ya usó su prueba gratis")

    id_dueno = generar_id_dueno()
    id_empleado = generar_id_empleado()
    usuario_id = f"DUENO{nombre_local[:3].upper()}{id_dueno[-3:]}"
    hoy = datetime.now(pytz.timezone('America/Lima'))

    table_usuarios.put_item(Item={
        'usuario_id': usuario_id,
        'nombre': nombre_local,
        'rol': 'dueño',
        'dni': dni,
        'celular': celular,
        'email': email or 'no-tiene',
        'password_hash': hash_password(password),
        'id_del_dueno': id_dueno,
        'id_del_empleado': id_empleado,
        'cliente_id': id_dueno, # FIX: Para tus tablas PRODUCTOS/VENTAS
        'plan': 'trial',
        'fecha_registro': hoy.isoformat(),
        'fecha_trial_fin': (hoy + timedelta(days=7)).isoformat(),
        'activo': True
    })

    table_duenos.put_item(Item={
        'id_del_dueno': id_dueno,
        'nombre_local': nombre_local
    })

    # Bloquear futuros trials - ZERO SCAN
    guardar_trial_usado('DNI', dni)
    guardar_trial_usado('CEL', celular)
    if email: guardar_trial_usado('EMAIL', email)

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

def activar_plan_por_dni(dni):
    """ZERO SCAN: Activa usando GSI dni-index"""
    table = get_dynamodb_table('NEXUS_USUARIOS')
    try:
        response = table.query(
            IndexName='dni-index',
            KeyConditionExpression=Key('dni').eq(dni)
        )
        if not response['Items']:
            return False, "DNI no encontrado"

        user = response['Items'][0]
        hoy = datetime.now(pytz.timezone('America/Lima'))
        table.update_item(
            Key={'usuario_id': user['usuario_id']},
            UpdateExpression='SET plan = :p, fecha_vencimiento = :f',
            ExpressionAttributeValues={
                ':p': 'premium',
                ':f': (hoy + timedelta(days=30)).isoformat()
            }
        )
        return True, f"Activado: {user['nombre']} - {user['usuario_id']}"
    except Exception as e:
        return False, f"Error: {e}. ¿Creaste el GSI dni-index?"

def mostrar_panel_admin():
    st.markdown('<h3 style="color: white;">🔧 Panel Admin</h3>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔑 Cambiar Claves", "🔓 Activar Plan S/30"])

    with tab1:
        usuario_id = st.text_input("ID del Usuario", placeholder="DUENOCHA001", key="admin_user")
        nueva_clave = st.text_input("Nueva Clave Temporal", type="password", key="admin_pass")

        if st.button("Actualizar Clave", use_container_width=True, key="btn_admin"):
            if usuario_id and nueva_clave:
                success, msg = cambiar_clave_usuario(usuario_id, nueva_clave)
                if success:
                    st.success(f"Listo. Dile al cliente: usuario `{usuario_id}` clave `{nueva_clave}`")
                else:
                    st.error(msg)
            else:
                st.warning("Completa ambos campos")

    with tab2:
        st.markdown("### Activar Plan S/30 por 30 días - ZERO SCAN")
        dni_activar = st.text_input("DNI del cliente que pagó S/30", max_chars=8, key="dni_act")
        if st.button("Activar 30 días", use_container_width=True, key="btn_activar"):
            if dni_activar:
                success, msg = activar_plan_por_dni(dni_activar)
                if success:
                    st.success(f"✅ {msg}")
                    st.info("Ya tiene productos ilimitados por 30 días")
                else:
                    st.error(msg)
            else:
                st.warning("Ingresa el DNI")

# ====== 4. MANEJO DE SESIÓN ======
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_data' not in st.session_state:
    st.session_state.user_data = None

# ====== 5. PANTALLA LOGIN NEXUS 5.0 ======
def mostrar_login():
    st.markdown("""
    <div class="main-header">
        <h1>⚡ NEXUS</h1>
        <p>Sistema de Gestión para Bodegas</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        tab1, tab2 = st.tabs(["🔐 Iniciar Sesión", "🆕 Prueba 7 días GRATIS"])

        with tab1:
            st.markdown('<h3 style="color: white; text-align: center;">Iniciar Sesión</h3>', unsafe_allow_html=True)
            usuario_id = st.text_input("ID de Usuario", key="login_user")
            password = st.text_input("Contraseña", type="password", key="login_pass")
            if st.button("Iniciar Sesión", use_container_width=True):
                if usuario_id and password:
                    success, result = login_usuario(usuario_id, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user_data = result
                        st.success("¡Bienvenido!")
                        st.rerun()
                    else:
                        # BLOQUEO TRIAL VENCIDO
                        if "TRIAL_VENCIDO" in str(result):
                            codigo = result.split("|")[1]
                            st.error("🔒 Tu prueba de 7 días terminó")
                            st.markdown("### Activa Plan S/30 - 30 días ilimitado")
                            st.code("Yapea S/30 al 924 848 001")
                            st.warning(f"IMPORTANTE: Pon este código en mensaje de Yape:")
                            st.code(codigo)
                            st.info("Manda captura a WhatsApp: 924 848 001. Activamos en 12h")
                        else:
                            st.error(result)
                else:
                    st.warning("Completa todos los campos")

        with tab2:
            st.markdown('<h3 style="color: white; text-align: center;">🎁 Prueba 7 días GRATIS</h3>', unsafe_allow_html=True)
            st.caption("Luego S/30 al mes. Sin instalación. Productos ilimitados.")
            nombre_local = st.text_input("Nombre de tu bodega", key="reg_local")
            dni = st.text_input("DNI *1 prueba gratis por DNI*", max_chars=8, key="reg_dni")
            celular = st.text_input("WhatsApp *Te avisamos antes que venza*", max_chars=9, key="reg_cel")
            email = st.text_input("Email *Opcional*", key="reg_email")
            password = st.text_input("Crea contraseña", type="password", key="reg_pass")

            st.caption("✅ Límite trial: 30 productos + 50 ventas. Plan S/30 es ilimitado.")

            if st.button("🚀 Empezar prueba GRATIS", use_container_width=True):
                if nombre_local and dni and celular and password:
                    if len(dni)!= 8:
                        st.error("DNI debe tener 8 dígitos"); st.stop()
                    if len(celular)!= 9:
                        st.error("WhatsApp debe tener 9 dígitos"); st.stop()
                    try:
                        usuario_id, id_dueno, id_empleado = registrar_local(nombre_local, dni, celular, email, password)
                        st.success(f"¡Listo! Tu usuario es: {usuario_id}")
                        st.info("Guárdalo. Ahora inicia sesión")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Completa DNI, WhatsApp, Nombre y Contraseña")

# ====== 6. DASHBOARD ======
def mostrar_dashboard():
    user = st.session_state.user_data

    # AVISO TRIAL
    if user.get('plan') == 'trial':
        fecha_fin = datetime.fromisoformat(user['fecha_trial_fin'])
        hoy = datetime.now(pytz.timezone('America/Lima'))
        dias_restantes = (fecha_fin - hoy).days

        if dias_restantes > 0:
            st.warning(f"⏰ Te quedan {dias_restantes} días de prueba GRATIS")
            st.info(f"Para continuar sin límites: Yapea S/30 al 924 848 001 con código ACT-{user['dni']}")
        else:
            st.error("🔒 Tu prueba terminó. Activa S/30 para seguir usando NEXUS")
            st.stop()

    st.markdown(f"""
    <div class="main-header">
        <h1>Bienvenido, {user['nombre']}!</h1>
        <p>Rol: {user['rol'].upper()} | Plan: {user.get('plan','').upper()}</p>
    </div>
    """, unsafe_allow_html=True)

    if user['rol'] == 'dueño':
        menu = st.selectbox("Menú", ["📊 Dashboard", "📦 Productos", "💰 Ventas", "👥 Usuarios", "🔧 Admin"])
    elif user['rol'] == 'admin':
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
