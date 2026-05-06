import streamlit as st
import boto3
from boto3.dynamodb.conditions import Key
import pandas as pd
from datetime import datetime, date
import uuid
import hashlib

# ====== CONFIGURACIÓN ======
st.set_page_config(page_title="Mi Bodega", page_icon="🏪", layout="wide")

# ====== CONEXIÓN DYNAMODB ======
@st.cache_resource
def init_dynamodb():
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=st.secrets["AWS_DEFAULT_REGION"],
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"]
    )
    return dynamodb

dynamodb = init_dynamodb()
tabla_usuarios = dynamodb.Table('NEXUS_DUENOS')        # Login usa esta tabla
tabla_productos = dynamodb.Table('NEXUS_PRODUCTOS')    
tabla_ventas = dynamodb.Table('NEXUS_VENTAS')          

# ====== FUNCIONES ======
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verificar_usuario(id_dueno, password):
    try:
        # Tu clave de partición es 'id_del_dueno'
        response = tabla_usuarios.get_item(Key={'id_del_dueno': id_dueno})
        if 'Item' in response:
            if response['Item']['password'] == hash_password(password):
                return response['Item']
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None

def agregar_producto(nombre, precio, stock, categoria):
    try:
        producto_id = str(uuid.uuid4())
        tabla_productos.put_item(Item={
            'producto_id': producto_id,
            'nombre': nombre,
            'precio': float(precio),
            'stock': int(stock),
            'categoria': categoria
        })
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def obtener_productos():
    try:
        response = tabla_productos.scan()
        return response['Items']
    except:
        return []

def registrar_venta(producto_id, cantidad, precio_unitario):
    try:
        venta_id = str(uuid.uuid4())
        tabla_ventas.put_item(Item={
            'venta_id': venta_id,
            'producto_id': producto_id,
            'cantidad': int(cantidad),
            'precio_unitario': float(precio_unitario),
            'total': float(cantidad * precio_unitario),
            'fecha': str(date.today())
        })
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def obtener_ventas():
    try:
        response = tabla_ventas.scan()
        return response['Items']
    except:
        return []
        # ====== LOGIN ======
def mostrar_login():
    st.title("🏪 Login Mi Bodega")
    
    with st.form("login_form"):
        id_dueno = st.text_input("ID Dueño")  # Usa el id_del_dueno de tu tabla
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Entrar")
        
        if submit:
            user_data = verificar_usuario(id_dueno, password)
            if user_data:
                st.session_state.logged_in = True
                st.session_state.user_data = user_data
                st.rerun()
            else:
                st.error("ID o contraseña incorrectos")

# ====== 7. MAIN APP ======
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_data = {}

if not st.session_state.logged_in:
    mostrar_login()
