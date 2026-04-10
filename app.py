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
except Exception as e:
    st.error(f"Error AWS: {e}")
    st.stop()

# ESTADOS DE SESIÓN
if 'sesion' not in st.session_state: st.session_state.sesion = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None

# --- LOGIN ---
if not st.session_state.sesion:
    st.title("🦷 Acceso Sistema BALLARTA")
    clave = st.text_input("Clave:", type="password")
    if st.button("Entrar"):
        if clave == admin_pass:
            st.session_state.sesion = True
            st.rerun()
    st.stop()

# --- INTERFAZ ---
st.title("🦷 Gestión Dental BALLARTA")

# CARGAR STOCK
items = tabla_stock.scan().get('Items', [])
if items:
    df_stock = pd.DataFrame(items)
    df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
    df_stock['Precio'] = pd.to_numeric(df_stock['Precio'])
else:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

t1, t2, t3, t4 = st.tabs(["🛒 Venta", "📊 Reportes", "📥 Cargar Stock", "🛠️ Mantenimiento"])

with t1:
    if st.session_state.boleta:
        st.balloons() # ¡Vuelven los globitos!
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: black; padding: 25px; border: 5px solid black; border-radius: 10px; max-width: 450px; margin: auto; font-family: Arial;">
            <div style="text-align: center;">
                <h1 style="margin: 0;">🦷 BALLARTA</h1>
                <p>Insumos Dentales</p>
                <hr style="border: 1px solid black;">
            </div>
            <p><b>FECHA:</b> {b['fecha']} | {b['hora']}</p>
            <table style="width: 100%;">
                <tr style="border-bottom: 2px solid black;"><th>Cant.</th><th>Producto</th><th style="text-align: right;">Total</th></tr>
        """
        for i in b['items']:
            ticket += f"<tr><td>{i['Cantidad']}</td><td>{i['Producto']}</td><td style='text-align: right;'>S/ {float(i['Subtotal']):.2f}</td></tr>"
        ticket += f"""
            </table>
            <hr style="border: 1px solid black;">
            <div style="text-align: right; font-size: 24px; font-weight: bold;">TOTAL: S/ {b['total']:.2f}</div>
            <p><b>MÉTODO:</b> {b['metodo']}</p>
        </div>
        """
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA"):
            st.session_state.boleta = None
            st.rerun()
        st.stop()

    if not df_stock.empty:
        col1, col2 = st.columns([3, 1])
        with col1:
            p_sel = st.selectbox("Seleccione Producto:", df_stock['Producto'].tolist())
            # PUNTO 1: Mostrar stock disponible de inmediato
            s_disp = df_stock.loc[df_stock['Producto'] == p_sel, 'Stock'].values[0]
            p_disp = df_stock.loc[df_stock['Producto'] == p_sel, 'Precio'].values[0]
            st.info(f"📦 Stock disponible: {s_disp} unidades | 💰 Precio: S/ {p_disp:.2f}")
        with col2:
            cant = st.number_input("Cant:", min_value=1, value=1)
        
        if st.button("➕ Agregar"):
            # PUNTO 2: Bloqueo de Precio 0
            if p_disp <= 0:
                st.error("No puedes vender un producto con precio 0. Corrígelo en Mantenimiento.")
            elif cant <= s_disp:
                st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': cant, 'Precio': p_disp, 'Subtotal': round(p_disp * cant, 2)})
                st.rerun()
            else:
                st.error("No hay stock suficiente.")

    if st.session_state.carrito:
        st.table(pd.DataFrame(st.session_state.carrito))
        total_v = sum(i['Subtotal'] for i in st.session_state.carrito)
        metodo = st.radio("Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
        
        # PUNTO 3: Mensaje de Confirmación
        st.warning(f"Total a cobrar: S/ {total_v:.2f}")
        confirma = st.checkbox("Confirmar que he recibido el pago")
        
        if st.button("✅ PROCESAR VENTA", disabled=not confirma):
            f, h, _ = obtener_tiempo_peru()
            st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total_v, 'metodo': metodo}
            for item in st.session_state.carrito:
                res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                n_s = int(res['Item']['Stock']) - item['Cantidad']
                tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                tabla_ventas.put_item(Item={'ID_Venta': f"V-{f}-{h}-{item['Producto'][:2]}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': metodo})
            st.session_state.carrito = []
            st.rerun()

# --- TAB 3: CARGAR STOCK ---
with t3:
    with st.form("stk"):
        p_lista = df_stock['Producto'].tolist() if not df_stock.empty else []
        p_ex = st.selectbox("Existente:", ["-- NUEVO --"] + p_lista)
        p_nw = st.text_input("Nombre si es Nuevo:")
        c_in = st.number_input("Cantidad:", min_value=1)
        pr_in = st.number_input("Precio de Venta:", min_value=0.1) # PUNTO 2: Precio mínimo 0.1
        if st.form_submit_button("Guardar"):
            prod = p_nw.strip() if p_nw.strip() else p_ex
            if prod != "-- NUEVO --":
                res = tabla_stock.get_item(Key={'Producto': prod})
                s_previo = int(res['Item']['Stock']) if 'Item' in res else 0
                tabla_stock.put_item(Item={'Producto': prod, 'Stock': s_previo + c_in, 'Precio': str(pr_in)})
                st.success("Guardado"); time.sleep(1); st.rerun()

# --- TAB 4: MANTENIMIENTO ---
with t4:
    if not df_stock.empty:
        p_edit = st.selectbox("Producto a corregir:", df_stock['Producto'].tolist())
        if st.button("🗑️ ELIMINAR COMPLETAMENTE"):
            tabla_stock.delete_item(Key={'Producto': p_edit})
            st.rerun()
