import streamlit as st
import pandas as pd
import boto3
from datetime import datetime, timedelta
import pytz
from boto3.dynamodb.conditions import Attr, Key
from fpdf import FPDF
import time
import re
import urllib.parse
from decimal import Decimal, ROUND_HALF_UP
import io
import uuid

# === CONFIG ===
TABLA_STOCK = st.secrets["tablas"]["stock"]
TABLA_VENTAS = st.secrets["tablas"]["ventas"]
TABLA_MOVS = st.secrets["tablas"]["movs"]
TABLA_TENANTS = st.secrets["tablas"]["tenants"]
TABLA_CIERRES = st.secrets["tablas"]["cierres"]
TABLA_PAGOS = st.secrets["tablas"]["pagos"]
NUMERO_SOPORTE = "51914282688"
YAPE_SOPORTE = "Alberto Ballarta"
DESARROLLADOR = "Alberto Ballarta - Software Engineer"

st.set_page_config(page_title="NEXUS BALLARTA", layout="wide", page_icon="🚀")
tz_peru = pytz.timezone('America/Lima')

st.markdown("""
    <style>
        [data-testid="stSidebar"][aria-expanded="true"] {min-width: 300px;}
    </style>
""", unsafe_allow_html=True)

def to_decimal(f): return Decimal(str(f)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def obtener_tiempo_peru():
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora.strftime("%Y%m%d%H%M%S%f")

# === AWS ===
dynamodb = boto3.resource('dynamodb',
    region_name=st.secrets["aws"]["aws_region"],
    aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
    aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"])
tabla_stock = dynamodb.Table(TABLA_STOCK)
tabla_ventas = dynamodb.Table(TABLA_VENTAS)
tabla_movs = dynamodb.Table(TABLA_MOVS)
tabla_tenants = dynamodb.Table(TABLA_TENANTS)
tabla_cierres = dynamodb.Table(TABLA_CIERRES)
tabla_pagos = dynamodb.Table(TABLA_PAGOS)

# === FUNCIONES CORE ===
def verificar_suscripcion(tid):
    try:
        t = tabla_tenants.get_item(Key={'TenantID': tid}).get('Item', {})
        if t.get('EstadoPago') == 'SUSPENDIDO': return False, "SUSPENDIDO"
        fc = datetime.strptime(t.get('ProximoCobro', '01/01/2000'), '%d/%m/%Y').date()
        if fc < datetime.now(tz_peru).date() - timedelta(days=5): return False, f"VENCIDO {t.get('ProximoCobro')}"
        return True, "ACTIVO"
    except: return True, "ERROR"

def contarProductosEnBD():
    try: return tabla_stock.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant), Select='COUNT').get('Count', 0)
    except: return 9999

@st.cache_data(ttl=10)
def obtener_datos():
    try:
        res = tabla_stock.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant), Limit=2000)
        items = res.get('Items', [])
        if not items: return pd.DataFrame(columns=['Producto', 'Precio_Compra', 'Precio', 'Stock'])
        df = pd.DataFrame(items)
        for col in ['Producto', 'Precio_Compra', 'Precio', 'Stock']:
            if col not in df.columns: df[col] = 0 if col!='Producto' else ''
        df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
        df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
        df['Precio_Compra'] = pd.to_numeric(df['Precio_Compra'], errors='coerce').fillna(0.0)
        df['Producto'] = df['Producto'].astype(str)
        return df[['Producto', 'Precio_Compra', 'Precio', 'Stock']].sort_values('Producto')
    except Exception as e:
        print(f"ERROR obtener_datos: {e}")
        return pd.DataFrame(columns=['Producto', 'Precio_Compra', 'Precio', 'Stock'])

def registrar_kardex(prod, cant, tipo, total=0, pc=0, metodo=""):
    f, h, uid = obtener_tiempo_peru()
    tabla_movs.put_item(Item={
        'TenantID': st.session_state.tenant, 'MovID': f"M-{uid}", 'Fecha': f, 'Hora': h,
        'FechaISO': datetime.now(tz_peru).strftime("%Y-%m-%d"), 'Producto': prod, 'Cantidad': int(cant),
        'Total': to_decimal(total), 'Precio_Compra': to_decimal(pc), 'Metodo': str(metodo), 'Tipo': tipo, 'Usuario': st.session_state.usuario
    })

