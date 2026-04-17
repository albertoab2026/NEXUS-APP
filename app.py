import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
from boto3.dynamodb.conditions import Attr
from fpdf import FPDF
import time
import re # Para validar que no metan símbolos raros

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

if 'auth' not in st.session_state: st.session_state.auth = False
if 'rol' not in st.session_state: st.session_state.rol = None
if 'tenant' not in st.session_state: st.session_state.tenant = None
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'confirmar' not in st.session_state: st.session_state.confirmar = False

# --- LOGIN REFORZADO ---
if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center; color: #3498db;'>🚀 NEXUS BALLARTA SaaS</h1>", unsafe_allow_html=True)
    lista_negocios = [k for k in st.secrets["auth_multi"].keys() if not k.endswith("_emp")]
    l_s = st.selectbox("📍 Seleccione su Negocio:", lista_negocios)
    cl = st.text_input("🔑 Contraseña:", type="password", help="Use solo letras y números")
    cl = cl.strip()[:30]
    col_l1, col_l2 = st.columns(2)
    
    def validar_acceso(tipo_rol):
        if not re.match("^[A-Za-z0-9]*$", cl):
            time.sleep(3); st.error("❌ Caracteres no permitidos."); return
        if cl == "": return
        clave_secreta = st.secrets["auth_multi"][l_s] if tipo_rol == "DUEÑO" else st.secrets["auth_multi"].get(f"{l_s}_emp")
        if clave_secreta and cl == str(clave_secreta):
            st.session_state.auth = True; st.session_state.tenant = l_s; st.session_state.rol = tipo_rol; st.rerun()
        else:
            time.sleep(2); st.error(f"❌ Contraseña de {tipo_rol} incorrecta")

    if col_l1.button("🔓 DUEÑO", use_container_width=True): validar_acceso("DUEÑO")
    if col_l2.button("🧑‍💼 EMPLEADO", use_container_width=True): validar_acceso("EMPLEADO")
    st.stop()
def generar_pdf_pro(b, local):
    pdf = FPDF(format=(80, 180))
    pdf.add_page()
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, local.upper(), ln=True, align='C')
    pdf.set_font("Arial", size=9)
    pdf.cell(0, 5, f"FECHA: {b['fecha']}   HORA: {b['hora']}", ln=True, align='C')
    pdf.cell(0, 5, "-"*40, ln=True, align='C')
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(40, 7, " PRODUCTO", 1, 0, 'L', True)
    pdf.cell(20, 7, "CANT", 1, 0, 'C', True)
    pdf.cell(0, 7, "TOTAL ", 1, 1, 'R', True)
    pdf.set_font("Arial", size=9)
    for i in b['items']:
        pdf.cell(40, 6, f" {i['Producto'][:15]}", 1)
        pdf.cell(20, 6, f"{i['Cantidad']}", 1, 0, 'C')
        pdf.cell(0, 6, f"S/ {i['Subtotal']:g} ", 1, 1, 'R')
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 10)
    if b['rebaja'] > 0: pdf.cell(0, 6, f"REBAJA: - S/ {b['rebaja']:g}", ln=True, align='R')
    pdf.cell(0, 8, f"TOTAL NETO: S/ {b['t_neto']:g}", ln=True, align='R')
    pdf.ln(5)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 5, "¡Gracias por su preferencia!", ln=True, align='C')
    pdf.cell(0, 5, "NEXUS BALLARTA SaaS", ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1')

def obtener_datos():
    res = tabla_stock.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant))
    df = pd.DataFrame(res.get('Items', []))
    if df.empty: return pd.DataFrame(columns=['Producto', 'Precio_Compra', 'Precio', 'Stock'])
    for col in ['Stock', 'Precio', 'Precio_Compra']: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['Stock'] = df['Stock'].astype(int)
    return df[['Producto', 'Precio_Compra', 'Precio', 'Stock']].sort_values('Producto')

df_inv = obtener_datos()
paginas = ["🛒 VENTA", "📦 STOCK"]
if st.session_state.rol == "DUEÑO": paginas += ["📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."]
tabs = st.tabs(paginas)

