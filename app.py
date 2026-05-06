import streamlit as st
import boto3
import uuid
from datetime import datetime, timedelta
import pytz
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# ====== 1. CONFIGURACIÓN AWS ======
st.set_page_config(page_title="NEXUS", page_icon="⚡", layout="wide")
# ====== CSS NEXUS PRO - ESTILO FUTURISTA ======
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

.stApp {
    background: #1a1d29;
    color: #ffffff;
    font-family: 'Inter', sans-serif;
}

h1, h2, h3 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    color: #ffffff !important;
}

.stButton > button {
    background: linear-gradient(135deg, #7C3AED 0%, #6366F1 100%);
    color: white !important;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 10px 20px;
    width: 100%;
}

.stTextInput > div > div > input, .stNumberInput > div > div > input {
    background-color: #252836 !important;
    color: #ffffff !important;
    border: 1px solid #3F4354 !important;
    border-radius: 8px;
}

.stTabs [data-baseweb="tab"] {
    background-color: transparent;
    color: #9CA3AF;
    font-weight: 600;
}
.stTabs [aria-selected="true"] {
    color: #F59E0B !important;
    border-bottom: 2px solid #F59E0B !important;
}

div[data-testid="metric-container"] {
    background: #252836;
    border: 1px solid #3F4354;
    border-radius: 12px;
    padding: 20px;
}
</style>
""", unsafe_allow_html=True)

AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = st.secrets["AWS_REGION"]

def get_dynamodb_table(table_name):
    dynamodb = boto3.resource(
        'dynamodb',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
    return dynamodb.Table(table_name)

# ====== 2. FUNCIONES USUARIOS ======
def registrar_dueno(dni, nombre, email, password):
    table = get_dynamodb_table('NEXUS_USUARIOS')
    id_dueno = str(uuid.uuid4())
    hoy = datetime.now(pytz.timezone('America/Lima'))
    fecha_fin = hoy + timedelta(days=7)

    table.put_item(Item={
        'id_del_empleado': str(uuid.uuid4()),
        'id_del_dueno': id_dueno,
        'dni': dni,
        'nombre': nombre,
        'email': email,
        'password': password,
        'rol': 'dueño',
        'plan': 'trial',
        'fecha_trial_fin': fecha_fin.isoformat(),
        'fecha_registro': hoy.isoformat()
    })
    return True

def login(dni, password):
    table = get_dynamodb_table('NEXUS_USUARIOS')
    response = table.scan(
        FilterExpression=Key('dni').eq(dni) & Key('password').eq(password)
    )
    return response['Items'][0] if response['Items'] else None

def activar_premium(dni_activar):
    table = get_dynamodb_table('NEXUS_USUARIOS')
    response = table.scan(FilterExpression=Key('dni').eq(dni_activar))
    if response['Items']:
        user = response['Items'][0]
        table.update_item(
            Key={'id_del_empleado': user['id_del_empleado']},
            UpdateExpression='SET plan = :p',
            ExpressionAttributeValues={':p': 'premium'}
        )
        return True
    return False

# ====== 3. FUNCIONES PRODUCTOS Y VENTAS ======
def contar_productos_dueno(id_dueno):
    table = get_dynamodb_table('NEXUS_PRODUCTOS')
    response = table.query(KeyConditionExpression=Key('id_del_dueno').eq(id_dueno))
    return len(response['Items'])

def registrar_producto(id_dueno, nombre, precio, costo, stock, categoria):
    table = get_dynamodb_table('NEXUS_PRODUCTOS')
    table.put_item(Item={
        'id_del_dueno': id_dueno,
        'producto_id': str(uuid.uuid4()),
        'nombre': nombre,
        'precio_venta': Decimal(str(precio)),
        'costo': Decimal(str(costo)),
        'stock': int(stock),
        'categoria': categoria,
        'fecha_registro': datetime.now(pytz.timezone('America/Lima')).isoformat()
    })

def listar_productos(id_dueno):
    table = get_dynamodb_table('NEXUS_PRODUCTOS')
    response = table.query(KeyConditionExpression=Key('id_del_dueno').eq(id_dueno))
    return response['Items']

def registrar_venta(id_dueno, id_empleado, productos_vendidos, total):
    table_ventas = get_dynamodb_table('NEXUS_VENTAS')
    table_productos = get_dynamodb_table('NEXUS_PRODUCTOS')

    for item in productos_vendidos:
        table_productos.update_item(
            Key={'id_del_dueno': id_dueno, 'producto_id': item['producto_id']},
            UpdateExpression='SET stock = stock - :cant',
            ExpressionAttributeValues={':cant': item['cantidad']}
        )

    table_ventas.put_item(Item={
        'id_del_dueno': id_dueno,
        'venta_id': str(uuid.uuid4()),
        'id_del_empleado': id_empleado,
        'fecha': datetime.now(pytz.timezone('America/Lima')).isoformat(),
        'productos': productos_vendidos,
        'total': Decimal(str(total)),
        'ganancia': Decimal(str(sum([i['ganancia'] for i in productos_vendidos])))
    })

def obtener_ventas_hoy(id_dueno):
    table = get_dynamodb_table('NEXUS_VENTAS')
    hoy = datetime.now(pytz.timezone('America/Lima')).date().isoformat()
    response = table.query(
        KeyConditionExpression=Key('id_del_dueno').eq(id_dueno) & Key('fecha').begins_with(hoy)
    )
    return response['Items']

# ====== 4. PANEL ADMIN ======
def mostrar_panel_admin():
    st.markdown("### 🔧 Panel Admin - Activar Premium")
    dni_activar = st.text_input("DNI del cliente a activar")
    if st.button("Activar Plan S/30"):
        if activar_premium(dni_activar):
            st.success(f"✅ Cliente {dni_activar} activado a PREMIUM")
            st.balloons()
        else:
            st.error("DNI no encontrado")

# ====== 5. DASHBOARD ======
def mostrar_dashboard():
    user = st.session_state.user_data
    hoy = datetime.now(pytz.timezone('America/Lima'))
    id_dueno = user['id_del_dueno']

    if user.get('plan') == 'trial':
        fecha_fin = datetime.fromisoformat(user['fecha_trial_fin'])
        dias_restantes = (fecha_fin - hoy).days
        if dias_restantes > 5:
            st.warning(f"⏰ Te quedan {dias_restantes} días de prueba GRATIS")
        elif dias_restantes > 0:
            st.error(f"🚨 URGENTE: Te quedan {dias_restantes} días de prueba GRATIS")
            st.warning(f"Yape/Plin S/30 AHORA al 914 282 688 - ALBERTO BALLARTA con código ACT-{user['dni']}")
        else:
            st.error("🔒 Tu prueba terminó. Activa S/30 para seguir usando NEXUS")
            st.stop()

    st.markdown(f"""
    <div style='background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); padding: 20px; border-radius: 10px; color: white;'>
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

    if menu == "📊 Dashboard":
        ventas_hoy = obtener_ventas_hoy(id_dueno)
        total_hoy = sum([float(v['total']) for v in ventas_hoy])
        ganancia_hoy = sum([float(v['ganancia']) for v in ventas_hoy])

        col1, col2, col3 = st.columns(3)
        col1.metric("Ventas Hoy", f"S/{total_hoy:.2f}")
        col2.metric("Ganancia Hoy", f"S/{ganancia_hoy:.2f}")
        col3.metric("N° Ventas", len(ventas_hoy))

        st.markdown("### Últimas Ventas")
        if ventas_hoy:
            for v in ventas_hoy[-5:]:
                st.text(f"S/{v['total']} - {v['fecha'][11:16]}")
        else:
            st.info("Aún no vendes hoy. ¡Vamos!")

    elif menu == "📦 Productos":
        st.markdown("### 📦 Gestión de Productos")
        total_productos = contar_productos_dueno(id_dueno)

        if user.get('plan') == 'trial' and total_productos >= 30:
            st.error("🔒 Límite de 30 productos en Trial alcanzado")
            st.warning(f"Activa Plan S/30 con código ACT-{user['dni']} para productos ilimitados")
            st.stop()

        with st.expander("➕ Registrar Producto Nuevo"):
            nombre = st.text_input("Nombre producto")
            col1, col2 = st.columns(2)
            precio = col1.number_input("Precio Venta", min_value=0.1, step=0.1)
            costo = col2.number_input("Costo", min_value=0.1, step=0.1)
            col3, col4 = st.columns(2)
            stock = col3.number_input("Stock", min_value=1, step=1)
            categoria = col4.selectbox("Categoría", ["Abarrotes","Bebidas","Limpieza","Otros"])

            if st.button("Guardar Producto"):
                if nombre and precio > costo:
                    registrar_producto(id_dueno, nombre, precio, costo, stock, categoria)
                    st.success(f"✅ {nombre} guardado")
                    st.rerun()
                else:
                    st.error("Precio debe ser mayor al costo")

        st.markdown("### Tus Productos")
        productos = listar_productos(id_dueno)
        if productos:
            for p in productos:
                col1, col2, col3, col4 = st.columns([3,1,1,1])
                col1.write(f"**{p['nombre']}**")
                col2.write(f"S/{p['precio_venta']}")
                col3.write(f"Stock: {p['stock']}")
                col4.write(f"Gana: S/{float(p['precio_venta'])-float(p['costo']):.2f}")
        else:
            st.info("No tienes productos. Registra el primero arriba ☝️")

        st.caption(f"Productos: {total_productos}/{'30' if user.get('plan')=='trial' else '∞'}")

    elif menu == "💰 Ventas":
        st.markdown("### 💰 Registrar Venta")
        productos = listar_productos(id_dueno)

        if not productos:
            st.warning("Primero registra productos en 📦 Productos")
            st.stop()

        if 'carrito' not in st.session_state:
            st.session_state.carrito = []

        col1, col2 = st.columns([2,1])
        producto_sel = col1.selectbox("Producto", options=[p['nombre'] for p in productos])
        cantidad = col2.number_input("Cantidad", min_value=1, step=1)

        if st.button("Agregar al Carrito"):
            prod = next(p for p in productos if p['nombre']==producto_sel)
            if prod['stock'] >= cantidad:
                st.session_state.carrito.append({
                    'producto_id': prod['producto_id'],
                    'nombre': prod['nombre'],
                    'cantidad': cantidad,
                    'precio': float(prod['precio_venta']),
                    'costo': float(prod['costo']),
                    'ganancia': (float(prod['precio_venta'])-float(prod['costo']))*cantidad
                })
                st.rerun()
            else:
                st.error(f"Solo tienes {prod['stock']} en stock")

        if st.session_state.carrito:
            st.markdown("### Carrito")
            total = 0
            for item in st.session_state.carrito:
                st.text(f"{item['cantidad']}x {item['nombre']} = S/{item['precio']*item['cantidad']:.2f}")
                total += item['precio']*item['cantidad']

            st.markdown(f"## Total: S/{total:.2f}")

            if st.button("💰 Cobrar Venta", use_container_width=True):
                registrar_venta(id_dueno, user['id_del_empleado'], st.session_state.carrito, total)
                st.success("✅ Venta registrada")
                st.balloons()
                st.session_state.carrito = []
                st.rerun()

    elif menu == "🔧 Admin":
        mostrar_panel_admin()
    elif menu == "👥 Usuarios":
        st.info("Módulo Empleados - Próximamente")

    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_data = None
        st.rerun()

# ====== 6. LOGIN Y REGISTRO ======
def mostrar_login():
    st.markdown("""
    <div style='text-align: center; margin-bottom: 40px;'>
        <div style='background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); 
                    border-radius: 15px; padding: 25px; margin-bottom: 30px;'>
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
                    padding: 20px; text-align: center; height: 180px;'>
            <div style='font-size: 2.2rem; margin-bottom: 10px;'>📦</div>
            <h3 style='font-size: 1rem; margin: 10px 0;'>Control Total</h3>
            <p style='color: #9CA3AF; font-size: 0.8rem;'>
                Sabes qué vendes y qué te falta. Adiós cuaderno.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='background: #252836; border: 1px solid #3F4354; border-radius: 12px; 
                    padding: 20px; text-align: center; height: 180px;'>
            <div style='font-size: 2.2rem; margin-bottom: 10px;'>💰</div>
            <h3 style='font-size: 1rem; margin: 10px 0;'>Más Ganancia</h3>
            <p style='color: #9CA3AF; font-size: 0.8rem;'>
                Ve qué productos más plata te dejan. Gana más.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style='background: #252836; border: 1px solid #3F4354; border-radius: 12px; 
                    padding: 20px; text-align: center; height: 180px;'>
            <div style='font-size: 2.2rem; margin-bottom: 10px;'>📱</div>
            <h3 style='font-size: 1rem; margin: 10px 0;'>Desde tu Celular</h3>
            <p style='color: #9CA3AF; font-size: 0.8rem;'>
                Sin computadoras. Gestiona desde donde estés.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div style='background: #252836; border: 1px solid #3F4354; border-radius: 12px; 
                    padding: 20px; text-align: center; height: 180px;'>
            <div style='font-size: 2.2rem; margin-bottom: 10px;'>⚡</div>
            <h3 style='font-size: 1rem; margin: 10px 0;'>Súper Barato</h3>
            <p style='color: #9CA3AF; font-size: 0.8rem;'>
                S/30 al mes. Otros cobran S/250.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("""
        <div style='background: #10B981; border-radius: 12px; padding: 20px; 
                    text-align: center; margin: 20px 0;'>
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

# ====== 7. MAIN ======
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        mostrar_dashboard()
    else:
        mostrar_login()

if __name__ == "__main__":
    main()