def registrar_cierre(total, u_turno, tipo, u_cierre, fecha=None):
    f, h, uid = obtener_tiempo_peru()
    if fecha: f = fecha
    tabla_cierres.put_item(Item={
        'TenantID': st.session_state.tenant, 'CierreID': f"C-{uid}", 'Fecha': f, 'Hora': h,
        'UsuarioTurno': u_turno, 'UsuarioCierre': u_cierre, 'Total': to_decimal(total), 'Tipo': tipo
    })

def obtener_limites_tenant():
    item = tabla_tenants.get_item(Key={'TenantID': st.session_state.tenant}).get('Item', {})
    if not item: st.error("Tenant no existe"); st.stop()
    if item.get('EstadoPago') == 'SUSPENDIDO': st.error(f"⛔ SUSPENDIDO. WhatsApp +{NUMERO_SOPORTE}"); st.stop()
    fc = datetime.strptime(item.get('ProximoCobro', '01/01/2000'), '%d/%m/%Y').date()
    if fc < datetime.now(tz_peru).date() - timedelta(days=5): st.error(f"⛔ VENCIÓ {item.get('ProximoCobro')}"); st.stop()
    max_p, max_s = int(item.get('MaxProductos', 0)), int(item.get('MaxStock', 0))
    if max_p == 0: st.error("Configura MaxProductos"); st.stop()
    df_temp = obtener_datos()
    stock_max = int(df_temp['Stock'].max()) if not df_temp.empty else 0
    if contarProductosEnBD() > max_p or stock_max > max_s:
        st.session_state.modo_lectura = True
        st.session_state.mensaje_lectura = f"⚠️ MODO LECTURA: Pasado de límites"
    else: st.session_state.modo_lectura = False
    return max_p, max_s, item.get('Plan', 'SIN_PLAN'), item.get('PrecioMensual', 0)

def tiene_whatsapp_habilitado():
    try: return tabla_tenants.get_item(Key={'TenantID': st.session_state.tenant}).get('Item', {}).get('WhatsApp', False) or PLAN_ACTUAL in ["PRO", "PREMIUM"]
    except: return PLAN_ACTUAL in ["PRO", "PREMIUM"]

# === ESTADO ===
for k in ['auth','rol','tenant','usuario','carrito','boleta','confirmar','modo_lectura']:
    if k not in st.session_state: st.session_state[k] = [] if k=='carrito' else False if k in ['auth','confirmar','modo_lectura'] else None
# === LOGIN ===
if not st.session_state.auth:
    st.markdown("<h1 style='text-align:center;color:#3498db;'>🚀 NEXUS BALLARTA</h1>", unsafe_allow_html=True)
    st.caption(f"<center>{DESARROLLADOR}</center>", unsafe_allow_html=True)
    tenants = [k for k in st.secrets if k not in ["tablas", "aws"] and not k.endswith("_emp")]
    t_sel = st.selectbox("📍 Negocio:", [t.replace("_", " ") for t in tenants])
    t_key = t_sel.replace(" ", "_")
    clave = st.text_input("🔑 Contraseña:", type="password").strip()[:30]
    col1, col2 = st.columns(2)
    if col1.button("🔓 DUEÑO", use_container_width=True):
        if clave == str(st.secrets[t_key]["clave"]):
            st.session_state.update({'auth':True,'tenant':t_sel,'rol':'DUEÑO','usuario':'DUEÑO'}); st.rerun()
        else: st.error("❌ Incorrecta")
    with col2:
        nombre = st.text_input("👤 Tu nombre:", max_chars=20).upper().strip()
        if st.button("🧑‍💼 EMPLEADO", use_container_width=True):
            if nombre and clave == str(st.secrets[f"{t_key}_emp"]["clave"]):
                st.session_state.update({'auth':True,'tenant':t_sel,'rol':'EMPLEADO','usuario':nombre}); st.rerun()
            else: st.error("❌ Nombre o clave incorrecta")
    st.stop()

# === POST LOGIN ===
MAX_PRODUCTOS_TOTALES, MAX_STOCK_POR_PRODUCTO, PLAN_ACTUAL, PRECIO_ACTUAL = obtener_limites_tenant()
df_inv = obtener_datos()
if st.session_state.get('modo_lectura', False): st.warning(st.session_state.mensaje_lectura)

# === TABS ===
tabs_list = ["🛒 VENTA", "📦 STOCK", "📊 REPORTES"]
if st.session_state.rol == "DUEÑO" and not st.session_state.get('modo_lectura', False):
    tabs_list += ["📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."]
