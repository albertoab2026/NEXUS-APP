import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
from boto3.dynamodb.conditions import Attr

# 1. CONFIGURACIÓN DE MARCA
MARCA_SaaS = "NEXUS BALLARTA SaaS"
st.set_page_config(page_title=MARCA_SaaS, layout="wide", page_icon="🚀")

TABLA_VENTAS_NAME = 'SaaS_Ventas_Test'
TABLA_STOCK_NAME = 'SaaS_Stock_Test'
tz_peru = pytz.timezone('America/Lima')

def obtener_tiempo_peru():
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora, ahora.strftime("%Y%m%d%H%M%S%f")

# 2. CONEXIÓN AWS
try:
    aws_id = st.secrets["aws"]["aws_access_key_id"].strip()
    aws_key = st.secrets["aws"]["aws_secret_access_key"].strip()
    aws_region = st.secrets["aws"]["aws_region"].strip()
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    tabla_ventas = dynamodb.Table(TABLA_VENTAS_NAME)
    tabla_stock = dynamodb.Table(TABLA_STOCK_NAME)
except Exception as e:
    st.error(f"Error Crítico AWS: {e}")
    st.stop()

# 3. ESTADOS DE SESIÓN (UNA SOLA VEZ)
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'tenant_id' not in st.session_state: st.session_state.tenant_id = None
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'reset_v' not in st.session_state: st.session_state.reset_v = 0
if 'df_stock_local' not in st.session_state: st.session_state.df_stock_local = pd.DataFrame()

def actualizar_stock_local():
    try:
        # Filtramos por TenantID para que cada cliente solo vea lo suyo
        response = tabla_stock.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant_id))
        items = response.get('Items', [])
        if items:
            df = pd.DataFrame(items)
            for col in ['Stock', 'Precio', 'P_Compra_U']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            df['Stock'] = df['Stock'].astype(int)
            df['Producto'] = df['Producto'].astype(str).str.upper().str.strip()
            st.session_state.df_stock_local = df.sort_values(by='Producto')
        else:
            st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])
    except Exception as e:
        st.error(f"Error al leer stock: {e}")
        st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])

# 4. LOGIN MULTI-TENANT
if not st.session_state.sesion_iniciada:
    st.markdown(f"<h1 style='text-align: center;'>{MARCA_SaaS}</h1>", unsafe_allow_html=True)
    auth_multi = st.secrets.get("auth_multi", {})
    if not auth_multi:
        st.warning("No hay empresas configuradas en Secrets.")
        st.stop()
        
    local_sel = st.selectbox("Empresa:", list(auth_multi.keys()))
    clave = st.text_input("Contraseña:", type="password")
    
    if st.button("🔓 Entrar", use_container_width=True):
        if local_sel in auth_multi and clave == auth_multi[local_sel].strip():
            st.session_state.sesion_iniciada = True
            st.session_state.tenant_id = local_sel
            actualizar_stock_local()
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.stop()

# 5. INTERFAZ PRINCIPAL
with st.sidebar:
    st.title(MARCA_SaaS)
    st.success(f"🏢 Local: {st.session_state.tenant_id}")
    if st.button("🔴 CERRAR SESIÓN"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])
df_stock = st.session_state.df_stock_local

