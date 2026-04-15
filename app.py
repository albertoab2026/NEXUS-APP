import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
from boto3.dynamodb.conditions import Attr

# 1. SETUP
st.set_page_config(page_title="NEXUS BALLARTA SaaS", layout="wide")
tz_peru = pytz.timezone('America/Lima')

def generar_id():
    return datetime.now(tz_peru).strftime("%Y%m%d%H%M%S%f")

# 2. CONEXIÓN (Limpia, sin tokens raros)
try:
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=st.secrets["aws"]["aws_region"],
        aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
        aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"]
    )
    t_stock = dynamodb.Table('SaaS_Stock_Test')
    t_ventas = dynamodb.Table('SaaS_Ventas_Test')
except Exception as e:
    st.error(f"Error AWS: {e}")
    st.stop()

# 3. SESIÓN
if 'login' not in st.session_state: st.session_state.login = False
if 'tenant' not in st.session_state: st.session_state.tenant = None

# 4. LOGIN (Clave: tiotuinventario)
if not st.session_state.login:
    st.title("🚀 NEXUS BALLARTA SaaS")
    locales = list(st.secrets.get("auth_multi", {"Local_Prueba": ""}).keys())
    empresa = st.selectbox("Seleccione su Local:", locales)
    clave = st.text_input("Contraseña:", type="password")
    
    if st.button("Entrar"):
        if clave == "tiotuinventario":
            st.session_state.login = True
            st.session_state.tenant = empresa
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    st.stop()

# 5. INTERFAZ
st.sidebar.subheader(f"Local: {st.session_state.tenant}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.login = False
    st.rerun()

menu = st.tabs(["🛒 VENTAS", "📦 STOCK", "📥 CARGA"])

# --- CARGA ---
with menu[2]:
    st.subheader("Cargar Nuevo Producto")
    with st.form("c"):
        n = st.text_input("Producto:").upper().strip()
        s = st.number_input("Stock:", min_value=0, step=1)
        p = st.number_input("Precio:", min_value=0.0)
        if st.form_submit_button("Guardar"):
            if n:
                t_stock.put_item(Item={
                    'TenantID': st.session_state.tenant, # SELLO DE PROPIEDAD
                    'Producto': n,
                    'Stock': int(s),
                    'Precio': str(p)
                })
                st.success("Guardado correctamente")
                st.rerun()

# --- STOCK (Solo muestra lo del cliente actual) ---
with menu[1]:
    res = t_stock.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant))
    items = res.get('Items', [])
    df_stock = pd.DataFrame(items) if items else pd.DataFrame()
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

# --- VENTAS (Seguridad total) ---
with menu[0]:
    if not df_stock.empty:
        p_v = st.selectbox("Elegir Producto:", df_stock['Producto'].tolist())
        c_v = st.number_input("Cantidad:", min_value=1, step=1)
        if st.button("Finalizar Venta"):
            try:
                # 1. Registrar Venta con TenantID
                t_ventas.put_item(Item={
                    'TenantID': st.session_state.tenant,
                    'VentaID': generar_id(),
                    'Producto': p_v,
                    'Cantidad': int(c_v),
                    'Fecha': datetime.now(tz_peru).strftime("%d/%m/%Y %H:%M")
                })
                # 2. Descontar Stock filtrando por TenantID
                t_stock.update_item(
                    Key={'TenantID': st.session_state.tenant, 'Producto': p_v},
                    UpdateExpression="SET Stock = Stock - :v",
                    ExpressionAttributeValues={':v': int(c_v)}
                )
                st.success("Venta realizada con éxito")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