tabs = st.tabs(tabs_list)
# === TAB VENTA ===
with tabs[0]:
    # === VERIFICAR SI YA CERRÓ CAJA HOY ===
    f_hoy, h_hoy, _ = obtener_tiempo_peru()
    res_cierre = tabla_cierres.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant), FilterExpression=Attr('Fecha').eq(f_hoy) & Attr('UsuarioTurno').eq(st.session_state.usuario))
    ya_cerro = len(res_cierre.get('Items', [])) > 0
    hora_cierre = max([c['Hora'] for c in res_cierre.get('Items', [])]) if ya_cerro else None

    if ya_cerro:
        st.warning(f"⚠️ YA CERRASTE CAJA HOY A LAS {hora_cierre}")
        st.info("Las ventas que hagas ahora son POST-CIERRE. Se sumarán al reporte de mañana.")
        if st.button("🔓 REABRIR CAJA - SOLO DUEÑO", use_container_width=True, key="btn_reabrir_caja") and st.session_state.rol == "DUEÑO":
            for c in res_cierre.get('Items', []):
                tabla_cierres.delete_item(Key={'TenantID': st.session_state.tenant, 'CierreID': c['CierreID']})
            st.success("✅ Caja reabierta"); time.sleep(1); st.rerun()

    if st.session_state.boleta:
        b = st.session_state.boleta
        st.success("✅ VENTA REALIZADA")
        st.markdown(f"""<div style="background:white;color:black;padding:20px;border:2px solid #333;max-width:350px;margin:auto;font-family:monospace;">
            <h3 style="text-align:center;margin:0;">{st.session_state.tenant}</h3>
            <p style="text-align:center;margin:0;">{b['fecha']} {b['hora']}</p><hr>
            {''.join([f'<div style="display:flex;justify-content:space-between;"><span>{i["Cantidad"]}x {i["Producto"]}</span><span>S/{float(i["Subtotal"]):.2f}</span></div>' for i in b['items']])}
            <hr><div style="display:flex;justify-content:space-between;"><span>MÉTODO:</span><span>{b['metodo']}</span></div>
            <div style="display:flex;justify-content:space-between;color:red;"><span>DESC:</span><span>- S/{float(b['rebaja']):.2f}</span></div>
            <div style="display:flex;justify-content:space-between;font-size:18px;"><b>NETO:</b><b>S/{float(b['t_neto']):.2f}</b></div></div>""", unsafe_allow_html=True)

        # === PDF 80mm SIN EMOJIS ===
        pdf = FPDF(orientation='P', unit='mm', format=(80, 200))
        pdf.add_page()
        pdf.set_font('Courier', 'B', 12)
        pdf.cell(0, 5, st.session_state.tenant, 0, 1, 'C')
        pdf.set_font('Courier', '', 8)
        pdf.cell(0, 4, f"{b['fecha']} {b['hora']}", 0, 1, 'C')
        pdf.cell(0, 2, '-'*40, 0, 1, 'C')
        for i in b['items']:
            nombre = str(i['Producto'])[:15]
            pdf.cell(40, 4, f"{i['Cantidad']}x {nombre}", 0, 0)
            pdf.cell(0, 4, f"S/{float(i['Subtotal']):.2f}", 0, 1, 'R')
        pdf.cell(0, 2, '-'*40, 0, 1, 'C')
        metodo_pdf = str(b['metodo']).replace('🟣 ', '').replace('🔵 ', '').replace('💵 ', '')
        pdf.cell(40, 4, f"METODO:", 0, 0)
        pdf.cell(0, 4, metodo_pdf, 0, 1, 'R')
        pdf.cell(40, 4, f"DESC:", 0, 0)
        pdf.cell(0, 4, f"- S/{float(b['rebaja']):.2f}", 0, 1, 'R')
        pdf.set_font('Courier', 'B', 10)
        pdf.cell(40, 5, f"NETO:", 0, 0)
        pdf.cell(0, 5, f"S/{float(b['t_neto']):.2f}", 0, 1, 'R')
        pdf_output = pdf.output(dest='S').encode('latin-1')

        # === EXCEL DE LA BOLETA ===
        df_boleta = pd.DataFrame(b['items'])
        df_boleta['Fecha'] = b['fecha']
        df_boleta['Hora'] = b['hora']
        df_boleta['Metodo'] = b['metodo']
        df_boleta['Descuento'] = float(b['rebaja'])
        df_boleta['Total_Neto'] = float(b['t_neto'])
        buf_excel = io.BytesIO()
        with pd.ExcelWriter(buf_excel, engine='openpyxl') as w:
            df_boleta[['Fecha', 'Hora', 'Producto', 'Cantidad', 'Precio', 'Subtotal', 'Metodo', 'Descuento', 'Total_Neto']].to_excel(w, index=False, sheet_name='Ticket')

        col1, col2 = st.columns(2)
        col1.download_button("📄 PDF 80mm", pdf_output, f"Ticket_{b['fecha'].replace('/','')}.pdf", "application/pdf", use_container_width=True, key="btn_pdf_boleta")
        col2.download_button("📊 EXCEL", buf_excel.getvalue(), f"Ticket_{b['fecha'].replace('/','')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="btn_excel_boleta")

        if tiene_whatsapp_habilitado():
            texto = f"*TICKET - {st.session_state.tenant}*\n{b['fecha']} {b['hora']}\n---\n" + "\n".join([f"{i['Cantidad']}x {i['Producto']} - S/{float(i['Subtotal']):.2f}" for i in b['items']]) + f"\n---\n*TOTAL: S/{float(b['t_neto']):.2f}*\nMetodo: {b['metodo']}"
            st.link_button("📲 WhatsApp", f"https://wa.me/?text={urllib.parse.quote(texto)}", use_container_width=True)
        if st.button("⬅️ NUEVA VENTA", use_container_width=True, key="btn_nueva_venta"): st.session_state.boleta = None; st.rerun()
    else:
        st.subheader("🛍️ Nueva Venta")
        busq = st.text_input("🔍 Buscar:", key="bv").upper()
        ops = []
        for _, f in df_inv.iterrows():
            if busq in str(f['Producto']):
                est = f"STOCK: {f['Stock']}" if f['Stock'] > 0 else "🚫 AGOTADO"
                ops.append(f"{f['Producto']} | S/ {f['Precio']:.2f} | {est}")
        col1, col2 = st.columns([3, 1])
        sel = col1.selectbox("Producto:", ops, key="sel_v")
        p_sel = sel.split(" | ")[0] if sel else None
        cant = col2.number_input("Cant:", min_value=1, value=1, key="cant_v")
        if p_sel:
            dp = df_inv[df_inv['Producto'] == p_sel].iloc[0]
            en_carro = sum(i['Cantidad'] for i in st.session_state.carrito if i['Producto'] == p_sel)
            disp = dp.Stock - en_carro
            st.info(f"Disponible: {disp}")
            if st.button("➕ Añadir", use_container_width=True, key="btn_add_carrito"):
                if cant <= disp:
                    st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': to_decimal(dp.Precio), 'Precio_Compra': to_decimal(dp.Precio_Compra), 'Subtotal': to_decimal(dp.Precio) * int(cant)})
                    st.rerun()
                else: st.error("❌ Sin stock")
        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito)[['Producto', 'Cantidad', 'Subtotal']])
            if st.button("🗑️ VACIAR", key="btn_vaciar_carrito"): st.session_state.carrito = []; st.rerun()
            metodo = st.radio("Pago:", ["💵 EFECTIVO", "🟣 YAPE", "🔵 PLIN"], horizontal=True, key="radio_metodo")
            rebaja = st.number_input("💸 Descuento:", min_value=0.0, value=0.0, key="num_rebaja")
            total = max(Decimal('0.00'), sum(i['Subtotal'] for i in st.session_state.carrito) - to_decimal(rebaja))
            st.markdown(f"<h1 style='text-align:center;color:#2ecc71;'>S/ {float(total):.2f}</h1>", unsafe_allow_html=True)
            if st.button("🚀 FINALIZAR", use_container_width=True, type="primary", key="btn_finalizar"): st.session_state.confirmar = True
            if st.session_state.confirmar:
                if st.button(f"✅ CONFIRMAR S/ {float(total):.2f}", use_container_width=True, key="btn_confirmar_venta"):
                    f, h, uid = obtener_tiempo_peru()
                    for item in st.session_state.carrito:
                        tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': item['Producto']}, UpdateExpression="SET Stock = Stock - :s", ConditionExpression="Stock >= :s", ExpressionAttributeValues={':s': item['Cantidad']})
                        tabla_ventas.put_item(Item={'TenantID': st.session_state.tenant, 'VentaID': f"V-{uid}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': item['Subtotal'], 'Precio_Compra': item['Precio_Compra'], 'Metodo': metodo, 'Rebaja': to_decimal(rebaja), 'Usuario': st.session_state.usuario})
                        registrar_kardex(item['Producto'], item['Cantidad'], "VENTA", item['Subtotal'], item['Precio_Compra'], metodo)
                    st.session_state.boleta = {'items': st.session_state.carrito, 't_neto': total, 'rebaja': to_decimal(rebaja), 'metodo': metodo, 'fecha': f, 'hora': h}
                    st.session_state.carrito = []; st.session_state.confirmar = False; st.rerun()
# === TAB STOCK SOLO CON BUSCADOR ===
with tabs[1]:
    st.subheader("📦 Inventario")
    busq = st.text_input("🔍 Escribe para buscar producto:", key="bs").upper()

    if busq:
        df_f = df_inv[df_inv['Producto'].str.contains(busq)]
        if not df_f.empty:
            st.caption(f"Resultados: {len(df_f)} productos")
            st.dataframe(df_f[['Producto', 'Stock', 'Precio_Compra', 'Precio']], use_container_width=True, hide_index=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w: df_f.to_excel(w, index=False)
            st.download_button("📥 DESCARGAR RESULTADOS", buf.getvalue(), f"Inventario_{st.session_state.tenant}_{datetime.now(tz_peru).strftime('%Y%m%d')}.xlsx", use_container_width=True, key="btn_desc_inv")
            bajo = df_f[df_f['Stock'] < 5]
            if not bajo.empty: st.warning(f"⚠️ Stock crítico: {len(bajo)} productos"); st.dataframe(bajo[['Producto', 'Stock']], hide_index=True)
        else:
            st.info(f"No se encontró '{busq}'")
    else:
        st.info("👆 Escribe arriba para buscar productos")
        st.caption(f"Total en BD: {contarProductosEnBD()} productos")

# === TAB REPORTES CON GANANCIA POR MÉTODO ===
with tabs[2]:
    if st.session_state.rol == "DUEÑO":
        col_f1, col_f2 = st.columns([3,1])
        fecha = col_f1.date_input("Día:", value=datetime.now(tz_peru).date(), label_visibility="collapsed", key="date_reportes")
        if col_f2.button("🔄 ACTUALIZAR", use_container_width=True, key="btn_actualizar_reportes"): st.cache_data.clear(); st.rerun()

        fecha_iso = fecha.strftime('%Y-%m-%d')
        fecha_sem_pasada = (fecha - timedelta(days=7)).strftime('%Y-%m-%d')

        res_hoy = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_iso))
        items_hoy = res_hoy.get('Items', [])
        df_v = pd.DataFrame([m for m in items_hoy if m.get('Tipo') == 'VENTA'])

        res_sem = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_sem_pasada))
        items_sem = res_sem.get('Items', [])
        df_v_sem = pd.DataFrame([m for m in items_sem if m.get('Tipo') == 'VENTA'])

        if not df_v.empty:
            df_v['Total'] = pd.to_numeric(df_v['Total'], errors='coerce').fillna(0)
            df_v['Precio_Compra'] = pd.to_numeric(df_v['Precio_Compra'], errors='coerce').fillna(0)
            df_v['Cantidad'] = pd.to_numeric(df_v['Cantidad'], errors='coerce').fillna(0)
            df_v['Metodo'] = df_v['Metodo'].fillna('').astype(str)
            df_v['Costo'] = df_v['Precio_Compra'] * df_v['Cantidad']
            df_v['Ganancia_Item'] = df_v['Total'] - df_v['Costo']

            vt = df_v['Total'].sum()
            tk = len(df_v)
            tp = vt/tk if tk else 0
            costo_total = df_v['Costo'].sum()
            gn_total = df_v['Ganancia_Item'].sum()

            # === COMPARATIVO ===
            vt_sem = df_v_sem['Total'].sum() if not df_v_sem.empty else 0
            dif = vt - vt_sem
            pct = (dif / vt_sem * 100) if vt_sem > 0 else 0
            color = "#2ecc71" if dif >= 0 else "#e74c3c"
            flecha = "↑" if dif >= 0 else "↓"

            st.markdown(f"### 💰 VENTA TOTAL DEL DÍA\n<h1 style='margin:0;font-size:48px;'>S/ {float(vt):.2f}</h1>", unsafe_allow_html=True)
            st.markdown(f"<div style='background:{color};color:white;padding:4px 12px;border-radius:20px;display:inline-block;font-size:14px;'>{flecha} {abs(pct):.1f}% vs sem. pasada</div>", unsafe_allow_html=True)
            st.write("")

            st.markdown(f"### 📈 GANANCIA REAL TOTAL\n<h1 style='margin:0;font-size:48px;color:#2ecc71;'>S/ {float(gn_total):.2f}</h1>", unsafe_allow_html=True)
            st.caption(f"Tickets: {tk} | Ticket Prom: S/{float(tp):.2f} | Margen: {(gn_total/vt*100) if vt > 0 else 0:.1f}%")
            st.write("---")

            # === DESGLOSE POR MÉTODO ===
            df_ef = df_v[df_v['Metodo'].str.contains('EFECTIVO')]
            df_yape = df_v[df_v['Metodo'].str.contains('YAPE')]
            df_plin = df_v[df_v['Metodo'].str.contains('PLIN')]

            if not df_ef.empty:
                venta_ef = df_ef['Total'].sum()
                gan_ef = df_ef['Ganancia_Item'].sum()
                st.markdown(f"### 💵 EFECTIVO\n<h2 style='margin:0;'>Venta: S/ {float(venta_ef):.2f}</h2>", unsafe_allow_html=True)
                st.caption(f"Ganancia: S/ {float(gan_ef):.2f}")
                st.write("")

            if not df_yape.empty:
                venta_yape = df_yape['Total'].sum()
                gan_yape = df_yape['Ganancia_Item'].sum()
                st.markdown(f"### 🟣 YAPE\n<h2 style='margin:0;'>Venta: S/ {float(venta_yape):.2f}</h2>", unsafe_allow_html=True)
                st.caption(f"Ganancia: S/ {float(gan_yape):.2f}")
                st.write("")

            if not df_plin.empty:
                venta_plin = df_plin['Total'].sum()
                gan_plin = df_plin['Ganancia_Item'].sum()
                st.markdown(f"### 🔵 PLIN\n<h2 style='margin:0;'>Venta: S/ {float(venta_plin):.2f}</h2>", unsafe_allow_html=True)
                st.caption(f"Ganancia: S/ {float(gan_plin):.2f}")
        else:
            st.info(f"No hay ventas {fecha.strftime('%d/%m/%Y')}")
