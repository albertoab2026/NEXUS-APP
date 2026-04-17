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
if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center;'>🚀 NEXUS BALLARTA SaaS</h1>", unsafe_allow_html=True)
    auth_multi = st.secrets.get("auth_multi", {"Demo": "tiotuinventario"})
    local_sel = st.selectbox("Seleccione Local:", list(auth_multi.keys()))
    clave = st.text_input("Contraseña:", type="password")
    if st.button("🔓 Ingresar", use_container_width=True):
        if clave == "tiotuinventario":
            st.session_state.auth = True; st.session_state.tenant = local_sel; st.rerun()
        else: st.error("❌ Clave incorrecta")
    st.stop()

def obtener_datos():
    try:
        res = tabla_stock.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant))
        df = pd.DataFrame(res.get('Items', []))
        if df.empty: return pd.DataFrame(columns=['Producto', 'Precio_Compra', 'Precio', 'Stock'])
        df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
        df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
        df['Precio_Compra'] = pd.to_numeric(df['Precio_Compra'], errors='coerce').fillna(0.0)
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
            {''.join([f'<div style="display:flex;justify-content:space-between;"><span>{i["Cantidad"]}x {i["Producto"]}</span><span>S/{float(i["Subtotal"]):.2f}</span></div>' for i in b['items']])}
            <hr><div style="display:flex;justify-content:space-between;"><b>TOTAL:</b><b>S/{float(b['total_neto']):.2f}</b></div>
            <p style="text-align:center;border:1px solid #ccc;margin-top:10px;">PAGO: {b['metodo']}</p></div>""", unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA"): st.session_state.boleta = None; st.rerun()
    else:
        bus = st.text_input("🔍 Buscar:", key="bus_venta").upper()
        prod_filt = [p for p in df_inv['Producto'].tolist() if bus in str(p)]
        c1, c2 = st.columns(2)
        p_sel = c1.selectbox("Producto:", prod_filt, key="sel_venta") if prod_filt else None
        cant = c2.number_input("Cant:", min_value=1, value=1, key="cant_venta")
        if p_sel:
            row = df_inv[df_inv['Producto'] == p_sel].iloc[0]
            st.info(f"💰 S/ {row['Precio']:.2f} | 📦 Stock: {row['Stock']}")
            if st.button("➕ Añadir"):
                if cant <= row['Stock']:
                    st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': row['Precio'], 'Precio_Compra': row['Precio_Compra'], 'Subtotal': round(row['Precio']*cant, 2)})
                    st.rerun()
        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito)[['Producto', 'Cantidad', 'Subtotal']])
            m_pago = st.radio("Pago:", ["💵 EFECTIVO", "🟣 YAPE", "🔵 PLIN"], horizontal=True, key="pago_radio")
            total_b = sum(i['Subtotal'] for i in st.session_state.carrito)
            rebaja = st.number_input("Rebaja:", min_value=0.0, value=0.0, key="rebaja_input")
            total_n = max(0.0, total_b - rebaja)
            if st.button(f"🚀 FINALIZAR S/ {total_n:.2f}", use_container_width=True, key="fin_btn"):
                f, h, uid = obtener_tiempo_peru()
                for i, item in enumerate(st.session_state.carrito):
                    tabla_ventas.put_item(Item={'TenantID': st.session_state.tenant, 'VentaID': f"V-{uid}-{i}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Precio_Compra': str(item['Precio_Compra']), 'Metodo': m_pago, 'Rebaja': str(rebaja)})
                    n_s = int(df_inv[df_inv['Producto']==item['Producto']]['Stock'].values[0]) - item['Cantidad']
                    tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': item['Producto']}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': n_s})
                st.session_state.boleta = {'items': st.session_state.carrito, 'total_neto': total_n, 'metodo': m_pago, 'fecha': f, 'hora': h}
                st.session_state.carrito = []; st.rerun()
with t2:
    st.subheader("📦 Inventario")
    if not df_inv.empty:
        def resaltar_bajo(row):
            return ['color: #ff4b4b; font-weight: bold;'] * len(row) if row.Stock < 5 else [''] * len(row)
        st.dataframe(df_inv.style.apply(resaltar_bajo, axis=1), use_container_width=True, hide_index=True)

with t3:
    st.subheader("📊 Ganancias")
    f_sel = st.date_input("Día:", datetime.now(tz_peru), key="f_rep").strftime("%d/%m/%Y")
    res_v = tabla_ventas.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant) & Attr('Fecha').eq(f_sel))
    v_data = res_v.get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        for col in ['Total', 'Precio_Compra', 'Cantidad']: df_v[col] = pd.to_numeric(df_v[col])
        ef = df_v[df_v['Metodo'].str.contains("EFECTIVO", na=False)]['Total'].sum()
        ya = df_v[df_v['Metodo'].str.contains("YAPE", na=False)]['Total'].sum()
        pl = df_v[df_v['Metodo'].str.contains("PLIN", na=False)]['Total'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("💵 EFECTIVO", f"S/ {ef:.2f}")
        c2.metric("🟣 YAPE", f"S/ {ya:.2f}")
        c3.metric("🔵 PLIN", f"S/ {pl:.2f}")
        st.divider()
        st.dataframe(df_v[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
    else: st.info("Sin ventas hoy.")

with t4:
    st.subheader("📋 Historial")
    f_h = st.date_input("Fecha:", datetime.now(tz_peru), key="f_h_hist").strftime("%d/%m/%Y")
    res_m = tabla_movs.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant) & Attr('Fecha').eq(f_h))
    movs = res_m.get('Items', [])
    if movs:
        df_m = pd.DataFrame(movs).sort_values("Hora", ascending=False)
        st.dataframe(df_m[['Hora', 'Producto', 'Cantidad', 'Tipo']], use_container_width=True, hide_index=True)
with t5:
    st.subheader("📥 Cargar Nuevo Stock")
    with st.form("f_carga"):
        p_n = st.text_input("PRODUCTO").upper()
        s_n = st.number_input("CANTIDAD", min_value=0)
        pv_n = st.number_input("PRECIO VENTA", min_value=0.0)
        pc_n = st.number_input("PRECIO COMPRA", min_value=0.0)
        if st.form_submit_button("🚀 GUARDAR"):
            if p_n:
                tabla_stock.put_item(Item={'TenantID': st.session_state.tenant, 'Producto': p_n, 'Stock': int(s_n), 'Precio': str(pv_n), 'Precio_Compra': str(pc_n)})
                registrar_kardex(p_n, s_n, "ENTRADA/NUEVO")
                st.success("Registrado"); st.rerun()

with t6:
    st.subheader("🛠️ Reposición")
    st.info("Solo se permite sumar stock.")
    if not df_inv.empty:
        p_edit_m = st.selectbox("Producto:", df_inv['Producto'].tolist(), key="sel_mantenimiento")
        s_actual = int(df_inv[df_inv['Producto'] == p_edit_m]['Stock'].values[0])
        cant_mas = st.number_input("Ingreso:", min_value=1, value=1, key="cant_mantenimiento")
        if st.button("✅ REGISTRAR", key="btn_mantenimiento"):
            nuevo_t = s_actual + cant_mas
            tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_edit_m}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': nuevo_t})
            registrar_kardex(p_edit_m, cant_mas, f"REPOSICIÓN (+{cant_mas})")
            st.success(f"Stock actualizado: {nuevo_t}"); st.rerun()

with st.sidebar:
    st.title(f"🏢 {st.session_state.tenant}")
    if st.button("🔴 CERRAR SESIÓN", key="logout_btn"): st.session_state.auth = False; st.rerun()
