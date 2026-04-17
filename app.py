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

# --- FUNCIÓN KARDEX MEJORADA ---
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
    st.markdown("<h1 style='text-align: center; color: #3498db;'>🚀 NEXUS BALLARTA SaaS</h1>", unsafe_allow_html=True)
    auth_multi = st.secrets.get("auth_multi", {"Demo": "tiotuinventario"})
    local_sel = st.selectbox("📍 Local:", list(auth_multi.keys()))
    clave = st.text_input("🔑 Contraseña:", type="password")
    if st.button("🔓 INGRESAR", use_container_width=True):
        if clave == "tiotuinventario":
            st.session_state.auth = True; st.session_state.tenant = local_sel; st.rerun()
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
        st.snow()
        b = st.session_state.boleta
        st.success("✅ VENTA REALIZADA")
        st.markdown(f"""<div style="background-color:white;color:black;padding:20px;border:2px solid #333;max-width:350px;margin:auto;font-family:monospace;">
            <h3 style="text-align:center;margin:0;">🦷 DENTAL BALLARTA</h3><p style="text-align:center;margin:0;">{b['fecha']} {b['hora']}</p><hr>
            {''.join([f'<div style="display:flex;justify-content:space-between;"><span>{i["Cantidad"]}x {i["Producto"]}</span><span>S/{i["Subtotal"]:g}</span></div>' for i in b['items']])}
            <hr><div style="display:flex;justify-content:space-between;font-size:20px;"><b>NETO:</b><b>S/{b['t_neto']:g}</b></div>
            <p style="text-align:center;border:1px solid #ccc;margin-top:10px;font-weight:bold;">PAGO: {b['metodo']}</p></div>""", unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA", use_container_width=True): st.session_state.boleta = None; st.rerun()
    else:
        bus_v = st.text_input("🔍 Buscar:", key="bv").upper()
        p_v = [p for p in df_inv['Producto'].tolist() if bus_v in str(p)]
        c1, c2 = st.columns(2)
        p_s = c1.selectbox("Producto:", p_v, key="pv") if p_v else None
        ct = c2.number_input("Cant:", min_value=1, value=1, key="cv")
        if p_s:
            row = df_inv[df_inv['Producto'] == p_s].iloc[0]
            st.info(f"💰 S/ {row['Precio']:g} | 📦 Stock: {row['Stock']}")
            if st.button("➕ Añadir"):
                if ct <= row['Stock']:
                    st.session_state.carrito.append({'Producto': p_s, 'Cantidad': int(ct), 'Precio': row['Precio'], 'Precio_Compra': row['Precio_Compra'], 'Subtotal': round(row['Precio']*ct, 2)})
                    st.rerun()
        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito)[['Producto', 'Cantidad', 'Subtotal']])
            if st.button("🗑️ VACIAR CARRITO", type="secondary"): st.session_state.carrito = []; st.rerun()
            m_p = st.radio("Método:", ["💵 EFECTIVO", "🟣 YAPE", "🔵 PLIN"], horizontal=True)
            t_n = sum(i['Subtotal'] for i in st.session_state.carrito)
            st.markdown(f"<h1 style='text-align:center; color:#2ecc71; font-size:50px;'>S/ {t_n:g}</h1>", unsafe_allow_html=True)
            if st.button("🚀 FINALIZAR", use_container_width=True, type="primary"): st.session_state.confirmar = True
            if st.session_state.confirmar:
                st.warning(f"⚠️ ¿Confirmar venta de S/ {t_n:g}?"); c_c1, c_c2 = st.columns(2)
                if c_c1.button("✅ SÍ"):
                    f, h, uid = obtener_tiempo_peru()
                    for i, it in enumerate(st.session_state.carrito):
                        tabla_ventas.put_item(Item={'TenantID': st.session_state.tenant, 'VentaID': f"V-{uid}-{i}", 'Fecha': f, 'Hora': h, 'Producto': it['Producto'], 'Cantidad': int(it['Cantidad']), 'Total': str(it['Subtotal']), 'Precio_Compra': str(it['Precio_Compra']), 'Metodo': m_p})
                        n_s = int(df_inv[df_inv['Producto']==it['Producto']]['Stock'].values[0]) - it['Cantidad']
                        tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': it['Producto']}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': n_s})
                    st.session_state.boleta = {'items': st.session_state.carrito, 't_neto': t_n, 'metodo': m_p, 'fecha': f, 'hora': h}
                    st.session_state.carrito = []; st.session_state.confirmar = False; st.rerun()
                if c_c2.button("❌ NO"): st.session_state.confirmar = False; st.rerun()
