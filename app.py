import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time

# 1. CONFIGURACIÓN BÁSICA
st.set_page_config(page_title="Dental BALLARTA", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora, ahora.strftime("%Y%m%d%H%M%S%f")

# 2. CONEXIÓN AWS
try:
    aws_id = st.secrets["aws"]["aws_access_key_id"]
    aws_key = st.secrets["aws"]["aws_secret_access_key"]
    aws_region = st.secrets["aws"]["aws_region"]
    admin_pass = st.secrets["auth"]["admin_password"]
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    tabla_ventas = dynamodb.Table('VentasDentaltio')
    tabla_stock = dynamodb.Table('StockProductos')
    tabla_auditoria = dynamodb.Table('EntradasInventario') 
except Exception as e:
    st.error(f"Error AWS: {e}"); st.stop()

if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None

# --- LOGIN ---
if not st.session_state.sesion_iniciada:
    st.markdown("<h2 style='text-align: center;'>🦷 Sistema BALLARTA</h2>", unsafe_allow_html=True)
    clave = st.text_input("Contraseña:", type="password")
    if st.button("🔓 INGRESAR", use_container_width=True):
        if clave == admin_pass: st.session_state.sesion_iniciada = True; st.rerun()
    st.stop()

def get_df_stock():
    try:
        items = tabla_stock.scan().get('Items', [])
        if items:
            df = pd.DataFrame(items)
            df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
            return df[['Producto', 'Stock', 'Precio']].sort_values(by='Producto')
    except: pass
    return pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

df_stock = get_df_stock()
tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 HOY", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])

# --- TAB 1: VENTA (LA BOLETA QUE SÍ FUNCIONA) ---
with tabs[0]:
    if st.session_state.boleta:
        b = st.session_state.boleta
        
        # CREAMOS LA BOLETA COMO TEXTO PLANO (ESTILO RECIBO REAL)
        # Usamos st.info o st.success para darle un marco limpio
        linea = "------------------------------------------"
        encabezado = f"**BALLARTA DENTAL**\n\nSanta Isabel, Carabayllo\n{b['fecha']}  {b['hora']}\n{linea}\n"
        
        cuerpo = "| Cant | Producto | P.U. | Total |\n| :--- | :--- | :--- | :--- |\n"
        for i in b['items']:
            cuerpo += f"| {i['Cantidad']} | {i['Producto']} | {i['Precio']:.2f} | {i['Subtotal']:.2f} |\n"
        
        pie = f"\n{linea}\n### **TOTAL: S/ {b['total']:.2f}**\nMetodo de pago: {b['metodo']}\n\n**¡Gracias por su preferencia!**"
        
        # Mostramos todo en un contenedor blanco
        with st.container():
            st.markdown(encabezado + cuerpo + pie)
        
        st.write("")
        if st.button("⬅️ NUEVA VENTA", use_container_width=True):
            st.session_state.boleta = None
            st.rerun()
    else:
        # Selección de productos
        if not df_stock.empty:
            p_sel = st.selectbox("Producto:", df_stock['Producto'].tolist())
            info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
            st.caption(f"En stock: {info['Stock']}")
            
            c1, c2 = st.columns(2)
            with c1: p_u = st.number_input("Precio S/:", value=float(info['Precio']))
            with c2: cant = st.number_input("Cantidad:", min_value=1, value=1)
            
            if st.button("➕ AÑADIR A LA LISTA", use_container_width=True):
                if cant <= info['Stock']:
                    st.session_state.carrito.append({'Producto': p_sel, 'Original': p_sel, 'Cantidad': int(cant), 'Precio': float(p_u), 'Subtotal': round(p_u * cant, 2)})
                    st.rerun()
                else: st.error("Sin stock suficiente")

        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito)[['Producto', 'Cantidad', 'Subtotal']])
            m = st.radio("Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)
            if st.button("🚀 FINALIZAR COBRO", type="primary", use_container_width=True):
                f, h, _, uid = obtener_tiempo_peru()
                total_f = sum(item['Subtotal'] for item in st.session_state.carrito)
                st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total_f, 'metodo': m}
                for item in st.session_state.carrito:
                    s_act = int(df_stock[df_stock['Producto'] == item['Original']]['Stock'].values[0])
                    tabla_stock.update_item(Key={'Producto': item['Original']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': s_act - item['Cantidad']})
                    tabla_ventas.put_item(Item={'ID_Venta': f"V-{uid}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': m})
                st.session_state.carrito = []
                st.rerun()

# --- REPORTE DE CAJA ---
with tabs[2]:
    st.subheader("📊 Reporte de Hoy")
    _, _, ahora_dt, _ = obtener_tiempo_peru()
    f_bus = st.date_input("Fecha:", ahora_dt).strftime("%d/%m/%Y")
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        df_dia = df_v[df_v['Fecha'] == f_bus].copy()
        if not df_dia.empty:
            df_dia['Total'] = pd.to_numeric(df_dia['Total'])
            st.metric("VENTA TOTAL", f"S/ {df_dia['Total'].sum():.2f}")
            st.dataframe(df_dia[['Hora', 'Producto', 'Total', 'Metodo']], use_container_width=True, hide_index=True)

# --- LAS DEMÁS PESTAÑAS ---
with tabs[1]: st.dataframe(df_stock, use_container_width=True, hide_index=True)
with tabs[4]:
    with st.form("fc"):
        pn = st.text_input("Producto:").upper()
        cn = st.number_input("Cant:", min_value=1)
        pr = st.number_input("Precio:", min_value=1.0)
        if st.form_submit_button("GUARDAR"):
            f, h, _, uid = obtener_tiempo_peru()
            s_ant = int(df_stock[df_stock['Producto'] == pn]['Stock'].values[0]) if pn in df_stock['Producto'].values else 0
            tabla_stock.put_item(Item={'Producto': pn, 'Stock': s_ant + cn, 'Precio': str(pr)})
            tabla_auditoria.put_item(Item={'ID_Ingreso': f"I-{uid}", 'Fecha': f, 'Hora': h, 'Producto': pn, 'Cantidad_Entrante': int(cn), 'Stock_Resultante': int(s_ant + cn)})
            st.success("Guardado"); time.sleep(1); st.rerun()
