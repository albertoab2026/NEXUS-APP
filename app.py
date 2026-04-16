import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
from boto3.dynamodb.conditions import Attr

# --- 0. CONFIGURACIÓN ---
TABLA_STOCK = 'SaaS_Stock_Test'
TABLA_VENTAS = 'SaaS_Ventas_Test'

st.set_page_config(page_title="NEXUS BALLARTA SaaS", layout="wide", page_icon="🚀")
tz_peru = pytz.timezone('America/Lima')

def obtener_tiempo_peru():
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora.strftime("%Y%m%d%H%M%S%f")

try:
    dynamodb = boto3.resource('dynamodb', 
                              region_name=st.secrets["aws"]["aws_region"],
                              aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
                              aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"])
    tabla_stock = dynamodb.Table(TABLA_STOCK)
    tabla_ventas = dynamodb.Table(TABLA_VENTAS)
except Exception as e:
    st.error(f"Error AWS: {e}"); st.stop()
if 'auth' not in st.session_state: st.session_state.auth = False
if 'tenant' not in st.session_state: st.session_state.tenant = None
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'confirmar' not in st.session_state: st.session_state.confirmar = False

if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center;'>🚀 NEXUS BALLARTA SaaS</h1>", unsafe_allow_html=True)
    auth_multi = st.secrets.get("auth_multi", {"Demo": "tiotuinventario"})
    local_sel = st.selectbox("Seleccione Local:", list(auth_multi.keys()))
    clave = st.text_input("Contraseña:", type="password")
    if st.button("🔓 Ingresar", use_container_width=True):
        if clave == "tiotuinventario":
            st.session_state.auth = True
            st.session_state.tenant = local_sel
            st.rerun()
        else: st.error("❌ Clave incorrecta")
    st.stop()

def obtener_datos():
    try:
        res = tabla_stock.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant))
        items = res.get('Items', [])
        df = pd.DataFrame(items)
        if df.empty: return pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'Precio_Compra'])
        df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
        df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
        df['Precio_Compra'] = pd.to_numeric(df['Precio_Compra'], errors='coerce').fillna(0.0)
        return df[['Producto', 'Stock', 'Precio', 'Precio_Compra']].sort_values('Producto')
    except: return pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'Precio_Compra'])

