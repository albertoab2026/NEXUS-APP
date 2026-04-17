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

# --- FUNCIÓN PARA REGISTRAR EN EL HISTORIAL (KARDEX) ---
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
if 'confirmar' not in st.session_state: st.session_state.confirmar = False
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
        st.success("✅ VENTA REALIZADA"); st.balloons()
        st.markdown(f"""<div style="background-color:white;color:black;padding:20px;border:2px solid #333;max-width:350px;margin:auto;font-family:monospace;">
            <h3 style="text-align:center;margin:0;">🦷 DENTAL BALLARTA</h3><p style="text-align:center;margin:0;">{b['fecha']} {b['hora']}</p><hr>
            {''.join([f'<div style="display:flex;justify-content:space-between;"><span>{i["Cantidad"]}x {i["Producto"]}</span><span>S/{float(i["Subtotal"]):.2f}</span></div>' for i in b['items']])}
            <hr><div style="display:flex;justify-content:space-between;"><b>TOTAL:</b><b>S/{float(b['total_neto']):.2f}</b></div>
            <p style="text-align:center;border:1px solid #ccc;margin-top:10px;">PAGO: {b['metodo']}</p></div>""", unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA", use_container_width=True): st.session_state.boleta = None; st.rerun()
    else:
        bus = st.text_input("🔍 Buscar Producto:").upper()
        prod_filt = [p for p in df_inv['Producto'].tolist() if bus in str(p)]
        c1, c2 = st.columns(2)
        p_sel = c1.selectbox("Producto:", prod_filt) if prod_filt else None
        cant = c2.number_input("Cant:", min_value=1, value=1)
        if p_sel:
            row = df_inv[df_inv['Producto'] == p_sel].iloc[0]
            st.info(f"💰 S/ {row['Precio']:.2f} | 📦 Stock: {row['Stock']}")
            if st.button("➕ Añadir al Carrito", use_container_width=True):
                if cant <= row['Stock']:
                    st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': row['Precio'], 'Precio_Compra': row['Precio_Compra'], 'Subtotal': round(row['Precio']*cant, 2)})
                    st.rerun()
                else: st.error("❌ Stock insuficiente")
        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c[['Producto', 'Cantidad', 'Subtotal']])
            m_pago = st.radio("Pago:", ["💵 EFECTIVO", "🟣 YAPE", "🔵 PLIN"], horizontal=True)
            total_b = df_c['Subtotal'].sum()
            rebaja = st.number_input("💸 Rebaja S/:", min_value=0.0, value=0.0)
            total_n = max(0.0, total_b - rebaja)
            st.markdown(f"<h1 style='text-align:center; color:#2ecc71;'>S/ {total_n:.2f}</h1>", unsafe_allow_html=True)
            if st.button("🚀 FINALIZAR VENTA", use_container_width=True, type="primary"):
                f, h, uid = obtener_tiempo_peru()
                for i, item in enumerate(st.session_state.carrito):
                    tabla_ventas.put_item(Item={'TenantID': st.session_state.tenant, 'VentaID': f"V-{uid}-{i}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Precio_Compra': str(item['Precio_Compra']), 'Metodo': m_pago, 'Rebaja': str(rebaja)})
                    n_s = int(df_inv[df_inv['Producto']==item['Producto']]['Stock'].values[0]) - item['Cantidad']
                    tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': item['Producto']}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': n_s})
                st.session_state.boleta = {'items': st.session_state.carrito, 'total_neto': total_n, 'metodo': m_pago, 'fecha': f, 'hora': h}
                st.session_state.carrito = []; st.rerun()
with t2:
    st.subheader("📦 Inventario de Almacén")
    bus_s = st.text_input("🔍 Buscar en stock:", key="f_stock").upper()
    df_f = df_inv[df_inv['Producto'].str.contains(bus_s, na=False)]
    st.dataframe(df_f[['Producto', 'Precio', 'Stock']], use_container_width=True, hide_index=True)

with t3: # REPORTES DE VENTAS
    st.subheader("📊 Reporte de Ventas")
    f_sel = st.date_input("📅 Seleccionar Día:", datetime.now(tz_peru), key="f_rep").strftime("%d/%m/%Y")
    res_v = tabla_ventas.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant) & Attr('Fecha').eq(f_sel))
    v_data = res_v.get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        for col in ['Total', 'Precio_Compra', 'Cantidad']: df_v[col] = pd.to_numeric(df_v[col])
        df_v['Utilidad'] = df_v['Total'] - (df_v['Precio_Compra'] * df_v['Cantidad'])
        c1, c2 = st.columns(2)
        c1.metric("VENTAS TOTALES", f"S/ {df_v['Total'].sum():.2f}")
        c2.metric("UTILIDAD BRUTA", f"S/ {df_v['Utilidad'].sum():.2f}")
        st.dataframe(df_v[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
    else: st.info(f"No hay ventas el {f_sel}")

with t4: # HISTORIAL DE MOVIMIENTOS (KARDEX)
    st.subheader("📋 Historial de Entradas y Ajustes")
    f_h = st.date_input("📅 Consultar Fecha:", datetime.now(tz_peru), key="f_hist").strftime("%d/%m/%Y")
    res_m = tabla_movs.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant) & Attr('Fecha').eq(f_h))
    movs = res_m.get('Items', [])
    if movs:
        df_m = pd.DataFrame(movs).sort_values("Hora", ascending=False)
        st.dataframe(df_m[['Hora', 'Producto', 'Cantidad', 'Tipo']], 
                     use_container_width=True, hide_index=True,
                     column_config={"Tipo": "TIPO DE MOVIMIENTO"})
    else: st.info(f"Sin movimientos registrados el {f_h}")
with t5:
    st.subheader("📥 Cargar Nuevo Stock")
    with st.form("f_carga"):
        p_n = st.text_input("NOMBRE DEL PRODUCTO").upper()
        s_n = st.number_input("CANTIDAD QUE INGRESA", min_value=0)
        pv_n = st.number_input("PRECIO VENTA", min_value=0.0)
        pc_n = st.number_input("PRECIO COMPRA (COSTO)", min_value=0.0)
        if st.form_submit_button("🚀 GUARDAR ENTRADA"):
            if p_n:
                tabla_stock.put_item(Item={'TenantID': st.session_state.tenant, 'Producto': p_n, 'Stock': int(s_n), 'Precio': str(pv_n), 'Precio_Compra': str(pc_n)})
                registrar_kardex(p_n, s_n, "ENTRADA/NUEVO")
                st.success("✅ Stock registrado con éxito"); st.rerun()

with t6:
    st.subheader("🛠️ Ajuste de Inventario")
    if not df_inv.empty:
        p_edit = st.selectbox("Seleccione Producto:", df_inv['Producto'].tolist(), key="p_edit")
        ns = st.number_input("Nuevo Stock Real:", value=0)
        if st.button("✅ ACTUALIZAR STOCK"):
            registrar_kardex(p_edit, ns, "AJUSTE MANUAL")
            tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_edit}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': int(ns)})
            st.success("✅ Ajuste realizado"); st.rerun()

with st.sidebar:
    st.title(f"🏢 {st.session_state.tenant}")
    st.write(f"📅 {datetime.now(tz_peru).strftime('%d/%m/%Y')}")
    st.write("---")
    if st.button("🔴 CERRAR SESIÓN", use_container_width=True):
        st.session_state.auth = False; st.session_state.tenant = None; st.rerun()
