import streamlit as st
import boto3
from boto3.dynamodb.conditions import Key
import pandas as pd
import io
import time
import uuid
from datetime import datetime, timedelta, timezone
import hashlib
from decimal import Decimal
import urllib.parse
import plotly.express as px
import streamlit.components.v1 as components

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
if "buscar_ventas" not in st.session_state:
    st.session_state["buscar_ventas"] = ""
if "ultima_venta" not in st.session_state:
    st.session_state.ultima_venta = None

# ======= 1. CSS MAESTRO (TODO EN UNO) =======
st.markdown("""
<style>
   .stApp { background-color: #0F172A!important; }

   .header-container {
        background: linear-gradient(135deg, #1e3a8a, #1e293b)!important;
        padding: 30px!important;
        border-radius: 20px!important;
        border: 1px solid #334155!important;
        text-align: center!important;
        margin-bottom: 20px!important;
    }

   .regalo-bar {
        background: #F59E0B!important;
        color: #000!important;
        padding: 15px!important;
        border-radius: 12px!important;
        text-align: center!important;
        margin-bottom: 25px!important;
        font-weight: 800!important;
    }

   .feature-grid {
        display: grid!important;
        grid-template-columns: 1fr 1fr!important;
        gap: 20px!important;
        margin-top: 30px!important;
    }
   .feature-card {
        padding: 25px!important;
        border-radius: 15px!important;
        text-align: center!important;
        color: white!important;
        border: 1px solid rgba(255,255,255,0.1)!important;
    }
   .card-1 { background: #2563eb!important; }
   .card-2 { background: #dc2626!important; }
   .card-3 { background: #059669!important; }
   .card-4 { background: #d97706!important; }
</style>
""", unsafe_allow_html=True)

# ======= 1.5 VERIFICACIÓN DE ESTADO DE CUENTA =======
if st.session_state.get('logged_in'):
    user_data = st.session_state.get('user_data', {})
    fecha_fin_str = user_data.get('fecha_trial_fin', '2026-05-29')
    plan = user_data.get('plan', 'trial')

    try:
        fecha_fin = datetime.strptime(fecha_fin_str[:10], '%Y-%m-%d')
        dias_restantes = (fecha_fin - datetime.now()).days + 1
    except:
        dias_restantes = 0

    if dias_restantes < 0:
        mensaje_wa = "Hola NEXUS, quiero renovar mi suscripción."
        link_wa = f"https://wa.me/51914282688?text={mensaje_wa.replace(' ', '%20')}"

        html_code = f"""
        <div style="display: flex; flex-direction: column; align-items: center; text-align: center; color: white; font-family: sans-serif;">
            <h1 style="font-size: 3em;">⏳</h1>
            <h1 style="color: #ffffff; font-size: 2em;">Tu acceso ha finalizado</h1>
            <div style="background-color: #1e293b; padding: 20px; border-radius: 15px; border: 1px solid #475569; margin: 20px 0; max-width: 400px;">
                <h3 style="color: #60a5fa; margin-top: 0;">💳 Datos para la Renovación</h3>
                <p style="margin: 5px 0;"><b>Yape / Plin:</b> +51914282688</p>
                <p style="margin: 5px 0;"><b>Titular:</b> Alberto Ballarta</p>
                <p style="font-size: 0.9em; color: #94a3b8; margin-top: 10px;">
                    <i>Envía tu comprobante y DNI al WhatsApp tras realizar el pago.</i>
                </p>
            </div>
            <a href="{link_wa}" target="_blank" style="background-color: #25d366; color: white; padding: 15px 30px; text-decoration: none; border-radius: 50px; font-weight: bold; font-size: 1.1em; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                📲 Enviar comprobante al WhatsApp
            </a>
        </div>
        """
        components.html(html_code, height=500)
        st.stop()

    elif dias_restantes <= 7:
        if plan == 'trial':
            st.warning(f"⚠️ Tu periodo de prueba vence en {dias_restantes} días.")
        elif plan == 'premium':
            st.info(f"ℹ️ Tu suscripción Premium renueva en {dias_restantes} días.")

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
            response = tabla_usuarios.query(
                IndexName='dni-index',
                KeyConditionExpression=Key('dni').eq(usuario_o_dni)
            )
            if response['Items']:
                user = response['Items'][0]

        if user and user.get('password_hash') == hash_password(password):
            if user.get('activo', True):
                return user
        return None
    except Exception as e:
        st.error(f"Error en el login: {e}")
        return None

