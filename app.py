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
    "Otro": ["General"]
}

# Session state seguro
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_data' not in st.session_state:
    st.session_state.user_data = {}
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# CSS Global Limpio
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #0F172A; color: #E2E8F0; }
.stButton>button { background: #6366F1; border: none; color: white; border-radius: 8px; font-weight: 500; }
.stButton>button:hover { background: #4F46E5; }
.stDataFrame, [data-testid="stContainer"] { background: #1E293B; border-radius: 8px; border: 1px solid #334155; }
.stTextInput>div>div>input { background: #1E293B; border: 1px solid #334155; color: #E2E8F0; border-radius: 6px; }
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
        tabla_usuarios.put_item(Item={
            'usuario_id': usuario_id, 'id_del_dueno': usuario_id,
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

def obtener_ventas():
    try:
        id_dueno = st.session_state.user_data['usuario_id']
        response = tabla_ventas.query(KeyConditionExpression=Key('usuario_id').eq(id_dueno))
        return response.get('Items', [])
    except Exception as e:
        st.error(f"Error cargando ventas: {e}")
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
        
        response = tabla_productos.get_item(Key={'id_del_dueno': str(id_dueno), 'producto_id': str(producto_id)})
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
            Key={'id_del_dueno': str(id_dueno), 'producto_id': str(producto_id)},
            UpdateExpression="SET precio_venta = :p, stock = :s",
            ExpressionAttributeValues={':p': Decimal(str(nuevo_precio)), ':s': int(nuevo_stock)}
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
        st.error(f"Error al eliminar en la base de datos: {e}")
        return False

# ======= 4. PANTALLA LOGIN =======
def mostrar_login():
    st.markdown("""
    <style>
    /* Asegura que el fondo cubra absolutamente toda la pantalla del celular */
    .stApp { 
        background: linear-gradient(135deg, #0F172A 0%, #020617 100%) !important; 
        min-height: 100vh !important;
    }
    header, .stDeployButton { display: none !important; }
    
    .header-box {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        padding: 24px; border-radius: 16px; text-align: center; margin-bottom: 25px;
        box-shadow: 0 10px 25px rgba(37, 99, 235, 0.2);
    }
    .header-box h1 { color: white !important; font-size: 38px; font-weight: 700; margin: 0; }
    .header-box p { color: rgba(255,255,255,0.9); font-size: 15px; margin: 6px 0 0 0; }
    
    .feature-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 20px 0; }
    
    /* CORRECCIÓN: Textos siempre blancos y legibles en las tarjetas */
    .feature-card { 
        padding: 16px 12px; border-radius: 12px; text-align: center; 
        color: #FFFFFF !important; border: 1px solid rgba(255,255,255,0.05); 
    }
    .feature-card h3 { font-size: 15px; font-weight: 700; margin: 4px 0; color: #FFFFFF !important; }
    .feature-card p { font-size: 12px; margin: 0; color: rgba(255,255,255,0.85) !important; }
    
    .card-1 { background: #1E3A8A; }
    .card-2 { background: #7F1D1D; }
    .card-3 { background: #064E3B; }
    .card-4 { background: #78350F; }
    
    .btn-free {
        background: linear-gradient(135deg, #D97706 0%, #B45309 100%); padding: 14px;
        border-radius: 12px; text-align: center; color: white; font-weight: 700; font-size: 16px; margin: 15px 0;
    }
    
    .clean-login {
        background: #1E293B; padding: 25px; border-radius: 16px;
        border: 1px solid #334155; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .clean-title { text-align: center; color: #F8FAFC; margin-bottom: 20px; font-weight: 700; font-size: 24px; }
    </style>
    """, unsafe_allow_html=True)

    
    st.markdown("<div class='header-box'><h1>⚡ NEXUS</h1><p>Sistema de Gestión para Negocios</p></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        st.markdown("<div class='clean-login'><h2 class='clean-title'>Iniciar Sesión</h2>", unsafe_allow_html=True)
        usuario_input = st.text_input("Usuario o DNI", placeholder="Ej: 71234567", key="login_user")
        password_input = st.text_input("Contraseña", type="password", placeholder="••••••••", key="login_pass")
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("Ingresar al Sistema", use_container_width=True):
            if usuario_input and password_input:
                user_validado = login(usuario_input, password_input)
                if user_validado:
                    st.session_state.logged_in = True
                    st.session_state.user_data = user_validado
                    st.rerun()
                else:
                    st.error("❌ Credenciales inválidas o cuenta inactiva")
            else:
                st.error("⚠️ Llena ambos campos")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<h3 style='text-align:center; color:#94A3B8; font-size:18px; margin:30px 0 10px 0;'>¿Cansado de perder plata en tu cuaderno?</h3>", unsafe_allow_html=True)
    
    st.markdown("""
    <div class='feature-grid'>
        <div class='feature-card card-1'><div>📦</div><h3>Control Total</h3><p>Sabes qué vendes y qué falta en tiempo real.</p></div>
        <div class='feature-card card-2'><div>💰</div><h3>Más Ganancia</h3><p>Mira al instante qué productos te dejan más plata.</p></div>
        <div class='feature-card card-3'><div>📱</div><h3>Desde tu Celular</h3><p>Diseñado para usarse rápido en pantallas móviles.</p></div>
        <div class='feature-card card-4'><div>⚡</div><h3>Súper Económico</h3><p>Solo S/30 al mes. Sin contratos complicados.</p></div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='btn-free'>🎁 Prueba 7 DÍAS GRATIS<br><span style='font-size:13px; font-weight:400;'>Regístrate con tu asesor. Sin compromisos.</span></div>", unsafe_allow_html=True)

# ======= 5. CONTROL DE FLUJO =======
if not st.session_state.logged_in:
    mostrar_login()
    st.stop()

# ======= 6. APP PRINCIPAL =======
user = st.session_state.user_data

with st.sidebar:
    st.markdown(f"### 🏢 {user.get('nombre_negocio', 'NEXUS')}")
    st.markdown(f"**Plan:** {user.get('plan', 'trial').upper()}")
    st.markdown("---")
    menu = st.sidebar.selectbox("Menú", ["Productos", "Ventas", "Reportes"])
    st.markdown("---")
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_data = {}
        st.session_state.carrito = []
        st.rerun()

# --- PÁGINA PRODUCTOS ---
if menu == "Productos":
    st.title("📦 Productos")
    productos = obtener_productos()

    with st.expander("➕ Nuevo Producto"):
        nombre = st.text_input("Nombre")
        precio_compra = st.number_input("Precio Compra S/", min_value=0.0, step=0.1)
        precio_venta = st.number_input("Precio Venta S/", min_value=0.0, step=0.1)
        stock = st.number_input("Stock", min_value=0, step=1)
        
        categoria_input = st.text_input("Categoría (Ej: Bebidas, Limpieza, Farmacia)", value="General")
        categoria = categoria_input.strip() if categoria_input.strip() else "General"

    if st.button("Guardar"):
        if nombre and agregar_producto(nombre, precio_venta, precio_compra, stock, categoria):
            st.success("¡Producto guardado!")
            st.rerun()

    # --- BLOQUE BLINDADO DE PRODUCTOS ---
    if productos:
        # 🔍 BUSCADOR EN TIEMPO REAL
        busqueda_p = st.text_input("🔍 Buscar producto por nombre:", key="buscar_inventario")
        
        # Filtramos la lista original según lo que escriba el usuario
        productos_filtrados = [
            p for p in productos 
            if busqueda_p.lower() in p.get('nombre', '').lower()
        ]

        productos_limpios = []
        for p in productos_filtrados:
            p_limpio = {
                'producto_id': p.get('producto_id', 'S/I'),
                'nombre': p.get('nombre', 'Producto sin nombre'),
                'precio_compra': float(p.get('precio_compra', 0.0)),
                'precio_venta': float(p.get('precio_venta', 0.0)),
                'stock': int(p.get('stock', 0)),
                'categoria': p.get('categoria', 'General')
            }
            productos_limpios.append(p_limpio)

        st.markdown("---")
        st.subheader("🗑️ Control de Inventario")
        
        for p in productos_limpios:
            p_id = p['producto_id']
            p_nombre = p['nombre']
            p_stock = p['stock']
            p_precio = p['precio_venta']
            p_cat = p['categoria']
            
            # Formato en columnas para que entre perfecto en pantallas móviles
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                st.write(f"**{p_nombre}** ({p_cat})  \nStock: `{p_stock}` | Precio: `S/{p_precio:.2f}`")
            with col_btn:
                # Cada botón tiene una llave única usando el ID del producto
                if st.button("🗑️", key=f"del_{p_id}"):
                    if eliminar_producto(p_id):
                        st.success(f"¡{p_nombre} eliminado!")
                        st.rerun()


    else:
        st.info("No hay productos. Agrega el primero.")

# --- PÁGINA VENTAS ---
elif menu == "Ventas":
    st.title("🛒 Ventas")
    productos = obtener_productos()

    if not productos:
        st.warning("No tienes productos. Agrega productos primero en la pestaña Productos.")
    else:
        col1, col2 = st.columns([1.8, 1.2])
        with col1:
            st.subheader("Seleccionar Productos")
            busqueda_v = st.text_input("🔍 Buscar producto por nombre:", key="buscar_ventas", placeholder="Escriba aquí para filtrar...")

            if busqueda_v.strip() == "":
                st.info("💡 Digite el nombre del producto arriba para empezar a vender.")
            else:
                productos_filtrados_v = [
                    prod for prod in productos
                    if busqueda_v.lower() in prod.get('nombre', '').lower()
                ]

                if not productos_filtrados_v:
                    st.error("❌ No se encontraron productos con ese nombre.")
                else:
                    for prod in productos_filtrados_v:
                        p_id = prod.get('producto_id', 'S/I')
                        p_nombre = prod.get('nombre', 'Producto sin nombre')
                        p_precio_venta = float(prod.get('precio_venta', 0.0))
                        p_precio_compra = float(prod.get('precio_compra', 0.0))
                        
                        # 🧠 Calculamos cuántas unidades de ESTE producto ya están en el carrito
                        cantidad_en_carrito = sum(int(item['cantidad']) for item in st.session_state.carrito if item['producto_id'] == p_id)
                        
                        p_stock_real = int(prod.get('stock', 0))
                        p_stock_disponible = p_stock_real - cantidad_en_carrito

                        if p_stock_real > 0:
                            col_a, col_b, col_c = st.columns([2.5, 1.2, 1.3])
                            with col_a:
                                if p_stock_disponible <= 0:
                                    st.write(f"**{p_nombre}**\nS/{p_precio_venta:.2f} | 🟡 Carrito Lleno")
                                else:
                                    st.write(f"**{p_nombre}**\nS/{p_precio_venta:.2f} | 🟢 Stock: {p_stock_disponible}")
                            with col_b:
                                qty = st.number_input("Cant", min_value=0, max_value=max(0, p_stock_disponible), key=f"qty_{p_id}", label_visibility="collapsed")
                            with col_c:
                                boton_bloqueado = p_stock_disponible <= 0
                                if st.button("Agregar", key=f"add_{p_id}", use_container_width=True, disabled=boton_bloqueado):
                                    if qty > 0:
                                        encontrado = False
                                        for item in st.session_state.carrito:
                                            if item['producto_id'] == p_id:
                                                item['cantidad'] = int(item['cantidad']) + qty
                                                encontrado = True
                                                break
                                        if not encontrado:
                                            st.session_state.carrito.append({
                                                'producto_id': p_id,
                                                'nombre': p_nombre,
                                                'precio_venta': p_precio_venta,
                                                'precio_compra': p_precio_compra,
                                                'cantidad': qty,
                                                'stock_max': p_stock_real
                                            })
                                        st.rerun()

        with col2:
            st.subheader("Carrito")
            if st.session_state.carrito:
                total_venta_bruto = 0
                total_costo = 0
                
                # Caja de scroll para listas gigantes
                with st.container(height=300):
                    for index, item in enumerate(st.session_state.carrito):
                        subtotal_venta = float(item['precio_venta']) * int(item['cantidad'])
                        subtotal_costo = float(item['precio_compra']) * int(item['cantidad'])
                        total_venta_bruto += subtotal_venta
                        total_costo += subtotal_costo
                        
                        c_prod, c_del = st.columns([3.8, 1.2])
                        with c_prod:
                            st.write(f"**({item['cantidad']})** {item['nombre']}\nS/{subtotal_venta:.2f}")
                        with c_del:
                            if st.button("🗑️", key=f"del_cart_{item['producto_id']}_{index}", type="secondary"):
                                st.session_state.carrito.pop(index)
                                st.rerun()

                st.markdown("---")
                
                descuento = st.number_input("🎁 Aplicar Descuento (S/):", min_value=0.0, max_value=total_venta_bruto, value=0.0, step=0.10, key="descuento_venta")
                
                total_venta_neto = round(total_venta_bruto - descuento, 2)
                ganancia_neta = round(total_venta_neto - total_costo, 2)

                st.markdown(f"### Total Venta: S/{total_venta_neto:.2f}")
                if descuento > 0:
                    st.caption(f"*(Precio original: S/{total_venta_bruto:.2f} | Ahorro: S/{descuento:.2f})*")
                st.markdown(f"### Ganancia: S/{ganancia_neta:.2f}")

                # Métodos de pago con círculos coloridos
                metodo_pago = st.radio(
                    "Forma de Pago:", 
                    ["💵 Efectivo", "🟣 Yape", "🔵 Plin"], 
                    horizontal=True
                )

                if st.button("Finalizar Venta", type="primary", use_container_width=True):
                    conteo_cantidades = {}
                    limites_stock = {}
                    
                    for item in st.session_state.carrito:
                        p_id = item['producto_id']
                        conteo_cantidades[p_id] = conteo_cantidades.get(p_id, 0) + int(item['cantidad'])
                        limites_stock[p_id] = (item['nombre'], int(item.get('stock_max', 9999)))
                    
                    stock_superado = False
                    for p_id, cant_total in conteo_cantidades.items():
                        nombre_p, s_max = limites_stock[p_id]
                        if cant_total > s_max:
                            st.error(f"❌ Stock insuficiente para '{nombre_p}'. Intentas vender {cant_total} unidades pero solo quedan {s_max} en stock.")
                            stock_superado = True
                    
                    if not stock_superado:
                        ok = True
                        factor_descuento = (total_venta_neto / total_venta_bruto) if total_venta_bruto > 0 else 1.0

                        for item in st.session_state.carrito:
                            sub_v_bruto = float(item['precio_venta']) * int(item['cantidad'])
                            total_v_item = round(sub_v_bruto * factor_descuento, 2)
                            total_c_item = round(float(item['precio_compra']) * int(item['cantidad']), 2)
                            ganancia_v_item = round(total_v_item - total_c_item, 2)

                            metodo_limpio = metodo_pago.split()[-1]

                            if not registrar_venta(
                                producto_id=item['producto_id'],
                                cantidad=int(item['cantidad']),
                                total_venta=total_v_item,
                                total_costo=total_c_item,
                                ganancia=ganancia_v_item,
                                metodo_pago=metodo_limpio
                            ):
                                ok = False
                                break

                        if ok:
                            st.session_state.carrito = []
                            st.success("✅ Venta registrada con éxito")
                            st.balloons()
                            st.rerun()

                if st.button("Vaciar Carrito", use_container_width=True):
                    st.session_state.carrito = []
                    st.rerun()
            else:
                st.info("Carrito vacío")
# --- PÁGINA REPORTES (Versión Comercial Blindada de Costo Cero) ---
elif menu == "Reportes":
    st.title("📊 Centro de Analítica - NEXUS")
    
    ventas_raw = obtener_ventas()  # QUERY eficiente a DynamoDB
    productos = obtener_productos()
    productos_dict = {p['producto_id']: p['nombre'] for p in productos}
    
    if not ventas_raw:
        st.info("🏪 Aún no tienes ventas registradas en el sistema.")
    else:
        # 1. BLINDAJE ABSOLUTO: Limpiamos y normalizamos cada registro antes de procesar
        ventas = []
        for v in ventas_raw:
            v_limpia = {
                'fecha': v.get('fecha', datetime.now(timezone.utc).isoformat()),
                'producto_id': v.get('producto_id', 'Desconocido'),
                'cantidad': int(v.get('cantidad', 0)),
                'total_venta': float(v.get('total_venta', 0.0)),
                'total_costo': float(v.get('total_costo', 0.0)),
                'ganancia': float(v.get('ganancia', 0.0)),
                'metodo_pago': str(v.get('metodo_pago', 'Efectivo')).strip().capitalize()
            }
            # Si el registro viejo no tenía ganancia calculada, la calculamos aquí en vivo
            if v_limpia['ganancia'] == 0.0 and v_limpia['total_venta'] > 0:
                v_limpia['ganancia'] = v_limpia['total_venta'] - v_limpia['total_costo']
                
            ventas.append(v_limpia)

        # Fechas clave para la comparación (Lunes con Lunes, etc.)
        hoy_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        hace_una_semana_str = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
        
        ventas_hoy = []
        ventas_hace_una_semana = []
        
        for v in ventas:
            v['nombre_producto'] = productos_dict.get(v['producto_id'], 'Producto eliminado')
            fecha_solo_v = v['fecha'].split('T')[0] if 'T' in v['fecha'] else v['fecha'][:10]
            
            if fecha_solo_v == hoy_str:
                ventas_hoy.append(v)
            elif fecha_solo_v == hace_una_semana_str:
                ventas_hace_una_semana.append(v)
        
        # --- CÁLCULOS DE HOY ---
        total_ingresos_hoy = sum(v['total_venta'] for v in ventas_hoy)
        total_costo_compra_hoy = sum(v['total_costo'] for v in ventas_hoy)
        ganancia_real_hoy = total_ingresos_hoy - total_costo_compra_hoy
        
        # Cajas separadas según el método de pago
        efectivo_hoy = sum(v['total_venta'] for v in ventas_hoy if v['metodo_pago'] == 'Efectivo')
        yape_hoy = sum(v['total_venta'] for v in ventas_hoy if v['metodo_pago'] == 'Yape')
        plin_hoy = sum(v['total_venta'] for v in ventas_hoy if v['metodo_pago'] == 'Plin')
        
        # --- CÁLCULOS DE COMPARACIÓN ---
        total_ingresos_pasado = sum(v['total_venta'] for v in ventas_hace_una_semana)
        
        porcentaje_cambio = 0.0
        delta_texto = "Primer día de registro"
        if total_ingresos_pasado > 0:
            porcentaje_cambio = ((total_ingresos_hoy - total_ingresos_pasado) / total_ingresos_pasado) * 100
            delta_texto = f"{porcentaje_cambio:+.1f}% vs misma fecha semana pasada"
        
        # --- INTERFAZ VISUAL PREMIUM ---
        st.subheader("📈 Rendimiento del Día")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if total_ingresos_pasado > 0:
                st.metric(label="Ingreso Total (Ventas)", value=f"S/{total_ingresos_hoy:.2f}", delta=delta_texto)
            else:
                st.metric(label="Ingreso Total (Ventas)", value=f"S/{total_ingresos_hoy:.2f}", delta="Sin datos previos")
                
        with col2:
            st.metric(label="Inversión (Costo de Compra)", value=f"S/{total_costo_compra_hoy:.2f}")
            
        with col3:
            st.metric(label="💰 GANANCIA REAL NETO", value=f"S/{ganancia_real_hoy:.2f}", help="Ingreso total de hoy menos el costo de compra.")
            
        st.markdown("---")
        st.subheader("💵 Distribución de Caja")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div style="background-color: #1E293B; padding: 15px; border-radius: 10px; border-left: 5px solid #10B981; text-align: center;"><p style="margin:0; color:#94A3B8; font-size:14px;">💵 Efectivo en Caja</p><h3 style="margin:5px 0 0 0; color:#F8FAFC; font-size:24px;">S/{efectivo_hoy:.2f}</h3></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div style="background-color: #1E293B; padding: 15px; border-radius: 10px; border-left: 5px solid #06B6D4; text-align: center;"><p style="margin:0; color:#94A3B8; font-size:14px;">📲 Total Yape</p><h3 style="margin:5px 0 0 0; color:#F8FAFC; font-size:24px;">S/{yape_hoy:.2f}</h3></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div style="background-color: #1E293B; padding: 15px; border-radius: 10px; border-left: 5px solid #6366F1; text-align: center;"><p style="margin:0; color:#94A3B8; font-size:14px;">🟣 Total Plin</p><h3 style="margin:5px 0 0 0; color:#F8FAFC; font-size:24px;">S/{plin_hoy:.2f}</h3></div>', unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("📋 Detalle de lo Vendido Hoy")
        if ventas_hoy:
            df_hoy = pd.DataFrame(ventas_hoy)
            df_hoy['hora'] = pd.to_datetime(df_hoy['fecha']).dt.strftime('%H:%M:%S')
            st.dataframe(
                df_hoy[['hora', 'nombre_producto', 'cantidad', 'metodo_pago', 'total_venta', 'ganancia']], 
                use_container_width=True,
                column_config={
                    "hora": "Hora", "nombre_producto": "Producto", "cantidad": "Cant", "metodo_pago": "Pago",
                    "total_venta": st.column_config.NumberColumn("Total Venta", format="S/%.2f"),
                    "ganancia": st.column_config.NumberColumn("Ganancia", format="S/%.2f")
                }
            )
        else:
            st.info("Aún no se han registrado ventas el día de hoy.")
            
        with st.expander("🗄️ Ver historial completo de auditoría"):
            df_all = pd.DataFrame(ventas)
            df_all['fecha_formato'] = pd.to_datetime(df_all['fecha']).dt.strftime('%d/%m %H:%M')
            st.dataframe(
                df_all[['fecha_formato', 'nombre_producto', 'cantidad', 'metodo_pago', 'total_venta', 'total_costo', 'ganancia']], 
                use_container_width=True,
                column_config={
                    "fecha_formato": "Fecha/Hora", "nombre_producto": "Producto", "cantidad": "Cant", "metodo_pago": "Método",
                    "total_venta": st.column_config.NumberColumn("Venta S/", format="S/%.2f"),
                    "total_costo": st.column_config.NumberColumn("Costo S/", format="S/%.2f"),
                    "ganancia": st.column_config.NumberColumn("Ganancia S/", format="S/%.2f")
                }
            )

