import streamlit as st
import boto3
from boto3.dynamodb.conditions import Key
import pandas as pd
import uuid
from datetime import datetime, timedelta
import hashlib

# ====== RUBROS Y CATEGORÍAS BASE - NUEVO ======
CATEGORIAS_POR_RUBRO = {
    "Bodega": ["Abarrotes", "Bebidas", "Limpieza", "Golosinas", "Lácteos", "Panadería"],
    "Farmacia": ["Medicinas", "Vitaminas", "Cuidado Personal", "Bebés", "Primeros Auxilios", "Recetas"],
    "Librería": ["Cuadernos", "Lapiceros", "Papelería", "Arte y Manualidades", "Libros", "Oficina"],
    "Ferretería": ["Herramientas", "Pinturas", "Electricidad", "Gasfitería", "Construcción"],
    "Minimarket": ["Abarrotes", "Bebidas", "Limpieza", "Lácteos", "Librería y Papelería"],
    "Almacén": ["Mayorista", "Distribución", "Inventario General"],
    "Otro": [] # Arranca vacío, crea todo desde cero
}

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
        user_id = st.session_state.user_data['usuario_id']
        response = tabla_productos.query(
            IndexName='usuario-index',
            KeyConditionExpression=Key('usuario_id').eq(user_id)
        )
        return response.get('Items', [])
    except Exception as e:
        st.error(f"Error cargando productos: {e}")
        return []

def agregar_producto(nombre, precio, stock, categoria):
    try:
        producto_id = str(uuid.uuid4())
        tabla_productos.put_item(
            Item={
                'producto_id': producto_id,
                'nombre': nombre,
                'precio': float(precio),
                'stock': int(stock),
                'categoria': categoria,
                'fecha_creacion': datetime.now().isoformat()
            }
        )
        return True
    except:
        return False

# ====== 5. FUNCIONES DE VENTAS ======
def registrar_venta(producto_id, cantidad, precio_unitario):
    try:
        venta_id = str(uuid.uuid4())
        total = float(precio_unitario) * int(cantidad)
        tabla_ventas.put_item(
            Item={
                'venta_id': venta_id,
                'producto_id': producto_id,
                'cantidad': int(cantidad),
                'precio_unitario': float(precio_unitario),
                'total': total,
                'fecha': datetime.now().isoformat()
            }
        )
        response = tabla_productos.get_item(Key={'producto_id': producto_id})
        if 'Item' in response:
            stock_actual = response['Item']['stock']
            tabla_productos.update_item(
                Key={'producto_id': producto_id},
                UpdateExpression='SET stock = :val',
                ExpressionAttributeValues={':val': stock_actual - int(cantidad)}
            )
        return True
    except:
        return False

