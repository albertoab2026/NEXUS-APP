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
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    color: #ffffff !important;
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
    color: white !important;
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

.stTextInput > div > div > input, .stNumberInput > div > div > input {
    background-color: rgba(37, 40, 54, 0.8) !important;
    color: #ffffff !important;
    border: 1px solid #4F46E5 !important;
    border-radius: 8px;
    box-shadow: 0 0 10px rgba(79, 70, 229, 0.2);
}

.stSelectbox > div > div {
    background-color: rgba(37, 40, 54, 0.8) !important;
    border: 1px solid #4F46E5 !important;
    border-radius: 8px;
    color: white !important;
    box-shadow: 0 0 10px rgba(79, 70, 229, 0.2);
}

.stTabs [data-baseweb="tab"] {
    background-color: transparent;
    color: #9CA3AF;
    font-weight: 600;
}
.stTabs [aria-selected="true"] {
    color: #F59E0B !important;
    border-bottom: 2px solid #F59E0B !important;
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
tabla_usuarios = dynamodb.Table('nexus_usuarios')
tabla_productos = dynamodb.Table('nexus_productos')
tabla_ventas = dynamodb.Table('nexus_ventas')

# ====== 3. FUNCIONES DE USUARIOS ======
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def registrar_dueno(dni, nombre, email, password):
    try:
        tabla_usuarios.put_item(
            Item={
                'usuario_id': dni,
                'dni': dni,
                'nombre': nombre,
                'email': email,
                'password': hash_password(password),
                'rol': 'dueno',
                'estado_suscripcion': 'trial',
                'fecha_registro': datetime.now().isoformat(),
                'fecha_vencimiento': (datetime.now() + timedelta(days=7)).isoformat(),
                'ventas_acumuladas': 0
            }
        )
        return True
    except:
        return False

def login(dni, password):
    try:
        response = tabla_usuarios.get_item(Key={'usuario_id': dni})
        if 'Item' in response:
            user = response['Item']
            if user['password'] == hash_password(password):
                return user
        return None
    except:
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
        # Actualizar stock
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

# ====== 6. UI LOGIN ======
def mostrar_login():
    st.markdown("""
    <div style='text-align: center; margin-bottom: 40px;'>
        <div class='main-header'>
            <h1 style='font-size: 2.5rem; margin: 0; color: white;'>⚡ NEXUS</h1>
            <p style='color: rgba(255,255,255,0.9); font-size: 1rem; margin-top: 8px;'>
                El Sistema que Controla tu Negocio
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='text-align: center; color: #60A5FA; margin-bottom: 30px; font-size: 1.5rem;'>¿Cansado de perder plata en tu negocio?</h2>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div style='background: #252836; border: 1px solid #3F4354; border-radius: 12px; 
                    padding: 20px; text-align: center; height: 190px; 
                    transition: all 0.3s ease;
                    box-shadow: 0 0 15px rgba(124, 58, 237, 0.1);'
             onmouseover="this.style.transform='translateY(-5px)'; 
                          this.style.boxShadow='0 8px 25px rgba(124, 58, 237, 0.4)';
                          this.style.border='1px solid #7C3AED';"
             onmouseout="this.style.transform='translateY(0)'; 
                         this.style.boxShadow='0 0 15px rgba(124, 58, 237, 0.1)';
                         this.style.border='1px solid #3F4354';">
            <div style='font-size: 2.2rem; margin-bottom: 10px;'>📦</div>
            <h3 style='font-size: 1rem; margin: 10px 0;'>Control Total</h3>
            <p style='color: #9CA3AF; font-size: 0.8rem; line-height: 1.3;'>
                Sabes qué vendes y qué te falta. Adiós cuaderno.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='background: #252836; border: 1px solid #3F4354; border-radius: 12px; 
                    padding: 20px; text-align: center; height: 190px; 
                    transition: all 0.3s ease;
                    box-shadow: 0 0 15px rgba(124, 58, 237, 0.1);'
             onmouseover="this.style.transform='translateY(-5px)'; 
                          this.style.boxShadow='0 8px 25px rgba(124, 58, 237, 0.4)';
                          this.style.border='1px solid #7C3AED';"
             onmouseout="this.style.transform='translateY(0)'; 
                         this.style.boxShadow='0 0 15px rgba(124, 58, 237, 0.1)';
                         this.style.border='1px solid #3F4354';">
            <div style='font-size: 2.2rem; margin-bottom: 10px;'>💰</div>
            <h3 style='font-size: 1rem; margin: 10px 0;'>Más Ganancia</h3>
            <p style='color: #9CA3AF; font-size: 0.8rem; line-height: 1.3;'>
                Ve qué productos más plata te dejan. Gana más.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style='background: #252836; border: 1px solid #3F4354; border-radius: 12px; 
                    padding: 20px; text-align: center; height: 190px; 
                    transition: all 0.3s ease;
                    box-shadow: 0 0 15px rgba(124, 58, 237, 0.1);'
             onmouseover="this.style.transform='translateY(-5px)'; 
                          this.style.boxShadow='0 8px 25px rgba(124, 58, 237, 0.4)';
                          this.style.border='1px solid #7C3AED';"
             onmouseout="this.style.transform='translateY(0)'; 
                         this.style.boxShadow='0 0 15px rgba(124, 58, 237, 0.1)';
                         this.style.border='1px solid #3F4354';">
            <div style='font-size: 2.2rem; margin-bottom: 10px;'>📱</div>
            <h3 style='font-size: 1rem; margin: 10px 0;'>Desde tu Celular</h3>
            <p style='color: #9CA3AF; font-size: 0.8rem; line-height: 1.3;'>
                Sin computadoras. Gestiona donde estés.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div style='background: #252836; border: 1px solid #3F4354; border-radius: 12px; 
                    padding: 20px; text-align: center; height: 190px; 
                    transition: all 0.3s ease;
                    box-shadow: 0 0 15px rgba(124, 58, 237, 0.1);'
             onmouseover="this.style.transform='translateY(-5px)'; 
                          this.style.boxShadow='0 8px 25px rgba(124, 58, 237, 0.4)';
                          this.style.border='1px solid #7C3AED';"
             onmouseout="this.style.transform='translateY(0)'; 
                         this.style.boxShadow='0 0 15px rgba(124, 58, 237, 0.1)';
                         this.style.border='1px solid #3F4354';">
            <div style='font-size: 2.2rem; margin-bottom: 10px;'>⚡</div>
            <h3 style='font-size: 1rem; margin: 10px 0;'>Súper Barato</h3>
            <p style='color: #9CA3AF; font-size: 0.8rem; line-height: 1.3;'>
                S/30 al mes. Otros cobran S/250.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("""
        <div style='background: #10B981; border-radius: 12px; padding: 20px; 
                    text-align: center; margin: 20px 0;
                    box-shadow: 0 0 20px rgba(16, 185, 129, 0.4);'>
            <h3 style='margin: 0; color: white; font-size: 1.1rem;'>🎁 Prueba 7 DÍAS GRATIS</h3>
            <p style='color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 0.85rem;'>
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
        st.markdown("<h3 style='text-align: center;'>Crea tu cuenta GRATIS</h3>", unsafe_allow_html=True)
        nombre = st.text_input("Nombre completo", placeholder="Juan Pérez", key="reg_nom")
        dni = st.text_input("DNI", placeholder="12345678", key="reg_dni")
        email = st.text_input("Email", placeholder="tu@email.com", key="reg_email")
        password = st.text_input("Contraseña", type="password", key="reg_pass")
        if st.button("ACTIVAR 7 DÍAS GRATIS", use_container_width=True):
            if registrar_dueno(dni, nombre, email, password):
                st.success("✅ Cuenta creada. 7 días gratis activados")
                st.balloons()
                st.info("Ahora inicia sesión en la pestaña de arriba")
            else:
                st.error("Error al registrar")

# ====== 7. MAIN APP ======
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    mostrar_login()
else:
    st.sidebar.title(f"⚡ NEXUS")
    st.sidebar.write(f"Bienvenido, {st.session_state.user_data['nombre']}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.rerun()
    
    tab1, tab2, tab3 = st.tabs(["📦 Productos", "💰 Ventas", "📊 Dashboard"])
    
    with tab1:
        st.header("Gestión de Productos")
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
    
    with tab2:
        st.header("Registrar Venta")
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
    
    with tab3:
        st.header("Dashboard")
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