else:
    # === DEFINIR VARIABLES ===
    user_data = st.session_state.user_data
    nombre = user_data.get('nombre_local', user_data.get('nombre', 'Bodega'))
    plan = user_data.get('plan', 'TRIAL').upper()
    vence = user_data.get('fecha_vencimiento', 'N/A')
    rol = user_data.get('rol', '').strip().upper()
    
    # === BANNER BIENVENIDA ===
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #9b59b6, #8e44ad); border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0 0 30px rgba(139, 92, 246, 0.3);'>
        <h2 style='margin: 0; color: white; font-size: 2rem;'>
        Bienvenido, {nombre}!
        </h2>
        <p style='color: rgba(255,255,255,0.85); margin: 10px 0 0 0;'>
        Rol: {rol} | Plan: {plan} | Vence: {vence}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # === SIDEBAR CON MENÚ ===
    with st.sidebar:
        st.markdown("### 📋 Menú")
        
        menu_opcion = st.selectbox(
            "Selecciona:",
            ["📊 Dashboard", "📦 Productos", "💰 Ventas", "🔧 Admin"]
        )
        
        # Submenú de Admin solo si es dueño
        if rol == "DUENO" and menu_opcion == "🔧 Admin":
            admin_opcion = st.radio(
                "Opciones de Admin:",
                ["Cambiar Claves", "Activar Plan S/30"]
            )
        
        st.divider()
        
        # Tarjeta YAPE/PLIN
        st.markdown("""
        <div style='background-color:#16a085; padding:15px; border-radius:10px; color:white; text-align:center'>
            <h4 style='margin:0'>💳 YAPE / PLIN</h4>
            <h3 style='margin:10px 0'>914 282 688</h3>
            <p style='margin:0; font-size:12px'>ALBERTO BALLARTA</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_data = {}
            st.rerun()
                # === CONTENIDO SEGÚN EL MENÚ ===
    
    if menu_opcion == "📊 Dashboard":
        st.header("📊 Dashboard")
        ventas = obtener_ventas()
        productos = obtener_productos()
        
        col1, col2, col3 = st.columns(3)
        with col1: 
            st.metric("Total Productos", len(productos))
        with col2: 
            total_ventas = sum([float(v.get('total', 0)) for v in ventas])
            st.metric("Ventas Totales", f"S/{total_ventas:.2f}")
        with col3: 
            st.metric("Transacciones", len(ventas))
        
        st.divider()
        if ventas:
            st.subheader("Últimas ventas")
            df_ventas = pd.DataFrame(ventas)
            st.dataframe(df_ventas[['fecha', 'total']], use_container_width=True)
        else:
            st.info("Aún no hay ventas registradas")

    elif menu_opcion == "📦 Productos":
        st.header("📦 Gestión de Productos")
        
        with st.form("form_producto"):
            col1, col2 = st.columns(2)
            with col1:
                nombre_prod = st.text_input("Nombre del producto")
                precio = st.number_input("Precio S/", min_value=0.0, format="%.2f")
            with col2:
                stock = st.number_input("Stock inicial", min_value=0, step=1)
                categoria = st.selectbox("Categoría", ["Abarrotes", "Bebidas", "Limpieza", "Otros"])
            
            if st.form_submit_button("Agregar Producto", use_container_width=True):
                if nombre_prod and precio > 0:
                    if agregar_producto(nombre_prod, precio, stock, categoria):
                        st.success("✅ Producto agregado")
                        st.rerun()
                else:
                    st.error("Completa nombre y precio")
        
        st.divider()
        productos = obtener_productos()
        if productos:
            df = pd.DataFrame(productos)
            st.dataframe(
                df[['nombre', 'precio', 'stock', 'categoria']], 
                use_container_width=True,
                column_config={
                    "precio": st.column_config.NumberColumn("Precio S/", format="S/ %.2f"),
                    "stock": st.column_config.NumberColumn("Stock")
                }
            )
        else:
            st.warning("No hay productos. Agrega el primero arriba")

    elif menu_opcion == "💰 Ventas":
        st.header("💰 Registrar Venta")
        productos = obtener_productos()
        
        if productos:
            nombres = [p['nombre'] for p in productos]
            producto_sel = st.selectbox("Selecciona producto", nombres)
            cantidad = st.number_input("Cantidad", min_value=1, value=1, step=1)
            
            producto = next((p for p in productos if p['nombre'] == producto_sel), None)
            if producto:
                precio_unit = float(producto['precio'])
                stock_actual = int(producto['stock'])
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Precio Unit.", f"S/{precio_unit:.2f}")
                col2.metric("Stock Disponible", stock_actual)
                col3.metric("Total Venta", f"S/{precio_unit * cantidad:.2f}")
                
                if cantidad > stock_actual:
                    st.error(f"❌ Solo tienes {stock_actual} unidades")
                elif st.button("Registrar Venta", use_container_width=True, type="primary"):
                    if registrar_venta(producto['producto_id'], cantidad, precio_unit):
                        st.success("✅ Venta registrada")
                        st.rerun()
        else:
            st.warning("⚠️ Primero agrega productos en el menú Productos")

    elif menu_opcion == "🔧 Admin":
        if rol == "DUENO":
            st.header("⚙️ Panel de Administración")
            st.success("✅ Acceso de dueño confirmado")
            
            if admin_opcion == "Cambiar Claves":
                st.subheader("🔑 Cambiar Claves")
                st.info("Función en desarrollo")
                
            elif admin_opcion == "Activar Plan S/30":
                st.subheader("💎 Activar Plan Premium S/30")
                st.info("Función en desarrollo")
                st.markdown("""
                **Beneficios del Plan Premium:**
                - Reportes avanzados
                - Soporte 24/7
                - Sin límite de productos
                """)
        else:
            st.error(f"❌ Solo el dueño puede acceder. Tu rol actual: '{rol}'")
            st.warning("Contacta al administrador para obtener acceso")