def obtener_ventas():
    try:
        user_id = st.session_state.user_data['usuario_id']
        response = tabla_ventas.query(
            IndexName='usuario-index',
            KeyConditionExpression=Key('usuario_id').eq(user_id)
        )
        return response.get('Items', [])
    except:
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

    with tab1:  # ← 4 ESPACIOS
        st.markdown("<h3 style='text-align: center;'>Iniciar Sesión</h3>", unsafe_allow_html=True)
        dni = st.text_input("Usuario o DNI", placeholder="12345678")
        password = st.text_input("Contraseña", type="password")
        if st.button("Iniciar Sesión", use_container_width=True):
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
else:
    # === SIDEBAR SOLO CAJA MORADA + YAPE + CERRAR SESIÓN ===
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
    
    # === DESPLIEGABLE AFUERA - SOLO DEBE HABER 1 VEZ EN TODO EL CODIGO ===
    menu = st.selectbox("Menu", ["📦 Productos", "💰 Ventas", "📊 Dashboard", "⚙️ ADMIN"], label_visibility="collapsed")
    st.write("")

    if menu == "📦 Productos":
        st.header("📦 Gestión de Productos")

        # ====== CATEGORÍAS DINÁMICAS POR RUBRO - NUEVO ======
        rubro_usuario = st.session_state.user_data.get('rubro', 'Otro')
        categorias_base = CATEGORIAS_POR_RUBRO.get(rubro_usuario, [])
        categorias_custom = st.session_state.user_data.get('categorias_custom', [])

        opciones_cat = categorias_base + categorias_custom + ["➕ Crear nueva categoría"]

        col1, col2 = st.columns([3,1])
        with col1:
            categoria_seleccionada = st.selectbox("Categoría", opciones_cat, key="cat_select_prod")

        with col2:
            if categoria_seleccionada == "➕ Crear nueva categoría":
                nueva_cat = st.text_input("Nueva", key="nueva_cat_prod", label_visibility="collapsed", placeholder="Nombre")
                if st.button("Guardar") and nueva_cat:
                    if nueva_cat not in opciones_cat:
                        categorias_custom.append(nueva_cat)
                        tabla_usuarios.update_item(
                            Key={'usuario_id': st.session_state.user_data['usuario_id']},
                            UpdateExpression='SET categorias_custom = :c',
                            ExpressionAttributeValues={':c': categorias_custom}
                        )
                        st.session_state.user_data['categorias_custom'] = categorias_custom
                        st.success(f"'{nueva_cat}' creada")
                        st.rerun()
                    else:
                        st.error("Ya existe")
                st.stop()

        # ====== FORM DE PRODUCTO ======
        with st.form("form_producto", clear_on_submit=True):
            nombre = st.text_input("Nombre del producto", placeholder="Ej: Paracetamol 500mg")
            precio = st.number_input("Precio", min_value=0.0, format="%.2f")
            stock = st.number_input("Stock inicial", min_value=0)

            if st.form_submit_button("Agregar Producto"):
                if nombre and categoria_seleccionada!= "➕ Crear nueva categoría":
                    if agregar_producto(nombre, precio, stock, categoria_seleccionada):
                        st.success("Producto agregado")
                        st.rerun()
                else:
                    st.error("Completa el nombre y elige categoría válida")

        st.divider()
        # ====== TABLA CON FILTRO + EDITAR/BORRAR ======
        st.subheader("Mis Productos")
        filtro = st.selectbox("Filtrar por categoría", ["Todas"] + categorias_base + categorias_custom, key="filtro_prod")

        productos = obtener_productos()
        if productos:
            df = pd.DataFrame(productos)
            if filtro != "Todas":
                df = df[df['categoria'] == filtro]

            if not df.empty:
                # Tabla + botones de acción
                for idx, row in df.iterrows():
                    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 1, 1])
                    with col1:
                        st.write(f"**{row['nombre']}**")
                        st.caption(row['categoria'])
                    with col2:
                        st.write(f"S/ {row['precio']:.2f}")
                    with col3:
                        st.write(f"{row['stock']} und")
                    with col4:
                        if st.button("✏️", key=f"edit_{row['producto_id']}"):
                            st.session_state.editando_producto = row['producto_id']
                            st.rerun()
                    with col5:
                        if st.button("🗑️", key=f"del_{row['producto_id']}"):
                            tabla_productos.delete_item(Key={'producto_id': row['producto_id']})
                            st.success("Producto borrado")
                            st.rerun()
            else:
                st.info(f"Sin productos en '{filtro}'")
        else:
            st.info("Aún no tienes productos. Agrega el primero arriba")

        # ====== FORMULARIO DE EDICIÓN ======
        if 'editando_producto' in st.session_state:
            prod_id = st.session_state.editando_producto
            prod = next((p for p in productos if p['producto_id'] == prod_id), None)
            
            if prod:
                st.divider()
                st.subheader(f"✏️ Editando: {prod['nombre']}")
                
                with st.form("form_editar"):
                    nuevo_nombre = st.text_input("Nombre", value=prod['nombre'])
                    nuevo_precio = st.number_input("Precio", value=float(prod['precio']), format="%.2f")
                    nuevo_stock = st.number_input("Stock", value=int(prod['stock']), min_value=0)
                    nueva_cat = st.selectbox("Categoría", categorias_base + categorias_custom, 
                                           index=(categorias_base + categorias_custom).index(prod['categoria']) 
                                           if prod['categoria'] in (categorias_base + categorias_custom) else 0)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Guardar Cambios"):
                            tabla_productos.update_item(
                                Key={'producto_id': prod_id},
                                UpdateExpression='SET nombre = :n, precio = :p, stock = :s, categoria = :c',
                                ExpressionAttributeValues={
                                    ':n': nuevo_nombre,
                                    ':p': float(nuevo_precio),
                                    ':s': int(nuevo_stock),
                                    ':c': nueva_cat
                                }
                            )
                            del st.session_state.editando_producto
                            st.success("Producto actualizado")
                            st.rerun()
                    with col2:
                        if st.form_submit_button("❌ Cancelar"):
                            del st.session_state.editando_producto
                            st.rerun()
    elif menu == "💰 Ventas":
        st.header("💰 Registrar Venta")
        productos = obtener_productos()
        if productos:
            nombres = [p['nombre'] for p in productos]
            producto_sel = st.selectbox("Producto", nombres)
            cantidad = st.number_input("Cantidad", min_value=1, value=1)
            producto = next((p for p in productos if p['nombre'] == producto_sel), None)
            if producto:
                st.write(f"Precio unitario: S/{producto['precio']:.2f}")
                st.write(f"Total: S/{producto['precio'] * cantidad:.2f}")
                if st.button("Registrar Venta"):
                    if registrar_venta(producto['producto_id'], cantidad, producto['precio']):
                        st.success("Venta registrada")
                        st.rerun()
        else:
            st.warning("Primero agrega productos")

    elif menu == "📊 Dashboard":
        st.header("📊 Dashboard")
        ventas = obtener_ventas()
        productos = obtener_productos()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Productos", len(productos))
        with col2:
            total_ventas = sum([v['total'] for v in ventas])
            st.metric("Ventas Totales", f"S/{total_ventas:.2f}")
        with col3:
            st.metric("Transacciones", len(ventas))

    elif menu == "⚙️ ADMIN":
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
