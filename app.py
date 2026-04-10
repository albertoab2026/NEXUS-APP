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
if 'confirmar' not in st.session_state: st.session_state.confirmar = False
if 'ultima_boleta' not in st.session_state: st.session_state.ultima_boleta = None

# --- PANTALLA DE LOGIN ---
if not st.session_state.sesion_iniciada:
    st.title("🔐 Acceso Restringido")
    clave_entrada = st.text_input("Clave del sistema:", type="password")
    if st.button("Ingresar", use_container_width=True):
        if clave_entrada == admin_pass:
            st.session_state.sesion_iniciada = True
            st.rerun()
        else: st.error("Clave incorrecta")
    st.stop()

# --- INTERFAZ PRINCIPAL ---
if st.sidebar.button("🔴 CERRAR SISTEMA"):
    st.session_state.sesion_iniciada = False
    st.rerun()

st.title("🦷 Gestión Dental BALLARTA")

# CARGAR STOCK ACTUAL (Línea corregida aquí)
items = tabla_stock.scan().get('Items', [])
if items:
    df_stock = pd.DataFrame(items)
    df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
    df_stock['Precio'] = pd.to_numeric(df_stock['Precio'])
else:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

tab_ventas, tab_admin = st.tabs(["🛒 Punto de Venta", "⚙️ Administración"])