def registrar_dueno(dni, nombre, nombre_negocio, email, password, rubro, celular):
    try:
        if 'Item' in tabla_trial.get_item(Key={'tipo_id': f'DNI-{dni}'}):
            st.error("❌ Este DNI ya usó los 7 días gratis")
            return False

        response = tabla_usuarios.scan(
            FilterExpression="email = :e OR celular = :c",
            ExpressionAttributeValues={":e": email, ":c": celular}
        )

        if response.get('Items'):
            for item in response['Items']:
                if item['email'] == email:
                    st.error("❌ Este email ya está registrado.")
                    return False
                if item.get('celular') == celular:
                    st.error("❌ Este celular ya tiene una cuenta asociada.")
                    return False

        timestamp = str(int(datetime.now().timestamp()))[-5:]
        usuario_id = f"DUENO{timestamp}"

        tabla_usuarios.put_item(Item={
            'usuario_id': usuario_id,
            'id_del_dueno': usuario_id,
            'dni': dni,
            'nombre': nombre,
            'nombre_negocio': nombre_negocio,
            'email': email,
            'celular': celular,
            'password_hash': hash_password(password),
            'rol': 'dueno',
            'rubro': rubro,
            'plan': 'trial',
            'activo': True,
            'fecha_registro': datetime.now().isoformat(),
            'fecha_trial_fin': (datetime.now() + timedelta(days=7)).isoformat()
        })

        tabla_trial.put_item(Item={'tipo_id': f'DNI-{dni}', 'fecha': datetime.now().isoformat()})
        return True
    except Exception as e:
        st.error(f"Error en registro: {e}")
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

def borrar_producto(producto_id, id_dueno):
    try:
        tabla_productos.delete_item(
            Key={'id_del_dueno': str(id_dueno), 'producto_id': str(producto_id)}
        )
        return True
    except Exception as e:
        st.error(f"Error al borrar: {e}")
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
            Key={'id_del_dueno': str(id_dueno), 'producto_id': str(producto_id)}
        )
        return True
    except Exception as e:
        st.error(f"Error al eliminar en la base de datos: {e}")
        return False

def registrar_venta(producto_id, cantidad, precio_venta, precio_compra, pago, cliente, celular):
    try:
        id_dueno = st.session_state.user_data['usuario_id']
        fecha_utc = datetime.now(timezone.utc).isoformat()
        total_venta = float(precio_venta) * int(cantidad)

        tabla_ventas.put_item(Item={
            'usuario_id': id_dueno,
            'Venta_id': str(uuid.uuid4()),
            'producto_id': producto_id,
            'cantidad': int(cantidad),
            'total_venta': Decimal(str(total_venta)),
            'precio_venta': Decimal(str(precio_venta)),
            'precio_compra': Decimal(str(precio_compra)),
            'fecha': fecha_utc,
            'pago': str(pago),
            'cliente': str(cliente),
            'celular': str(celular)
        })
        return True
    except Exception as e:
        st.error(f"Error en venta: {e}")
        return False

def procesar_carga_excel(df):
    tamanio_bloque = 25
    total_filas = len(df)

    try:
        progreso_bar = st.progress(0)

        for i in range(0, total_filas, tamanio_bloque):
            bloque = df.iloc[i : i + tamanio_bloque]

            for index, row in bloque.iterrows():
                agregar_producto(
                    nombre=str(row['nombre']),
                    precio_venta=float(row['precio_venta']),
                    precio_compra=float(row['precio_compra']),
                    stock=int(row['stock']),
                    categoria=str(row['categoria'])
                )

            progreso = min((i + tamanio_bloque) / total_filas, 1.0)
            progreso_bar.progress(progreso)

        st.success(f"✅ ¡Carga completada! Se procesaron {total_filas} productos.")
        return True

    except Exception as e:
        st.error(f"Error detectado al procesar productos: {e}")
        st.warning("Consejo: Revisa que los nombres de las columnas en tu Excel sean: nombre, precio_venta, precio_compra, stock, categoria.")
        return False

