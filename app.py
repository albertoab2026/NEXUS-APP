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
    tabla_movs.put_item(Item={'TenantID': st.session_state.tenant, 'MovID': f"M-{uid}", 'Fecha': f, 'Hora': h, 'Producto': producto, 'Cantidad': int(cantidad), 'Tipo': tipo})

if 'auth' not in st.session_state: st.session_state.auth = False
if 'tenant' not in st.session_state: st.session_state.tenant = None
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'confirmar' not in st.session_state: st.session_state.confirmar = False

if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center; color: #3498db;'>🚀 NEXUS BALLARTA SaaS</h1>", unsafe_allow_html=True)
    auth_multi = st.secrets.get("auth_multi", {"Demo": "tiotuinventario"})
    l_s = st.selectbox("📍 Local:", list(auth_multi.keys()))
    cl = st.text_input("🔑 Contraseña:", type="password")
    if st.button("🔓 INGRESAR", use_container_width=True):
        if cl == "tiotuinventario":
            st.session_state.auth = True; st.session_state.tenant = l_s; st.rerun()
        else: st.error("❌ Clave incorrecta")
    st.stop()
def obtener_datos():
    res = tabla_stock.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant))
    df = pd.DataFrame(res.get('Items', []))
    if df.empty: return pd.DataFrame(columns=['Producto', 'Precio_Compra', 'Precio', 'Stock'])
    for col in ['Stock', 'Precio', 'Precio_Compra']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['Stock'] = df['Stock'].astype(int)
    return df[['Producto', 'Precio_Compra', 'Precio', 'Stock']].sort_values('Producto')

df_inv = obtener_datos()
t1, t2, t3, t4, t5, t6 = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])

with t1:
    if st.session_state.boleta:
        st.snow(); b = st.session_state.boleta
        st.success("✅ VENTA REALIZADA"); st.markdown(f"""<div style="background-color:white;color:black;padding:20px;border:2px solid #333;max-width:350px;margin:auto;font-family:monospace;">
            <h3 style="text-align:center;margin:0;">🦷 DENTAL BALLARTA</h3><p style="text-align:center;margin:0;">{b['fecha']} {b['hora']}</p><hr>
            {''.join([f'<div style="display:flex;justify-content:space-between;"><span>{i["Cantidad"]}x {i["Producto"]}</span><span>S/{i["Subtotal"]:g}</span></div>' for i in b['items']])}
            <hr><div style="display:flex;justify-content:space-between;color:red;"><span>REBAJA:</span><span>- S/{b['rebaja']:g}</span></div>
            <div style="display:flex;justify-content:space-between;font-size:20px;"><b>NETO:</b><b>S/{b['t_neto']:g}</b></div>
            <p style="text-align:center;border:1px solid #ccc;margin-top:10px;font-weight:bold;">PAGO: {b['metodo']}</p></div>""", unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA", use_container_width=True): st.session_state.boleta = None; st.rerun()
    else:
        bus_v = st.text_input("🔍 Buscar:", key="bv").upper()
        p_v = [p for p in df_inv['Producto'].tolist() if bus_v in str(p)]
        c1, c2 = st.columns(2); p_s = c1.selectbox("Producto:", p_v, key="pv") if p_v else None; ct = c2.number_input("Cant:", min_value=1, value=1, key=f"cv_{p_s}")
        if p_s:
            row_v = df_inv[df_inv['Producto'] == p_s].iloc
            st.info(f"💰 Precio: S/ {row_v.Precio:g} | 📦 Stock: {row_v.Stock}")
            if st.button("➕ Añadir al Carrito"):
                if ct <= row_v.Stock:
                    st.session_state.carrito.append({'Producto': p_s, 'Cantidad': int(ct), 'Precio': float(row_v.Precio), 'Precio_Compra': float(row_v.Precio_Compra), 'Subtotal': round(float(row_v.Precio)*ct, 2)})
                    st.rerun()
        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito)[['Producto', 'Cantidad', 'Subtotal']])
            if st.button("🗑️ VACIAR"): st.session_state.carrito = []; st.rerun()
            m_p = st.radio("Método:", ["💵 EFECTIVO", "🟣 YAPE", "🔵 PLIN"], horizontal=True)
            rebaja = st.number_input("💸 Rebaja S/:", min_value=0.0, value=0.0, key="rbj")
            t_b = sum(i['Subtotal'] for i in st.session_state.carrito)
            t_n = max(0.0, t_b - rebaja)
            st.markdown(f"<h1 style='text-align:center; color:#2ecc71; font-size:60px;'>S/ {t_n:g}</h1>", unsafe_allow_html=True)
            if st.button("🚀 FINALIZAR VENTA", use_container_width=True, type="primary"): st.session_state.confirmar = True
            if st.session_state.confirmar:
                st.warning(f"⚠️ ¿Confirmar S/ {t_n:g}?"); cc1, cc2 = st.columns(2)
                if cc1.button("✅ SÍ"):
                    f, h, uid = obtener_tiempo_peru()
                    for i, it in enumerate(st.session_state.carrito):
                        tabla_ventas.put_item(Item={'TenantID': st.session_state.tenant, 'VentaID': f"V-{uid}-{i}", 'Fecha': f, 'Hora': h, 'Producto': it['Producto'], 'Cantidad': int(it['Cantidad']), 'Total': str(it['Subtotal']), 'Precio_Compra': str(it['Precio_Compra']), 'Metodo': m_p, 'Rebaja': str(rebaja)})
                        s_ant = int(df_inv[df_inv['Producto']==it['Producto']].iloc.Stock)
                        tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': it['Producto']}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': s_ant - it['Cantidad']})
                    st.session_state.boleta = {'items': st.session_state.carrito, 't_neto': t_n, 'rebaja': rebaja, 'metodo': m_p, 'fecha': f, 'hora': h}
                    st.session_state.carrito = []; st.session_state.confirmar = False; st.rerun()
                if cc2.button("❌ NO"): st.session_state.confirmar = False; st.rerun()

