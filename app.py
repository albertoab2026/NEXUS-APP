import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
from boto3.dynamodb.conditions import Attr

# --- 0. CONFIGURACIÓN ---
TABLA_STOCK = 'SaaS_Stock_Test'
TABLA_VENTAS = 'SaaS_Ventas_Test'
TABLA_MOVS = 'SaaS_Movimientos_Test'

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
    tabla_movs = dynamodb.Table(TABLA_MOVS)
except Exception as e:
    st.error(f"Error AWS: {e}"); st.stop()

def registrar_kardex(producto, cantidad, tipo):
    f, h, uid = obtener_tiempo_peru()
    tabla_movs.put_item(Item={
        'TenantID': st.session_state.tenant,
        'MovID': f"M-{uid}",
        'Fecha': f, 'Hora': h,
        'Producto': producto,
        'Cantidad': int(cantidad),
        'Tipo': tipo
    })

if 'auth' not in st.session_state: st.session_state.auth = False
if 'tenant' not in st.session_state: st.session_state.tenant = None
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
def obtener_datos():
    try:
        res = tabla_stock.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant))
        df = pd.DataFrame(res.get('Items', []))
        if df.empty: return pd.DataFrame(columns=['Producto', 'Precio_Compra', 'Precio', 'Stock'])
        df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
        df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0).round(2)
        df['Precio_Compra'] = pd.to_numeric(df['Precio_Compra'], errors='coerce').fillna(0.0).round(2)
        return df[['Producto', 'Precio_Compra', 'Precio', 'Stock']].sort_values('Producto')
    except: return pd.DataFrame(columns=['Producto', 'Precio_Compra', 'Precio', 'Stock'])

df_inv = obtener_datos()
t1, t2, t3, t4, t5, t6 = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])

with t1:
    if st.session_state.boleta:
        b = st.session_state.boleta
        st.success("✅ VENTA REALIZADA")
        st.markdown(f"""<div style="background-color:white;color:black;padding:20px;border:2px solid #333;max-width:350px;margin:auto;font-family:monospace;">
            <h3 style="text-align:center;">🦷 DENTAL BALLARTA</h3><p style="text-align:center;">{b['fecha']} {b['hora']}</p><hr>
            {''.join([f'<div style="display:flex;justify-content:space-between;"><span>{i["Cantidad"]}x {i["Producto"]}</span><span>S/{i["Subtotal"]:g}</span></div>' for i in b['items']])}
            <hr><div style="display:flex;justify-content:space-between;"><b>TOTAL:</b><b>S/{b['total_neto']:g}</b></div>
            <p style="text-align:center;border:1px solid #ccc;margin-top:10px;">PAGO: {b['metodo']}</p></div>""", unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA"): st.session_state.boleta = None; st.rerun()
    else:
        bus = st.text_input("🔍 Buscar Producto:", key="bus_v").upper()
        prod_f = [p for p in df_inv['Producto'].tolist() if bus in str(p)]
        c1, c2 = st.columns([3, 1])
        p_sel = c1.selectbox("Seleccionar:", prod_f, key="p_v") if prod_f else None
        cant = c2.number_input("Cant:", min_value=1, value=1, key="c_v")
        if p_sel:
            row = df_inv[df_inv['Producto'] == p_sel].iloc[0]
            st.info(f"💰 S/ {row['Precio']:g} | 📦 Stock: {row['Stock']}")
            if st.button("➕ Añadir", use_container_width=True):
                if cant <= row['Stock']:
                    st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': row['Precio'], 'Precio_Compra': row['Precio_Compra'], 'Subtotal': round(row['Precio']*cant, 2)})
                    st.rerun()
        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito)[['Producto', 'Cantidad', 'Subtotal']])
            m_pago = st.radio("Pago:", ["💵 EFECTIVO", "🟣 YAPE", "🔵 PLIN"], horizontal=True, key="pg")
            total_b = sum(i['Subtotal'] for i in st.session_state.carrito)
            rebaja = st.number_input("Rebaja:", min_value=0.0, value=0.0, key="rb")
            total_n = max(0.0, total_b - rebaja)
            if st.button(f"🚀 COBRAR S/ {total_n:g}", use_container_width=True, key="fin"):
                f, h, uid = obtener_tiempo_peru()
                for i, item in enumerate(st.session_state.carrito):
                    tabla_ventas.put_item(Item={'TenantID': st.session_state.tenant, 'VentaID': f"V-{uid}-{i}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Precio_Compra': str(item['Precio_Compra']), 'Metodo': m_pago, 'Rebaja': str(rebaja)})
                    n_s = int(df_inv[df_inv['Producto']==item['Producto']]['Stock'].values[0]) - item['Cantidad']
                    tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': item['Producto']}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': n_s})
                st.session_state.boleta = {'items': st.session_state.carrito, 'total_neto': total_n, 'metodo': m_pago, 'fecha': f, 'hora': h}
                st.session_state.carrito = []; st.rerun()