df_inv = obtener_datos()
t1, t2, t3, t4, t5, t6 = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])
with t1:
    if st.session_state.boleta:
        st.balloons()
        b = st.session_state.boleta
        st.success("✅ ¡VENTA REALIZADA!")
        st.markdown(f"""
        <div style="background-color: white; color: black; padding: 20px; border: 2px solid #333; max-width: 350px; margin: auto; font-family: monospace;">
            <h3 style="text-align: center; margin:0;">🦷 DENTAL BALLARTA</h3>
            <p style="text-align: center; font-size: 12px; margin:0;">{b['fecha']} {b['hora']}</p>
            <hr>
            {''.join([f'<div style="display: flex; justify-content: space-between;"><span>{i["Cantidad"]} x {i["Producto"]}</span><span>S/ {float(i["Subtotal"]):.2f}</span></div>' for i in b['items']])}
            <hr>
            <div style="display: flex; justify-content: space-between;"><b>TOTAL:</b> <b>S/ {float(b['total_bruto']):.2f}</b></div>
            <div style="display: flex; justify-content: space-between; color: red;"><span>REBAJA:</span><span>- S/ {float(b['rebaja']):.2f}</span></div>
            <div style="display: flex; justify-content: space-between; font-size: 18px;"><b>NETO:</b> <b>S/ {float(b['total_neto']):.2f}</b></div>
            <p style="text-align: center; margin-top: 10px; font-weight: bold; border: 1px solid #ccc; padding: 5px;">PAGO: {b['metodo']}</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA", use_container_width=True): 
            st.session_state.boleta = None; st.rerun()
    else:
        st.subheader("🛒 Punto de Venta")
        bus = st.text_input("🔍 Buscar Producto:").upper()
        prod_lista = [p for p in df_inv['Producto'].tolist() if bus in str(p)]
        c1, c2 = st.columns(2)
        with c1: p_sel = st.selectbox("Seleccionar:", prod_lista) if prod_lista else None
        with c2: cant = st.number_input("Cant:", min_value=1, value=1, key=f"cant_{p_sel}" if p_sel else "cant_none")
        
        if p_sel and not df_inv[df_inv['Producto'] == p_sel].empty:
            info = df_inv[df_inv['Producto'] == p_sel].iloc[0]
            st.info(f"💰 Precio: S/ {float(info['Precio']):.2f} | 📦 Stock: {int(info['Stock'])}")
            if st.button("➕ Añadir al Carrito", use_container_width=True):
                if cant <= info['Stock']:
                    st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': float(info['Precio']), 'Precio_Compra': float(info['Precio_Compra']), 'Subtotal': round(float(info['Precio']) * cant, 2)})
                    st.rerun()
                else: st.error("❌ Stock insuficiente")
        
        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            df_c['Subtotal_V'] = df_c['Subtotal'].map('{:.2f}'.format)
            st.table(df_c[['Producto', 'Cantidad', 'Subtotal_V']])
            total_bruto = sum(i['Subtotal'] for i in st.session_state.carrito)
            m_pago = st.radio("Pago:", ["💵 EFECTIVO", "🟣 YAPE", "🔵 PLIN"], horizontal=True, label_visibility="collapsed")
            rebaja = st.number_input("💸 Rebaja S/:", min_value=0.0, step=0.5, value=0.0)
            total_neto = max(0.0, total_bruto - rebaja)
            st.markdown(f"<h1 style='text-align:center; color:#2ecc71;'>S/ {total_neto:.2f}</h1>", unsafe_allow_html=True)
            if st.button("🚀 FINALIZAR COMPRA", use_container_width=True, type="primary"): st.session_state.confirmar = True
            if st.session_state.confirmar:
                st.warning(f"⚠️ ¿Confirmar venta de S/ {total_neto:.2f}?")
                cc1, cc2 = st.columns(2)
                if cc1.button("✅ SÍ, PROCESAR", use_container_width=True):
                    f, h, uid = obtener_tiempo_peru()
                    for i, item in enumerate(st.session_state.carrito):
                        tabla_ventas.put_item(Item={'TenantID': st.session_state.tenant, 'VentaID': f"V-{uid}-{i}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Precio_Compra': str(item['Precio_Compra']), 'Metodo': m_pago, 'Rebaja': str(rebaja)})
                        n_s = int(df_inv[df_inv['Producto'] == item['Producto']]['Stock'].values[0]) - item['Cantidad']
                        tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': item['Producto']}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': n_s})
                    st.session_state.boleta = {'items': st.session_state.carrito, 'total_bruto': total_bruto, 'rebaja': rebaja, 'total_neto': total_neto, 'metodo': m_pago, 'fecha': f, 'hora': h}
                    st.session_state.carrito = []; st.session_state.confirmar = False; st.rerun()
                if cc2.button("❌ NO, CANCELAR", use_container_width=True): st.session_state.confirmar = False; st.rerun()
with t2:
    st.subheader("📦 Inventario de Almacén")
    bus_stock = st.text_input("🔍 Buscar en stock:", key="bus_stock").upper()
    if not df_inv.empty:
        df_f = df_inv[df_inv['Producto'].str.contains(bus_stock, na=False)].copy()
        # Mostramos nombres Pro en la tabla pero usamos los reales para el código
        df_f.columns = ['NOMBRE DEL PRODUCTO', 'STOCK ACTUAL', 'P. VENTA (S/)', 'P. COMPRA (S/)']
        st.dataframe(df_f, use_container_width=True, hide_index=True)
    else: st.info("Inventario vacío.")

with t3: st.info("📊 Reportes próximamente.")
with t4: st.info("📋 Historial próximamente.")
with t5:
    with st.form("carga"):
        p_n = st.text_input("Producto").upper()
        s_n = st.number_input("Stock", min_value=0)
        pr_n = st.number_input("Precio Venta", min_value=0.0); pc_n = st.number_input("Precio Compra", min_value=0.0)
        if st.form_submit_button("Guardar"):
            if p_n:
                tabla_stock.put_item(Item={'TenantID': st.session_state.tenant, 'Producto': p_n, 'Stock': int(s_n), 'Precio': str(pr_n), 'Precio_Compra': str(pc_n)})
                st.success("Guardado"); st.rerun()
with t6:
    if not df_inv.empty:
        p_edit = st.selectbox("Editar:", df_inv['Producto'].tolist())
        ns = st.number_input("Nuevo Stock", value=0)
        if st.button("Actualizar Stock"):
            tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_edit}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': int(ns)})
            st.success("Actualizado"); st.rerun()
        if st.button("🗑️ Eliminar"):
            tabla_stock.delete_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_edit})
            st.error("Eliminado"); st.rerun()