with t2:
    st.subheader("📦 Consulta de Almacén")
    bus_stock = st.text_input("🔍 Filtrar Stock:", key="bus_s").upper()
    df_f = df_inv[df_inv['Producto'].str.contains(bus_stock, na=False)]
    def r_r(r): return ['color: #ff4b4b; font-weight: bold;'] * len(r) if r.Stock < 5 else [''] * len(r)
    st.dataframe(df_f.style.apply(r_r, axis=1).format({"Precio": "{:g}", "Precio_Compra": "{:g}", "Stock": "{:d}"}), use_container_width=True, hide_index=True)
with t3:
    st.subheader("📊 Reporte Económico")
    f_r = st.date_input("Día:", datetime.now(tz_peru), key="fr").strftime("%d/%m/%Y")
    res_v = tabla_ventas.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant) & Attr('Fecha').eq(f_r))
    v_d = res_v.get('Items', [])
    if v_d:
        df_v = pd.DataFrame(v_d)
        for col in ['Total', 'Precio_Compra', 'Cantidad']: df_v[col] = pd.to_numeric(df_v[col])
        df_v['Inv'] = df_v['Precio_Compra'] * df_v['Cantidad']
        def met(m):
            f = df_v[df_v['Metodo'].str.contains(m, na=False)]; return f['Total'].sum(), f['Total'].sum() - f['Inv'].sum()
        e_t, e_g = met("EFECTIVO"); y_t, y_g = met("YAPE"); p_t, p_g = met("PLIN")
        c1, c2, c3 = st.columns(3)
        c1.metric("💵 EFECTIVO", f"S/ {e_t:g}", f"Ganancia: S/ {e_g:g}"); c2.metric("🟣 YAPE", f"S/ {y_t:g}", f"Ganancia: S/ {y_g:g}"); c3.metric("🔵 PLIN", f"S/ {p_t:g}", f"Ganancia: S/ {p_g:g}")
        st.divider(); st.metric("📈 GANANCIA NETA TOTAL", f"S/ {(df_v['Total'].sum() - df_v['Inv'].sum()):g}")
        st.dataframe(df_v[['Hora', 'Producto', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
    
    st.subheader("🕵️ Alertas de Stock")
    res_m_aud = tabla_movs.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant) & Attr('Fecha').eq(f_r))
    movs_aud = [m for m in res_m_aud.get('Items', []) if any(x in m['Tipo'] for x in ["REPOSICIÓN", "ENTRADA", "PRECIOS"])]
    if movs_aud:
        st.dataframe(pd.DataFrame(movs_aud)[['Hora', 'Producto', 'Tipo']], use_container_width=True, hide_index=True)

with t4:
    st.subheader("📋 Historial")
    f_h = st.date_input("Fecha:", datetime.now(tz_peru), key="fh").strftime("%d/%m/%Y")
    res_m = tabla_movs.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant) & Attr('Fecha').eq(f_h))
    if res_m.get('Items'):
        df_m = pd.DataFrame(res_m.get('Items')).sort_values("Hora", ascending=False)
        st.dataframe(df_m[['Hora', 'Producto', 'Cantidad', 'Tipo']], use_container_width=True, hide_index=True)