# === TAB HISTORIAL/CARGAR/MANT SOLO DUEÑO ===
if st.session_state.rol == "DUEÑO" and not st.session_state.get('modo_lectura', False):
    # TAB 3: HISTORIAL CON CARGA AUTO
    with tabs[3]:
        st.subheader("📋 Kardex")
        col_h1, col_h2 = st.columns([3,1])
        fecha_b = col_h1.date_input("📅 Fecha:", value=datetime.now(tz_peru).date(), key="hf", label_visibility="collapsed")
        if col_h2.button("🔄 ACTUALIZAR", use_container_width=True, key="btn_actualizar_historial"): st.cache_data.clear(); st.rerun()

        # CARGA AUTO DEL DÍA
        res = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_b.strftime('%Y-%m-%d')), Limit=500)
        df_h = pd.DataFrame(res.get('Items', []))

        if not df_h.empty:
            st.caption(f"Movimientos del {fecha_b.strftime('%d/%m/%Y')}: {len(df_h)}")
            st.dataframe(df_h[['Hora', 'Producto', 'Cantidad', 'Metodo', 'Tipo', 'Usuario']], use_container_width=True, hide_index=True)
        else:
            st.info(f"No hay movimientos el {fecha_b.strftime('%d/%m/%Y')}")

        with st.expander("📥 DESCARGAR MES"):
            mes = st.date_input("Mes:", value=datetime.now(tz_peru).date().replace(day=1), key="date_mes_descarga")
            if st.button("📊 EXCEL MES", use_container_width=True, key="btn_excel_mes"):
                inicio = mes.replace(day=1).strftime('%Y-%m-%d')
                fin = (mes.replace(month=mes.month+1, day=1) - timedelta(days=1)).strftime('%Y-%m-%d') if mes.month < 12 else (mes.replace(year=mes.year+1, month=1, day=1) - timedelta(days=1)).strftime('%Y-%m-%d')
                res = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').between(inicio, fin))
                df_m = pd.DataFrame(res.get('Items', []))
                if not df_m.empty:
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='openpyxl') as w: df_m.to_excel(w, index=False)
                    st.download_button("📥 DESCARGAR", buf.getvalue(), f"Kardex_{mes.strftime('%Y%m')}.xlsx", use_container_width=True, key="btn_download_mes")

    # TAB 4: CARGAR
    with tabs[4]:
        st.subheader("📂 Carga Masiva")
        st.caption(f"Columnas: Producto, Precio_Compra, Precio, Stock | Máx: 500")
        archivo = st.file_uploader("Excel/CSV", type=['xlsx', 'csv'], key="file_carga")
        if archivo:
            df_b = pd.read_excel(archivo) if archivo.name.endswith('xlsx') else pd.read_csv(archivo)
            df_b.columns = [str(c).strip().title() for c in df_b.columns]
            st.write(df_b.head(3))
            if len(df_b) > 500: st.error("❌ Máx 500"); st.stop()
            if contarProductosEnBD() + len(df_b) > MAX_PRODUCTOS_TOTALES: st.error(f"❌ Solo {MAX_PRODUCTOS_TOTALES - contarProductosEnBD()} espacios"); st.stop()
            if st.button("⚡ PROCESAR", use_container_width=True, key="btn_procesar_carga"):
                barra = st.progress(0)
                with tabla_stock.batch_writer() as batch:
                    for i, f in df_b.iterrows():
                        p = str(f['Producto']).upper().strip()
                        batch.put_item(Item={'TenantID': st.session_state.tenant, 'Producto': p, 'Precio_Compra': to_decimal(f['Precio_Compra']), 'Precio': to_decimal(f['Precio']), 'Stock': int(f['Stock'])})
                        registrar_kardex(p, int(f['Stock']), "CARGA MASIVA", to_decimal(f['Precio']) * int(f['Stock']), to_decimal(f['Precio_Compra']), "")
                        barra.progress((i + 1) / len(df_b))
                st.success(f"✅ {len(df_b)} productos"); time.sleep(1); st.rerun()

    # TAB 5: MANT
    with tabs[5]:
        st.subheader("🛠️ Mantenimiento")
        with st.expander("➕ CREAR PRODUCTO"):
            c1, c2 = st.columns(2)
            np = c1.text_input("Nombre:", key="txt_nombre_new").upper().strip()
            nc = c1.number_input("Precio Compra:", min_value=0.0, key="num_pc_new")
            nv = c2.number_input("Precio Venta:", min_value=0.0, key="num_pv_new")
            ns = c2.number_input("Stock:", min_value=1, value=1, key="num_stock_new")
            if st.button("💾 CREAR", use_container_width=True, key="btn_crear_prod"):
                if np and ns > 0 and contarProductosEnBD() < MAX_PRODUCTOS_TOTALES:
                    tabla_stock.put_item(Item={'TenantID': st.session_state.tenant, 'Producto': np, 'Precio_Compra': to_decimal(nc), 'Precio': to_decimal(nv), 'Stock': int(ns)})
                    registrar_kardex(np, ns, "PRODUCTO NUEVO", to_decimal(nv) * ns, to_decimal(nc), "")
                    st.success(f"✅ {np} creado"); time.sleep(1); st.rerun()
        st.divider()
        acc = st.radio("Acción:", ["➕ REPONER", "📝 PRECIOS", "🗑️ ELIMINAR"], horizontal=True, key="radio_acc_mant")
        busq_m = st.text_input("🔍 Buscar:", key="txt_busq_mant").upper()
        lista = [p for p in df_inv['Producto'].tolist() if busq_m in str(p)]
        if lista:
            p_sel = st.selectbox("Producto:", lista, key="sel_prod_mant")
            idx = df_inv[df_inv['Producto'] == p_sel].index[0]
            if acc == "➕ REPONER":
                cant = st.number_input("Ingreso:", min_value=1, key="num_repo_mant")
                if st.button("✅ ACTUALIZAR", key="btn_actualizar_repo"):
                    nuevo = int(df_inv.at[idx, 'Stock'] + cant)
                    if nuevo <= MAX_STOCK_POR_PRODUCTO:
                        tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_sel}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': nuevo})
                        registrar_kardex(p_sel, cant, f"REPOSICIÓN", 0, 0, ""); st.success("✅"); time.sleep(1); st.rerun()
                    else: st.error(f"❌ Máx {MAX_STOCK_POR_PRODUCTO}")
            elif acc == "📝 PRECIOS":
                nc = st.number_input("Costo:", value=float(df_inv.at[idx, 'Precio_Compra']), key="num_pc_edit")
                nv = st.number_input("Venta:", value=float(df_inv.at[idx, 'Precio']), key="num_pv_edit")
                if st.button("💾 GUARDAR", key="btn_guardar_precios"):
                    tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_sel}, UpdateExpression="SET Precio_Compra=:pc,Precio=:pv", ExpressionAttributeValues={':pc': to_decimal(nc), ':pv': to_decimal(nv)})
                    registrar_kardex(p_sel, 0, "CAMBIO PRECIOS", 0, 0, ""); st.success("✅"); time.sleep(1); st.rerun()
            else:
                if st.button(f"🗑️ ELIMINAR {p_sel}", key="btn_eliminar_prod"):
                    tabla_stock.delete_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_sel})
                    registrar_kardex(p_sel, 0, "BORRADO", 0, 0, ""); st.warning("Eliminado"); time.sleep(1); st.rerun()
