import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
import io

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Gestión Dental BALLARTA", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora

# 2. CONEXIÓN SEGURA CON AWS
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
    st.error(f"Error de conexión: {e}")
    st.stop()

# ESTADOS DE MEMORIA
if 'sesion' not in st.session_state: st.session_state.sesion = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None

# --- PANTALLA DE ACCESO ---
if not st.session_state.sesion:
    st.title("🦷 Acceso Sistema BALLARTA")
    clave = st.text_input("Ingresa la clave maestra:", type="password")
    if st.button("Entrar", use_container_width=True):
        if clave == admin_pass:
            st.session_state.sesion = True
            st.rerun()
        else:
            st.error("Clave incorrecta")
    st.stop()

# --- PANEL PRINCIPAL ---
st.title("🦷 Gestión Dental BALLARTA")

# Cargar inventario actualizado
items_raw = tabla_stock.scan().get('Items', [])
if items_raw:
    df_stock = pd.DataFrame(items_raw)
    df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
    df_stock['Precio'] = pd.to_numeric(df_stock['Precio'])
else:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

t1, t2, t3, t4 = st.tabs(["🛒 Ventas", "📊 Reportes", "📥 Cargar Stock", "🛠️ Mantenimiento"])

# --- TAB 1: VENTAS Y BOLETA ---
with t1:
    if st.session_state.boleta:
        b = st.session_state.boleta
        # Diseño de la boleta blindado
        ticket = f"""
        <div style="background-color: white; color: black; padding: 25px; border: 5px solid black; border-radius: 10px; max-width: 450px; margin: auto; font-family: 'Courier New', Courier, monospace;">
            <div style="text-align: center;">
                <h1 style="margin: 0; font-size: 30px;">🦷 BALLARTA</h1>
                <p style="margin: 5px 0; font-weight: bold;">Insumos Dentales</p>
                <p style="font-size: 12px;">Carabayllo, Lima</p>
                <hr style="border-top: 2px dashed black;">
            </div>
            <div style="font-size: 16px;">
                <p><b>FECHA:</b> {b['fecha']}<br><b>HORA:</b> {b['hora']}</p>
                <hr style="border-top: 1px solid black;">
                <table style="width: 100%; font-size: 15px;">
                    <tr style="text-align: left; border-bottom: 2px solid black;">
                        <th>Cant.</th><th>Producto</th><th style="text-align: right;">Total</th>
                    </tr>
        """
        for item in b['items']:
            ticket += f"<tr><td>{item['Cantidad']}</td><td>{item['Producto']}</td><td style='text-align: right;'>S/ {float(item['Subtotal']):.2f}</td></tr>"
        
        ticket += f"""
                </table>
                <hr style="border-top: 2px solid black;">
                <div style="text-align: right; font-size: 22px; font-weight: bold;">TOTAL: S/ {b['total']:.2f}</div>
                <p style="font-size: 14px; margin-top: 10px;"><b>MÉTODO:</b> {b['metodo']}</p>
                <div style="text-align: center; margin-top: 20px; border: 1px dashed black; padding: 5px;">
                    <p style="margin: 0;">¡Gracias por su preferencia!</p>
                </div>
            </div>
        </div>
        """
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ REGRESAR", use_container_width=True):
            st.session_state.boleta = None
            st.rerun()
        st.stop()

    # Interfaz de selección de productos
    if not df_stock.empty:
        col_p, col_c = st.columns([3, 1])
        with col_p:
            p_sel = st.selectbox("Elegir Producto:", df_stock['Producto'].tolist())
        with col_c:
            cant = st.number_input("Cant:", min_value=1, value=1)
        
        if st.button("➕ AGREGAR AL CARRITO", use_container_width=True):
            s_actual = int(df_stock.loc[df_stock['Producto'] == p_sel, 'Stock'].values[0])
            if cant <= s_actual:
                precio = float(df_stock.loc[df_stock['Producto'] == p_sel, 'Precio'].values[0])
                st.session_state.carrito.append({
                    'Producto': p_sel, 'Cantidad': cant, 
                    'Precio': precio, 'Subtotal': round(precio * cant, 2)
                })
                st.rerun()
            else:
                st.error(f"Solo quedan {s_actual} en stock.")

    if st.session_state.carrito:
        st.subheader("Carrito Actual")
        df_cart = pd.DataFrame(st.session_state.carrito)
        st.table(df_cart[['Producto', 'Cantidad', 'Subtotal']])
        total_venta = df_cart['Subtotal'].sum()
        
        metodo = st.radio("Método de Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
        
        if st.button("✅ FINALIZAR VENTA", type="primary", use_container_width=True):
            f, h, _ = obtener_tiempo_peru()
            # Guardar boleta en memoria
            st.session_state.boleta = {
                'fecha': f, 'hora': h, 'items': list(st.session_state.carrito),
                'total': total_venta, 'metodo': metodo
            }
            # Actualizar base de datos
            for item in st.session_state.carrito:
                res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                nuevo_stock = int(res['Item']['Stock']) - item['Cantidad']
                tabla_stock.update_item(
                    Key={'Producto': item['Producto']},
                    UpdateExpression="set Stock = :s",
                    ExpressionAttributeValues={':s': nuevo_stock}
                )
                tabla_ventas.put_item(Item={
                    'ID_Venta': f"V-{f}-{h}-{item['Producto'][:3]}",
                    'Fecha': f, 'Hora': h, 'Producto': item['Producto'],
                    'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']),
                    'Metodo': metodo
                })
            st.session_state.carrito = []
            st.rerun()