# --- PESTAÑA VENTAS ---
with tabs[0]:
    if st.session_state.boleta:
        st.balloons()
        st.success(f"✅ VENTA REALIZADA - TOTAL: S/ {st.session_state.boleta['total_neto']:.2f}")
        if st.button("⬅️ NUEVA VENTA"):
            st.session_state.boleta = None
            st.rerun()
    else:
        st.subheader("Punto de Venta")
        bus_v = st.text_input("🔍 Buscar producto:").upper()
        prod_filt = [p for p in df_stock['Producto'].tolist() if bus_v in p]
        
        if prod_filt:
            c1, c2 = st.columns([3, 1])
            p_sel = c1.selectbox("Producto:", prod_filt, key=f"v_{st.session_state.reset_v}")
            info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
            cant = c2.number_input("Cant:", min_value=1, max_value=int(info['Stock']), value=1)
            
            if st.button("➕ AÑADIR AL CARRITO"):
                st.session_state.carrito.append({
                    'Producto': p_sel, 
                    'Cantidad': int(cant), 
                    'Precio': float(info['Precio']), 
                    'Subtotal': round(float(info['Precio']) * cant, 2),
                    'TenantID': st.session_state.tenant_id
                })
                st.session_state.reset_v += 1
                st.rerun()
        
        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c[['Producto', 'Cantidad', 'Precio', 'Subtotal']])
            total = df_c['Subtotal'].sum()
            st.markdown(f"### Total a Pagar: S/ {total:.2f}")
            
            if st.button("🚀 FINALIZAR VENTA", type="primary"):
                f, h, _, idv = obtener_tiempo_peru()
                # 1. Registrar Venta
                tabla_ventas.put_item(Item={
                    'VentaID': f"V-{idv}", 
                    'TenantID': st.session_state.tenant_id, 
                    'Fecha': f, 'Hora': h, 
                    'Total': str(total), 
                    'Items': str(st.session_state.carrito)
                })
                # 2. Descontar Stock Real
                for item in st.session_state.carrito:
                    tabla_stock.update_item(
                        Key={'Producto': item['Producto'], 'TenantID': st.session_state.tenant_id},
                        UpdateExpression="SET Stock = Stock - :v",
                        ExpressionAttributeValues={':v': item['Cantidad']}
                    )
                st.session_state.boleta = {'total_neto': total}
                st.session_state.carrito = []
                actualizar_stock_local()
                st.rerun()

# --- PESTAÑA STOCK ---
with tabs[1]:
    st.subheader("Inventario Actual")
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

# --- PESTAÑA CARGA ---
with tabs[4]:
    st.subheader("📥 Cargar Productos")
    opcion = st.radio("Método:", ["Manual", "Masivo (Excel/CSV)"], horizontal=True)
    
    if opcion == "Manual":
        with st.form("f_manual"):
            n = st.text_input("Nombre del Producto:").upper().strip()
            s = st.number_input("Stock Inicial:", min_value=0)
            pv = st.number_input("Precio Venta:", min_value=0.0)
            pc = st.number_input("Precio Compra:", min_value=0.0)
            if st.form_submit_button("Guardar Producto"):
                if n:
                    tabla_stock.put_item(Item={
                        'Producto': n, 
                        'TenantID': st.session_state.tenant_id, 
                        'Stock': int(s), 
                        'Precio': str(pv), 
                        'P_Compra_U': str(pc)
                    })
                    st.success("Producto registrado")
                    actualizar_stock_local()
                    st.rerun()
    else:
        archivo = st.file_uploader("Subir archivo:", type=['csv', 'xlsx'])
        if archivo and st.button("🚀 INICIAR CARGA MASIVA"):
            df_m = pd.read_csv(archivo) if archivo.name.endswith('.csv') else pd.read_excel(archivo)
            with tabla_stock.batch_writer() as batch:
                for _, r in df_m.iterrows():
                    batch.put_item(Item={
                        'Producto': str(r['Producto']).upper().strip(),
                        'TenantID': st.session_state.tenant_id,
                        'Stock': int(r.get('Stock', 0)),
                        'Precio': str(r.get('Precio', 0)),
                        'P_Compra_U': str(r.get('P_Compra_U', 0))
                    })
            st.success("Carga masiva completada")
            actualizar_stock_local()
            st.rerun()

# --- PESTAÑA MANTENIMIENTO ---
with tabs[5]:
    st.subheader("🛠️ Gestión de Productos")
    if not df_stock.empty:
        prod_sel = st.selectbox("Seleccione producto para editar/eliminar:", df_stock['Producto'].tolist())
        col1, col2 = st.columns(2)
        if col1.button("❌ ELIMINAR PRODUCTO", use_container_width=True):
            tabla_stock.delete_item(Key={'Producto': prod_sel, 'TenantID': st.session_state.tenant_id})
            st.error(f"{prod_sel} eliminado")
            actualizar_stock_local()
            st.rerun()
