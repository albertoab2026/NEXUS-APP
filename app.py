import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
import io

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Sistema Dental BALLARTA", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora

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
    st.error(f"Error AWS: {e}")
    st.stop()

# ESTADOS DE SESIÓN
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None

# --- LOGIN ---
if not st.session_state.sesion_iniciada:
    st.markdown("<h1 style='text-align: center;'>🦷</h1>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #2E86C1;'>Sistema Dental BALLARTA</h1>", unsafe_allow_html=True)
    col_login, _ = st.columns([1, 1])
    with col_login:
        clave = st.text_input("Clave del sistema:", type="password")
        if st.button("🔓 Ingresar", use_container_width=True):
            if clave == admin_pass:
                st.session_state.sesion_iniciada = True
                st.rerun()
            else: st.error("❌ Contraseña incorrecta")
    st.stop()

if st.sidebar.button("🔴 CERRAR SESIÓN"):
    st.session_state.sesion_iniciada = False
    st.rerun()

# CARGAR STOCK
items = tabla_stock.scan().get('Items', [])
if items:
    df_stock = pd.DataFrame(items)
    df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
    df_stock['Precio'] = pd.to_numeric(df_stock['Precio'])
    df_stock = df_stock[['Producto', 'Stock', 'Precio']].sort_values(by='Producto')
else:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

# --- PESTAÑAS ---
t1, t2, t3, t4, t5, t6 = st.tabs([
    "🛒 Punto de Venta", "📦 Stock Actual", "📊 Reporte Ventas", 
    "📋 Historial Entradas", "📥 Cargar Stock", "🛠️ Mantenimiento"
])

