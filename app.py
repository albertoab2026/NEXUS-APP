import streamlit as st
import boto3
from boto3.dynamodb.conditions import Key
import pandas as pd
import uuid
from datetime import datetime, timedelta, timezone
import hashlib
from decimal import Decimal

# ======= 1. CONFIG INICIAL =======
st.set_page_config(page_title="NEXUS", page_icon="⚡", layout="wide")

CATEGORIAS_POR_RUBRO = {
    "Bodega": ["Abarrotes", "Bebidas", "Limpieza", "Golosinas", "Lácteos"],
    "Farmacia": ["Medicinas", "Vitaminas", "Cuidado Personal", "Bebé"],
    "Librería": ["Cuadernos", "Lapiceros", "Papelería", "Arte y Manualidades"],
    "Ferretería": ["Herramientas", "Pinturas", "Electricidad", "Gasfitería"],
    "Minimarket": ["Abarrotes", "Bebidas", "Limpieza", "Lácteos"],
    "Almacén": ["Mayorista", "Distribución", "Inventario General"],
    "Otro": []
}

# Session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

.stApp {
    background: linear-gradient(135deg, #1e3a8a 0%, #312e81 100%) !important;
    font-family: 'Inter', sans-serif !important;
}

header, .stDeployButton {display: none !important;}

div.login-box {
    background: #ffffff !important;
    padding: 2rem !important;
    border-radius: 15px !important;
    margin: 2rem auto !important;
    max-width: 400px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3) !important;
}       

.login-title {
    text-align: center;
    color: #1e3a8a !important;
    margin: 0 0 20px 0 !important;
    font-size: 26px !important;
    font-weight: 700 !important;
}

.stTextInput input {
    background: #f8fafc !important;
    border: 2px solid #e2e8f0 !important;
    border-radius: 10px !important;
    color: #1e293b !important;
}

