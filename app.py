import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time

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
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'ultima_boleta' not in st.session_state: st.session_state.ultima_boleta = None

# --- LOGIN ---
if not st.session_state.sesion_iniciada:
    st.title("🔐 Acceso")
    clave_entrada = st.text_input("Clave:", type="password")
    if st.button("Ingresar"):
        if clave_entrada == admin_pass:
            st.session_state.sesion_iniciada = True
            st.rerun()
    st.stop()

st.title("🦷 Gestión Dental BALLARTA")

# CARGAR STOCK
items = tabla_stock.scan().get('Items', [])
if items:
    df_stock = pd.DataFrame(items)
    df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
    df_stock['Precio'] = pd.to_numeric(df_stock['Precio'])
else:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

tab_ventas, tab_admin = st.tabs(["🛒 Venta", "⚙️ Administración"])

with tab_ventas:
    if st.session_state.ultima_boleta:
        b = st.session_state.ultima_boleta
        
        # EL SÚPER BLINDAJE: Forzamos fondo blanco y letras negras en TODO
        st.markdown(f"""
        <div style="background-color: white !important; color: black !important; padding: 30px; border: 4px solid black !important; max-width: 600px; margin: auto; font-family: Arial, sans-serif; border-radius: 10px;">
            <div style="text-align: center; color: black !important;">
                <h1 style="color: black !important; margin-bottom: 5px; font-size: 45px; font-weight: 900;">🦷 BALLARTA</h1>
                <p style="color: black !important; font-size: 20px; font-weight: bold; margin: 0;">Insumos y Suministros Dentales</p>
                <p style="color: black !important; font-size: 16px; margin: 5px 0;">Carabayllo, Lima</p>
                <hr style="border: 1.5px solid black !important; opacity: 1;">
            </div>
            
            <div style="color: black !important; font-size: 22px; line-height: 1.6;">
                <p style="margin: 5px 0; color: black !important;"><b>FECHA:</b> {b['fecha']}</p>
                <p style="margin: 5px 0; color: black !important;"><b>HORA:</b> {b['hora']}</p>
                <hr style="border: 1px solid black !important; opacity: 1;">
                
                <table style="width: 100%; border-collapse: collapse; color: black !important; font-size: 20px;">
                    <tr style="border-bottom: 3px solid black !important; text-align: left;">
                        <th style="padding: 10px; color: black !important;">Cant.</th>
                        <th style="padding: 10px; color: black !important;">Producto</th>
                        <th style="padding: 10px; text-align: right; color: black !important;">Total</th>
                    </tr>
        """, unsafe_allow_html=True)

        for item in b['items']:
            st.markdown(f"""
                    <tr style="border-bottom: 1px solid black !important;">
                        <td style="padding: 12px 10px; color: black !important; font-weight: bold;">{item['Cantidad']}</td>
                        <td style="padding: 12px 10px; color: black !important; font-weight: bold;">{item['Producto']}</td>
                        <td style="padding: 12px 10px; text-align: right; color: black !important; font-weight: bold;">S/ {float(item['Subtotal']):.2f}</td>
                    </tr>
            """, unsafe_allow_html=True)

        st.markdown(f"""
                </table>
                <br>
                <div style="text-align: right; font-size: 32px; font-weight: 900; color: black !important; background-color: #f0f0f0; padding: 10px; border: 2px solid black;">
                    TOTAL: S/ {b['total']:.2f}
                </div>
                <hr style="border: 1px solid black !important; opacity: 1;">
                <p style="font-size: 20px; color: black !important; font-weight: bold;">MÉTODO: {b['metodo']}</p>
                
                <div style="text-align: center; margin-top: 30px; border: 2px dashed black; padding: 10px;">
                    <h3 style="color: black !important; font-size: 24px; margin: 0; font-weight: 900;">¡Gracias por su preferencia!</h3>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("##")
        if st.button("⬅️ REGRESAR / NUEVA VENTA", use_container_width=True):
            st.session_state.ultima_boleta = None
            st.rerun()
        st.stop()

    # --- FLUJO DE VENTA ---
    if not df_stock.empty:
        c1, c2 = st.columns([3, 1])
        with c1: p_sel = st.selectbox("Producto:", df_stock['Producto'].tolist())
        with c2: cant = st.number_input("Cantidad:", min_value=1, value=1)
        
        if st.button("➕ Agregar al Carrito"):
            stock_act = int(df_stock.loc[df_stock['Producto'] == p_sel, 'Stock'].values[0])
            if cant <= stock_act:
                prec = float(df_stock.loc[df_stock['Producto'] == p_sel, 'Precio'].values[0])
                st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': cant, 'Precio': prec, 'Subtotal': round(prec * cant, 2)})
                st.rerun()
            else: st.error("Sin stock suficiente")

    if st.session_state.carrito:
        st.table(pd.DataFrame(st.session_state.carrito))
        total = sum(i['Subtotal'] for i in st.session_state.carrito)
        metodo = st.radio("Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)

        if st.button("✅ FINALIZAR Y GENERAR BOLETA", type="primary", use_container_width=True):
            f, h, _ = obtener_tiempo_peru()
            st.session_state.ultima_boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total, 'metodo': metodo}
            
            for item in st.session_state.carrito:
                res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                n_s = int(res['Item']['Stock']) - item['Cantidad']
                tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                tabla_ventas.put_item(Item={'ID_Venta': f"V-{f}-{h}-{item['Producto'][:2]}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': metodo})
            st.session_state.carrito = []
            st.rerun()

# --- ADMIN ---
with tab_admin:
    st.write("### Inventario Actual")
    st.dataframe(df_stock, use_container_width=True)
    if st.button("Cerrar Sesión"):
        st.session_state.sesion_iniciada = False
        st.rerun()
