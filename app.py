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
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'ultima_boleta' not in st.session_state: st.session_state.ultima_boleta = None

# --- LOGIN ---
if not st.session_state.sesion_iniciada:
    st.title("🔐 Acceso")
    clave_entrada = st.text_input("Clave del sistema:", type="password")
    if st.button("Ingresar", use_container_width=True):
        if clave_entrada == admin_pass:
            st.session_state.sesion_iniciada = True
            st.rerun()
        else: st.error("Clave incorrecta")
    st.stop()

# --- INTERFAZ ---
st.title("🦷 Gestión Dental BALLARTA")

# CARGAR DATOS
items = tabla_stock.scan().get('Items', [])
if items:
    df_stock = pd.DataFrame(items)
    df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
    df_stock['Precio'] = pd.to_numeric(df_stock['Precio'])
else:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

tab_ventas, tab_admin = st.tabs(["🛒 Punto de Venta", "⚙️ Administración"])

# --- TABLA DE VENTAS ---
with tab_ventas:
    if st.session_state.ultima_boleta:
        b = st.session_state.ultima_boleta
        ticket_html = f"""
        <div style="background-color: white !important; color: black !important; padding: 25px; border: 4px solid black !important; border-radius: 10px; font-family: Arial, sans-serif; max-width: 500px; margin: auto;">
            <div style="text-align: center;">
                <h1 style="color: black !important; margin: 0; font-size: 35px;">🦷 BALLARTA</h1>
                <p style="color: black !important; font-size: 18px; font-weight: bold; margin: 5px 0;">Insumos y Suministros Dentales</p>
                <hr style="border: 1px solid black !important;">
            </div>
            <div style="color: black !important; font-size: 18px;">
                <p><b>FECHA:</b> {b['fecha']} | <b>HORA:</b> {b['hora']}</p>
                <hr style="border: 1px solid black !important;">
                <table style="width: 100%; border-collapse: collapse; color: black !important;">
                    <tr style="border-bottom: 2px solid black !important; text-align: left;">
                        <th>Cant.</th><th>Prod.</th><th style="text-align: right;">Total</th>
                    </tr>
        """
        for i in b['items']:
            ticket_html += f"<tr><td>{i['Cantidad']}</td><td>{i['Producto']}</td><td style="text-align: right;">S/ {float(i['Subtotal']):.2f}</td></tr>"
        
        ticket_html += f"""
                </table>
                <br>
                <div style="text-align: right; font-size: 24px; font-weight: bold; border-top: 2px solid black;">TOTAL: S/ {b['total']:.2f}</div>
                <p><b>MÉTODO:</b> {b['metodo']}</p>
                <div style="text-align: center; margin-top: 20px; border: 1px dashed black; padding: 10px;">
                    <p style="margin: 0; font-weight: bold;">¡Gracias por su preferencia!</p>
                </div>
            </div>
        </div>
        """
        st.markdown(ticket_html, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA", use_container_width=True):
            st.session_state.ultima_boleta = None
            st.rerun()
        st.stop()

    if not df_stock.empty:
        c1, c2 = st.columns([3, 1])
        with c1: p_sel = st.selectbox("Producto:", df_stock['Producto'].tolist())
        with c2: cant = st.number_input("Cantidad:", min_value=1, value=1)
        if st.button("➕ Añadir"):
            s_act = int(df_stock.loc[df_stock['Producto'] == p_sel, 'Stock'].values[0])
            if cant <= s_act:
                pr = float(df_stock.loc[df_stock['Producto'] == p_sel, 'Precio'].values[0])
                st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': cant, 'Precio': pr, 'Subtotal': round(pr*cant, 2)})
                st.rerun()
            else: st.error("Sin stock")

    if st.session_state.carrito:
        st.table(pd.DataFrame(st.session_state.carrito))
        total_v = sum(i['Subtotal'] for i in st.session_state.carrito)
        metodo = st.radio("Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
        if st.button("✅ FINALIZAR", type="primary", use_container_width=True):
            f, h, _ = obtener_tiempo_peru()
            st.session_state.ultima_boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total_v, 'metodo': metodo}
            for item in st.session_state.carrito:
                res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                n_s = int(res['Item']['Stock']) - item['Cantidad']
                tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                tabla_ventas.put_item(Item={'ID_Venta': f"V-{f}-{h}-{item['Producto'][:2]}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': metodo})
            st.session_state.carrito = []
            st.rerun()

# --- ADMIN ---
with tab_admin:
    t_rep, t_stk, t_man = st.tabs(["📊 Ventas", "📥 Cargar Stock", "🛠️ Mantenimiento"])
    
    with t_rep:
        _, _, hoy = obtener_tiempo_peru()
        f_ver = st.date_input("Día:", hoy).strftime("%d/%m/%Y")
        vts = tabla_ventas.scan().get('Items', [])
        df_v = pd.DataFrame([v for v in vts if v['Fecha'] == f_ver])
        if not df_v.empty:
            df_v['Total'] = pd.to_numeric(df_v['Total'])
            st.metric("Total Hoy", f"S/ {df_v['Total'].sum():.2f}")
            st.dataframe(df_v[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as wr:
                df_v.to_excel(wr, index=False)
            st.download_button("📥 Descargar Excel", output.getvalue(), f"Ventas_{f_ver}.xlsx")
        else: st.info("Sin ventas hoy.")

    with t_stk:
        with st.form("stk"):
            p_ex = st.selectbox("Existente:", df_stock['Producto'].tolist()) if not df_stock.empty else ""
            p_nw = st.text_input("Nuevo:")
            final_p = p_nw.strip() if p_nw.strip() else p_ex
            c_in = st.number_input("Cantidad:", min_value=1)
            pr_in = st.number_input("Precio:", min_value=0.1)
            if st.form_submit_button("Guardar"):
                if final_p:
                    res = tabla_stock.get_item(Key={'Producto': final_p})
                    n_stk = (int(res['Item']['Stock']) if 'Item' in res else 0) + c_in
                    tabla_stock.put_item(Item={'Producto': final_p, 'Stock': n_stk, 'Precio': str(pr_in)})
                    st.success("Actualizado")
                    time.sleep(1); st.rerun()

    with t_man:
        if not df_stock.empty:
            p_edit = st.selectbox("Producto a borrar/editar:", df_stock['Producto'].tolist())
            if st.button("🗑️ Eliminar Producto"):
                tabla_stock.delete_item(Key={'Producto': p_edit})
                st.success("Borrado"); time.sleep(1); st.rerun()
            n_nom = st.text_input("Cambiar nombre a:")
            if st.button("✏️ Renombrar"):
                if n_nom:
                    res = tabla_stock.get_item(Key={'Producto': p_edit})['Item']
                    tabla_stock.put_item(Item={'Producto': n_nom, 'Stock': res['Stock'], 'Precio': res['Precio']})
                    tabla_stock.delete_item(Key={'Producto': p_edit})
                    st.success("Cambiado"); time.sleep(1); st.rerun()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.sesion_iniciada = False
    st.rerun()