def actualizar_inventario_masivo(df_editado):
    try:
        contador = 0
        with st.spinner("Actualizando base de datos..."):
            for index, row in df_editado.iterrows():
                tabla_productos.update_item(
                    Key={
                        'id_del_dueno': str(st.session_state.user_data['usuario_id']),
                        'producto_id': str(row['producto_id'])
                    },
                    UpdateExpression="SET nombre = :n, precio_venta = :pv, precio_compra = :pc, stock = :s, categoria = :c",
                    ExpressionAttributeValues={
                        ':n': row['nombre'],
                        ':pv': Decimal(str(row['precio_venta'])),
                        ':pc': Decimal(str(row['precio_compra'])),
                        ':s': int(row['stock']),
                        ':c': row['categoria']
                    }
                )
                contador += 1

        if contador > 0:
            st.success("✅ ¡Inventario actualizado correctamente!")
            return True
        else:
            st.warning("⚠️ No se detectaron cambios en el inventario.")
            return False

    except Exception as e:
        st.error(f"Error al actualizar en la base de datos: {e}")
        return False

def mostrar_ajustes():
    st.header("⚙️ Ajustes de Cuenta")

    tab_seguridad, tab_pagos = st.tabs(["🔒 Seguridad", "💳 Planes y Pagos"])

    with tab_seguridad:
        st.subheader("Cambiar Contraseña")
        with st.form("form_cambio_clave"):
            st.text_input("Contraseña Actual", type="password")
            st.text_input("Nueva Contraseña", type="password")
            st.text_input("Confirmar Nueva Contraseña", type="password")
            st.form_submit_button("Actualizar Clave")

    with tab_pagos:
        st.subheader("Renovación de Planes")
        col1, col2 = st.columns(2)
        col1.info("### 🟢 Básico\nS/ 40 mensuales")
        col2.warning("### 🔵 Premium\nS/ 50 mensuales")
        st.markdown("---")
        st.write("Realiza el depósito vía **Yape/Plin** al: **914282688**")
        st.write("Tecnico: **Alberto Ballarta**")

        dni_actual = st.session_state.user_data.get('dni', '')
        dni_input = st.text_input("Ingresa tu DNI:", value=dni_actual)

        mensaje = f"Hola Alberto, soy el cliente con DNI {dni_input} y deseo renovar mi plan."
        link_wa = f"https://wa.me/51914282688?text={mensaje.replace(' ', '%20')}"

        st.markdown(f'<a href="{link_wa}" target="_blank" style="background-color: #25d366; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">📲 Enviar comprobante al WhatsApp</a>', unsafe_allow_html=True)

# ======= 4. INTERFAZ DE INICIO =======
if st.session_state.get("logged_in"):
    nombre_negocio = st.session_state.user_data.get('nombre_negocio', 'Tu Negocio')
    st.markdown(f"""
        <div style="background-color: #1e3a8a; padding: 20px; border-radius: 10px; text-align: center;">
            <h1 style="color: white;">👋 ¡Bienvenido, {nombre_negocio}!</h1>
            <p style="color: #cbd5e1;">Sistema de Gestión NEXUS - Tu negocio bajo control.</p>
        </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <div style="background-color: #1e3a8a; padding: 20px; border-radius: 10px; text-align: center;">
            <h1 style="color: white;">⚡ NEXUS</h1>
            <p style="color: #cbd5e1;">Gestión Nexus - Tu negocio bajo control</p>
        </div>
    """, unsafe_allow_html=True)

