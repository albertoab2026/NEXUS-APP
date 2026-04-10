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

st.title("🦷 Gestión Dental BALLARTA")

# CARGAR STOCK
items = tabla_stock.scan().get('Items', [])
if items:
    df_stock = pd.DataFrame(items)
    df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
    df_stock['Precio'] = pd.to_numeric(df_stock['Precio'])
    df_stock = df_stock.sort_values(by='Producto')
else:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

# --- CUADRO DE INVENTARIO GENERAL ---
with st.expander("📦 VER TODO MI INVENTARIO (Stock Actual)", expanded=True):
    if not df_stock.empty:
        # CORRECCIÓN DE ERROR: Usamos .style.map en lugar de applymap
        def resaltar_bajo_stock(val):
            color = 'background-color: #ff4b4b; color: white; font-weight: bold' if val <= 5 else ''
            return color
        
        st.dataframe(
            df_stock.style.map(resaltar_bajo_stock, subset=['Stock']),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("El inventario está vacío.")

t1, t2, t3, t4 = st.tabs(["🛒 Venta", "📊 Reportes", "📥 Cargar Stock", "🛠️ Mantenimiento"])

with t1:
    if st.session_state.boleta:
        st.balloons()
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
                <tr style="border-bottom: 2px solid black; text-align: left;"><th>Cant.</th><th>Producto</th><th style="text-align: right;">Total</th></tr>
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
            s_disp = df_stock.loc[df_stock['Producto'] == p_sel, 'Stock'].values[0]
            p_disp = df_stock.loc[df_stock['Producto'] == p_sel, 'Precio'].values[0]
            
            if s_disp <= 5:
                st.error(f"⚠️ ¡ALERTA! Stock Crítico: Quedan {s_disp} unidades.")
            else:
                st.info(f"📦 Disponible: {s_disp} | 💰 Precio: S/ {p_disp:.2f}")

        with col2:
            cant = st.number_input("Cant:", min_value=1, value=1)
        
        if st.button("➕ Agregar al Carrito", use_container_width=True):
            if cant <= s_disp:
                st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': cant, 'Precio': p_disp, 'Subtotal': round(p_disp * cant, 2)})
                st.rerun()
            else:
                st.error("No hay suficiente stock.")

    if st.session_state.carrito:
        st.subheader("Venta actual")
        st.table(pd.DataFrame(st.session_state.carrito))
        total_v = sum(i['Subtotal'] for i in st.session_state.carrito)
        metodo = st.radio("Método de Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
        
        st.warning(f"Total a cobrar: S/ {total_v:.2f}")
        confirma = st.checkbox("Confirmar que recibí el dinero")
        
        if st.button("✅ FINALIZAR VENTA", disabled=not confirma, type="primary", use_container_width=True):
            f, h, _ = obtener_tiempo_peru()
            st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total_v, 'metodo': metodo}
            for item in st.session_state.carrito:
                res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                n_s = int(res['Item']['Stock']) - item['Cantidad']
                tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                tabla_ventas.put_item(Item={'ID_Venta': f"V-{f}-{h}-{item['Producto'][:2]}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': metodo})
            st.session_state.carrito = []
            st.rerun()

# --- TAB 2: REPORTES ---
with t2:
    st.subheader("Consultar Ventas")
    _, _, hoy_dt = obtener_tiempo_peru()
    f_ver = st.date_input("Día a consultar:", hoy_dt).strftime("%d/%m/%Y")
    
    # Escaneo y filtrado
    vts_raw = tabla_ventas.scan().get('Items', [])
    if vts_raw:
        df_v = pd.DataFrame(vts_raw)
        df_v_dia = df_v[df_v['Fecha'] == f_ver].copy()
        
        if not df_v_dia.empty:
            df_v_dia['Total'] = pd.to_numeric(df_v_dia['Total'])
            st.metric("Venta del día", f"S/ {df_v_dia['Total'].sum():.2f}")
            st.dataframe(df_v_dia[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_v_dia.to_excel(writer, index=False)
            st.download_button("📥 Descargar Excel", output.getvalue(), f"Ventas_{f_ver}.xlsx")
        else:
            st.info(f"Sin ventas el {f_ver}.")
    else:
        st.info("No hay datos registrados aún.")

# --- TAB 3: CARGAR STOCK ---
with t3:
    st.subheader("Carga de Mercadería")
    with st.form("carga"):
        p_l = df_stock['Producto'].tolist() if not df_stock.empty else []
        p_e = st.selectbox("Producto existente:", ["-- NUEVO --"] + p_l)
        p_n = st.text_input("Nombre si es nuevo:")
        c_i = st.number_input("Cantidad que entra:", min_value=1)
        pr_i = st.number_input("Precio de Venta (S/):", min_value=0.1)
        
        if st.form_submit_button("Guardar en Sistema"):
            nombre = p_n.strip() if p_n.strip() else p_e
            if nombre != "-- NUEVO --":
                res = tabla_stock.get_item(Key={'Producto': nombre})
                s_prev = int(res['Item']['Stock']) if 'Item' in res else 0
                tabla_stock.put_item(Item={'Producto': nombre, 'Stock': s_prev + c_i, 'Precio': str(pr_i)})
                st.success("Inventario actualizado."); time.sleep(1); st.rerun()

# --- TAB 4: MANTENIMIENTO ---
with t4:
    if not df_stock.empty:
        p_del = st.selectbox("Eliminar producto:", df_stock['Producto'].tolist())
        if st.button("🗑️ BORRAR DEFINITIVAMENTE"):
            tabla_stock.delete_item(Key={'Producto': p_del})
            st.warning("Producto eliminado."); time.sleep(1); st.rerun()

if st.sidebar.button("🔴 Cerrar Sesión"):
    st.session_state.sesion = False
    st.rerun()
