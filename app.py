import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
import io

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Sistema Dental BALLARTA", layout="wide")

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
    st.error(f"Error de conexión: {e}")
    st.stop()

# 3. ESTADOS DE SESIÓN
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'form_contador' not in st.session_state: st.session_state.form_contador = 0

# --- LOGIN ---
if not st.session_state.sesion_iniciada:
    st.markdown("<h1 style='text-align: center;'>🦷</h1><h1 style='text-align: center; color: #2E86C1;'>Sistema Dental BALLARTA</h1>", unsafe_allow_html=True)
    col_login, _ = st.columns([1, 1])
    with col_login:
        clave = st.text_input("Clave del sistema:", type="password")
        if st.button("🔓 Ingresar", use_container_width=True):
            if clave == admin_pass:
                st.session_state.sesion_iniciada = True
                st.rerun()
            else: st.error("❌ Contraseña incorrecta")
    st.stop()

# SIDEBAR
if st.sidebar.button("🔴 CERRAR SESIÓN"):
    st.session_state.sesion_iniciada = False
    st.rerun()

# CARGAR STOCK
def get_df_stock():
    try:
        items = tabla_stock.scan().get('Items', [])
        if items:
            df = pd.DataFrame(items)
            for col in ['Stock', 'Precio', 'Producto']:
                if col not in df.columns: df[col] = 0 if col != 'Producto' else "Sin Nombre"
            df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0)
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
            return df[['Producto', 'Stock', 'Precio']].sort_values(by='Producto')
    except: pass
    return pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

df_stock = get_df_stock()

tabs = st.tabs(["🛒 Venta", "📦 Stock", "📊 Reportes", "📋 Historial", "📥 Cargar", "🛠️ Mant."])