with tabs[0]: # VENTA
    if st.session_state.boleta:
        st.snow(); b = st.session_state.boleta
        st.success("✅ VENTA REALIZADA")
        st.markdown(f"""<div style="background-color:white;color:black;padding:20px;border:2px solid #333;max-width:350px;margin:auto;font-family:monospace;">
            <h3 style="text-align:center;margin:0;">{st.session_state.tenant}</h3><p style="text-align:center;margin:0;">{b['fecha']} {b['hora']}</p><hr>
            {''.join([f'<div style="display:flex;justify-content:space-between;"><span>{i["Cantidad"]}x {i["Producto"]}</span><span>S/{i["Subtotal"]:g}</span></div>' for i in b['items']])}
            <hr><div style="display:flex;justify-content:space-between;color:red;"><span>REBAJA:</span><span>- S/{b['rebaja']:g}</span></div>
            <div style="display:flex;justify-content:space-between;font-size:20px;"><b>NETO:</b><b>S/{b['t_neto']:g}</b></div></div>""", unsafe_allow_html=True)
        pdf_v2 = generar_pdf_pro(b, st.session_state.tenant)
        st.download_button("📥 DESCARGAR BOLETA PDF", pdf_v2, f"Boleta_{b['fecha']}.pdf", "application/pdf", use_container_width=True)
        if st.button("⬅️ NUEVA VENTA", use_container_width=True): st.session_state.boleta = None; st.rerun()
    else:
        bus_v = st.text_input("🔍 Buscar:", key="bv").upper()
        p_v = [p for p in df_inv['Producto'].tolist() if bus_v in str(p)]
        c1, c2 = st.columns(2); p_s = c1.selectbox("Seleccionar:", p_v, key="pv") if p_v else None; ct = c2.number_input("Cant:", min_value=1, value=1, key=f"cv_{p_s}")
        if p_s:
            row_v = df_inv[df_inv['Producto'] == p_s].iloc[0]
            # CANDADO 1: No añadir más de lo disponible considerando el carrito
            ya_en_carrito = sum(i['Cantidad'] for i in st.session_state.carrito if i['Producto'] == p_s)
            disponible = row_v.Stock - ya_en_carrito
            st.info(f"💰 S/ {row_v.Precio:g} | 📦 Disponible: {disponible}")
            if st.button("➕ Añadir"):
                if ct <= disponible:
                    st.session_state.carrito.append({'Producto': p_s, 'Cantidad': int(ct), 'Precio': float(row_v.Precio), 'Precio_Compra': float(row_v.Precio_Compra), 'Subtotal': round(float(row_v.Precio)*ct, 2)})
                    st.rerun()
                else: st.error("❌ Stock insuficiente.")
        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito)[['Producto', 'Cantidad', 'Subtotal']])
            if st.button("🗑️ VACIAR"): st.session_state.carrito = []; st.rerun()
            m_p = st.radio("Pago:", ["💵 EFECTIVO", "🟣 YAPE", "🔵 PLIN"], horizontal=True)
            reb = st.number_input("💸 Rebaja S/:", min_value=0.0, value=0.0, key="rbj")
            t_b = sum(i['Subtotal'] for i in st.session_state.carrito); t_n = max(0.0, t_b - reb)
            st.markdown(f"<h1 style='text-align:center; color:#2ecc71;'>S/ {t_n:g}</h1>", unsafe_allow_html=True)
            if st.button("🚀 FINALIZAR", use_container_width=True, type="primary"): st.session_state.confirmar = True
            if st.session_state.confirmar:
                if st.button("✅ CONFIRMAR COBRO"):
                    f, h, uid = obtener_tiempo_peru()
                    # CANDADO 2: Verificación final en AWS antes de procesar
                    for it in st.session_state.carrito:
                        res_st = tabla_stock.get_item(Key={'TenantID': st.session_state.tenant, 'Producto': it['Producto']})
                        st_real = int(res_st.get('Item', {}).get('Stock', 0))
                        if st_real < it['Cantidad']:
                            st.error(f"❌ ¡Error! El producto {it['Producto']} ya no tiene stock suficiente."); st.stop()
                        tabla_ventas.put_item(Item={'TenantID': st.session_state.tenant, 'VentaID': f"V-{uid}", 'Fecha': f, 'Hora': h, 'Producto': it['Producto'], 'Cantidad': int(it['Cantidad']), 'Total': str(it['Subtotal']), 'Precio_Compra': str(it['Precio_Compra']), 'Metodo': m_p, 'Rebaja': str(reb)})
                        tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': it['Producto']}, UpdateExpression="SET Stock = Stock - :s", ExpressionAttributeValues={':s': it['Cantidad']})
                    st.session_state.boleta = {'items': st.session_state.carrito, 't_neto': t_n, 'rebaja': reb, 'metodo': m_p, 'fecha': f, 'hora': h}
                    st.session_state.carrito = []; st.session_state.confirmar = False; st.rerun()

with tabs[1]: # STOCK
    st.subheader("📦 Consulta de Almacén")
    bus_s = st.text_input("🔍 Filtrar Stock:", key="bus_s").upper()
    df_f = df_inv[df_inv['Producto'].str.contains(bus_s, na=False)]
    def r_r(r):
        if r.Stock <= 0: return ['background-color: #721c24; color: white; font-weight: bold;'] * len(r)
        return ['color: #ff4b4b; font-weight: bold;'] * len(r) if r.Stock < 5 else [''] * len(r)
    st.dataframe(df_f.style.apply(r_r, axis=1).format({"Precio": "{:g}", "Precio_Compra": "{:g}", "Stock": "{:d}"}), use_container_width=True, hide_index=True)