# --- TAB 2: REPORTES ---
with t2:
    _, _, t_hoy = obtener_tiempo_peru()
    f_buscar = st.date_input("Consultar día:", t_hoy).strftime("%d/%m/%Y")
    data_v = tabla_ventas.scan().get('Items', [])
    df_v = pd.DataFrame([v for v in data_v if v['Fecha'] == f_buscar])
    
    if not df_v.empty:
        df_v['Total'] = pd.to_numeric(df_v['Total'])
        st.success(f"Ventas del día: S/ {df_v['Total'].sum():.2f}")
        st.dataframe(df_v[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_v.to_excel(writer, index=False)
        st.download_button("📥 Descargar Reporte Excel", buf.getvalue(), f"Ventas_{f_buscar}.xlsx")
    else:
        st.info("No hay ventas registradas en esta fecha.")

# --- TAB 3: CARGAR STOCK ---
with t3:
    st.subheader("Ingreso de Mercadería")
    with st.form("form_stock"):
        p_lista = df_stock['Producto'].tolist() if not df_stock.empty else []
        p_existente = st.selectbox("Seleccionar producto existente:", ["-- NUEVO --"] + p_lista)
        p_nuevo = st.text_input("O escribir nombre de producto NUEVO:")
        
        cant_in = st.number_input("Cantidad que entra:", min_value=1)
        prec_vta = st.number_input("Precio de venta (S/):", min_value=0.0)
        
        if st.form_submit_button("Guardar en Inventario"):
            prod_final = p_nuevo.strip() if p_nuevo.strip() else p_existente
            if prod_final != "-- NUEVO --":
                res = tabla_stock.get_item(Key={'Producto': prod_final})
                stock_previo = int(res['Item']['Stock']) if 'Item' in res else 0
                tabla_stock.put_item(Item={
                    'Producto': prod_final,
                    'Stock': stock_previo + cant_in,
                    'Precio': str(prec_vta)
                })
                st.success(f"Actualizado: {prod_final}")
                time.sleep(1)
                st.rerun()

# --- TAB 4: MANTENIMIENTO ---
with t4:
    st.subheader("Herramientas de Control")
    if not df_stock.empty:
        p_borrar = st.selectbox("Eliminar o Corregir producto:", df_stock['Producto'].tolist())
        if st.button("🗑️ ELIMINAR PRODUCTO PERMANENTEMENTE"):
            tabla_stock.delete_item(Key={'Producto': p_borrar})
            st.warning(f"Se eliminó {p_borrar}")
            time.sleep(1)
            st.rerun()
            
    if st.sidebar.button("🔴 CERRAR SESIÓN"):
        st.session_state.sesion = False
        st.rerun()