# --- TAB 1: VENTA (BOLETA CON NOMBRE APARTE) ---
with tabs[0]:
    if st.session_state.boleta:
        st.balloons()
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: black; padding: 20px; border: 2px solid #333; border-radius: 10px; max-width: 400px; margin: auto; font-family: monospace;">
            <center>
                <p style="margin:0; font-size: 14px; letter-spacing: 2px;">TIENDA DENTAL</p>
                <h1 style="margin:0; color: #2E86C1; font-size: 32px;">BALLARTA</h1>
                <p style="margin-bottom: 10px;">Insumos Profesionales</p>
            </center>
            <hr>
            <p><b>FECHA:</b> {b['fecha']} | {b['hora']}</p>
            <table style="width: 100%;">
        """
        for i in b['items']: ticket += f"<tr><td>{i['Cantidad']} x {i['Producto']}</td><td style='text-align: right;'>S/ {float(i['Subtotal']):.2f}</td></tr>"
        ticket += f"</table><hr><h2 style='text-align: right;'>TOTAL: S/ {b['total']:.2f}</h2><p><b>PAGO:</b> {b['metodo']}</p></div>"
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA"):
            st.session_state.boleta = None
            st.rerun()
    else:
        if not df_stock.empty:
            c1, c2 = st.columns([3, 1])
            with c1:
                p_sel = st.selectbox("Elegir Producto:", df_stock['Producto'].tolist())
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                if info['Stock'] <= 5: st.error(f"⚠️ ¡STOCK CRÍTICO: {info['Stock']:.0f} UNIDADES!")
                else: st.info(f"📦 Stock disponible: {info['Stock']:.0f}")
            with c2: cant = st.number_input("Cant:", min_value=1, value=1)
            if st.button("➕ AÑADIR AL CARRITO", use_container_width=True):
                if cant <= info['Stock']:
                    st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': float(info['Precio']), 'Subtotal': round(float(info['Precio']) * cant, 2)})
                    st.rerun()
                else: st.error("No hay suficiente stock")

        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito))
            total_v = sum(i['Subtotal'] for i in st.session_state.carrito)
            st.markdown(f"<h1 style='color: #2ECC71; text-align: center;'>TOTAL: S/ {total_v:.2f}</h1>", unsafe_allow_html=True)
            metodo = st.radio("Método de Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
            if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
                f, h, _, uid = obtener_tiempo_peru()
                st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total_v, 'metodo': metodo}
                for item in st.session_state.carrito:
                    n_s = int(df_stock[df_stock['Producto'] == item['Producto']]['Stock'].values[0]) - item['Cantidad']
                    tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                    tabla_ventas.put_item(Item={'ID_Venta': f"V-{uid}-{item['Producto'][:2]}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': metodo})
                st.session_state.carrito = []
                st.rerun()

# --- TAB 2: STOCK (CON ALERTAS EN ROJO) ---
with tabs[1]:
    st.subheader("📦 Inventario General")
    if not df_stock.empty:
        # Función para pintar de rojo si el stock es 5 o menos
        def resaltado_critico(s):
            return ['background-color: #ff4b4b; color: white; font-weight: bold' if val <= 5 else '' for val in s]
        
        st.dataframe(
            df_stock.style.apply(resaltado_critico, subset=['Stock']).format({"Precio": "S/ {:.2f}", "Stock": "{:.0f}"}),
            use_container_width=True, 
            hide_index=True
        )

# --- TAB 3: REPORTES ---
with tabs[2]:
    st.subheader("📊 Reporte Diario")
    _, _, ahora_dt, _ = obtener_tiempo_peru()
    f_bus = st.date_input("Día a consultar:", ahora_dt).strftime("%d/%m/%Y")
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        df_dia = df_v[df_v['Fecha'] == f_bus].copy()
        if not df_dia.empty:
            df_dia['Total'] = pd.to_numeric(df_dia['Total'], errors='coerce').fillna(0)
            st.metric("VENTA TOTAL DEL DÍA", f"S/ {df_dia['Total'].sum():.2f}")
            st.dataframe(df_dia[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
        else: st.info("No hubo ventas hoy.")

# --- TAB 4: HISTORIAL ---
with tabs[3]:
    st.subheader("📋 Auditoría de Movimientos")
    h_data = tabla_auditoria.scan().get('Items', [])
    if h_data:
        df_h = pd.DataFrame(h_data)
        df_h['Sort'] = pd.to_datetime(df_h['Fecha'] + ' ' + df_h['Hora'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        df_h = df_h.sort_values(by='Sort', ascending=False)
        col1, col2 = st.columns(2)
        with col1:
            st.write("### 📥 Entradas")
            st.dataframe(df_h[df_h['Tipo'] != 'ELIMINADO'][['Fecha', 'Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante']], use_container_width=True, hide_index=True)
        with col2:
            st.write("### 🗑️ Eliminados")
            st.dataframe(df_h[df_h['Tipo'] == 'ELIMINADO'][['Fecha', 'Hora', 'Producto', 'Stock_Resultante']], use_container_width=True, hide_index=True)

# --- TAB 5: CARGAR STOCK ---
with tabs[4]:
    st.subheader("📥 Registro de Mercadería")
    with st.form(key=f"f_{st.session_state.form_contador}"):
        p_ex = st.selectbox("Producto Existente:", [""] + df_stock['Producto'].tolist())
        p_nu = st.text_input("Nuevo Producto:").upper().strip()
        p_final = p_ex if p_ex != "" else p_nu
        cant_in = st.number_input("Cantidad:", min_value=1)
        prec_in = st.number_input("Precio:", min_value=0.1)
        if st.form_submit_button("GRABAR", use_container_width=True):
            if p_final:
                f, h, _, uid = obtener_tiempo_peru()
                s_ant = int(df_stock[df_stock['Producto'] == p_final]['Stock'].values[0]) if p_final in df_stock['Producto'].values else 0
                tabla_stock.put_item(Item={'Producto': p_final, 'Stock': s_ant + cant_in, 'Precio': str(prec_in)})
                tabla_auditoria.put_item(Item={'ID_Ingreso': f"I-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_final, 'Cantidad_Entrante': int(cant_in), 'Stock_Resultante': int(s_ant + cant_in), 'Tipo': 'INGRESO'})
                st.success("Guardado."); st.session_state.form_contador += 1
                time.sleep(1); st.rerun()

# --- TAB 6: MANTENIMIENTO ---
with tabs[5]:
    st.subheader("🛠️ Limpieza de Base de Datos")
    if not df_stock.empty:
        p_del = st.selectbox("Producto a quitar definitivamente:", df_stock['Producto'].tolist())
        if st.button("ELIMINAR AHORA", use_container_width=True):
            f, h, _, uid = obtener_tiempo_peru()
            s_del = int(df_stock[df_stock['Producto'] == p_del]['Stock'].values[0])
            tabla_stock.delete_item(Key={'Producto': p_del})
            tabla_auditoria.put_item(Item={'ID_Ingreso': f"D-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_del, 'Cantidad_Entrante': 0, 'Stock_Resultante': s_del, 'Tipo': 'ELIMINADO'})
            st.success("Eliminado."); time.sleep(1); st.rerun()
