import streamlit as st
import boto3
from boto3.dynamodb.conditions import Key
import pandas as pd
import uuid
from datetime import datetime, timedelta, timezone
import hashlib
from decimal import Decimal

# ======= RUBROS Y CATEGORÍAS BASE - NUEVO =======
CATEGORIAS_POR_RUBRO = {
    "Bodega": ["Abarrotes", "Bebidas", "Limpieza", "Golosinas", "Lácteos"],
    "Farmacia": ["Medicinas", "Vitaminas", "Cuidado Personal", "Bebé"],
    "Librería": ["Cuadernos", "Lapiceros", "Papelería", "Arte y Manualidades"],
    "Ferretería": ["Herramientas", "Pinturas", "Electricidad", "Gasfitería"],
    "Minimarket": ["Abarrotes", "Bebidas", "Limpieza", "Lácteos"],
    "Almacén": ["Mayorista", "Distribución", "Inventario General"],
    "Otro": [] # Arranca vacío, crea todo desde cero
}

# --- INICIALIZAR CARRITO ---
if 'carrito' not in st.session_state:
    st.session_state.carrito = []
if 'procesando_venta' not in st.session_state:
    st.session_state.procesando_venta = False
# --- FIN CARRITO ---

# ====== 1. CONFIGURACIÓN AWS ======
st.set_page_config(page_title="NEXUS", page_icon="⚡", layout="wide")

# ====== CSS NEXUS - CON GLOW Y ANIMACIÓN ======
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