if not st.session_state.get("logged_in", False):
    st.markdown("""
        <div style="background-color: #FFF3CD; border: 2px solid #FFC107; padding: 20px; border-radius: 10px; text-align: center; color: #856404; font-size: 20px; font-weight: bold; margin-bottom: 20px;">
            🎁 ¡PRUEBA 7 DÍAS GRATIS! <br>
            <span style="font-size: 16px; font-weight: normal;">Regístrate ahora sin compromiso y empieza hoy mismo.</span>
        </div>
    """, unsafe_allow_html=True)
else:
    st.info("⚡ Estás en modo de prueba. ¡Disfruta de la gestión total de tu negocio!")

if not st.session_state.logged_in:
    _, col_central, _ = st.columns([1, 2, 1])

    with col_central:
        tab1, tab2 = st.tabs(["🔑 Iniciar Sesión", "✨ Registrarse"])

        with tab1:
            usuario_input = st.text_input("Usuario o DNI", placeholder="Ej: 71234567", key="login_user")
            password_input = st.text_input("Contraseña", type="password", placeholder="••••", key="login_pass")
            if st.button("Ingresar al Sistema", use_container_width=True):
                user_validado = login(usuario_input, password_input)
                if user_validado:
                    st.session_state.logged_in = True
                    st.session_state.user_data = user_validado
                    st.rerun()
                else:
                    st.error("❌ Credenciales inválidas")

        with tab2:
            if "registro_exitoso" in st.session_state and st.session_state.registro_exitoso:
                st.success("¡Registro exitoso! Ya puedes iniciar sesión.")
                st.balloons()

                if st.button("Volver al inicio"):
                    for key in ["reg_dni", "reg_nombre", "reg_negocio", "reg_email", "reg_celular", "reg_pass"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    del st.session_state.registro_exitoso
                    st.rerun()
            else:
                reg_dni = st.text_input("DNI del dueño", key="reg_dni")
                reg_nombre = st.text_input("Nombre completo", key="reg_nombre")
                reg_negocio = st.text_input("Nombre del negocio", key="reg_negocio")
                reg_email = st.text_input("Email", key="reg_email")
                reg_celular = st.text_input("Número de celular", key="reg_celular")
                reg_rubro = st.selectbox("Rubro", list(CATEGORIAS_POR_RUBRO.keys()), key="reg_rubro")
                reg_password = st.text_input("Contraseña", type="password", key="reg_pass")

                if st.button("Activar prueba gratis", use_container_width=True):
                    if reg_dni and reg_nombre and reg_email and reg_password and reg_celular:
                        if registrar_dueno(reg_dni, reg_nombre, reg_negocio, reg_email, reg_password, reg_rubro, reg_celular):
                            st.session_state.registro_exitoso = True
                            st.rerun()
                        else:
                            st.error("Error al registrar: intenta con otros datos.")
                    else:
                        st.warning("Por favor, completa todos los campos.")

    st.markdown("<div style='margin-top: 60px;'></div>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center; color:#94A3B8; font-size:20px;'>¿Cansado de perder plata en tu cuaderno?</h3>", unsafe_allow_html=True)

    st.markdown("""
    <div class='feature-grid'>
        <div class='feature-card card-1'><div>📦</div><h3>Control Total</h3><p>Sabes qué vendes y qué falta en tiempo real.</p></div>
        <div class='feature-card card-2'><div>💰</div><h3>Más Ganancia</h3><p>Mira al instante qué productos te dejan más plata.</p></div>
        <div class='feature-card card-3'><div>📱</div><h3>Desde tu Celular</h3><p>Diseñado para usarse rápido en pantallas móviles.</p></div>
        <div class='feature-card card-4'><div>⚡</div><h3>Súper Económico</h3><p>Solo S/30 al mes. Sin contratos complicados.</p></div>
    </div>
    """, unsafe_allow_html=True)

    st.stop()

# ======= 6. APP PRINCIPAL =======
user = st.session_state.user_data

with st.sidebar:
    st.markdown(f"### 🏢 {user.get('nombre_negocio', 'NEXUS')}")
    st.markdown(f"**Plan:** {user.get('plan', 'trial').upper()}")
    st.markdown("---")
    menu = st.sidebar.selectbox("Menú", ["Productos", "Ventas", "Reportes", "⚙️ Ajustes"])
    st.markdown("---")
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_data = {}
        st.session_state.carrito = []
        st.rerun()

if menu == "Productos":
    st.title("📦 Gestión de Inventario")

    with st.expander("📂 Carga masiva desde Excel"):
        archivo = st.file_uploader("Sube tu archivo Excel", type=["xlsx", "xls"])

        if archivo:
            df_excel = pd.read_excel(archivo)
            st.write("Vista previa de los datos:")
            st.dataframe(df_excel.head())

            if st.button("🚀 Procesar Carga Masiva"):
                procesar_carga_excel(df_excel)
                st.rerun()

    with st.expander("➕ Agregar Nuevo Producto"):
        rubro = st.session_state.user_data.get('rubro', 'Otro')
        opciones_base = CATEGORIAS_POR_RUBRO.get(rubro, ["General"])
        opciones_lista = opciones_base + ["+ Agregar nueva categoría"]

        seleccion_cat = st.selectbox("Selecciona categoría", opciones_lista, key="sel_cat")

        cat_final = seleccion_cat
        if seleccion_cat == "+ Agregar nueva categoría":
            cat_final = st.text_input("Escribe el nombre de tu nueva categoría:", key="input_manual_unico")

        with st.form("form_unico_producto", clear_on_submit=True):
            nombre_nuevo = st.text_input("Nombre del producto")
            pv_nuevo = st.number_input("Precio Venta", step=0.1)
            pc_nuevo = st.number_input("Precio Compra", step=0.1)
            stk_nuevo = st.number_input("Stock", step=1)

            if st.form_submit_button("Guardar Producto Nuevo"):
                if seleccion_cat == "+ Agregar nueva categoría" and not cat_final:
                    st.error("Por favor, escribe el nombre de la nueva categoría.")
                elif nombre_nuevo and cat_final:
                    if agregar_producto(nombre_nuevo, pv_nuevo, pc_nuevo, stk_nuevo, cat_final):
                        st.success("¡Producto agregado!")
                        st.session_state["input_manual_unico"] = ""
                        st.rerun()
                else:
                    st.error("Nombre y categoría son obligatorios")

    st.subheader("Control de Inventario")
    productos = obtener_productos()

    if productos:
        df_inv = pd.DataFrame(productos)      

# --- FILTROS ---
        col1, col2 = st.columns(2)
        with col1:
            busqueda_p = st.text_input("🔍 Buscar por nombre:", key="buscador_unico")
        with col2:
            categorias_unicas = sorted(df_inv['categoria'].unique().tolist())
            filtro_cat = st.selectbox("📂 Filtrar por Categoría:", ["Todas"] + categorias_unicas)

        df_mostrar = df_inv.copy()
        if busqueda_p:
            df_mostrar = df_mostrar[df_mostrar['nombre'].str.contains(busqueda_p, case=False, na=False)]
        if filtro_cat!= "Todas":
            df_mostrar = df_mostrar[df_mostrar['categoria'] == filtro_cat]

        columnas_a_mostrar = ['producto_id', 'nombre', 'precio_compra', 'precio_venta', 'stock', 'categoria']

        df_editado = st.data_editor(
            df_mostrar[columnas_a_mostrar],
            key='editor_inventario',
            column_config={
                "producto_id": None,
                "precio_compra": st.column_config.NumberColumn(format="S/%.2f"),
                "precio_venta": st.column_config.NumberColumn(format="S/%.2f"),
            },
            use_container_width=True,
            height=400
        )

        if st.button("💾 Guardar cambios masivos"):
            actualizar_inventario_masivo(df_editado)
            st.rerun()

        st.divider()
        st.subheader("🗑️ Eliminar Producto")

        producto_a_borrar = st.selectbox(
            "Selecciona el producto a eliminar:",
            options=df_mostrar['nombre'].tolist(),
            key="selector_borrado"
        )

        if st.button("❌ Confirmar Eliminación"):
            fila_prod = df_mostrar[df_mostrar['nombre'] == producto_a_borrar].iloc[0]
            if borrar_producto(fila_prod['producto_id'], st.session_state.user_data['usuario_id']):
                st.success(f"¡{producto_a_borrar} eliminado correctamente!")
                st.rerun()

    else:
        st.info("Aún no hay productos registrados.")

if menu == "Ventas":
    st.title("🛒 Terminal de Ventas")

    productos = obtener_productos()
    tenant_actual = st.session_state.get('tenant_id', 'MI LOCAL')

    if not productos:
        st.info("💡 Aún no hay productos registrados en el inventario. Agrega algunos en la pestaña Productos.")
    else:
        categorias_disponibles = sorted(list(set(prod.get('categoria', 'General') for prod in productos)))
        opciones_categoria = ["📁 Todas las Categorías"] + [f"🏷️ {cat}" for cat in categorias_disponibles]

        c_busq, c_cat = st.columns([2, 1])
        with c_busq:
            busqueda_v = st.text_input("🔍 Buscar producto por nombre:", value=st.session_state["buscar_ventas"], key="input_buscar_ventas")
        with c_cat:
            categoria_seleccionada = st.selectbox("Filtrar por Categoría:", opciones_categoria)

        productos_mostrar = productos
        if busqueda_v.strip()!= "":
            productos_mostrar = [p for p in productos_mostrar if busqueda_v.lower() in p.get('nombre', '').lower()]
        if categoria_seleccionada!= "📁 Todas las Categorías":
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
                                elif p_stock_disponible <= 5:
                                    st.markdown(f"🟡 **Stock: {p_stock_disponible}** · **S/{p_precio_venta:.2f}**", unsafe_allow_html=True)
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

                for index, item in enumerate(st.session_state.carrito):
                    subtotal = float(item['precio_venta']) * int(item['cantidad'])
                    total_venta_bruto += subtotal

                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.markdown(f"**{item['nombre']}** - {item['cantidad']} x S/{item['precio_venta']:.2f}")
                    with c2:
                        if st.button("🗑️", key=f"del_{index}"):
                            st.session_state.carrito.pop(index)
                            st.rerun()

                st.markdown("---")
                descuento = st.number_input("🎁 Descuento (S/):", min_value=0.0, value=0.0)
                total_venta_neto = round(total_venta_bruto - descuento, 2)
                st.markdown(f"### Total a pagar: S/{total_venta_neto:.2f}")

                metodo_pago = st.radio("Forma de Pago:", ["💵 Efectivo", "📱 Yape", "💳 Plin"], horizontal=True)
                w_cliente_nombre = st.text_input("Nombre Cliente:", key="w_cli_nom")
                w_cliente_celular = st.text_input("Celular:", key="w_cli_cel")

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
                                pago=metodo_pago,
                                cliente=w_cliente_nombre.strip() if w_cliente_nombre.strip() else "Consumidor Final",
                                celular=w_cliente_celular.strip()
                            )
                            if res:
                                nuevo_stock = int(item['stock_max']) - int(item['cantidad'])
                                actualizar_producto(
                                    producto_id=item['producto_id'],
                                    nuevo_precio=item['precio_venta'],
                                    nuevo_stock=nuevo_stock
                                )
                            else:
                                ok = False
                                break
                        except Exception as e:
                            st.error(f"Error al registrar: {e}")
                            ok = False
                            break

                    if ok:
                        hora_servidor = datetime.now()
                        hora_peru = hora_servidor - timedelta(hours=5)
                        fecha_formateada = hora_peru.strftime("%Y-%m-%d %H:%M:%S")

                        st.session_state.ultima_venta = {
                            "tenant": tenant_actual,
                            "fecha": fecha_formateada,
                            "items": items_guardar,
                            "descuento": descuento,
                            "total": total_venta_neto,        
        
        