with t3: # REPORTES PROFESIONALES
    st.subheader("📊 Balance Económico")
    f_sel = st.date_input("Día:", datetime.now(tz_peru), key="f_r").strftime("%d/%m/%Y")
    res_v = tabla_ventas.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant) & Attr('Fecha').eq(f_sel))
    v_data = res_v.get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        for col in ['Total', 'Precio_Compra', 'Cantidad']: df_v[col] = pd.to_numeric(df_v[col])
        
        ventas_totales = df_v['Total'].sum()
        inversion_total = (df_v['Precio_Compra'] * df_v['Cantidad']).sum()
        ganancia_real = ventas_totales - inversion_total
        
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 VENTAS TOTALES", f"S/ {ventas_totales:g}")
        c2.metric("📦 INVERSIÓN (Costo)", f"S/ {inversion_total:g}", delta_color="inverse")
        c3.metric("📈 GANANCIA NETA", f"S/ {ganancia_real:g}")
        
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.markdown(f"**EFECTIVO:** S/ {df_v[df_v['Metodo'].str.contains('EFECTIVO', na=False)]['Total'].sum():g}")
        m2.markdown(f"**YAPE:** S/ {df_v[df_v['Metodo'].str.contains('YAPE', na=False)]['Total'].sum():g}")
        m3.markdown(f"**PLIN:** S/ {df_v[df_v['Metodo'].str.contains('PLIN', na=False)]['Total'].sum():g}")
        st.dataframe(df_v[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
    else: st.info("Sin datos hoy.")
with t6: # MANTENIMIENTO CON BUSCADOR
    st.subheader("🛠️ Reposición Rápida")
    st.caption("Escribe el nombre del producto para filtrarlo rápidamente.")
    if not df_inv.empty:
        bus_m = st.text_input("🔍 Escriba el producto a buscar:", key="b_m").upper()
        prod_m = [p for p in df_inv['Producto'].tolist() if bus_m in str(p)]
        
        if prod_m:
            p_sel_m = st.selectbox("Confirmar Producto:", prod_m, key="p_m_s")
            row_m = df_inv[df_inv['Producto'] == p_sel_m].iloc[0]
            st.warning(f"Stock actual de {p_sel_m}: {row_m['Stock']}")
            
            cant_mas = st.number_input("¿Cuánto ingresa?", min_value=1, value=1, key="c_m_m")
            if st.button("✅ REGISTRAR INGRESO", use_container_width=True, key="b_m_r"):
                nuevo_t = int(row_m['Stock']) + cant_mas
                tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_sel_m}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': nuevo_t})
                registrar_kardex(p_sel_m, cant_mas, f"REPOSICIÓN (+{cant_mas})")
                st.success("¡Stock actualizado!"); st.rerun()
        else: st.error("No se encontró ese producto.")

with st.sidebar:
    if st.session_state.auth:
        st.title(f"🏢 {st.session_state.tenant}")
        if st.button("🔴 CERRAR SESIÓN", key="lo"): st.session_state.auth = False; st.rerun()