with t5:
    st.subheader("📥 Cargar Nuevo Producto")
    with st.form("fn"):
        pn = st.text_input("NOMBRE").upper(); sn = st.number_input("STOCK INICIAL", min_value=1)
        pc_n = st.number_input("PRECIO COMPRA (COSTO)", min_value=0.0); pv_n = st.number_input("PRECIO VENTA", min_value=0.0)
        if st.form_submit_button("🚀 GUARDAR"):
            if pn:
                if not df_inv[df_inv['Producto'] == pn].empty:
                    st.error(f"❌ Ya existe. Use 'MANT.'")
                else:
                    tabla_stock.put_item(Item={'TenantID': st.session_state.tenant, 'Producto': pn, 'Stock': int(sn), 'Precio': str(pv_n), 'Precio_Compra': str(pc_n)})
                    registrar_kardex(pn, sn, "ENTRADA (NUEVO)"); st.success("✅ Guardado"); import time; time.sleep(1); st.rerun()

with t6:
    st.subheader("🛠️ Gestión de Almacén")
    op = st.radio("Acción:", ["➕ REPONER STOCK", "📝 MODIFICAR PRECIOS", "🗑️ ELIMINAR"], horizontal=True)
    bus_m = st.text_input("🔍 Buscar Producto:", key="bm").upper()
    p_m = [p for p in df_inv['Producto'].tolist() if bus_m in str(p)]
    if p_m:
        p_s = st.selectbox("Seleccionar:", p_m, key="psm")
        r_m = df_inv[df_inv['Producto'] == p_s].iloc
        if op == "➕ REPONER STOCK":
            c_m = st.number_input("¿Cuánto entra?", min_value=1, key=f"cm_{p_s}") 
            if st.button("✅ ACTUALIZAR STOCK"):
                n_t = int(r_m.Stock + c_m)
                tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_s}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': n_t})
                registrar_kardex(p_s, c_m, f"REPOSICIÓN: {r_m.Stock} -> {n_t} (+{c_m})")
                st.success(f"✅ ¡Actualizado!"); import time; time.sleep(1); st.rerun()
        elif op == "📝 MODIFICAR PRECIOS":
            c_p1, c_p2 = st.columns(2)
            n_c = c_p1.number_input("Costo:", value=float(r_m.Precio_Compra))
            n_v = c_p2.number_input("Venta:", value=float(r_m.Precio))
            if st.button("💾 GUARDAR PRECIOS"):
                tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_s}, UpdateExpression="SET Precio_Compra = :pc, Precio = :pv", ExpressionAttributeValues={':pc': str(n_c), ':pv': str(n_v)})
                registrar_kardex(p_s, 0, f"NUEVOS PRECIOS: C:{n_c} V:{n_v}")
                st.success("✅ Precios guardados"); import time; time.sleep(1); st.rerun()
        else:
            if st.button(f"🗑️ ELIMINAR {p_s}"):
                tabla_stock.delete_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_s})
                registrar_kardex(p_s, 0, "ELIMINADO"); st.warning("Borrado."); import time; time.sleep(1); st.rerun()

with st.sidebar:
    st.title(f"🏢 {st.session_state.tenant}")
    if st.button("🔴 CERRAR SESIÓN"): st.session_state.auth = False; st.rerun()
