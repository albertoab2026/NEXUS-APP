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

# CARGAR STOCK (CON MANEJO DE ERRORES)
def get_df_stock():
    try:
        items = tabla_stock.scan().get('Items', [])
        if items:
            df = pd.DataFrame(items)
            df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0)
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
            return df[['Producto', 'Stock', 'Precio']].sort_values(by='Producto')
    except: pass
    return pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

df_stock = get_df_stock()

# PESTAÑAS
tabs = st.tabs(["🛒 Venta", "📦 Stock", "📊 Reportes", "📋 Historial", "📥 Cargar", "🛠️ Mant."])

# --- TAB 1: VENTA ---
with tabs[0]:
    if st.session_state.boleta:
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: black; padding: 20px; border: 2px solid #333; border-radius: 10px; max-width: 400px; margin: auto; font-family: monospace;">
            <center><h2>🦷 BALLARTA</h2></center><hr>
            <p>FECHA: {b['fecha']} | {b['hora']}</p>
            <table style="width: 100%;">
        """
        for i in b['items']: ticket += f"<tr><td>{i['Cantidad']} x {i['Producto']}</td><td style='text-align: right;'>S/ {float(i['Subtotal']):.2f}</td></tr>"
        ticket += f"</table><hr><h3 style='text-align: right;'>TOTAL: S/ {b['total']:.2f}</h3><p>PAGO: {b['metodo']}</p></div>"
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
                if info['Stock'] <= 5: st.error(f"⚠️ ¡STOCK BAJO: {info['Stock']:.0f}!")
                else: st.info(f"📦 Stock: {info['Stock']:.0f} | 💰 S/ {info['Precio']:.2f}")
            with c2: cant = st.number_input("Cant:", min_value=1, value=1)
            if st.button("➕ AÑADIR AL CARRITO", use_container_width=True):
                if cant <= info['Stock']:
                    st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': float(info['Precio']), 'Subtotal': round(float(info['Precio']) * cant, 2)})
                    st.rerun()
                else: st.error("Sin stock suficiente")

        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito))
            total_v = sum(i['Subtotal'] for i in st.session_state.carrito)
            st.markdown(f"<h1 style='color: #2ECC71; text-align: center; border: 2px solid #2ECC71; border-radius: 10px; padding: 10px;'>TOTAL: S/ {total_v:.2f}</h1>", unsafe_allow_html=True)
            metodo = st.radio("Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
            if st.button("🚀 FINALIZAR VENTA", use_container_width=True):
                f, h, _, uid = obtener_tiempo_peru()
                st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total_v, 'metodo': metodo}
                for item in st.session_state.carrito:
                    n_s = int(df_stock[df_stock['Producto'] == item['Producto']]['Stock'].values[0]) - item['Cantidad']
                    tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                    tabla_ventas.put_item(Item={'ID_Venta': f"V-{uid}-{item['Producto'][:2]}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': metodo})
                st.session_state.carrito = []
                st.rerun()

# --- TAB 2: STOCK (CORREGIDO COMANDO MAP) ---
with tabs[1]:
    st.subheader("📦 Stock Actual")
    if not df_stock.empty:
        def style_red(val):
            return 'background-color: #E74C3C; color: white; font-weight: bold' if val <= 5 else ''
        
        # Se usa map() en lugar de applymap() para compatibilidad total
        st.dataframe(df_stock.style.map(style_red, subset=['Stock']).format({"Precio": "S/ {:.2f}", "Stock": "{:.0f}"}), use_container_width=True, hide_index=True)

# --- TAB 3: REPORTES ---
with tabs[2]:
    st.subheader("📊 Reporte Diario")
    _, _, ahora_dt, _ = obtener_tiempo_peru()
    f_bus = st.date_input("Fecha:", ahora_dt).strftime("%d/%m/%Y")
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        df_dia = df_v[df_v['Fecha'] == f_bus].copy()
        if not df_dia.empty:
            df_dia['Total'] = pd.to_numeric(df_dia['Total'])
            ce, cy, cp = df_dia[df_dia['Metodo'] == "💵 Efectivo"]['Total'].sum(), df_dia[df_dia['Metodo'] == "🟢 Yape"]['Total'].sum(), df_dia[df_dia['Metodo'] == "🟣 Plin"]['Total'].sum()
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("EFECTIVO", f"S/ {ce:.2f}"); m2.metric("YAPE", f"S/ {cy:.2f}"); m3.metric("PLIN", f"S/ {cp:.2f}"); m4.metric("TOTAL", f"S/ {df_dia['Total'].sum():.2f}")
            st.dataframe(df_dia.sort_values(by='Hora', ascending=False)[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)

# --- TAB 4: HISTORIAL (BLINDADO TOTAL) ---
with tabs[3]:
    st.subheader("📋 Historial de Movimientos")
    h_data = tabla_auditoria.scan().get('Items', [])
    if h_data:
        df_h = pd.DataFrame(h_data)
        # Si la columna 'Tipo' no existe en registros viejos, se crea automáticamente
        if 'Tipo' not in df_h.columns:
            df_h['Tipo'] = 'INGRESO'
        
        df_h['Sort'] = pd.to_datetime(df_h['Fecha'] + ' ' + df_h['Hora'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        df_h = df_h.sort_values(by='Sort', ascending=False)
        
        st.markdown("### 📥 Ingresos")
        ingresos = df_h[df_h['Tipo'].fillna('INGRESO') != 'ELIMINADO']
        st.dataframe(ingresos[['Fecha', 'Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante']], use_container_width=True, hide_index=True)
        
        st.markdown("### 🗑️ Eliminados")
        eliminados = df_h[df_h['Tipo'] == 'ELIMINADO']
        if not eliminados.empty:
            st.dataframe(eliminados[['Fecha', 'Hora', 'Producto', 'Stock_Resultante']], use_container_width=True, hide_index=True)
        else: st.info("No hay registros de eliminación.")

# --- TAB 5: CARGAR STOCK ---
with tabs[4]:
    st.subheader("📥 Cargar Stock")
    with st.form("carga_stock"):
        p_ex = st.selectbox("Producto existente:", [""] + df_stock['Producto'].tolist())
        p_nu = st.text_input("O Nuevo (Nombre):").upper()
        p_f = p_nu if p_nu else p_ex
        c_i = st.number_input("Cantidad que entra:", min_value=1)
        pr_i = st.number_input("Precio de venta:", min_value=0.1)
        if st.form_submit_button("💾 REGISTRAR"):
            if p_f:
                f, h, _, uid = obtener_tiempo_peru()
                s_a = int(df_stock[df_stock['Producto'] == p_f]['Stock'].values[0]) if p_f in df_stock['Producto'].values else 0
                n_s = s_a + c_i
                tabla_stock.put_item(Item={'Producto': p_f, 'Stock': n_s, 'Precio': str(pr_i)})
                tabla_auditoria.put_item(Item={'ID_Ingreso': f"ING-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_f, 'Cantidad_Entrante': int(c_i), 'Stock_Resultante': int(n_s), 'Tipo': 'INGRESO'})
                st.success(f"✅ Cargado: {p_f}")
                time.sleep(1); st.rerun()

# --- TAB 6: MANTENIMIENTO ---
with tabs[5]:
    st.subheader("🛠️ Mantenimiento")
    if not df_stock.empty:
        p_b = st.selectbox("Eliminar del sistema:", df_stock['Producto'].tolist())
        if st.button("🗑️ ELIMINAR PERMANENTE", use_container_width=True):
            f, h, _, uid = obtener_tiempo_peru()
            s_borrar = int(df_stock[df_stock['Producto'] == p_b]['Stock'].values[0])
            tabla_stock.delete_item(Key={'Producto': p_b})
            tabla_auditoria.put_item(Item={'ID_Ingreso': f"DEL-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_b, 'Cantidad_Entrante': 0, 'Stock_Resultante': s_borrar, 'Tipo': 'ELIMINADO'})
            st.success(f"✅ Eliminado: {p_b}")
            time.sleep(2); st.rerun()
