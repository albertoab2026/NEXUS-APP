import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
import io

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="LABORATORIO - Pruebas Dental", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora

# 2. CONEXIÓN AWS (Apuntando a Tablas TEST)
try:
    aws_id = st.secrets["aws"]["aws_access_key_id"]
    aws_key = st.secrets["aws"]["aws_secret_access_key"]
    aws_region = st.secrets["aws"]["aws_region"]
    admin_pass = st.secrets["auth"]["admin_password"]
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    # Nombres de tablas de prueba
    tabla_ventas = dynamodb.Table('Ventas_Test')
    tabla_stock = dynamodb.Table('Stock_Test')
    tabla_auditoria = dynamodb.Table('Auditoria_Test')
except Exception as e:
    st.error(f"Error de Conexión: {e}")
    st.stop()

# ESTADOS DE SESIÓN
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'confirmar' not in st.session_state: st.session_state.confirmar = False

# --- LOGIN DE PRUEBAS ---
if not st.session_state.sesion_iniciada:
    st.title("🧪 LABORATORIO DE DESARROLLO")
    st.info("Este entorno es para pruebas. No afecta el stock real.")
    clave = st.text_input("Clave de Desarrollador:", type="password")
    if st.button("Ingresar al Lab"):
        if clave == admin_pass:
            st.session_state.sesion_iniciada = True
            st.rerun()
        else: st.error("Clave incorrecta")
    st.stop()

# --- INTERFAZ ---
st.title("🧪 Sistema Dental (Modo Test)")
st.sidebar.warning("⚠️ CONECTADO A BASE DE DATOS DE PRUEBA")

# CARGAR STOCK
items = tabla_stock.scan().get('Items', [])
df_stock = pd.DataFrame(items) if items else pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

tab_v, tab_a = st.tabs(["🛒 Probar Venta", "⚙️ Configurar Test"])

with tab_v:
    if not df_stock.empty:
        df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
        
        # Alerta Stock Bajo
        stock_bajo = df_stock[df_stock['Stock'] < 5]
        if not stock_bajo.empty:
            for _, f in stock_bajo.iterrows():
                st.error(f"🚨 TEST ALERT: {f['Producto']} tiene solo {f['Stock']}")

        with st.expander("Ver Stock de Prueba"):
            df_m = df_stock.copy()
            df_m['Estado'] = df_m['Stock'].apply(lambda x: "🚨 CRÍTICO" if x < 5 else "✅ OK")
            st.dataframe(df_m[['Estado', 'Producto', 'Stock', 'Precio']], use_container_width=True, hide_index=True)

        c1, c2, c3 = st.columns([3,1,1])
        with c1: p_sel = st.selectbox("Elegir producto:", df_stock['Producto'].tolist())
        with c2: can = st.number_input("Cant:", min_value=1, value=1)
        with c3:
            st.write("##")
            if st.button("➕"):
                s_d = int(df_stock.loc[df_stock['Producto'] == p_sel, 'Stock'].values[0])
                if can <= s_d:
                    pre = float(df_stock.loc[df_stock['Producto'] == p_sel, 'Precio'].values[0])
                    st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': can, 'Precio': pre, 'Subtotal': round(pre*can, 2)})
                    st.rerun()
                else: st.error("Sin stock en Test")

    if st.session_state.carrito:
        st.table(pd.DataFrame(st.session_state.carrito))
        if st.button("🗑️ Vaciar Carrito"):
            st.session_state.carrito = []; st.rerun()
        
        if st.button("🚀 PROCESAR TEST", type="primary"):
            st.session_state.confirmar = True

        if st.session_state.confirmar:
            if st.button("✅ CONFIRMAR"):
                fe, ho, _ = obtener_tiempo_peru()
                for i in st.session_state.carrito:
                    # Bajar stock en TEST
                    res = tabla_stock.get_item(Key={'Producto': i['Producto']})
                    n_s = int(res['Item']['Stock']) - i['Cantidad']
                    tabla_stock.update_item(Key={'Producto': i['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                    # Venta en TEST
                    tabla_ventas.put_item(Item={'ID_Venta': f"TEST-{fe}-{ho}", 'Fecha': fe, 'Hora': ho, 'Producto': i['Producto'], 'Total': str(i['Subtotal'])})
                st.session_state.carrito = []; st.session_state.confirmar = False; st.success("Venta de prueba guardada"); time.sleep(1); st.rerun()

with tab_a:
    st.write("### 📥 Crear Productos para Pruebas")
    with st.form("f_test"):
        np = st.text_input("Nombre:")
        stk = st.number_input("Stock inicial:", min_value=1)
        pr = st.number_input("Precio:", min_value=0.0)
        if st.form_submit_button("Guardar Producto de Prueba"):
            tabla_stock.put_item(Item={'Producto': np, 'Stock': stk, 'Precio': str(pr)})
            st.success("Producto creado en tablas de prueba"); time.sleep(1); st.rerun()