# === SIDEBAR ===
if st.session_state.auth:
    with st.sidebar:
        st.title(f"🏢 {st.session_state.tenant}")
        st.write(f"Usuario: **{st.session_state.usuario}**")
        st.caption(f"{'🔵' if PLAN_ACTUAL=='BASICO' else '🟣' if PLAN_ACTUAL=='PRO' else '🟡'} **Plan {PLAN_ACTUAL}** | S/ {float(PRECIO_ACTUAL):.0f}/mes")

        st.markdown("---")
        if st.button("🔒 CERRAR CAJA", use_container_width=True, type="primary", key="btn_cerrar_caja_sidebar"):
            f_hoy, _, _ = obtener_tiempo_peru()
            res_c = tabla_cierres.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant), FilterExpression=Attr('Fecha').eq(f_hoy) & Attr('UsuarioTurno').eq(st.session_state.usuario))
            cierres = res_c.get('Items', [])
            hora_ult = max([c['Hora'] for c in cierres]) if cierres else "00:00:00"
            res_v = tabla_ventas.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant), FilterExpression=Attr('Fecha').eq(f_hoy) & Attr('Usuario').eq(st.session_state.usuario) & Attr('Hora').gt(hora_ult))
            total = sum([Decimal(str(v['Total'])) for v in res_v.get('Items', [])])
            if total > 0:
                registrar_cierre(total, st.session_state.usuario, f"CIERRE {st.session_state.rol}", st.session_state.usuario)
                st.success(f"✅ S/ {float(total):.2f}")
                st.balloons()
                time.sleep(1)
                st.rerun()
            else:
                st.warning("No hay ventas nuevas")

        if st.session_state.rol == "DUEÑO":
            st.markdown("---")
            st.subheader("🚨 CIERRE TARDÍO")
            hora_actual = datetime.now(tz_peru).hour
            if 0 <= hora_actual <= 6:
                ayer = (datetime.now(tz_peru) - timedelta(days=1)).strftime("%d/%m/%Y")
                res_v = tabla_ventas.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant), FilterExpression=Attr('Fecha').eq(ayer))
                res_c = tabla_cierres.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant), FilterExpression=Attr('Fecha').eq(ayer))

                # Filtrar solo EMPLEADOS, no DUEÑO
                ventas_empleados = [v for v in res_v.get('Items', []) if v['Usuario']!= 'DUEÑO']
                cierres_empleados = [c for c in res_c.get('Items', []) if c['UsuarioTurno']!= 'DUEÑO']
                usuarios_cerrados = [c['UsuarioTurno'] for c in cierres_empleados]

                if ventas_empleados:
                    users = {}
                    for v in ventas_empleados:
                        if v['Usuario'] not in usuarios_cerrados:
                            users[v['Usuario']] = users.get(v['Usuario'], Decimal('0.00')) + Decimal(str(v['Total']))

                    if users:
                        st.warning(f"⚠️ {len(users)} empleado(s) no cerraron")
                        u_sel = st.selectbox("Empleado:", list(users.keys()), key="sel_emp_tardio")
                        st.metric("Pendiente", f"S/ {float(users[u_sel]):.2f}")
                        if st.button("🔒 CERRAR CAJA EMPLEADO", use_container_width=True, key="cerrar_tardio"):
                            registrar_cierre(users[u_sel], u_sel, "CIERRE TARDÍO DUEÑO", st.session_state.usuario, ayer)
                            st.success(f"✅ Cerraste caja de {u_sel}: S/ {float(users[u_sel]):.2f}")
                            st.balloons()
                            time.sleep(2)
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        st.success("✅ Todos los empleados cerraron")
                else:
                    st.info("No hubo ventas de empleados ayer")
            else:
                st.info("⏰ Solo disponible 12am-6am")

        st.markdown("---")
        st.caption(f"📲 Soporte: +{NUMERO_SOPORTE}")
        st.caption(f"💳 Yape/Plin: {YAPE_SOPORTE}")
        if st.button("🔴 CERRAR SESIÓN", key="btn_logout"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()                    
