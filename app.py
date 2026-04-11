import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
from io import BytesIO

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

def get_df_stock():
    try:
        items = tabla_stock.scan().get('Items', [])
        if items:
            df = pd.DataFrame(items)
            for col in ['Stock', 'Precio', 'Producto']:
                if col not in df.columns: df[col] = 0 if col != 'Producto' else "Sin Nombre"
            df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
            return df[['Producto', 'Stock', 'Precio']].sort_values(by='Producto')
    except: pass
    return pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

df_stock = get_df_stock()

tabs = st.tabs(["🛒 Venta", "📦 Stock", "📊 Reportes", "📋 Historial", "📥 Cargar", "🛠️ Mant."])

# --- TAB 1: VENTA ---
with tabs[0]:
    if st.session_state.boleta:
        st.balloons()
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: #000; padding: 20px; border: 2px solid #000; border-radius: 10px; max-width: 350px; margin: auto; font-family: monospace;">
            <center>
                <h2 style="margin:0; color: #2E86C1;">BALLARTA</h2>
                <hr>
                <p>{b['fecha']} | {b['hora']}</p>
            </center>
            <table style="width: 100%;">
        """
        for i in b['items']: 
            ticket += f"<tr><td>{i['Cantidad']} x {i['Producto']}</td><td style='text-align:right;'>S/ {i['Subtotal']:.2f}</td></tr>"
            if i['Rebaja'] > 0:
                ticket += f"<tr><td colspan='2' style='font-size:11px; color:red;'>* Rebaja: - S/ {i['Rebaja']:.2f}</td></tr>"
        
        ticket += f"""
            </table>
            <hr>
            <h2 style='text-align: right;'>TOTAL: S/ {b['total']:.2f}</h2>
            <p>PAGO: {b['metodo']}</p>
        </div>
        """
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA", use_container_width=True):
            st.session_state.boleta = None
            st.rerun()
    else:
        if not df_stock.empty:
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                p_sel = st.selectbox("Elegir Producto:", df_stock['Producto'].tolist())
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                precio_fijo = float(info['Precio'])
                # Alerta visual en la venta
                if info['Stock'] <= 5:
                    st.error(f"⚠️ ¡QUEDAN POCOS! Stock: {info['Stock']}")
                else:
                    st.info(f"Precio: S/ {precio_fijo:.2f} | Stock: {info['Stock']}")
            
            with c2: cant = st.number_input("Cantidad:", min_value=1, value=1)
            with c3: rebaja = st.number_input("Rebaja (S/):", min_value=0.0, value=0.0)
            
            subtotal_final = round((precio_fijo * cant) - rebaja, 2)
            st.markdown(f"### Subtotal: S/ {max(0.0, subtotal_final):.2f}")

            if st.button("➕ AÑADIR AL CARRITO", use_container_width=True):
                if cant <= info['Stock']:
                    st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': precio_fijo, 'Rebaja': rebaja, 'Subtotal': subtotal_final})
                    st.rerun()
                else: st.error("Stock insuficiente")

        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito)[['Producto', 'Cantidad', 'Subtotal']])
            total_v = sum(i['Subtotal'] for i in st.session_state.carrito)
            st.markdown(f"<h1 style='color: #2ECC71; text-align: center;'>TOTAL: S/ {total_v:.2f}</h1>", unsafe_allow_html=True)
            
            if st.button("🗑️ VACÍAR"):
                st.session_state.carrito = []
                st.rerun()

            metodo = st.radio("Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
            if st.button("🚀 FINALIZAR", type="primary", use_container_width=True):
                f, h, _, uid = obtener_tiempo_peru()
                st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total_v, 'metodo': metodo}
                for item in st.session_state.carrito:
                    s_actual = int(df_stock[df_stock['Producto'] == item['Producto']]['Stock'].values[0])
                    tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': s_actual - item['Cantidad']})
                    tabla_ventas.put_item(Item={'ID_Venta': f"V-{uid}-{item['Producto'][:2]}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': metodo})
                st.session_state.carrito = []
                st.rerun()

# --- TAB 2: STOCK (CON LETRAS ROJAS) ---
with tabs[1]:
    st.subheader("📦 Inventario")
    if not df_stock.empty:
        # Función para pintar de rojo si es menor o igual a 5
        def resaltado_critico(s):
            return ['color: red; font-weight: bold' if val <= 5 else '' for val in s]
        
        st.dataframe(
            df_stock.style.apply(resaltado_critico, subset=['Stock']).format({"Precio": "S/ {:.2f}"}),
            use_container_width=True, hide_index=True
        )

# --- TAB 3: REPORTES ---
with tabs[2]:
    st.subheader("📊 Caja")
    _, _, ahora_dt, _ = obtener_tiempo_peru()
    f_bus = st.date_input("Día:", ahora_dt).strftime("%d/%m/%Y")
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        df_dia = df_v[df_v['Fecha'] == f_bus].copy() if not df_v.empty else pd.DataFrame()
        if not df_dia.empty:
            df_dia['Total'] = pd.to_numeric(df_dia['Total'])
            st.metric("VENTA TOTAL", f"S/ {df_dia['Total'].sum():.2f}")
            st.dataframe(df_dia[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)

# --- LAS DEMÁS PESTAÑAS ---
with tabs[3]:
    h_data = tabla_auditoria.scan().get('Items', [])
    if h_data: st.dataframe(pd.DataFrame(h_data).sort_values(by='Hora', ascending=False), use_container_width=True, hide_index=True)

with tabs[4]:
    with st.form("c"):
        p_ex = st.selectbox("Existente:", [""] + df_stock['Producto'].tolist())
        p_nu = st.text_input("O Nuevo:").upper().strip()
        p_f = p_ex if p_ex != "" else p_nu
        c_i = st.number_input("Cantidad:", min_value=1)
        pr_i = st.number_input("Precio:", min_value=0.1)
        if st.form_submit_button("REGISTRAR"):
            if p_f:
                f, h, _, uid = obtener_tiempo_peru()
                s_ant = int(df_stock[df_stock['Producto'] == p_f]['Stock'].values[0]) if p_f in df_stock['Producto'].values else 0
                tabla_stock.put_item(Item={'Producto': p_f, 'Stock': s_ant + c_i, 'Precio': str(round(pr_i, 2))})
                tabla_auditoria.put_item(Item={'ID_Ingreso': f"I-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_f, 'Cantidad_Entrante': int(c_i), 'Stock_Resultante': int(s_ant + c_i), 'Tipo': 'INGRESO'})
                st.success("Guardado"); time.sleep(1); st.rerun()

with tabs[5]:
    st.subheader("🛠️ Gestión")
    if not df_stock.empty:
        p_d = st.selectbox("Borrar producto:", df_stock['Producto'].tolist())
        confirm = st.checkbox(f"Seguro de borrar {p_d}")
        if st.button("🗑️ ELIMINAR", type="primary", disabled=not confirm):
            tabla_stock.delete_item(Key={'Producto': p_d})
            st.success("Eliminado"); time.sleep(1); st.rerun()