if st.session_state.rol == "DUEÑO":
    with tabs[2]: # REPORTES
        st.subheader("📊 Ganancia Neta")
        f_r = st.date_input("Día:", datetime.now(tz_peru), key="fr").strftime("%d/%m/%Y")
        res_v = tabla_ventas.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant) & Attr('Fecha').eq(f_r))
        v_d = res_v.get('Items', [])
        if v_d:
            df_v = pd.DataFrame(v_d); [df_v.__setitem__(c, pd.to_numeric(df_v[c])) for c in ['Total', 'Precio_Compra', 'Cantidad']]
            df_v['Inv'] = df_v['Precio_Compra'] * df_v['Cantidad']
            def met(m):
                f = df_v[df_v['Metodo'].str.contains(m, na=False)]; return f['Total'].sum(), f['Total'].sum() - f['Inv'].sum()
            e_t, e_g = met("EFECTIVO"); y_t, y_g = met("YAPE"); p_t, p_g = met("PLIN")
            c1, c2, c3 = st.columns(3)
            c1.metric("💵 EFECTIVO", f"S/ {e_t:g}", f"Gana: S/ {e_g:g}"); c2.metric("🟣 YAPE", f"S/ {y_t:g}", f"Gana: S/ {y_g:g}"); c3.metric("🔵 PLIN", f"S/ {p_t:g}", f"Gana: S/ {p_g:g}")
            st.divider(); st.metric("📈 GANANCIA TOTAL", f"S/ {(df_v['Total'].sum() - df_v['Inv'].sum()):g}")
            st.dataframe(df_v[['Hora', 'Producto', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
    with tabs[3]: # HISTORIAL
        st.subheader("📋 Historial Completo")
        f_h = st.date_input("Fecha:", datetime.now(tz_peru), key="fh").strftime("%d/%m/%Y")
        res_m = tabla_movs.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant) & Attr('Fecha').eq(f_h))
        if res_m.get('Items'):
            df_m = pd.DataFrame(res_m.get('Items')).sort_values("Hora", ascending=False)
            st.dataframe(df_m[['Hora', 'Producto', 'Cantidad', 'Tipo']], use_container_width=True, hide_index=True)

def registrar_kardex(producto, cantidad, tipo):
    f, h, uid = obtener_tiempo_peru()
    tabla_movs.put_item(Item={'TenantID': st.session_state.tenant, 'MovID': f"M-{uid}", 'Fecha': f, 'Hora': h, 'Producto': producto, 'Cantidad': int(cantidad), 'Tipo': tipo})

if st.session_state.rol == "DUEÑO":
    with tabs[4]: # CARGAR
        st.subheader("📥 Registro de Producto")
        with st.form("fn"):
            pn = st.text_input("NOMBRE").upper(); sn = st.number_input("STOCK INICIAL", min_value=1)
            pc_n = st.number_input("COSTO", min_value=0.0); pv_n = st.number_input("VENTA", min_value=0.0)
            if st.form_submit_button("🚀 GUARDAR"):
                if pn and df_inv[df_inv['Producto'] == pn].empty:
                    tabla_stock.put_item(Item={'TenantID': st.session_state.tenant, 'Producto': pn, 'Stock': int(sn), 'Precio': str(pv_n), 'Precio_Compra': str(pc_n)})
                    registrar_kardex(pn, sn, "ENTRADA (NUEVO)"); st.success("✅ Guardado"); st.rerun()
                else: st.error("Error: Ya existe o nombre vacío.")

    with tabs[5]: # MANTENIMIENTO
        st.subheader("🛠️ Gestión")
        op = st.radio("Acción:", ["➕ REPONER", "📝 PRECIOS", "🗑️ ELIMINAR"], horizontal=True)
        bus_m = st.text_input("🔍 Buscar:", key="bm").upper()
        p_m = [p for p in df_inv['Producto'].tolist() if bus_m in str(p)]
        if p_m:
            p_s = st.selectbox("Seleccionar:", p_m, key="psm"); idx_m = df_inv[df_inv['Producto'] == p_s].index
            if op == "➕ REPONER":
                c_m = st.number_input("¿Cuánto?", min_value=1, key=f"cm_{p_s}") 
                if st.button("✅ ACTUALIZAR"):
                    n_t = int(df_inv.at[idx_m[0], 'Stock'] + c_m)
                    tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_s}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': n_t})
                    registrar_kardex(p_s, c_m, f"REPOSICIÓN (+{c_m})"); st.success("✅ Hecho"); st.rerun()
            elif op == "📝 PRECIOS":
                nc = st.number_input("Costo:", value=float(df_inv.at[idx_m[0], 'Precio_Compra']))
                nv = st.number_input("Venta:", value=float(df_inv.at[idx_m[0], 'Precio']))
                if st.button("💾 GUARDAR"):
                    tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_s}, UpdateExpression="SET Precio_Compra = :pc, Precio = :pv", ExpressionAttributeValues={':pc': str(nc), ':pv': str(nv)})
                    registrar_kardex(p_s, 0, "CAMBIO PRECIOS"); st.success("✅ Guardado"); st.rerun()
            else:
                if st.button(f"🗑️ ELIMINAR {p_s}"):
                    tabla_stock.delete_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_s})
                    registrar_kardex(p_s, 0, "ELIMINADO"); st.rerun()

with st.sidebar:
    st.title(f"🏢 {st.session_state.tenant}"); st.write(f"Rol: **{st.session_state.rol}**")
    if st.button("🔴 SALIR"): st.session_state.auth = False; st.rerun()