# --- TAB 1: VENTA ---
with t1:
    if st.session_state.boleta:
        st.balloons()
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: black; padding: 25px; border: 5px solid black; border-radius: 10px; max-width: 450px; margin: auto; font-family: Arial;">
            <div style="text-align: center;">
                <h1 style="margin: 0;">🦷 BALLARTA</h1>
                <p>Insumos y Suministros Dentales</p>
                <hr style="border: 1px solid black;">
            </div>
            <p><b>FECHA:</b> {b['fecha']} | {b['hora']}</p>
            <table style="width: 100%;">
                <tr style="border-bottom: 2px solid black; text-align: left;"><th>Cant.</th><th>Producto</th><th style="text-align: right;">Total</th></tr>
        """
        for i in b['items']:
            ticket += f"<tr><td>{i['Cantidad']}</td><td>{i['Producto']}</td><td style='text-align: right;'>S/ {float(i['Subtotal']):.2f}</td></tr>"
        ticket += f"""
            </table>
            <hr style="border: 1px solid black;">
            <div style="text-align: right; font-size: 26px; font-weight: bold;">TOTAL PAGADO: S/ {b['total']:.2f}</div>
            <p><b>MÉTODO:</b> {b['metodo']}</p>
        </div>
        """
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA / LIMPIAR", use_container_width=True):
            st.session_state.boleta = None
            st.rerun()
    
    else:
        if not df_stock.empty:
            c1, c2 = st.columns([3, 1])
            with c1:
                prod_sel = st.selectbox("Buscar Producto:", df_stock['Producto'].tolist())
                s_disp = df_stock.loc[df_stock['Producto'] == prod_sel, 'Stock'].values[0]
                p_disp = df_stock.loc[df_stock['Producto'] == prod_sel, 'Precio'].values[0]
                if s_disp <= 5: st.error(f"⚠️ **STOCK CRÍTICO:** Solo quedan {s_disp:.0f}")
                else: st.info(f"📦 Stock: {s_disp:.0f} | 💰 Precio: S/ {p_disp:.2f}")
            with c2:
                cant_sel = st.number_input("Cantidad:", min_value=1, value=1)
            
            if st.button("➕ AÑADIR AL CARRITO", use_container_width=True):
                if cant_sel <= s_disp:
                    st.session_state.carrito.append({'Producto': prod_sel, 'Cantidad': cant_sel, 'Precio': p_disp, 'Subtotal': round(p_disp * cant_sel, 2)})
                    st.rerun()
                else: st.error("No hay suficiente stock")

        if st.session_state.carrito:
            st.divider()
            df_car = pd.DataFrame(st.session_state.carrito)
            # Formateamos la tabla para que no salgan muchos ceros
            st.table(df_car.style.format({"Precio": "S/ {:.2f}", "Subtotal": "S/ {:.2f}"}))
            
            total_v = df_car['Subtotal'].sum()
            
            # --- NUEVO: PRECIO GRANDE ---
            st.markdown(f"""
                <div style="background-color: #1E1E1E; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #2E86C1;">
                    <h2 style="margin: 0; color: white;">TOTAL A COBRAR</h2>
                    <h1 style="margin: 0; color: #2ECC71; font-size: 50px;">S/ {total_v:.2f}</h1>
                </div>
            """, unsafe_allow_html=True)
            
            st.write("") # Espacio
            m_pago = st.radio("Método de Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
            confirma = st.checkbox("Confirmar que recibí el dinero")
            
            if st.button("🚀 FINALIZAR Y GENERAR BOLETA", disabled=not confirma, type="primary", use_container_width=True):
                f, h, _ = obtener_tiempo_peru()
                st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total_v, 'metodo': m_pago}
                for item in st.session_state.carrito:
                    res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                    n_s = int(res['Item']['Stock']) - item['Cantidad']
                    tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                    tabla_ventas.put_item(Item={'ID_Venta': f"V-{f}-{h}-{item['Producto'][:2]}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': m_pago})
                st.session_state.carrito = []
                st.rerun()
            
            if st.button("🗑️ Vaciar Carrito"):
                st.session_state.carrito = []
                st.rerun()

# --- TAB 2: STOCK ACTUAL ---
with t2:
    st.subheader("📦 Inventario Completo")
    if not df_stock.empty:
        st.dataframe(df_stock.style.map(lambda x: 'background-color: #ff4b4b; color: white; font-weight: bold' if x <= 5 else '', subset=['Stock']).format({"Precio": "S/ {:.2f}", "Stock": "{:,.0f}"}), use_container_width=True, hide_index=True)

# --- TAB 3: REPORTE VENTAS ---
with t3:
    st.subheader("📊 Ventas del Día")
    _, _, ahora_dt = obtener_tiempo_peru()
    f_bus = st.date_input("Día a consultar:", ahora_dt).strftime("%d/%m/%Y")
    ventas = tabla_ventas.scan().get('Items', [])
    if ventas:
        df_v = pd.DataFrame(ventas)
        df_v_dia = df_v[df_v['Fecha'] == f_bus].copy()
        if not df_v_dia.empty:
            df_v_dia['Total'] = pd.to_numeric(df_v_dia['Total'])
            ce, cy, cp = df_v_dia[df_v_dia['Metodo'] == "💵 Efectivo"]['Total'].sum(), df_v_dia[df_v_dia['Metodo'] == "🟢 Yape"]['Total'].sum(), df_v_dia[df_v_dia['Metodo'] == "🟣 Plin"]['Total'].sum()
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💵 EFECTIVO", f"S/ {ce:.2f}"); m2.metric("🟢 YAPE", f"S/ {cy:.2f}"); m3.metric("🟣 PLIN", f"S/ {cp:.2f}"); m4.metric("💰 TOTAL", f"S/ {df_v_dia['Total'].sum():.2f}")
            st.divider()
            df_ord = df_v_dia.sort_values(by='Hora', ascending=False)[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']]
            st.dataframe(df_ord, use_container_width=True, hide_index=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                df_ord.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte (Excel)", buf.getvalue(), f"Ventas_{f_bus}.xlsx")
        else: st.info("No se registraron ventas este día.")

# --- TAB 4: HISTORIAL EN