.stButton button {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 14px !important;
    font-weight: 700 !important;
    width: 100% !important;
}
</style>
""", unsafe_allow_html=True)

# ======= 2. CONEXIÓN AWS =======
AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = st.secrets["AWS_REGION"]

@st.cache_resource
def init_dynamodb():
    return boto3.resource('dynamodb', aws_access_key_id=AWS_ACCESS_KEY_ID,
                          aws_secret_access_key=AWS_SECRET_ACCESS_KEY, region_name=AWS_REGION)

dynamodb = init_dynamodb()
tabla_usuarios = dynamodb.Table('NEXUS_USUARIOS')
tabla_productos = dynamodb.Table('NEXUS_PRODUCTOS')
tabla_ventas = dynamodb.Table('NEXUS_VENTAS')
tabla_trial = dynamodb.Table('NEXUS_TRIAL_USADOS')

# ======= 3. FUNCIONES CORE =======
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login(usuario_o_dni, password):
    try:
        response = tabla_usuarios.get_item(Key={'usuario_id': usuario_o_dni})
        user = response.get('Item')
        if not user:
            response = tabla_usuarios.query(IndexName='dni-index', KeyConditionExpression=Key('dni').eq(usuario_o_dni))
            if response['Items']:
                user = response['Items'][0]
        if user and user.get('password_hash') == hash_password(password) and user.get('activo', True):
            return user
        return None
    except Exception as e:
        st.error(f"Error login: {e}")
        return None

def registrar_dueno(dni, nombre, nombre_negocio, email, password, rubro):
    try:
        if 'Item' in tabla_trial.get_item(Key={'tipo_id': f'DNI-{dni}'}):
            st.error("❌ Este DNI ya usó los 7 días gratis")
            return False
        timestamp = str(int(datetime.now().timestamp()))[-5:]
        usuario_id = f"DUENO{timestamp}"
        cliente_id = f"DUENO-{timestamp[-3:]}"
        tabla_usuarios.put_item(Item={
            'usuario_id': usuario_id, 'cliente_id': cliente_id, 'id_del_dueno': cliente_id,
            'dni': dni, 'nombre': nombre, 'nombre_negocio': nombre_negocio, 'email': email,
            'password_hash': hash_password(password), 'rol': 'dueno', 'rubro': rubro,
            'plan': 'trial', 'activo': True,
            'fecha_registro': datetime.now().isoformat(),
            'fecha_trial_fin': (datetime.now() + timedelta(days=7)).isoformat()
        })
        tabla_trial.put_item(Item={'tipo_id': f'DNI-{dni}', 'fecha': datetime.now().isoformat()})
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def obtener_productos():
    try:
        id_dueno = st.session_state.user_data['usuario_id']
        response = tabla_productos.query(KeyConditionExpression=Key('id_del_dueno').eq(id_dueno))
        return response.get('Items', [])
    except Exception as e:
        st.error(f"Error cargando productos: {e}")
        return []

def agregar_producto(nombre, precio_venta, precio_compra, stock, categoria):
    try:
        id_dueno = st.session_state.user_data['usuario_id']
        tabla_productos.put_item(Item={
            'id_del_dueno': str(id_dueno),
            'producto_id': str(uuid.uuid4()),
            'nombre': nombre,
            'precio_venta': Decimal(str(precio_venta)),
            'precio_compra': Decimal(str(precio_compra)),
            'stock': int(stock),
            'categoria': categoria
        })
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def registrar_venta(producto_id, cantidad, precio_venta, precio_compra):
    try:
        id_dueno = st.session_state.user_data['usuario_id']
        fecha_utc = datetime.now(timezone.utc).isoformat()
        total_venta = float(precio_venta) * int(cantidad)
        total_costo = float(precio_compra) * int(cantidad)
        ganancia = total_venta - total_costo

        tabla_ventas.put_item(Item={
            'usuario_id': id_dueno,
            'Venta_id': str(uuid.uuid4()),
            'producto_id': producto_id,
            'cantidad': int(cantidad),
            'precio_venta': Decimal(str(precio_venta)),
            'precio_compra': Decimal(str(precio_compra)),
            'total_venta': Decimal(str(total_venta)),
            'total_costo': Decimal(str(total_costo)),
            'ganancia': Decimal(str(ganancia)),
            'fecha': fecha_utc
        })
        
        # Descontar stock
        response = tabla_productos.get_item(
            Key={'id_del_dueno': str(id_dueno), 'producto_id': str(producto_id)}
        )
        if 'Item' in response:
            nuevo_stock = response['Item']['stock'] - int(cantidad)
            actualizar_producto(producto_id, response['Item']['precio_venta'], nuevo_stock)
            
        return True
    except Exception as e:
        st.error(f"Error en venta: {e}")
        return False

def actualizar_producto(producto_id, nuevo_precio, nuevo_stock):
    try:
        id_dueno = st.session_state.user_data['usuario_id']  
        tabla_productos.update_item(
            Key={
                'id_del_dueno': str(id_dueno),
                'producto_id': str(producto_id), 
            },
            UpdateExpression="SET precio_venta = :p, stock = :s",
            ExpressionAttributeValues={
                ':p': Decimal(str(nuevo_precio)),
                ':s': int(nuevo_stock)
            }
        )
        return True
    except Exception as e:
        st.error(f"Error actualizando: {e}")
        return False

# ======= 4. PANTALLA LOGIN =======
def mostrar_login():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #1e3a8a 0%, #312e81 100%);
        font-family: 'Inter', sans-serif;
    }
    
    header, .stDeployButton {display: none;}
    
    .header-box {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        padding: 28px 20px;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 10px 30px rgba(37, 99, 235, 0.4);
    }
    
    .header-box h1 {
        color: white;
        font-size: 42px;
        font-weight: 700;
        margin: 0;
    }
    
    .feature-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        margin: 20px 0;
    }
    
    .feature-card {
        padding: 20px 14px;
        border-radius: 14px;
        text-align: center;
        color: white;
        border: 2px solid rgba(255,255,255,0.2);
    }
    
    .card-1 { background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); }
    .card-2 { background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%); }
    .card-3 { background: linear-gradient(135deg, #059669 0%, #047857 100%); }
    .card-4 { background: linear-gradient(135deg, #d97706 0%, #b45309 100%); }
    
    .btn-free {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        padding: 18px;
        border-radius: 14px;
        text-align: center;
        color: white;
        font-weight: 700;
        font-size: 18px;
        margin: 20px 0;
    }
    
    div.login-box {
        background: #ffffff !important;
        padding: 2rem !important;
        border-radius: 15px !important;
        margin: 2rem auto !important;
        max-width: 400px !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3) !important;
    }       
    
    .login-title {
        text-align: center;
        color: #1e3a8a;
        margin: 0 0 20px 0;
        font-size: 26px;
        font-weight: 700;
    }
    
    .stTextInput input {
        background: #f8fafc;
        border: 2px solid #e2e8f0;
        border-radius: 10px;
    }
    
    .stButton button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 14px;
        font-weight: 700;
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # HEADER AZUL
    st.markdown("""
    <div class='header-box'>
        <h1>⚡ NEXUS</h1>
        <p style='color:rgba(255,255,255,0.95); margin:8px 0 0 0;'>Sistema de Gestión para Negocios</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<h3 style='text-align:center; color:white; font-size:21px; margin:20px 0;'>¿Cansado de perder plata en tu negocio?</h3>", unsafe_allow_html=True)
    
        # TARJETAS
    st.markdown("""
    <div class='feature-grid'>
        <div class='feature-card card-1'>
            <div style='font-size:32px;'>📦</div>
            <h3>Control Total</h3>
            <p>Sabes qué vendes y qué te falta.</p>
        </div>
        <div class='feature-card card-2'>
            <div style='font-size:32px;'>💰</div>
            <h3>Más Ganancia</h3>
            <p>Ve tus productos que más plata te dejan.</p>
        </div>
        <div class='feature-card card-3'>
            <div style='font-size:32px;'>📱</div>
            <h3>Desde tu Celular</h3>
            <p>Sin computadoras. Solo tu WhatsApp.</p>
        </div>
        <div class='feature-card card-4'>
            <div style='font-size:32px;'>⚡</div>
            <h3>Súper Barato</h3>
            <p>S/30 al mes. Otros cobran S/250.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='btn-free'>🎁 Prueba 7 DÍAS GRATIS<br><span style='font-size:14px;'>Sin tarjeta. Sin compromiso.</span></div>", unsafe_allow_html=True)

# ====== APP PRINCIPAL ======
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_data = {}

if not st.session_state.logged_in:
    # LOGIN BOX - ABRE AQUÍ
    st.markdown("<div class='login-box'><h2 class='login-title'>Iniciar Sesión</h2>", unsafe_allow_html=True)

    usuario = st.text_input("Usuario o DNI", placeholder="Ingresa tu usuario", label_visibility="collapsed")
    password = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña", label_visibility="collapsed")

    if st.button("Iniciar Sesión", use_container_width=True):
        user = login(usuario, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_data = user
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()  # Para que no cargue el resto
else:
    # AQUÍ VA TU APP CUANDO YA INICIÓ SESIÓN
    with st.sidebar:
        user = st.session_state.user_data
        st.markdown(f"### {user.get('nombre_negocio', 'NEXUS')}")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_data = {}
            st.rerun()
    
    # ...tu código de Productos, Ventas, Reportes
    
    st.write("Bienvenido a NEXUS")
    menu = st.sidebar.selectbox("Menú", ["Productos", "Ventas", "Reportes"])

    # Página Productos
    if menu == "Productos":
        st.title("📦 Productos")
        productos = obtener_productos()

        with st.expander("➕ Nuevo Producto"):
            nombre = st.text_input("Nombre")
            precio_compra = st.number_input("Precio Compra S/", min_value=0.0, step=0.1)
            precio_venta = st.number_input("Precio Venta S/", min_value=0.0, step=0.1)
            stock = st.number_input("Stock", min_value=0, step=1)
    
            rubro_usuario = user.get('rubro', 'General')
            categorias_disponibles = CATEGORIAS_POR_RUBRO.get(rubro_usuario, ['General'])
            categoria = st.selectbox("Categoría", categorias_disponibles)
    
            if st.button("Guardar"):
                if agregar_producto(nombre, precio_venta, precio_compra, stock, categoria):
                    st.success("Producto guardado!")
                    st.rerun()

        if productos:
            df = pd.DataFrame(productos)
            st.dataframe(df[['nombre', 'precio_venta', 'stock', 'categoria']], use_container_width=True)
        else:
            st.info("No hay productos. Agrega el primero.")

    # Página Ventas
    elif menu == "Ventas":
        st.title("🛒 Ventas")
        
        productos = obtener_productos()
        
        if not productos:
            st.warning("No tienes productos. Agrega productos primero en la pestaña Productos.")
        else:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("Seleccionar Productos")
                for prod in productos:
                    if prod['stock'] > 0:
                        col_a, col_b, col_c = st.columns([3, 1, 1])
                        with col_a:
                            st.write(f"**{prod['nombre']}** - Venta: S/{float(prod['precio_venta']):.2f} - Compra: S/{float(prod['precio_compra']):.2f} - Stock: {prod['stock']}")
                        with col_b:
                            qty = st.number_input("Cant", min_value=0, max_value=int(prod['stock']), 
                                                  key=f"qty_{prod['producto_id']}")
                        with col_c:
                            if st.button("Agregar", key=f"add_{prod['producto_id']}"):
                                if qty > 0:
                                    encontrado = False
                                    for item in st.session_state.carrito:
                                        if item['producto_id'] == prod['producto_id']:
                                            item['cantidad'] += qty
                                            encontrado = True
                                            break
                                    if not encontrado:
                                        st.session_state.carrito.append({
                                            'producto_id': prod['producto_id'],
                                            'nombre': prod['nombre'],
                                            'precio_venta': float(prod['precio_venta']),
                                            'precio_compra': float(prod['precio_compra']),
                                            'cantidad': qty
                                        })
                                    st.success(f"Agregado {qty} x {prod['nombre']}")
                                    st.rerun()
            
            with col2:
                st.subheader("Carrito")
                if 'carrito' not in st.session_state:
                    st.session_state.carrito = []
                    
                if st.session_state.carrito:
                    total_venta = 0
                    total_costo = 0
                    for item in st.session_state.carrito:
                        subtotal_venta = float(item['precio_venta']) * int(item['cantidad'])
                        subtotal_costo = float(item['precio_compra']) * int(item['cantidad'])
                        total_venta += subtotal_venta
                        total_costo += subtotal_costo
                        ganancia = subtotal_venta - subtotal_costo
                        st.write(f"{item['cantidad']}x {item['nombre']} = S/{subtotal_venta:.2f}")
                        st.caption(f"Ganancia: S/{ganancia:.2f}")
                    
                    st.markdown(f"### Total Venta: S/{total_venta:.2f}")
                    st.markdown(f"### Ganancia: S/{total_venta - total_costo:.2f}")
                    
                    if st.button("Finalizar Venta", type="primary", use_container_width=True):
                        ok = True
                        for item in st.session_state.carrito:
                            if not registrar_venta(item['producto_id'], item['cantidad'], 
                                                   item['precio_venta'], item['precio_compra']):
                                ok = False
                                break
                        if ok:
                            st.session_state.carrito = []
                            st.success("✅ Venta registrada")
                            st.balloons()
                            st.rerun()
                    
                    if st.button("Vaciar Carrito", use_container_width=True):
                        st.session_state.carrito = []
                        st.rerun()
                else:
                    st.info("Carrito vacío")

    # Página Reportes
    elif menu == "Reportes":
        st.title("📊 Reportes")
        st.info("Aquí van tus reportes")
        
        ventas = obtener_ventas()
        productos = obtener_productos()
        productos_dict = {p['producto_id']: p['nombre'] for p in productos}
        
        if not ventas:
            st.info("Aún no tienes ventas registradas.")
        else:
            hoy = datetime.now(timezone.utc).date()
            ventas_hoy = []
            
            for v in ventas:
                v['nombre_producto'] = productos_dict.get(v['producto_id'], 'Producto eliminado')
                fecha_venta = datetime.fromisoformat(v['fecha']).date()
                if fecha_venta == hoy:
                    ventas_hoy.append(v)
            
            # Métricas del día
            if ventas_hoy:
                total_venta_hoy = sum(float(v['total_venta']) for v in ventas_hoy)
                total_costo_hoy = sum(float(v['total_costo']) for v in ventas_hoy)
                ganancia_hoy = total_venta_hoy - total_costo_hoy
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Ventas Hoy", len(ventas_hoy))
                with col2:
                    st.metric("Ingresos", f"S/{total_venta_hoy:.2f}")
                with col3:
                    st.metric("Costo", f"S/{total_costo_hoy:.2f}")
                with col4:
                    st.metric("Ganancia Real", f"S/{ganancia_hoy:.2f}")
                
                st.markdown("---")
                
                # Tabla de hoy
                st.subheader("Ventas de Hoy")
                df_hoy = pd.DataFrame(ventas_hoy)
                df_hoy['fecha'] = pd.to_datetime(df_hoy['fecha']).dt.strftime('%H:%M:%S')
                st.dataframe(
                    df_hoy[['fecha', 'nombre_producto', 'cantidad', 'total_venta', 'ganancia']], 
                    use_container_width=True,
                    column_config={
                        "fecha": "Hora",
                        "nombre_producto": "Producto",
                        "cantidad": "Cant",
                        "total_venta": st.column_config.NumberColumn("Total Venta", format="S/%.2f"),
                        "ganancia": st.column_config.NumberColumn("Ganancia", format="S/%.2f")
                    }
                )
            else:
                st.info("No hay ventas hoy aún.")
                st.metric("Ganancia Real Hoy", "S/0.00")
            
            # Historial completo
            with st.expander("Ver historial completo"):
                df_all = pd.DataFrame(ventas)
                df_all['nombre_producto'] = df_all['producto_id'].map(productos_dict).fillna('Producto eliminado')
                df_all['fecha'] = pd.to_datetime(df_all['fecha']).dt.strftime('%d/%m %H:%M')
                st.dataframe(
                    df_all[['fecha', 'nombre_producto', 'cantidad', 'total_venta', 'total_costo', 'ganancia']], 
                    use_container_width=True,
                    column_config={
                        "fecha": "Fecha/Hora",
                        "nombre_producto": "Producto",
                        "cantidad": "Cant",
                        "total_venta": st.column_config.NumberColumn("Venta S/", format="S/%.2f"),
                        "total_costo": st.column_config.NumberColumn("Costo S/", format="S/%.2f"),
                        "ganancia": st.column_config.NumberColumn("Ganancia S/", format="S/%.2f")
                    }
                )