.stApp {
    background: linear-gradient(135deg, #1e2139 0%, #2d1b69 50%, #1a1d29 100%);
    background-attachment: fixed;
    color: #ffffff;
    font-family: 'Inter', sans-serif;
}

h1, h2, h3 {
    font-family: 'Inter', sans-serif!important;
    font-weight: 700!important;
    color: #ffffff!important;
}

.main-header {
    background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #7C3AED 100%);
    border-radius: 15px;
    padding: 25px;
    margin-bottom: 30px;
    box-shadow: 0 0 40px rgba(139, 92, 246, 0.6), 0 0 80px rgba(99, 102, 241, 0.3);
    animation: pulseGlow 3s ease-in-out infinite;
}

@keyframes pulseGlow {
    0%, 100% {
        box-shadow: 0 0 40px rgba(139, 92, 246, 0.6), 0 0 80px rgba(99, 102, 241, 0.3);
        transform: scale(1);
    }
    50% {
        box-shadow: 0 0 60px rgba(139, 92, 246, 0.9), 0 0 100px rgba(99, 102, 241, 0.5);
        transform: scale(1.01);
    }
}

.stButton > button {
    background: linear-gradient(135deg, #7C3AED 0%, #6366F1 100%);
    color: white!important;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 10px 20px;
    width: 100%;
    transition: all 0.3s;
    box-shadow: 0 0 20px rgba(124, 58, 237, 0.4);
}
.stButton > button:hover {
    transform: scale(1.03);
    box-shadow: 0 0 35px rgba(124, 58, 237, 0.8);
}

.stTextInput > div > div > input,.stNumberInput > div > div > input {
    background-color: rgba(37, 40, 54, 0.8)!important;
    color: #ffffff!important;
    border: 1px solid #4F46E5!important;
    border-radius: 8px;
    box-shadow: 0 0 10px rgba(79, 70, 229, 0.2);
}

.stSelectbox > div > div {
    background-color: rgba(37, 40, 54, 0.8)!important;
    border: 1px solid #4F46E5!important;
    border-radius: 8px;
    color: white!important;
    box-shadow: 0 0 10px rgba(79, 70, 229, 0.2);
}

.stTabs [data-baseweb="tab"] {
    background-color: transparent;
    color: #9CA3AF;
    font-weight: 600;
}
.stTabs [aria-selected="true"] {
    color: #F59E0B!important;
    border-bottom: 2px solid #F59E0B!important;
    text-shadow: 0 0 10px rgba(245, 158, 11, 0.5);
}

div[data-testid="metric-container"] {
    background: rgba(37, 40, 54, 0.6);
    border: 1px solid #4F46E5;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 0 15px rgba(79, 70, 229, 0.3);
}
</style>
""", unsafe_allow_html=True)

AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = st.secrets["AWS_REGION"]

# ====== 2. CONEXIÓN DYNAMODB ======
@st.cache_resource
def init_dynamodb():
    dynamodb = boto3.resource(
        'dynamodb',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
    return dynamodb

dynamodb = init_dynamodb()
tabla_usuarios = dynamodb.Table('NEXUS_USUARIOS')
tabla_productos = dynamodb.Table('NEXUS_PRODUCTOS')
tabla_ventas = dynamodb.Table('NEXUS_VENTAS')
tabla_trial = dynamodb.Table('NEXUS_TRIAL_USADOS')

# ====== 3. FUNCIONES DE USUARIOS ======
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verificar_trial_usado(dni, email):
    try:
        resp_dni = tabla_trial.get_item(Key={'tipo_id': f'DNI-{dni}'})
        if 'Item' in resp_dni:
            return True
        resp_email = tabla_trial.get_item(Key={'tipo_id': f'EMAIL-{email}'})
        if 'Item' in resp_email:
            return True
        return False
    except:
        return False

def registrar_dueno(dni, nombre, nombre_negocio, email, password, rubro):  # ← 1. AGREGA rubro AQUÍ
    try:
        if verificar_trial_usado(dni, email):
            st.error("❌ Este DNI o Email ya usó los 7 días gratis")
            return False

        timestamp = str(int(datetime.now().timestamp()))[-5:]
        usuario_id = f"DUENO{timestamp}"
        cliente_id = f"DUENO-{timestamp[-3:]}"

        tabla_usuarios.put_item(
            Item={
                'usuario_id': usuario_id,
                'cliente_id': cliente_id,
                'id_del_dueno': cliente_id,
                'id_del_empleado': f"EMP-{timestamp[-3:]}",
                'dni': dni,
                'nombre': nombre,
                'nombre_negocio': nombre_negocio,
                'email': email,
                'password_hash': hash_password(password),
                'rol': 'dueno',
                'rubro': rubro,  # ← 2. LÍNEA NUEVA
                'categorias_custom': [],  # ← 3. LÍNEA NUEVA
                'plan': 'trial',
                'activo': True,
                'celular': '',
                'fecha_registro': datetime.now().isoformat(),
                'fecha_trial_fin': (datetime.now() + timedelta(days=7)).isoformat(),
                'ventas_acumuladas': 0
            }
        )

        tabla_trial.put_item(Item={'tipo_id': f'DNI-{dni}', 'fecha': datetime.now().isoformat()})
        tabla_trial.put_item(Item={'tipo_id': f'EMAIL-{email}', 'fecha': datetime.now().isoformat()})

        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def login(usuario_o_dni, password):
    try:
        user = None

        # 1. Intenta con usuario_id usando GET_ITEM - cuesta casi nada
        try:
            response = tabla_usuarios.get_item(Key={'usuario_id': usuario_o_dni})
            if 'Item' in response:
                user = response['Item']
        except:
            pass

        # 2. Si no encontró, busca por DNI con QUERY al GSI - barato
        if not user:
            response = tabla_usuarios.query(
                IndexName='dni-index',
                KeyConditionExpression=Key('dni').eq(usuario_o_dni)
            )
            if response['Items']:
                user = response['Items'][0]

        # 3. Validar password y activo
        if user:
            if user.get('password_hash') == hash_password(password):
                if user.get('activo', True): # True por defecto
                    return user
                else:
                    st.error("❌ Cuenta desactivada")
                    return None
            else:
                st.error("❌ Contraseña incorrecta")
                return None
        else:
            st.error("❌ Usuario o DNI no encontrado")
            return None

    except Exception as e:
        st.error(f"Error login: {e}")
        return None

# ====== 4. FUNCIONES DE PRODUCTOS ======
def obtener_productos():
    try:
        id_dueno = st.session_state.user_data['usuario_id']
        response = tabla_productos.query(
            KeyConditionExpression=Key('id_del_dueno').eq(id_dueno)
        )
        return response.get('Items', [])
    except Exception as e:
        st.error(f"Error cargando productos: {e}")
        return []

def agregar_producto(nombre, precio, stock, categoria):
    try:
        id_dueno = st.session_state.user_data['usuario_id']
        producto_id = str(uuid.uuid4())  # genera el id aquí
        
        tabla_productos.put_item(
            Item={
                'id_del_dueno': str(id_dueno),
                'producto_id': producto_id,
                'nombre': nombre,
                'precio': Decimal(str(precio)),
                'stock': int(stock),
                'categoria': categoria
            }
        )
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def actualizar_producto(producto_id, nuevo_precio, nuevo_stock):
    try:
        id_dueno = st.session_state.user_data['usuario_id']  
        tabla_productos.update_item(
            Key={
                'id_del_dueno': str(id_dueno),
                'producto_id': str(producto_id), 
            },
            UpdateExpression="SET precio = :p, stock = :s",
            ExpressionAttributeValues={
                ':p': Decimal(str(nuevo_precio)),
                ':s': int(nuevo_stock)
            }
        )
        return True
    except Exception as e:
        st.error(f"Error actualizando: {e}")
        return False

def eliminar_producto(producto_id):
    try:
        id_dueno = st.session_state.user_data['usuario_id']
        tabla_productos.delete_item(
            Key={
                'id_del_dueno': str(id_dueno),
                'producto_id': str(producto_id)
            }
        )
        return True
    except Exception as e:
        st.error(f"Error eliminando: {e}")
        return False

# ====== 5. FUNCIONES DE VENTAS ======
def registrar_venta(producto_id, cantidad, precio):
    try:
        id_dueno = st.session_state.user_data['usuario_id']
        fecha_utc = datetime.now(timezone.utc).isoformat()
        
        total = float(precio) * int(cantidad)  # <-- agrega esto

        tabla_ventas.put_item(
            Item={
                'usuario_id': id_dueno,
                'Venta_id': str(uuid.uuid4()),
                'producto_id': producto_id,
                'cantidad': int(cantidad),
                'precio': Decimal(str(precio)),
                'total': Decimal(str(total)),  # <-- y esto
                'fecha': fecha_utc
            }
        )
        
        # Actualizar stock del producto
        response = tabla_productos.get_item(
            Key={
                'id_del_dueno': str(id_dueno),
                'producto_id': str(producto_id)
            }
        )
        if 'Item' in response:
            nuevo_stock = response['Item']['stock'] - int(cantidad)
            actualizar_producto(producto_id, response['Item']['precio'], nuevo_stock)
            
        return True
    except Exception as e:
        st.error(f"Error en venta: {e}")
        return False

def obtener_ventas():
    try:
        id_dueno = st.session_state.user_data['usuario_id']
        response = tabla_ventas.query(
            KeyConditionExpression=Key('usuario_id').eq(id_dueno),
            ScanIndexForward=False  # para que salgan las más recientes primero
        )
        return response.get('Items', [])
    except Exception as e:
        st.error(f"Error cargando ventas: {e}")
        return []
# ====== 6. UI LOGIN ======
def mostrar_login():
    st.markdown("""
    <div style='text-align: center; margin-bottom: 45px;'>
        <div class='main-header'>
            <h1 style='font-size: 3.2rem; margin: 0; color: #FFFFFF; font-weight: 800;
                       text-shadow: 0 0 20px rgba(255, 255, 255, 0.5);'>
                ⚡ NEXUS
            </h1>
            <p style='color: #E0E7FF; font-size: 1.15rem; margin-top: 12px; font-weight: 500;'>
                Sistema de Gestión para Negocios
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='text-align: center; color: #38BDF8; margin-bottom: 35px; font-size: 1.7rem; font-weight: 700;'>¿Cansado de perder plata en tu negocio?</h2>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
                    border: 1px solid #334155; border-radius: 16px;
                    padding: 24px 16px; text-align: center;
                    box-shadow: 0 8px 20px rgba(0,0,0,0.3);'>
            <div style='font-size: 2.5rem; margin-bottom: 12px;'>📦</div>
            <h3 style='font-size: 1.1rem; margin: 0 0 10px 0; color: white; font-weight: 700;'>Control Total</h3>
            <p style='color: #CBD5E1; font-size: 0.8rem; line-height: 1.4; margin: 0;'>
                Sabes qué vendes y qué te falta. Adiós cuaderno.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #2D1B3D 0%, #1E1B4B 100%);
                    border: 1px solid #4C1D95; border-radius: 16px;
                    padding: 24px 16px; text-align: center;
                    box-shadow: 0 8px 20px rgba(0,0,0,0.3);'>
            <div style='font-size: 2.5rem; margin-bottom: 12px;'>💰</div>
            <h3 style='font-size: 1.1rem; margin: 0 0 10px 0; color: white; font-weight: 700;'>Más Ganancia</h3>
            <p style='color: #CBD5E1; font-size: 0.8rem; line-height: 1.4; margin: 0;'>
                Ve tus productos que más plata te dejan. Gana más.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #1E3A3A 0%, #0F2624 100%);
                    border: 1px solid #134E4A; border-radius: 16px;
                    padding: 24px 16px; text-align: center;
                    box-shadow: 0 8px 20px rgba(0,0,0,0.3);'>
            <div style='font-size: 2.5rem; margin-bottom: 12px;'>📱</div>
            <h3 style='font-size: 1.1rem; margin: 0 0 10px 0; color: white; font-weight: 700;'>Desde tu Celular</h3>
            <p style='color: #CBD5E1; font-size: 0.8rem; line-height: 1.4; margin: 0;'>
                Sin computadoras. Solo tu WhatsApp y listo.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #3D2E1E 0%, #292016 100%);
                    border: 1px solid #92400E; border-radius: 16px;
                    padding: 24px 16px; text-align: center;
                    box-shadow: 0 8px 20px rgba(0,0,0,0.3);'>
            <div style='font-size: 2.5rem; margin-bottom: 12px;'>⚡</div>
            <h3 style='font-size: 1.1rem; margin: 0 0 10px 0; color: white; font-weight: 700;'>Súper Barato</h3>
            <p style='color: #CBD5E1; font-size: 0.8rem; line-height: 1.4; margin: 0;'>
                S/30 al mes. Otros cobran S/250.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #10B981 0%, #059669 100%);
                    border-radius: 16px; padding: 24px;
                    text-align: center; margin: 20px 0;
                    box-shadow: 0 8px 25px rgba(16, 185, 129, 0.5);'>
            <h3 style='margin: 0; color: white; font-size: 1.2rem; font-weight: 700;'>🎁 Prueba 7 DÍAS GRATIS</h3>
            <p style='color: rgba(255,255,255,0.95); margin: 10px 0 0 0; font-size: 0.9rem;'>
                Sin tarjeta. Sin compromiso. Cancela cuando quieras.
            </p>
        </div>
        """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔑 Iniciar Sesión", "🚀 Prueba 7 días GRATIS"])

    with tab1:
        st.markdown("<h3 style='text-align: center;'>Iniciar Sesión</h3>", unsafe_allow_html=True)
        with st.form("login_form"):
            dni = st.text_input("Usuario o DNI", placeholder="12345678")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Iniciar Sesión", use_container_width=True):
                user = login(dni, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_data = user
                    st.rerun()
                else:
                    st.error("❌ DNI o contraseña incorrectos")
    with tab2:  # ← 4 ESPACIOS
        st.markdown("<h3 style='text-align: center;'>Crea tu cuenta GRATIS</h3>", unsafe_allow_html=True)
        nombre = st.text_input("Nombre completo", placeholder="Juan Pérez", key="reg_nom")
        nombre_negocio = st.text_input("Nombre de tu Local", placeholder="Bodega Don Juan", key="reg_negocio") # ← Cambié "Bodega" por "Local"
        dni = st.text_input("DNI", placeholder="12345678", key="reg_dni")
        email = st.text_input("Email", placeholder="tu@email.com", key="reg_email")
        password = st.text_input("Contraseña", type="password", key="reg_pass")
        rubro = st.selectbox("¿Qué tipo de negocio tienes?", list(CATEGORIAS_POR_RUBRO.keys()), key="reg_rubro") # ← LÍNEA NUEVA 1
    
        if st.button("ACTIVAR 7 DÍAS GRATIS", use_container_width=True):
            if nombre and nombre_negocio and dni and email and password and rubro: # ← AGREGA 'and rubro'
                if registrar_dueno(dni, nombre, nombre_negocio, email, password, rubro): # ← LÍNEA NUEVA 2: pásale rubro
                    st.success("✅ Cuenta creada. 7 días gratis activados")
                    st.balloons()
                    st.info("Ahora inicia sesión en la pestaña de arriba")
            else:
                st.error("Completa todos los campos")
            
# ====== 7. MAIN APP CON SIDEBAR ESTILO FOTO ======
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    mostrar_login()
    st.stop() # ← LÍNEA CLAVE QUE TE FALTA
else:
    with st.sidebar:
        user = st.session_state.user_data
        
        # === CAJA DINAMICA CON DATOS DEL CLIENTE ===
        nombre_negocio = user.get('nombre_negocio', 'ADMIN NEXUS')
        plan_actual = user.get('plan', 'TRIAL')
        
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #7B2FF7 0%, #4A00E0 100%);
                    padding: 20px; border-radius: 15px; margin: 10px 0;
                    box-shadow: 0 0 30px rgba(123, 47, 247, 0.6);'>
            <h3 style='margin:0; font-size:16px; opacity:0.9;'>{nombre_negocio.upper()}</h3>
            <p style='margin:5px 0 0 0; font-size:24px; font-weight:bold;'>{plan_actual.upper()}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        st.write("**YAPE/PLIN:**")
        st.info("📱 914 282 688\n**Alberto Ballarta**\n*Soporte & Desarrollo NEXUS*")
        
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
    
    # ===== PAYWALL S/30 - BLOQUEA SI ESTÁ VENCIDO =====
    user = st.session_state.user_data
    from datetime import datetime
    
    plan = user.get('plan', 'trial')
    dni_usuario = user.get('dni', 'ADMIN_SIN_DNI')
    
    # Agarra la fecha de vencimiento según el plan
    if plan == 'trial':
        fecha_vencimiento = user.get('fecha_trial_fin')
        nombre_plan = "prueba gratis"
    elif plan == 'premium':
        fecha_vencimiento = user.get('fecha_trial_fin')  # ← Cambia esto por tu campo real de premium
        nombre_plan = "Premium"
    else:
        fecha_vencimiento = None
    
    # Convertir fecha si viene como string
    if isinstance(fecha_vencimiento, str):
        fecha_vencimiento = datetime.fromisoformat(fecha_vencimiento.replace('Z', ''))
    
    # ===== ALERTA + BLOQUEO =====
    if fecha_vencimiento:
        try:
            import pytz
            from datetime import datetime
            
            lima = pytz.timezone('America/Lima')
            ahora = datetime.now(lima)
            
            # CONVIERTE A DATETIME SI VIENE COMO STRING
            if isinstance(fecha_vencimiento, str):
                fecha_vencimiento = datetime.fromisoformat(fecha_vencimiento.replace('Z', ''))
            
            # TU FDCHS YA ESTS DN LIMA
            fecha_venc_lima = lima.localize(fecha_vencimiento)
            
            # Calcular diferencia en HORAS, no días
            segundos_restantes = (fecha_venc_lima - ahora).total_seconds()
            horas_restantes = segundos_restantes / 3600
            dias_restantes = int(horas_restantes / 24)
            
            texto_dia = "día" if dias_restantes == 1 else "días"
                     
            # 1. YA VENCIÓ - BLOQUEA
            if segundos_restantes <= 0:
                st.error(f"🚫 Tu {nombre_plan} venció")
                st.markdown("### 💎 Renueva tu Plan Premium - S/30")
                st.markdown(f"""
                **📱 Paso 1: Yapea o Plinea S/30 a:**
                '''
                914 282 688
                Alberto Ballarta
                '''                          
                **📲 Paso 2: Envíanos por WhatsApp:**
                1. Captura del pago
                2. Tu DNI: **{dni_usuario}**
                """)
                mensaje = f"Hola, pagué S/30. Mi DNI es {dni_usuario}. Adjunto captura."
                whatsapp_url = f"https://wa.me/51914282688?text={mensaje.replace(' ', '%20')}"
                st.link_button("📲 Enviar comprobante por WhatsApp", whatsapp_url, use_container_width=True)
                st.info("⚠️ Solo activamos pagos confirmados en Yape/Plin")
                st.stop()                                            
            
            # 2. HOY VENCE - Menos de 24 horas
            elif horas_restantes < 24:
                st.error(f"🚨 ¡HOY SE VENCE tu {nombre_plan}! Renueva ahora para no perder acceso")
            
            # 3. FALTAN 1-3 DÍAS
            elif dias_restantes >= 1 and dias_restantes <= 3:
                st.warning(f"⚠️ Te quedan {dias_restantes} {texto_dia} de {nombre_plan} - Renueva pronto")
            
            # 4. FALTAN MÁS DE 3 DÍAS  
            else:
                st.info(f"📅 Te quedan {dias_restantes} {texto_dia} de {nombre_plan}")
                
        except Exception as e:
            st.error(f"Error en paywall: {e}")
    # ===== FIN PAYWALL =====        
    # ===== AQUÍ VA TU APP NORMAL =====    
    # === MENSAJE BIENVENIDA EN EL CENTRO ===
    user = st.session_state.user_data
    nombre_negocio = user.get('nombre_negocio', 'NEXUS ADMIN')
    nombre_usuario = user.get('nombre', 'Usuario')
    
    st.markdown(f"### 👋 Bienvenido, **{nombre_usuario}**")
    st.markdown(f"**🏪 Local:** {nombre_negocio}")
    st.divider()
    
# === DESPLEGABLE AFUERA - SOLO DEBE HABER 1 VEZ EN TODO EL CODIGO ===
opciones_menu = {
    "📊 Dashboard": "Dashboard",
    "📦 Productos": "Productos", 
    "💰 Ventas": "Ventas",
    "⚙️ ADMIN": "ADMIN"
}

menu_visible = st.selectbox("Menú", list(opciones_menu.keys()), label_visibility="collapsed")
menu = opciones_menu[menu_visible]

if menu == "Productos":  # ← SIN EMOJI
    st.header("📦 Gestión de Productos")

    productos = obtener_productos()

    # ===== BARRA DE HERRAMIENTAS =====
    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
    with col1:
        busqueda = st.text_input("🔍 Buscar producto", placeholder="Nombre o categoría...")
    with col2:
        categorias = ["Todas"] + sorted(list(set([p.get('categoria', 'Sin categoría') for p in productos if p.get('categoria')])))
        filtro_cat = st.selectbox("Categoría", categorias)
    with col3:
        filtro_stock = st.selectbox("Stock", ["Todos", "Stock bajo <5", "Sin stock"])
    with col4:
        if st.button("➕ Nuevo", use_container_width=True):
            st.session_state.mostrar_form = True
    
    # ===== FILTRAR PRODUCTOS =====
    productos_filtrados = productos
    if busqueda:
        productos_filtrados = [p for p in productos_filtrados if busqueda.lower() in p.get('nombre', '').lower()]
    if filtro_cat != "Todas":
        productos_filtrados = [p for p in productos_filtrados if p.get('categoria') == filtro_cat]
    if filtro_stock == "Stock bajo <5":
        productos_filtrados = [p for p in productos_filtrados if float(p.get('stock', 0)) < 5 and float(p.get('stock', 0)) > 0]
    elif filtro_stock == "Sin stock":
        productos_filtrados = [p for p in productos_filtrados if float(p.get('stock', 0)) == 0]        

    # ===== PAGINACIÓN - SOLO 10 POR PÁGINA =====
    items_por_pagina = 10
    total_paginas = max(1, (len(productos_filtrados) + items_por_pagina - 1) // items_por_pagina)

    if 'pagina_actual' not in st.session_state:
        st.session_state.pagina_actual = 1

    # Resetear página si cambia el filtro
    if st.session_state.get('ultimo_total') != len(productos_filtrados):
        st.session_state.pagina_actual = 1
        st.session_state.ultimo_total = len(productos_filtrados)

    col_pag1, col_pag2, col_pag3 = st.columns([1,2,1])

    with col_pag1:
        if st.button("◀ Anterior", disabled=st.session_state.pagina_actual == 1):
            st.session_state.pagina_actual -= 1
            st.rerun()

    with col_pag2:
        st.write(f"Página {st.session_state.pagina_actual} de {total_paginas}")

    with col_pag3:
        if st.button("Siguiente ▶", disabled=st.session_state.pagina_actual == total_paginas):
            st.session_state.pagina_actual += 1
            st.rerun()

    # CORTAR LA LISTA - SOLO 10 ITEMS
    inicio = (st.session_state.pagina_actual - 1) * items_por_pagina
    fin = inicio + items_por_pagina
    productos_pagina = productos_filtrados[inicio:fin]

    st.caption(f"Mostrando {len(productos_pagina)} de {len(productos_filtrados)} productos")

    # ===== AVISOS DE STOCK BAJO =====
    try:
        productos_criticos = [p for p in productos_filtrados if float(p.get('stock', 0)) < 5 and float(p.get('stock', 0)) > 0]
        productos_agotados = [p for p in productos_filtrados if float(p.get('stock', 0)) == 0]
        if productos_agotados:
            for p in productos_agotados:
                st.error(f"❌ AGOTADO: {p.get('nombre', 'Sin nombre')} - Reponer urgente", icon="❌")

        if productos_criticos:
            for p in productos_criticos:
                st.warning(f"⚠️ STOCK BAJO: {p.get('nombre', 'Sin nombre')} - Solo quedan {int(float(p['stock']))} unidades", icon="⚠️")
    except Exception as e:
        st.error(f"Error calculando stock: {e}")
    
    # ===== FORMULARIO NUEVO PRODUCTO =====
    if st.session_state.get('mostrar_form', False):
        with st.form("nuevo_producto", clear_on_submit=True):
            st.subheader("➕ Agregar Producto")
            c1, c2 = st.columns(2)
            with c1:
                nombre = st.text_input("Nombre*")
                precio = st.number_input("Precio S/*", min_value=0.01, value=1.0, step=0.5)
            with c2:
                stock = st.number_input("Stock inicial*", min_value=0, value=10)
                categoria = st.text_input("Categoría*", placeholder="bebidas, snacks...")
            
            col_g, col_c = st.columns(2)
            with col_g:
                if st.form_submit_button("💾 Guardar", use_container_width=True):
                    if nombre and categoria:
                        if agregar_producto(nombre, precio, stock, categoria):
                            st.success("Producto agregado")
                            st.session_state.mostrar_form = False
                            st.rerun()
                    else:
                        st.error("Completa nombre y categoría")
            with col_c:
                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                    st.session_state.mostrar_form = False
                    st.rerun()
    
    # ===== TABLA PROFESIONAL =====
    if productos_pagina:  # ← CAMBIO: usa productos_pagina
        # Convertir a DataFrame para tabla
        import pandas as pd
        df = pd.DataFrame(productos_pagina)  # ← CAMBIO: productos_pagina
        df['precio'] = df['precio'].apply(lambda x: f"S/ {float(x):.2f}")
        df['stock_status'] = df['stock'].apply(lambda x: "🔴" if float(x) == 0 else "🟡" if float(x) < 5 else "🟢")  # ← CAMBIO: float(x)
        df_display = df[['nombre', 'categoria', 'precio', 'stock', 'stock_status']]
        df_display.columns = ['Producto', 'Categoría', 'Precio', 'Stock', 'Estado']
        
        # Tabla con selección
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Estado": st.column_config.TextColumn(width="small"),
                "Precio": st.column_config.TextColumn(width="small"),
                "Stock": st.column_config.NumberColumn(width="small")
    }
)

elif menu == "Registrar Venta":
    # Inicializar carrito si no existe
    if 'carrito' not in st.session_state:
        st.session_state.carrito = []
    if 'show_cart' not in st.session_state:
        st.session_state.show_cart = False

    # Header con icono de carrito
    col_title, col_cart = st.columns([6, 1])
    with col_title:
        st.write("")
    with col_cart:
        if st.button(f"🛒 {len(st.session_state.carrito)}", key="cart_icon", use_container_width=True):
            st.session_state.show_cart = True

    # --- Sección para agregar productos ---
    productos = obtener_productos()
    if productos:
        nombres = [p['nombre'] for p in productos]
        producto_sel = st.selectbox("Producto", nombres, key="prod_sel")
        cantidad = st.number_input("Cantidad", min_value=1, value=1, step=1)
        producto = next((p for p in productos if p['nombre'] == producto_sel), None)

        if producto:
            st.write(f"Precio: S/{producto['precio']:.2f} | Stock: {producto['stock']}")
            if st.button("➕ Agregar al Carrito", use_container_width=True):
                if producto['stock'] >= cantidad:
                    for item in st.session_state.carrito:
                        if item['producto_id'] == producto['producto_id']:
                            item['cantidad'] += cantidad
                            item['subtotal'] = item['cantidad'] * item['precio']
                            break
                    else:
                        st.session_state.carrito.append({
                            'producto_id': producto['producto_id'],
                            'nombre': producto['nombre'],
                            'precio': producto['precio'],
                            'cantidad': cantidad,
                            'subtotal': producto['precio'] * cantidad
                        })
                    st.success(f"Agregado: {cantidad}x {producto['nombre']}")
                    st.rerun()
                else:
                    st.error("Stock insuficiente")
    else:
        st.info("No hay productos. Agrega el primero con el botón + Nuevo Producto")

    # --- Modal del carrito ---
    if st.session_state.get('show_cart', False):
        with st.expander(f"🛒 Carrito ({len(st.session_state.carrito)})", expanded=True):
            if st.session_state.carrito:
                total = 0
                for i, item in enumerate(st.session_state.carrito):
                    col_a, col_b = st.columns([4, 1])
                    with col_a:
                        st.write(f"**{item['cantidad']}x {item['nombre']}**")
                        st.caption(f"S/{item['precio']:.2f} c/u")
                    with col_b:
                        if st.button("🗑️", key=f"del_exp_{i}", use_container_width=True):
                            st.session_state.carrito.pop(i)
                            st.rerun()
                    total += item['subtotal']
                    if i < len(st.session_state.carrito) - 1:
                        st.divider()

                st.write(f"### Total: S/{total:.2f}")

                col_c, col_d = st.columns(2)
                with col_c:
                    if st.button("🗑️ Vaciar", key="vaciar_exp", use_container_width=True):
                        st.session_state.carrito = []
                        st.session_state.show_cart = False
                        st.rerun()
                with col_d:
                    if st.button("✅ Finalizar Venta", key="finalizar_exp", type="primary", use_container_width=True):
                        ok = True
                        for item in st.session_state.carrito:
                            if not registrar_venta(item['producto_id'], item['cantidad'], item['precio']):
                                ok = False
                                break
                        if ok:
                            st.success("Venta registrada correctamente")
                            st.session_state.carrito = []
                            st.session_state.show_cart = False
                            st.rerun()
                        else:
                            st.error("Error al registrar venta")

                if st.button("❌ Cerrar", key="cerrar_exp", use_container_width=True):
                    st.session_state.show_cart = False
                    st.rerun()
            else:
                st.info("Carrito vacío")

    # --- CSS para botón flotante en móvil ---
    st.markdown("""
    <style>
    @media (max-width: 768px) {
        div[data-testid="stButton"] button[kind="secondary"] {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 999;
            border-radius: 50px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
    }
    </style>
    """, unsafe_allow_html=True)
st.subheader("Acciones")
producto_nombres = [p['nombre'] for p in productos_filtrados]  # Este sí usa filtrados para editar cualquiera
prod_sel = st.selectbox("Selecciona producto para editar/eliminar", producto_nombres)
producto_obj = next((p for p in productos_filtrados if p['nombre'] == prod_sel), None)

if producto_obj:
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        nuevo_precio = st.number_input("Nuevo precio", value=float(producto_obj['precio']), key="edit_precio")
    with c2:
        nuevo_stock = st.number_input("Nuevo stock", value=int(float(producto_obj['stock'])), key="edit_stock")
    with c3:
        st.write("") # espacio
        if st.button("💾 Actualizar", use_container_width=True):
            if actualizar_producto(producto_obj['producto_id'], nuevo_precio, nuevo_stock):
                st.success("Actualizado")
                st.rerun()
        if st.button("🗑️ Eliminar", use_container_width=True, type="secondary"):
            if eliminar_producto(producto_obj['producto_id']):
                st.success("Eliminado")
                st.rerun()
else:
    st.info("No hay productos. Agrega el primero con el botón ➕ Nuevo")        
    
        

# Modal reemplazo con expander
    if st.session_state.get('show_cart', False):
        with st.expander(f"🛒 Carrito ({len(st.session_state.carrito)})", expanded=True):
            if st.session_state.carrito:
                total = 0
                for i, item in enumerate(st.session_state.carrito):
                    col_a, col_b = st.columns([4, 1])
                    with col_a:
                        st.write(f"**{item['cantidad']}x {item['nombre']}**")
                        st.caption(f"S/{item['precio']:.2f} c/u")
                    with col_b:
                        if st.button("🗑️", key=f"del_exp_{i}", use_container_width=True):
                            st.session_state.carrito.pop(i)
                            st.rerun()
                    total += item['subtotal']
                    if i < len(st.session_state.carrito) - 1:
                        st.divider()

                st.write(f"### Total: S/{total:.2f}")

                col_c, col_d = st.columns(2)
                with col_c:
                    if st.button("🗑️ Vaciar", key="vaciar_exp", use_container_width=True):
                        st.session_state.carrito = []
                        st.session_state.show_cart = False
                        st.rerun()
                with col_d:
                    if st.button("✅ Finalizar", key="finalizar_exp", type="primary", use_container_width=True):
                        ok = True
                        for item in st.session_state.carrito:
                            if not registrar_venta(item['producto_id'], item['cantidad'], item['precio']):
                                ok = False
                                break
                        if ok:
                            st.success("Venta registrada")
                            st.session_state.carrito = []
                            st.session_state.show_cart = False
                            st.rerun()
                        else:
                            st.error("Error al registrar")

        if st.button("❌ Cerrar", key="cerrar_exp", use_container_width=True):
            st.session_state.show_cart = False
            st.rerun()
    else:  # presiona espacio 8 veces
        st.info("Carrito vacío")  # presiona espacio 12 veces

elif menu == "Dashboard": # 0 espacios, pegado al borde
    st.header("📊 Dashboard")
    ventas = obtener_ventas()
    productos = obtener_productos()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Productos", len(productos))
    with col2:
        total_ventas = sum(v.get('total', 0) for v in ventas)
        st.metric("Ventas Totales", f"S/{total_ventas:.2f}")
    with col3:
        st.metric("Transacciones", len(ventas))

elif menu == "ADMIN": # 0 espacios también
    st.header("⚙️ Panel Admin")
    rol_usuario = st.session_state.user_data.get('rol', 'cliente')

    if rol_usuario == 'admin':
        # SI ERES ADMIN: 2 PESTAÑAS
        tab_clave_admin, tab_plan = st.tabs(["🔑 Cambiar Clave de Cliente", "🔒 Activar Plan S/30"])

        with tab_clave_admin:
            st.subheader("Cambiar Clave de Cualquier Usuario")
            dni_usuario = st.text_input("DNI del usuario")
            nueva_clave_admin = st.text_input("Nueva Clave para el usuario", type="password", key="new_pass_admin")
            if st.button("Cambiar Clave del Usuario"):
                if not dni_usuario or not nueva_clave_admin:
                    st.error("Completa DNI y nueva clave")
                else:
                    try:
                        from boto3.dynamodb.conditions import Key
                        response = tabla_usuarios.query(
                            IndexName='dni-index',
                            KeyConditionExpression=Key('dni').eq(dni_usuario)
                        )
                        if response['Items']:
                            uid = response['Items'][0]['usuario_id']
                            tabla_usuarios.update_item(
                                Key={'usuario_id': uid},
                                UpdateExpression='SET password_hash = :val',
                                ExpressionAttributeValues={':val': hash_password(nueva_clave_admin)}
                            )
                            st.success(f"✅ Clave cambiada para DNI {dni_usuario}")
                        else:
                            st.error("DNI no encontrado")
                    except Exception as e:
                        st.error(f"Error: {e}")

        with tab_plan:
            st.subheader("Activar Plan S/30 por 30 días")
            dni_cliente = st.text_input("DNI del cliente que pagó S/30", key="dni_plan")
            if st.button("Activar 30 días"):
                if not dni_cliente:
                    st.error("Ingresa el DNI")
                else:
                    try:
                        from boto3.dynamodb.conditions import Key
                        from datetime import datetime, timedelta
                        nueva_fecha = (datetime.now() + timedelta(days=30)).isoformat()
                        response = tabla_usuarios.query(
                            IndexName='dni-index',
                            KeyConditionExpression=Key('dni').eq(dni_cliente)
                        )
                        if response['Items']:
                            uid = response['Items'][0]['usuario_id']
                            tabla_usuarios.update_item(
                                Key={'usuario_id': uid},
                                UpdateExpression='SET #p = :p, fecha_trial_fin = :f, activo = :a',
                                ExpressionAttributeNames={'#p': 'plan'},
                                ExpressionAttributeValues={
                                    ':p': 'premium',
                                    ':f': nueva_fecha,
                                    ':a': True
                                }
                            )
                            st.success(f"✅ Plan PREMIUM activado para DNI {dni_cliente} por 30 días")
                            st.balloons()
                        else:
                            st.error("DNI no encontrado")
                    except Exception as e:
                        st.error(f"Error: {e}")

    else:
        # SI ES CLIENTE: SOLO CAMBIAR SU PROPIA CLAVE
        st.subheader("🔑 Cambiar Mi Clave")
        nueva_clave = st.text_input("Nueva Clave", type="password", key="new_pass_cliente")
        confirmar_clave = st.text_input("Confirmar Nueva Clave", type="password", key="confirm_pass_cliente")
        if st.button("Cambiar Mi Clave"):
            if nueva_clave!= confirmar_clave:
                st.error("Las claves no coinciden")
            elif len(nueva_clave) < 6:
                st.error("Mínimo 6 caracteres")
            else:
                try:
                    tabla_usuarios.update_item(
                        Key={'usuario_id': user['usuario_id']},
                        UpdateExpression='SET password_hash = :val',
                        ExpressionAttributeValues={':val': hash_password(nueva_clave)}
                    )
                    st.success("✅ Tu clave fue cambiada")
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.error(f"Error: {e}")
