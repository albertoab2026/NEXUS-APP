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
        
# Cambia la definición de la función así:
def registrar_venta(producto_id, cantidad, precio_venta, precio_compra, pago):
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
            'fecha': fecha_utc,
            'pago': pago  # <--- AGREGA ESTA LÍNEA AQUÍ
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

# --- PÁGINA VENTAS (Diseño Estilo SaaS Comercial) ---
elif menu == "Ventas":
    st.title("🛒 Terminal de Ventas (POS Premium)")
    
    productos = obtener_productos()
    tenant_actual = st.session_state.get('tenant_id', 'MI LOCAL')
    
    if not productos:
        st.info("💡 Aún no hay productos registrados en el inventario. Agrega algunos en la pestaña Productos.")
    else:
        if "carrito" not in st.session_state:
            st.session_state.carrito = []
        if "buscar_ventas" not in st.session_state:
            st.session_state["buscar_ventas"] = ""
        if "ultima_venta" not in st.session_state:
            st.session_state.ultima_venta = None

        categorias_disponibles = sorted(list(set(prod.get('categoria', 'General') for prod in productos)))
        opciones_categoria = ["📁 Todas las Categorías"] + [f"🏷️ {cat}" for cat in categorias_disponibles]
        
        c_busq, c_cat = st.columns([2, 1])
        with c_busq:
            busqueda_v = st.text_input("🔍 Buscar producto por nombre:", value=st.session_state["buscar_ventas"], key="input_buscar_ventas")
        with c_cat:
            categoria_seleccionada = st.selectbox("Filtrar por Categoría:", opciones_categoria)

        productos_mostrar = productos
        if busqueda_v.strip() != "":
            productos_mostrar = [p for p in productos_mostrar if busqueda_v.lower() in p.get('nombre', '').lower()]
        if categoria_seleccionada != "📁 Todas las Categorías":
            cat_pura = categoria_seleccionada.replace("🏷️ ", "")
            productos_mostrar = [p for p in productos_mostrar if p.get('categoria', 'General') == cat_pura]

        col_productos, col_carrito = st.columns([1.2, 1.0])
        
        with col_productos:
            st.markdown("### 📦 Catálogo")
            if not productos_mostrar:
                st.error("❌ No se encontraron productos en este filtro.")
            else:
                st.markdown("---")
                with st.container(height=500, border=False):
                    for prod in productos_mostrar:
                        p_id = prod.get('producto_id', 'S/I')
                        p_nombre = prod.get('nombre', 'Producto sin nombre')
                        p_precio_venta = float(prod.get('precio_venta', 0.0))
                        p_precio_compra = float(prod.get('precio_compra', 0.0))
                        
                        cantidad_en_carrito = sum(int(item['cantidad']) for item in st.session_state.carrito if item['producto_id'] == p_id)
                        p_stock_real = int(prod.get('stock', 0))
                        p_stock_disponible = p_stock_real - cantidad_en_carrito
                        
                        with st.container(border=True):
                            c_info, c_cant, c_btn = st.columns([2.1, 1.1, 1.2])
                            with c_info:
                                st.markdown(f"**{p_nombre}**")
                                if p_stock_disponible <= 0:
                                    st.markdown(f"🔴 **Agotado** · <span style='color:gray;'>S/{p_precio_venta:.2f}</span>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"🟢 **Stock: {p_stock_disponible}** · **S/{p_precio_venta:.2f}**", unsafe_allow_html=True)
                            
                            with c_cant:
                                qty = st.number_input("Cant", min_value=0, max_value=max(0, p_stock_disponible), key=f"qty_{p_id}", label_visibility="collapsed")
                            
                            with c_btn:
                                es_invalido = p_stock_disponible <= 0
                                def agregar_al_carrito_saas(id_p, nom_p, pre_v, pre_c, cant_solicitada, stock_r):
                                    if cant_solicitada > 0:
                                        existe = False
                                        for item in st.session_state.carrito:
                                            if item['producto_id'] == id_p:
                                                item['cantidad'] = int(item['cantidad']) + cant_solicitada
                                                existe = True
                                                break
                                        if not existe:
                                            st.session_state.carrito.append({
                                                'producto_id': id_p, 'nombre': nom_p, 'precio_venta': pre_v,
                                                'precio_compra': pre_c, 'cantidad': cant_solicitada, 'stock_max': stock_r
                                            })
                                        st.session_state["buscar_ventas"] = ""

                                st.button("🛒 Añadir", key=f"btn_saas_{p_id}", use_container_width=True, disabled=es_invalido, on_click=agregar_al_carrito_saas, args=(p_id, p_nombre, p_precio_venta, p_precio_compra, qty, p_stock_real))

        with col_carrito:
            st.markdown("### 🧾 Resumen de Pedido")
            if st.session_state.carrito:
                total_venta_bruto = 0
                for item in st.session_state.carrito:
                    total_venta_bruto += float(item['precio_venta']) * int(item['cantidad'])
                
                descuento = st.number_input("🎁 Aplicar Descuento (S/):", min_value=0.0, value=0.0, step=0.50, key="desc_global")
                total_venta_neto = round(total_venta_bruto - descuento, 2)

                st.markdown(f"### Total: S/{total_venta_neto:.2f}")
                metodo_pago = st.radio("Forma de Pago:", ["💵 Efectivo", "📱 Yape", "💳 Plin"], horizontal=True)
                
                w_cliente_nombre = st.text_input("Nombre Cliente:")
                w_cliente_celular = st.text_input("Celular:")

                if st.button("⚡ Finalizar y Registrar Venta", type="primary", use_container_width=True):
                    ok = True
                    items_guardar = [item.copy() for item in st.session_state.carrito]
                    
                    for item in st.session_state.carrito:
                        try:
                            res = registrar_venta(
                                producto_id=item['producto_id'],
                                cantidad=int(item['cantidad']),
                                precio_venta=float(item['precio_venta']),
                                precio_compra=float(item['precio_compra']),
                                pago=metodo_pago
                            )
                            if res is False:
                                ok = False
                                break
                        except Exception as e:
                            st.error(f"Error: {e}")
                            ok = False
                            break

                    if ok:
                        st.session_state.carrito = []
                        st.success("🎉 Venta procesada con éxito.")
                        st.rerun()

        # =====================================================================
        # 🏢 SECCIÓN: COMPROBANTE DIGITAL AUTO-GENERADO CON DESCUENTO REFLEJADO
        # =====================================================================
        if st.session_state.ultima_venta is not None:
            st.markdown("---")
            st.markdown("### 📄 Último Comprobante Generado")
            
            uv = st.session_state.ultima_venta
            
            # Formateamos las líneas de productos para el texto plano de WhatsApp
            lineas_productos = ""
            total_sin_descuento = 0
            for it in uv["items"]:
                subtotal_item = int(it['cantidad']) * float(it['precio_venta'])
                total_sin_descuento += subtotal_item
                lineas_productos += f"{it['cantidad']}x {it['nombre']} (S/{float(it['precio_venta']):.2f}) - S/{subtotal_item:.2f}\n"
            
            # Texto estructurado para WhatsApp con el descuento visible
            texto_whatsapp = (
                f"=== COMPROBANTE DE COMPRA ===\n"
                f"🏪 Comercio: {uv['tenant']}\n"
                f"📅 Fecha: {uv['fecha']}\n"
                f"👤 Cliente: {uv['cliente_nom']}\n"
                f"-----------------------------------------\n"
                f"{lineas_productos}"
                f"-----------------------------------------\n"
                f"💰 Subtotal: S/{total_sin_descuento:.2f}\n"
                f"🎁 Descuento Aplicado: -S/{float(uv['descuento']):.2f}\n"
                f"💵 TOTAL PAGADO: S/{uv['total']:.2f}\n"
                f"💳 Medio de Pago: {uv['pago']}\n\n"
                f"¡Gracias por su preferencia! ✨"
            )

            # Estructura del HTML del Ticket Térmico con el Nombre Comercial Dinámico
            html_ticket = f"""
            <div id="ticket-saas-print" style="width: 280px; background-color: white; color: black; padding: 15px; font-family: 'Courier New', Courier, monospace; font-size: 12px; border: 1px dashed #000; margin: 0 auto;">
                <div style="text-align: center; font-weight: bold; font-size: 14px; margin-bottom: 5px; text-transform: uppercase;">{uv['tenant']}</div>
                <div style="text-align: center; margin-bottom: 10px;">*** COMPROBANTE DE COMPRA ***<br><small style="font-size:10px;">Control Interno Comercial</small></div>
                <p style="margin: 3px 0;"><b>Fecha:</b> {uv['fecha']}</p>
                <p style="margin: 3px 0;"><b>Cliente:</b> {uv['cliente_nom']}</p>
                <div style="border-bottom: 1px dashed black; margin: 8px 0;"></div>
                <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
            """
            for it in uv["items"]:
                subt = int(it['cantidad']) * float(it['precio_venta'])
                html_ticket += f"""
                <tr>
                    <td style="padding: 2px 0;">{it['cantidad']}x {it['nombre']}</td>
                    <td style="text-align: right; padding: 2px 0;">S/{subt:.2f}</td>
                </tr>
                """
            html_ticket += f"""
                </table>
                <div style="border-bottom: 1px dashed black; margin: 8px 0;"></div>
                <div style="display: table; width: 100%;">
                    <div style="display: table-row;">
                        <div style="display: table-cell; padding: 2px 0;">Subtotal:</div>
                        <div style="display: table-cell; text-align: right; padding: 2px 0;">S/{total_sin_descuento:.2f}</div>
                    </div>
                    <div style="display: table-row; color: #c0392b;">
                        <div style="display: table-cell; padding: 2px 0; font-weight: bold;">🎁 Descuento:</div>
                        <div style="display: table-cell; text-align: right; padding: 2px 0; font-weight: bold;">-S/{float(uv['descuento']):.2f}</div>
                    </div>
                    <div style="display: table-row; font-size: 14px; font-weight: bold;">
                        <div style="display: table-cell; padding-top: 8px;">TOTAL COBRADO:</div>
                        <div style="display: table-cell; text-align: right; padding-top: 8px; font-size: 15px;">S/{uv['total']:.2f}</div>
                    </div>
                </div>
                <div style="border-bottom: 1px dashed black; margin: 8px 0;"></div>
                <p style="margin: 3px 0; text-align: center;"><b>Forma de Pago:</b> {uv['pago']}</p>
                <div style="text-align: center; margin-top: 15px; font-weight: bold;">¡GRACIAS POR SU COMPRA!</div>
            </div>
            """
            
            # Renderizamos el Comprobante en la pantalla
            col_comp, col_acciones = st.columns([1.1, 1.0])
            with col_comp:
                st.markdown("<div style='background-color:#f9f9f9; padding:10px; border-radius:5px;'>", unsafe_allow_html=True)
                st.html(html_ticket)
                st.markdown("</div>", unsafe_allow_html=True)
                
            with col_acciones:
                st.markdown("#### ⚡ Acciones del Comprobante")
                
                # Botón de impresión física (JavaScript)
                js_print = """
                <button onclick="var w = window.open(); w.document.write(document.getElementById('ticket-saas-print').outerHTML); w.document.close(); w.focus(); setTimeout(function(){w.print(); w.close();}, 500);" 
                style="width: 100%; background-color: #34495e; color: white; border: none; padding: 10px; font-weight: bold; border-radius: 5px; cursor: pointer; margin-bottom: 10px;">
                    🖨️ Imprimir Formato Ticket (80mm)
                </button>
                """
                st.components.v1.html(js_print, height=50)
                
                # Enlace de WhatsApp dinámico
                import urllib.parse
                texto_url = urllib.parse.quote(texto_whatsapp)
                
                if uv["cliente_cel"] != "":
                    url_wa = f"https://wa.me/51{uv['cliente_cel']}?text={texto_url}"
                else:
                    url_wa = f"https://wa.me/?text={texto_url}"
                    
                st.markdown(f"""
                <a href="{url_wa}" target="_blank" style="text-decoration: none;">
                    <button style="width: 100%; background-color: #25d366; color: white; border: none; padding: 10px; font-weight: bold; border-radius: 5px; cursor: pointer; margin-bottom: 10px;">
                        📱 Enviar por WhatsApp Digital
                    </button>
                </a>
                """, unsafe_allow_html=True)
                
                # Botón de descarga de datos rápidos
                import pandas as pd
                df_items = pd.DataFrame([{
                    "Producto": it["nombre"],
                    "Cantidad": it["cantidad"],
                    "Precio Unitario": float(it["precio_venta"]),
                    "Total Item": int(it["cantidad"]) * float(it["precio_venta"])
                } for it in uv["items"]])
                
                csv_data = df_items.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📊 Descargar Detalle en Excel (CSV)",
                    data=csv_data,
                    file_name=f"ticket_{uv['fecha'].replace(' ', '_').replace(':', '-')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                if st.button("Limpiar y Nueva Venta", use_container_width=True):
                    st.session_state.ultima_venta = None
                    st.rerun()
                    
# --- PÁGINA REPORTES (Versión Comercial Blindada de Costo Cero) ---
elif menu == "Reportes":
    st.title("📊 Centro de Analítica - NEXUS")
    
    ventas_raw = obtener_ventas()
    productos_raw = obtener_productos()
    
    if not ventas_raw:
        st.info("💡 No hay ventas registradas.")
    else:
        import pandas as pd
        df = pd.DataFrame(ventas_raw)
        
        # 1. Asegurar formato de fecha
        df['fecha_dt'] = pd.to_datetime(df['fecha']).dt.tz_localize(None) - pd.Timedelta(hours=5)
        df['Fecha_Corta'] = df['fecha_dt'].dt.date
        df['Hora'] = df['fecha_dt'].dt.strftime('%H:%M:%S')
        
        fecha_busqueda = st.date_input("Selecciona el día:")
        df_filtrado = df[df['Fecha_Corta'] == fecha_busqueda].copy()
        
        if df_filtrado.empty:
            st.warning(f"No hay ventas para {fecha_busqueda}.")
        else:
            # 2. Mapeo de productos
            mapa_productos = {p['producto_id']: p['nombre'] for p in productos_raw} if productos_raw else {}
            df_filtrado['Producto'] = df_filtrado['producto_id'].map(mapa_productos).fillna(df_filtrado['producto_id'])
            
            # 3. Gestión de pagos (Lógica preventiva)
            # Como el campo no existe en tu BD, asignamos 'Efectivo' por defecto hasta que lo implementes
            if 'pago' in df_filtrado.columns:
                df_filtrado['pago_norm'] = df_filtrado['pago'].astype(str).str.lower()
            else:
                df_filtrado['pago_norm'] = 'efectivo' # Placeholder hasta que envíes el campo real
            
            # 4. Cálculos financieros
            df_filtrado['total_venta'] = pd.to_numeric(df_filtrado['total_venta'], errors='coerce').fillna(0)
            yape = df_filtrado[df_filtrado['pago_norm'] == 'yape']['total_venta'].sum()
            plin = df_filtrado[df_filtrado['pago_norm'] == 'plin']['total_venta'].sum()
            efectivo = df_filtrado[df_filtrado['pago_norm'] == 'efectivo']['total_venta'].sum()
            
            # 5. Visualización estable
            st.markdown("### 💵 Distribución de Caja")
            c1, c2, c3 = st.columns(3)
            c1.metric("💵 Efectivo", f"S/{efectivo:.2f}")
            c2.metric("📱 Yape", f"S/{yape:.2f}")
            c3.metric("🔮 Plin", f"S/{plin:.2f}")
            
            st.dataframe(df_filtrado[['Hora', 'Producto', 'cantidad', 'total_venta', 'pago_norm']], use_container_width=True)
