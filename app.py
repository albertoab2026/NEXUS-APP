import streamlit as st
import boto3
from boto3.dynamodb.conditions import Key
import pandas as pd
import uuid
from datetime import datetime, timedelta
import hashlib

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

def registrar_dueno(dni, nombre, email, password):
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
                'email': email,
                'password_hash': hash_password(password),
                'rol': 'dueno',
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
        response = tabla_usuarios.scan(
            FilterExpression=Key('dni').eq(usuario_o_dni) | Key('usuario_id').eq(usuario_o_dni)
        )
        if response['Items']:
            user = response['Items'][0]
            if user.get('password_hash') == hash_password(password):
                if user.get('activo', False):
                    return user
                else:
                    st.error("❌ Cuenta desactivada")
                    return None
        return None
    except Exception as e:
        st.error(f"Error login: {e}")
        return None
# ====== 4. FUNCIONES DE PRODUCTOS ======
def obtener_productos():
    try:
        response = tabla_productos.scan()
        return response.get('Items', [])
    except:
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
        response = tabla_ventas.scan()
        return response.get('Items', [])
    except:
        return []

# ====== 6. UI LOGIN - SIN ERRORES DE INDENTACIÓN ======
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

    with tab2:
        dni = st.text_input("DNI", key="reg_dni")
        nombre = st.text_input("Nombre de tu Bodega", key="reg_nombre")
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Contraseña", type="password", key="reg_pass")
        
        if st.button("ACTIVAR 7 DÍAS GRATIS", use_container_width=True):
            if registrar_dueno(dni, nombre, email, password):
                st.success("✅ Cuenta creada. 7 días gratis activados")
                st.balloons()
                st.info("Ahora inicia sesión en la pestaña de arriba")
            else:
                st.error("Error al registrar")
    
    # ====== INFO DE PAGO YAPE/PLIN - PÉGALO AQUÍ 👇 ======
    st.markdown("---")
    st.markdown("""
    <div style='background: #1E293B; border: 2px solid #10B981; border-radius: 12px; 
                padding: 16px; text-align: center; margin-top: 20px;'>
        <p style='color: #10B981; font-size: 0.9rem; margin: 0; font-weight: 600;'>
            💳 PAGOS YAPE/PLIN
        </p>
        <h3 style='color: white; margin: 8px 0; font-size: 1.4rem; letter-spacing: 1px;'>
            914 282 688
        </h3>
        <p style='color: #94A3B8; font-size: 0.85rem; margin: 0;'>
            ALBERTO BALLARTA
        </p>
    </div>
    """, unsafe_allow_html=True)

# ====== 7. MAIN APP ======
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    mostrar_login()
else:
    user_data = st.session_state.user_data
    nombre = user_data['nombre']
    rol = user_data['rol'].upper()
    plan = user_data.get('plan', 'trial').upper()
    
    # ====== BANNER BIENVENIDA COMO EN LA FOTO ======
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #7C3AED 100%);
                border-radius: 15px; padding: 20px; margin-bottom: 20px;
                box-shadow: 0 0 30px rgba(139, 92, 246, 0.5); text-align: center;'>
        <h2 style='margin: 0; color: white; font-size: 1.8rem; font-weight: 700;'>
            Bienvenido, {nombre}!
        </h2>
        <p style='color: rgba(255,255,255,0.85); margin: 8px 0 0 0; font-size: 0.9rem;'>
            Rol: {rol} | Plan: {plan}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ====== SIDEBAR CON MENÚ DESPLEGABLE ======
    st.sidebar.markdown("### Menú")
    
    menu_opcion = st.sidebar.selectbox(
        "Selecciona:",
        ["📊 Dashboard", "📦 Productos", "💰 Ventas", "🔧 Admin"],
        label_visibility="collapsed"
    )
    
    # Submenú Admin solo para DUEÑO
    if rol == "DUENO" and menu_opcion == "🔧 Admin":
        st.sidebar.markdown("### ⚙️ Panel Admin")
        admin_accion = st.sidebar.radio(
            "Opciones Admin:",
            ["🔑 Cambiar Claves", "💳 Activar Plan S/30"],
            label_visibility="collapsed"
        )
        
        if admin_accion == "💳 Activar Plan S/30":
            st.sidebar.markdown("#### Activar Plan S/30 por 30 días")
            dni_cliente = st.sidebar.text_input("DNI del cliente que pagó S/30")
            if st.sidebar.button("Activar 30 días", use_container_width=True):
                st.sidebar.success(f"✅ Plan activado para DNI: {dni_cliente}")
        
        elif admin_accion == "🔑 Cambiar Claves":
            st.sidebar.markdown("#### Cambiar Contraseña")
            nueva_pass = st.sidebar.text_input("Nueva contraseña", type="password")
            if st.sidebar.button("Actualizar Clave", use_container_width=True):
                st.sidebar.success("✅ Contraseña actualizada")
    
    # INFO YAPE/PLIN SIEMPRE VISIBLE
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style='background: #10B981; border-radius: 10px; padding: 12px; text-align: center;'>
        <p style='color: white; font-size: 0.75rem; margin: 0; font-weight: 600;'>
            💳 YAPE/PLIN
        </p>
        <p style='color: white; margin: 4px 0; font-size: 1.1rem; font-weight: 700;'>
            914 282 688
        </p>
        <p style='color: rgba(255,255,255,0.9); font-size: 0.7rem; margin: 0;'>
            ALBERTO BALLARTA
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

    # ====== CONTENIDO SEGÚN EL MENÚ ======
    if menu_opcion == "📦 Productos":
        st.header("📦 Gestión de Productos")
        with st.form("form_producto"):
            nombre = st.text_input("Nombre del producto")
            precio = st.number_input("Precio", min_value=0.0, format="%.2f")
            stock = st.number_input("Stock inicial", min_value=0)
            categoria = st.selectbox("Categoría", ["Abarrotes", "Bebidas", "Limpieza", "Otros"])
            if st.form_submit_button("Agregar Producto"):
                if agregar_producto(nombre, precio, stock, categoria):
                    st.success("Producto agregado")
                    st.rerun()

        productos = obtener_productos()
        if productos:
            df = pd.DataFrame(productos)
            st.dataframe(df[['nombre', 'precio', 'stock', 'categoria']], use_container_width=True)

    elif menu_opcion == "💰 Ventas":
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

    elif menu_opcion == "📊 Dashboard":
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
            
    elif menu_opcion == "🔧 Admin":
        if rol != "DUENO":
            st.error("❌ Solo el dueño puede acceder al panel admin")
        else:
            st.header("⚙️ Panel de Administración")
            st.info("Selecciona una opción del menú lateral en 'Admin'")
