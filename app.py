import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time

# 1. CONFIGURACIÓN E INTERFAZ
st.set_page_config(page_title="Sistema Dental BALLARTA", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora, ahora.strftime("%Y%m%d%H%M%S%f")

# 2. CONEXIÓN AWS DYNAMODB
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

# 3. CONTROL DE ESTADOS
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'reset_v' not in st.session_state: st.session_state.reset_v = 0

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

# Obtener Stock actualizado
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

tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])

# 1. PESTAÑA DE VENTAS
with tabs[0]:
    if st.session_state.boleta:
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: #000; padding: 20px; border: 2px solid #000; border-radius: 10px; max-width: 350px; margin: auto; font-family: monospace;">
            <center><b>BALLARTA DENTAL</b><br>{b['fecha']} {b['hora']}</center>
            <hr>
            <table style="width: 100%;">
        """
        for i in b['items']:
            ticket += f"<tr><td>{i['Cantidad']}</td><td>{i['Producto']}</td><td style='text-align: right;'>S/ {i['Subtotal']:.2f}</td></tr>"
        ticket += f"</table><hr><div style='text-align: right;'><b>TOTAL: S/ {b['total_neto']:.2f}</b></div></div>"
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA"):
            st.session_state.boleta = None
            st.rerun()
    else:
        c1, c2 = st.columns([3, 1])
        with c1:
            p_sel = st.selectbox("Producto:", df_stock['Producto'].tolist(), key="p_venta", 
                               on_change=lambda: st.session_state.update({"reset_v": st.session_state.reset_v + 1}))
            info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
            st.info(f"Precio: S/ {info['Precio']:.2f} | Stock: {info['Stock']}")
        with c2:
            cant = st.number_input("Cantidad:", min_value=1, value=1, key=f"v_{st.session_state.reset_v}")
        
        if st.button("➕ AÑADIR", use_container_width=True):
            if cant <= info['Stock']:
                st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': float(info['Precio']), 'Subtotal': round(float(info['Precio']) * cant, 2)})
                st.rerun()
            else: st.error("Sin stock suficiente")

        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c.style.format({"Precio": "{:.2f}", "Subtotal": "{:.2f}"}))
            t_bruto = df_c['Subtotal'].sum()
            rebaja = st.number_input("Rebaja (S/):", min_value=0.0, value=0.0)
            t_final = max(0.0, t_bruto - rebaja)
            st.success(f"TOTAL: S/ {t_final:.2f}")
            if st.button("🚀 COBRAR"):
                f, h, _, uid = obtener_tiempo_peru()
                st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total_neto': t_final, 'total_bruto': t_bruto, 'rebaja_total': rebaja, 'metodo': "Efectivo"}
                for idx, item in enumerate(st.session_state.carrito):
                    n_s = int(df_stock[df_stock['Producto'] == item['Producto']]['Stock'].values[0]) - item['Cantidad']
                    tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                    v_db = item['Subtotal'] - rebaja if idx == 0 else item['Subtotal']
                    tabla_ventas.put_item(Item={'ID_Venta': f"V-{uid}-{idx}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(round(max(0, v_db), 2))})
                st.session_state.carrito = []
                st.rerun()

# 2. PESTAÑA DE STOCK (CON MAP PARA EVITAR ERROR)
with tabs[1]:
    st.subheader("📦 Inventario")
    if not df_stock.empty:
        st.dataframe(df_stock.style.map(lambda x: 'color: red; font-weight: bold' if x <= 5 else '', subset=['Stock']).format({"Precio": "S/ {:.2f}"}), use_container_width=True, hide_index=True)

# 3. REPORTES (ORDENADOS)
with tabs[2]:
    st.subheader("📊 Ventas")
    f_bus = st.date_input("Fecha:").strftime("%d/%m/%Y")
    ventas = tabla_ventas.scan().get('Items', [])
    if ventas:
        df_v = pd.DataFrame(ventas)
        df_hoy = df_v[df_v['Fecha'] == f_bus].copy() if not df_v.empty else pd.DataFrame()
        if not df_hoy.empty:
            df_hoy = df_hoy.sort_values(by='Hora', ascending=False)
            st.metric("Total", f"S/ {pd.to_numeric(df_hoy['Total']).sum():.2f}")
            st.dataframe(df_hoy[['Hora', 'Producto', 'Cantidad', 'Total']], hide_index=True, use_container_width=True)

# 4. HISTORIAL
with tabs[3]:
    h_data = tabla_auditoria.scan().get('Items', [])
    if h_data:
        st.dataframe(pd.DataFrame(h_data).sort_values(by=['Fecha', 'Hora'], ascending=False), use_container_width=True, hide_index=True)

# 5. CARGAR STOCK (CORREGIDO PARA NUEVOS)
with tabs[4]:
    st.subheader("📥 Cargar Stock")
    
    # Elección clara: O uno existente o uno nuevo
    modo = st.radio("Tipo de ingreso:", ["Producto Existente", "Nuevo Producto"], horizontal=True)
    
    with st.form("form_carga_final"):
        if modo == "Producto Existente":
            p_final = st.selectbox("Elegir producto:", df_stock['Producto'].tolist())
            p_precio_sug = df_stock[df_stock['Producto'] == p_final]['Precio'].values[0] if p_final in df_stock['Producto'].values else 10.0
        else:
            p_final = st.text_input("Nombre del Nuevo Producto:").upper().strip()
            p_precio_sug = 1.0

        p_cant = st.number_input("Cantidad a sumar:", min_value=1, value=1)
        p_precio = st.number_input("Precio de venta:", min_value=0.1, value=float(p_precio_sug))
        
        if st.form_submit_button("REGISTRAR INGRESO"):
            if p_final:
                f, h, _, uid = obtener_tiempo_peru()
                s_ant = int(df_stock[df_stock['Producto'] == p_final]['Stock'].values[0]) if p_final in df_stock['Producto'].values else 0
                n_total = s_ant + p_cant
                
                tabla_stock.put_item(Item={'Producto': p_final, 'Stock': n_total, 'Precio': str(round(p_precio, 2))})
                tabla_auditoria.put_item(Item={'ID_Ingreso': f"I-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_final, 'Cantidad_Entrante': int(p_cant), 'Stock_Resultante': int(n_total)})
                
                st.success(f"¡{p_final} actualizado!")
                time.sleep(1)
                st.cache_data.clear() # Limpia para que aparezca en el menú de ventas
                st.rerun()
            else: st.error("Falta el nombre")

# 6. MANTENIMIENTO
with tabs[5]:
    p_b = st.selectbox("Borrar:", [""] + df_stock['Producto'].tolist(), key="borrar_key")
    if st.button("🗑️ ELIMINAR") and p_b != "":
        tabla_stock.delete_item(Key={'Producto': p_b})
        st.rerun()
