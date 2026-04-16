import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
from boto3.dynamodb.conditions import Attr

# --- CONFIGURACIÓN ---
TABLA_STOCK = 'SaaS_Stock_Test'
TABLA_VENTAS = 'SaaS_Ventas_Test'

st.set_page_config(page_title="NEXUS BALLARTA SaaS", layout="wide")
tz_peru = pytz.timezone('America/Lima')

def obtener_tiempo():
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora.strftime("%Y%m%d%H%M%S%f")

# --- CONEXIÓN ---
try:
    dynamodb = boto3.resource('dynamodb', 
                              region_name=st.secrets["aws"]["aws_region"],
                              aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
                              aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"])
    tabla_stock = dynamodb.Table(TABLA_STOCK)
    tabla_ventas = dynamodb.Table(TABLA_VENTAS)
except Exception as e:
    st.error(f"Error AWS: {e}")
    st.stop()

# --- SESIÓN ---
if 'auth' not in st.session_state: st.session_state.auth = False
if 'tenant' not in st.session_state: st.session_state.tenant = None
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None

# --- LOGIN ---
if not st.session_state.auth:
    st.title("🚀 NEXUS BALLARTA SaaS")
    local_sel = st.selectbox("Local:", list(st.secrets.get("auth_multi", {"Demo":""}).keys()))
    clave = st.text_input("Clave:", type="password")
    if st.button("Ingresar"):
        if clave == "tiotuinventario":
            st.session_state.auth = True
            st.session_state.tenant = local_sel
            st.rerun()
    st.stop()

# --- CARGA DE DATOS (CON ESCUDO ANTI-ERRORES) ---
def cargar_inventario():
    try:
        res = tabla_stock.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant))
        items = res.get('Items', [])
        df = pd.DataFrame(items)
        if df.empty:
            return pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'Precio_Compra'])
        # Asegurar que existan las columnas para que no salga el error rojo
        for c in ['Producto', 'Stock', 'Precio', 'Precio_Compra']:
            if c not in df.columns: df[c] = 0
        df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
        df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
        return df[['Producto', 'Stock', 'Precio', 'Precio_Compra']].sort_values('Producto')
    except:
        return pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'Precio_Compra'])

df_inv = cargar_inventario()

tabs = st.tabs(["🛒 VENTA", "📊 REPORTES", "📦 GESTIÓN"])

# --- PESTAÑA VENTAS ---
with tabs[0]:
    if st.session_state.boleta:
        st.success("✅ Venta registrada con éxito")
        if st.button("Nueva Venta"):
            st.session_state.boleta = None
            st.rerun()
    else:
        st.subheader("Punto de Venta")
        prod = st.selectbox("Producto:", df_inv['Producto'].tolist()) if not df_inv.empty else None
        cant = st.number_input("Cantidad:", min_value=1, value=1)
        
        if prod:
            info = df_inv[df_inv['Producto'] == prod].iloc[0]
            st.write(f"Precio: S/ {info['Precio']} | Stock: {info['Stock']}")
            if st.button("Añadir"):
                st.session_state.carrito.append({'Producto': prod, 'Cantidad': cant, 'Precio': info['Precio'], 'Subtotal': info['Precio']*cant, 'Precio_Compra': info['Precio_Compra']})
                st.rerun()

        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c)
            total = df_c['Subtotal'].sum()
            st.markdown(f"<h1 style='color:#2ecc71;'>TOTAL: S/ {total:.2f}</h1>", unsafe_allow_html=True)
            
            if st.button("🚀 FINALIZAR COMPRA"):
                f, h, uid = obtener_tiempo()
                try:
                    for i, item in enumerate(st.session_state.carrito):
                        # AQUÍ ESTÁ LA SOLUCIÓN: Usar exactamente 'VentalID' como pide tu AWS
                        tabla_ventas.put_item(Item={
                            'TenantID': st.session_state.tenant,
                            'VentalID': f"{uid}-{i}", # Esto cumple con la Clave de Ordenación de tu foto
                            'Fecha': f,
                            'Hora': h,
                            'Producto': item['Producto'],
                            'Cantidad': int(item['Cantidad']),
                            'Total': str(item['Subtotal']),
                            'Precio_Compra': str(item['Precio_Compra'])
                        })
                    st.session_state.boleta = True
                    st.session_state.carrito = []
                    st.rerun()
                except Exception as e:
                    st.error(f"Fallo al guardar en AWS: {e}")

# --- PESTAÑA REPORTES (CON PROTECCIÓN CONTRA KEYERROR) ---
with tabs[1]:
    st.subheader("Historial")
    try:
        res_v = tabla_ventas.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant))
        v_items = res_v.get('Items', [])
        if v_items:
            df_v = pd.DataFrame(v_items)
            # Solo intentamos mostrar columnas si existen, así evitamos el KeyError de tu foto
            cols_ver = [c for c in ['Fecha', 'Hora', 'Producto', 'Total'] if c in df_v.columns]
            st.dataframe(df_v[cols_ver])
        else:
            st.info("No hay ventas grabadas todavía.")
    except:
        st.warning("No se pudo cargar el historial.")

# --- PESTAÑA GESTIÓN ---
with tabs[2]:
    st.subheader("Cargar Stock")
    with st.form("carga"):
        p = st.text_input("Producto").upper()
        s = st.number_input("Stock", min_value=0)
        pr = st.number_input("Precio Venta", min_value=0.0)
        pc = st.number_input("Precio Compra", min_value=0.0)
        if st.form_submit_button("Guardar"):
            tabla_stock.put_item(Item={'TenantID': st.session_state.tenant, 'Producto': p, 'Stock': int(s), 'Precio': str(pr), 'Precio_Compra': str(pc)})
            st.success("Guardado")
            st.rerun()