with t2:
    st.subheader("📦 Stock Actual")
    def resaltar_rojo(row):
        return ['color: #ff4b4b; font-weight: bold;'] * len(row) if row.Stock < 5 else [''] * len(row)
    st.dataframe(df_inv.style.apply(resaltar_rojo, axis=1).format({"Precio": "{:g}", "Precio_Compra": "{:g}", "Stock": "{:d}"}), use_container_width=True, hide_index=True)

with t3: # REPORTES CON MÉTODOS SEPARADOS
    st.subheader("📊 Reporte Detallado de Ganancias")
    f_r = st.date_input("Día:", datetime.now(tz_peru), key="fr").strftime("%d/%m/%Y")
    res_v = tabla_ventas.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant) & Attr('Fecha').eq(f_r))
    v_d = res_v.get('Items', [])
    if v_d:
        df_v = pd.DataFrame(v_d)
        for col in ['Total', 'Precio_Compra', 'Cantidad']: df_v[col] = pd.to_numeric(df_v[col])
        df_v['Inv'] = df_v['Precio_Compra'] * df_v['Cantidad']
        
        def met(m):
            filtro = df_v[df_v['Metodo'].str.contains(m, na=False)]
            return filtro['Total'].sum(), filtro['Total'].sum() - filtro['Inv'].sum()

        ef_t, ef_g = met("EFECTIVO"); ya_t, ya_g = met("YAPE"); pl_t, pl_g = met("PLIN")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("💵 EFECTIVO", f"S/ {ef_t:g}", f"Ganancia: S/ {ef_g:g}")
        c2.metric("🟣 YAPE", f"S/ {ya_t:g}", f"Ganancia: S/ {ya_g:g}")
        c3.metric("🔵 PLIN", f"S/ {pl_t:g}", f"Ganancia: S/ {pl_g:g}")
        
        st.divider()
        st.metric("📈 GANANCIA NETA TOTAL DEL DÍA", f"S/ {(df_v['Total'].sum() - df_v['Inv'].sum()):g}")
        st.dataframe(df_v[['Hora', 'Producto', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
    else: st.info("Sin ventas.")
with t4:
    st.subheader("📋 Historial de Movimientos")
    f_h = st.date_input("Fecha:", datetime.now(tz_peru), key="fh").strftime("%d/%m/%Y")
    res_m = tabla_movs.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant) & Attr('Fecha').eq(f_h))
    movs = res_m.get('Items', [])
    if movs:
        df_m = pd.DataFrame(movs).sort_values("Hora", ascending=False)
        st.dataframe(df_m[['Hora', 'Producto', 'Cantidad', 'Tipo']], use_container_width=True, hide_index=True)
    else: st.info("Sin movimientos.")

with t5:
    st.subheader("📥 Cargar Nuevo Producto")
    with st.form("fn"):
        pn = st.text_input("NOMBRE").upper(); sn = st.number_input("STOCK", min_value=0); pvn = st.number_input("P. VENTA", min_value=0.0); pcn = st.number_input("P. COSTO", min_value=0.0)
        if st.form_submit_button("🚀 GUARDAR"):
            tabla_stock.put_item(Item={'TenantID': st.session_state.tenant, 'Producto': pn, 'Stock': int(sn), 'Precio': str(pvn), 'Precio_Compra': str(pcn)})
            registrar_kardex(pn, sn, "ENTRADA/NUEVO"); st.success("Guardado"); st.rerun()

with t6:
    st.subheader("🛠️ Gestión de Almacén")
    op = st.radio("Acción:", ["➕ REPONER STOCK", "🗑️ ELIMINAR PRODUCTO"], horizontal=True)
    bus_m = st.text_input("🔍 Buscar producto:", key="bm").upper()
    p_m = [p for p in df_inv['Producto'].tolist() if bus_m in str(p)]
    
    if p_m:
        p_s = st.selectbox("Seleccionar:", p_m, key="psm")
        row_m = df_inv[df_inv['Producto'] == p_s].iloc[0]
        
        if op == "➕ REPONER STOCK":
            c_m = st.number_input("¿Cuánto entra?", min_value=1, key="cm")
            if st.button("✅ ACTUALIZAR"):
                tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_s}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': int(row_m['Stock'] + c_m)})
                registrar_kardex(p_s, c_m, f"REPOSICIÓN (+{c_m})"); st.success("Actualizado"); st.rerun()
        
        else: # ELIMINAR
            st.error(f"⚠️ ¿Seguro que desea ELIMINAR '{p_s}' por completo?")
            if st.button("🗑️ SÍ, ELIMINAR DEFINITIVAMENTE"):
                tabla_stock.delete_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_s})
                registrar_kardex(p_s, 0, "ELIMINADO DEL SISTEMA")
                st.warning("Producto borrado y registrado en historial."); st.rerun()

with st.sidebar:
    st.title(f"🏢 {st.session_state.tenant}")
    if st.button("🔴 CERRAR SESIÓN"): st.session_state.auth = False; st.rerun()