with tab_ventas:
    # --- VISTA DE LA BOLETA (BLINDADA CONTRA MODO OSCURO) ---
    if st.session_state.ultima_boleta:
        b = st.session_state.ultima_boleta
        
        st.markdown(f"""
        <div style="background-color: white !important; color: black !important; padding: 25px; border-radius: 15px; border: 2px solid #ddd; max-width: 500px; margin: auto; font-family: 'Courier New', Courier, monospace;">
            <div style="text-align: center;">
                <h1 style="color: black !important; margin-bottom: 5px;">🦷 BALLARTA</h1>
                <p style="color: black !important; margin-top: 0; font-size: 14px;">Insumos y Suministros Dentales</p>
                <p style="color: black !important; font-size: 12px;">Carabayllo, Lima</p>
                <hr style="border: 0.5px dashed #ccc !important;">
            </div>
            <div style="color: black !important;">
                <p><b>Fecha:</b> {b['fecha']}</p>
                <p><b>Hora:</b> {b['hora']}</p>
                <hr style="border: 0.5px dashed #ccc !important;">
                <table style="width: 100%; color: black !important;">
                    <tr style="text-align: left;">
                        <th>Cant.</th>
                        <th>Producto</th>
                        <th style="text-align: right;">Total</th>
                    </tr>
        """, unsafe_allow_html=True)

        for item in b['items']:
            st.markdown(f"""
                    <tr style="color: black !important;">
                        <td>{item['Cantidad']}</td>
                        <td>{item['Producto']}</td>
                        <td style="text-align: right;">S/ {float(item['Subtotal']):.2f}</td>
                    </tr>
            """, unsafe_allow_html=True)

        st.markdown(f"""
                </table>
                <hr style="border: 0.5px dashed #ccc !important;">
                <div style="text-align: right; color: black !important;">
                    <h3>TOTAL A PAGAR: S/ {b['total']:.2f}</h3>
                </div>
                <p style="color: black !important; font-size: 14px;"><b>Método:</b> {b['metodo']}</p>
                <div style="text-align: center; margin-top: 20px; color: black !important;">
                    <p>¡Gracias por su preferencia!</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("##")
        if st.button("⬅️ VOLVER AL MENÚ", use_container_width=True):
            st.session_state.ultima_boleta = None
            st.rerun()
        st.stop()

    # --- FLUJO NORMAL DE VENTA ---
    if not df_stock.empty:
        bajos = df_stock[df_stock['Stock'] < 5]
        for _, r in bajos.iterrows():
            st.warning(f"🚨 Poco stock: {r['Producto']} ({r['Stock']} unid.)")

        with st.expander("Ver Inventario"):
            st.dataframe(df_stock[['Producto', 'Stock', 'Precio']], use_container_width=True, hide_index=True)

        c1, c2, c3 = st.columns([3, 1, 1])
        with c1: p_sel = st.selectbox("Producto:", df_stock['Producto'].tolist())
        with c2: cant = st.number_input("Cantidad:", min_value=1, value=1)
        with c3:
            st.write("##")
            if st.button("➕"):
                stock_act = int(df_stock.loc[df_stock['Producto'] == p_sel, 'Stock'].values[0])
                if cant <= stock_act:
                    prec = float(df_stock.loc[df_stock['Producto'] == p_sel, 'Precio'].values[0])
                    st.session_state.carrito.append({
                        'Producto': p_sel, 'Cantidad': cant, 
                        'Precio': prec, 'Subtotal': round(prec * cant, 2)
                    })
                    st.rerun()
                else: st.error("Stock insuficiente")

    if st.session_state.carrito:
        df_c = pd.DataFrame(st.session_state.carrito)
        st.table(df_c[['Producto', 'Cantidad', 'Subtotal']])
        total = df_c['Subtotal'].sum()
        st.metric("TOTAL", f"S/ {total:.2f}")

        metodo = st.radio("Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)

        if st.button("✅ FINALIZAR VENTA", type="primary", use_container_width=True):
            f, h, _ = obtener_tiempo_peru()
            st.session_state.ultima_boleta = {
                'fecha': f, 'hora': h, 'items': list(st.session_state.carrito),
                'total': total, 'metodo': metodo
            }
            for item in st.session_state.carrito:
                res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                n_s = int(res['Item']['Stock']) - item['Cantidad']
                tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                tabla_ventas.put_item(Item={
                    'ID_Venta': f"V-{f}-{h}-{item['Producto'][:2]}", 
                    'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 
                    'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 
                    'Metodo': metodo
                })
            st.session_state.carrito = []
            st.rerun()

# --- TAB ADMINISTRACIÓN ---
with tab_admin:
    t1, t2, t3 = st.tabs(["📊 Reportes", "📥 Stock", "🛠️ Ajustes"])
    
    with t1:
        _, _, hoy = obtener_tiempo_peru()
        f_ver = st.date_input("Día:", hoy).strftime("%d/%m/%Y")
        vts = tabla_ventas.scan().get('Items', [])
        df_vts = pd.DataFrame([v for v in vts if v['Fecha'] == f_ver])
        
        if not df_vts.empty:
            df_vts['Total'] = pd.to_numeric(df_vts['Total'])
            efec = df_vts[df_vts['Metodo'] == "💵 Efectivo"]['Total'].sum()
            digi = df_vts[df_vts['Metodo'] != "💵 Efectivo"]['Total'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("EFECTIVO", f"S/ {efec:.2f}")
            c2.metric("YAPE/PLIN", f"S/ {digi:.2f}")
            c3.metric("TOTAL", f"S/ {df_vts['Total'].sum():.2f}")
            st.dataframe(df_vts[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
        else: st.info("Sin ventas.")

    with t2:
        with st.form("add"):
            p_ex = st.selectbox("Existente:", df_stock['Producto'].tolist()) if not df_stock.empty else ""
            p_nw = st.text_input("Nuevo:")
            final_p = p_nw.strip() if p_nw.strip() else p_ex
            cant_in = st.number_input("Cantidad:", min_value=1)
            prec_in = st.number_input("Precio Venta:", min_value=0.1)
            if st.form_submit_button("Guardar Stock"):
                if final_p:
                    res = tabla_stock.get_item(Key={'Producto': final_p})
                    n_stk = (int(res['Item']['Stock']) if 'Item' in res else 0) + cant_in
                    tabla_stock.put_item(Item={'Producto': final_p, 'Stock': n_stk, 'Precio': str(prec_in)})
                    st.success("¡Guardado!")
                    time.sleep(1)
                    st.rerun()

    with t3:
        if not df_stock.empty:
            p_borrar = st.selectbox("Producto a quitar/editar:", df_stock['Producto'].tolist())
            if st.button("🗑️ Eliminar Producto"):
                tabla_stock.delete_item(Key={'Producto': p_borrar})
                st.success("Borrado.")
                time.sleep(1)
                st.rerun()
