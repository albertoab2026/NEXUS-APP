import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
from boto3.dynamodb.conditions import Attr
import time

# 1. CONFIGURACIÓN DE MARCA Y PÁGINA
st.set_page_config(page_title="NEXUS BALLARTA SaaS", layout="wide", page_icon="🚀")
MARCA_SaaS = "NEXUS BALLARTA SaaS"

# Nombres de tus tablas (Basado en tus capturas de AWS)
TABLA_VENTAS_NAME = 'SaaS_Ventas_Test'
TABLA_STOCK_NAME = 'SaaS_Stock_Test'
TABLA_AUDITORIA_NAME = 'SaaS_Audit_Test'
tz_peru = pytz.timezone('America/Lima')

def obtener_tiempo_peru():
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora, ahora.strftime("%Y%m%d%H%M%S%f")

# 2. CONEXIÓN AWS (CORREGIDA SIN TOKEN TEMPORAL)
try:
    aws_id = st.secrets["aws"]["aws_access_key_id"].strip()
    aws_key = st.secrets["aws"]["aws_secret_access_key"].strip()
    aws_region = st.secrets["aws"]["aws_region"].strip()
    
    # Conexión directa con credenciales fijas de IAM
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    tabla_ventas = dynamodb.Table(TABLA_VENTAS_NAME)
    tabla_stock = dynamodb.Table(TABLA_STOCK_NAME)
    tabla_auditoria = dynamodb.Table(TABLA_AUDITORIA_NAME)
except Exception as e:
    st.error(f"❌ Error de Conexión AWS: {e}")
    st.stop()

# 3. INICIALIZACIÓN DE ESTADOS
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'tenant_id' not in st.session_state: st.session_state.tenant_id = None
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'reset_v' not in st.session_state: st.session_state.reset_v = 0
if 'df_stock_local' not in st.session_state: st.session_state.df_stock_local = pd.DataFrame()

# 4. FUNCIÓN PARA CARGAR DATOS
def actualizar_stock_local():
    try:
        response = tabla_stock.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant_id))
        items = response.get('Items', [])
        if items:
            df = pd.DataFrame(items)
            for col in ['Stock', 'Precio', 'P_Compra_U']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            df['Stock'] = df['Stock'].astype(int)
            df['Producto'] = df['Producto'].astype(str).str.upper().str.strip()
            st.session_state.df_stock_local = df.sort_values(by='Producto')
        else:
            st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])
    except Exception as e:
        st.error(f"Error de sincronización: {e}")

# 5. LOGIN CON CLAVE INTEGRADA: tiotuinventario
if not st.session_state.sesion_iniciada:
    st.markdown(f"<h1 style='text-align: center;'>{MARCA_SaaS}</h1>", unsafe_allow_html=True)
    
    # Usamos auth_multi de tus secrets para la lista de empresas
    auth_config = st.secrets.get("auth_multi", {})
    
    if auth_config:
        local_sel = st.selectbox("Seleccione su local:", list(auth_config.keys()))
        clave_ingresada = st.text_input("Ingrese contraseña:", type="password")
        
        if st.button("🔓 Iniciar Sesión", use_container_width=True):
            # Validamos contra 'tiotuinventario' o el valor en secrets
            if clave_ingresada == "tiotuinventario" or clave_ingresada == auth_config[local_sel].strip():
                st.session_state.sesion_iniciada = True
                st.session_state.tenant_id = local_sel
                actualizar_stock_local()
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta.")
    else:
        st.warning("⚠️ No se encontró 'auth_multi' en Secrets.")
    st.stop()

# 6. PANEL PRINCIPAL
with st.sidebar:
    st.title("🚀 Panel Control")
    st.success(f"🏢 Local: {st.session_state.tenant_id}")
    if st.button("🔴 CERRAR SESIÓN"):
        st.session_state.sesion_iniciada = False
        st.rerun()

tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])
df_stock = st.session_state.df_stock_local

# --- LÓGICA DE VENTAS ---
with tabs[0]:
    if st.session_state.boleta:
        st.success("✅ VENTA REALIZADA")
        if st.button("NUEVA VENTA"):
            st.session_state.boleta = None
            st.rerun()
    else:
        bus_v = st.text_input("🔍 Buscar Producto:").upper()
        prod_filt = [p for p in df_stock['Producto'].tolist() if bus_v in p]
        
        if prod_filt:
            p_sel = st.selectbox("Producto:", prod_filt, key=f"v_{st.session_state.reset_v}")
            info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
            cant = st.number_input("Cantidad:", min_value=1, max_value=int(info['Stock']), value=1)
            
            if st.button("➕ Añadir al Carrito"):
                st.session_state.carrito.append({
                    'Producto': p_sel, 'Cantidad': int(cant), 
                    'Precio': float(info['Precio']), 'Subtotal': round(float(info['Precio']) * cant, 2),
                    'TenantID': st.session_state.tenant_id
                })
                st.session_state.reset_v += 1
                st.rerun()

        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito)[['Producto', 'Cantidad', 'Subtotal']])
            if st.button("🚀 FINALIZAR VENTA"):
                f, h, _, idv = obtener_tiempo_peru()
                total = sum(i['Subtotal'] for i in st.session_state.carrito)
                
                # Guardar venta
                tabla_ventas.put_item(Item={
                    'VentaID': f"V-{idv}", 'TenantID': st.session_state.tenant_id,
                    'Fecha': f, 'Hora': h, 'Total': str(total)
                })
                
                # Descontar stock
                for item in st.session_state.carrito:
                    tabla_stock.update_item(
                        Key={'Producto': item['Producto'], 'TenantID': st.session_state.tenant_id},
                        UpdateExpression="SET Stock = Stock - :v",
                        ExpressionAttributeValues={':v': item['Cantidad']}
                    )
                st.session_state.boleta = {'total': total}
                st.session_state.carrito = []
                actualizar_stock_local()
                st.rerun()

# --- PESTAÑA STOCK ---
with tabs[1]:
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

# --- PESTAÑA CARGAR ---
with tabs[4]:
    st.subheader("📥 Cargar Mercadería")
    with st.form("form_carga"):
        n = st.text_input("Nombre del Producto:").upper().strip()
        s = st.number_input("Stock:", min_value=0)
        pv = st.number_input("Precio Venta:", min_value=0.0)
        pc = st.number_input("Precio Compra:", min_value=0.0)
        if st.form_submit_button("Guardar"):
            if n:
                tabla_stock.put_item(Item={
                    'TenantID': st.session_state.tenant_id,
                    'Producto': n, 'Stock': int(s), 
                    'Precio': str(pv), 'P_Compra_U': str(pc)
                })
                st.success("Guardado.")
                actualizar_stock_local()
                st.rerun()

# --- PESTAÑA MANTENIMIENTO ---
with tabs[5]:
    if not df_stock.empty:
        p_del = st.selectbox("Elegir para borrar:", df_stock['Producto'].tolist())
        if st.button("🗑️ Eliminar"):
            tabla_stock.delete_item(Key={'Producto': p_del, 'TenantID': st.session_state.tenant_id})
            st.error("Eliminado.")
            actualizar_stock_local()
            st.rerun()
