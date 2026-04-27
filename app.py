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

st.set_page_config(page_title="NEXUS BALLARTA", layout="wide", page_icon="🚀", initial_sidebar_state="collapsed")
tz_peru = pytz.timezone('America/Lima')

# === CSS ===
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
        * {font-family: 'Poppins', sans-serif;}

    html, body, [class*="stApp"], [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            color-scheme: light only!important;
            forced-color-adjust: none!important;
            -webkit-forced-color-adjust: none!important;
        }
.main {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)!important;}
.block-container {
            background: white!important;
            color: #262730!important;
            border-radius: 20px;
            padding: 2rem;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
.block-container p,.block-container h1,.block-container h2,.block-container h3,
.block-container h4,.block-container label,.block-container span,
.stMarkdown,.stText,.stCaption {
            color: #262730!important;
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)!important;
            padding: 20px; border-radius: 15px; box-shadow: 0 8px 16px rgba(102,126,234,0.3); border: none;
        }
        div[data-testid="stMetric"] label {color: white!important; font-weight: 600;}
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {color: white!important; font-size: 36px;}
        div[data-testid="stMetric"] [data-testid="stMetricDelta"] {color: white!important; font-size: 14px;}
.stButton>button {
            border-radius: 12px; font-weight: 600; border: none;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)!important;
            color: white!important; box-shadow: 0 4px 12px rgba(102,126,234,0.4);
        }
.stTabs [data-baseweb="tab-list"] {gap: 8px; background: #f8f9fa!important; padding: 10px; border-radius: 15px;}
.stTabs [data-baseweb="tab"] {border-radius: 10px; padding: 10px 20px; font-weight: 600; color: #262730!important;}
.stTabs [aria-selected="true"] {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)!important; color: white!important;}

    button[key="btn_yape"] {
            background: linear-gradient(135deg, #720e9e 0%, #5a0b7a 100%)!important;
            color: white!important;
            font-size: 24px!important;
            font-weight: 800!important;
            height: 100px!important;
            border: 4px solid #5a0b7a!important;
            border-radius: 15px!important;
            box-shadow: 0 8px 16px rgba(114,14,158,0.4)!important;
        }
    button[key="btn_plin"] {
            background: linear-gradient(135deg, #00b9e5 0%, #0094b8 100%)!important;
            color: white!important;
            font-size: 24px!important;
            font-weight: 800!important;
            height: 100px!important;
            border: 4px solid #0094b8!important;
            border-radius: 15px!important;
            box-shadow: 0 8px 16px rgba(0,185,229,0.4)!important;
        }
    button[key="btn_efectivo"] {
            background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%)!important;
            color: white!important;
            font-size: 24px!important;
            font-weight: 800!important;
            height: 100px!important;
            border: 4px solid #27ae60!important;
            border-radius: 15px!important;
            box-shadow: 0 8px 16px rgba(46,204,113,0.4)!important;
        }
    button[key="btn_yape"]:active, button[key="btn_plin"]:active, button[key="btn_efectivo"]:active {
            transform: scale(0.95)!important;
        }

.stSelectbox>div {
            background: white!important;
            border: 2px solid #e0e0e0!important;
            border-radius: 10px!important;
        }
.stSelectbox>div>div>div {color: #262730!important;}
.stSelectbox svg {fill: #262730!important;}
    [data-baseweb="select"] {background-color: white!important;}
    [data-baseweb="select"] > div {background-color: white!important; color: #262730!important;}
    [data-baseweb="popover"] {background-color: white!important;}
    [data-baseweb="menu"] {background-color: white!important;}
    [data-baseweb="menu"] li {background-color: white!important; color: #262730!important;}
    [data-baseweb="menu"] li:hover {background-color: #e3f2fd!important;}

.stTextInput>div>div>input,.stNumberInput>div>div>input,.stDateInput input {
            border-radius: 10px; border: 2px solid #e0e0e0!important; padding: 12px;
            background: white!important; color: #262730!important;
        }
    [data-testid="stNumberInput"] {background: white!important;}
    [data-testid="stNumberInput"] input {
            background-color: white!important;
            color: #262730!important;
        }
    [data-testid="stNumberInput"] button {
            background-color: #f0f0f0!important;
            color: #262730!important;
        }
.stSelectbox label,.stTextInput label,.stNumberInput label,.stDateInput label,.stRadio label {color: #262730!important;}

        [data-testid="stSidebar"] {background: linear-gradient(180deg, #667eea 0%, #764ba2 100%)!important;}
        [data-testid="stSidebar"] * {color: white!important;}
        [data-testid="stSidebar"].stButton>button {background: white!important; color: #667eea!important;}

    [data-testid="stExpander"] {
            background-color: white!important;
            border: 1px solid #e0e0e0!important;
        }
    [data-testid="stExpander"] summary {
            background-color: #f5f7fa!important;
            color: #262730!important;
        }
    [data-testid="stExpander"] > div {background-color: white!important;}
.streamlit-expanderHeader {background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)!important; border-radius: 10px; font-weight: 600; color: #262730!important;}
.stAlert {border-radius: 12px; border-left: 5px solid;}
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
    except: return pd.DataFrame(columns=['Producto', 'Precio_Compra', 'Precio', 'Stock'])

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
    if contarProductos
# === LOGIN CON SEGURIDAD ===
if not st.session_state.auth:
    if st.session_state.bloqueo_hasta and datetime.now() < st.session_state.bloqueo_hasta:
        tiempo_restante = (st.session_state.bloqueo_hasta - datetime.now()).seconds
        st.error(f"🔒 BLOQUEADO POR SEGURIDAD")
        st.warning(f"⏱️ Espera {tiempo_restante} segundos para intentar de nuevo")
        st.progress(1 - (tiempo_restante / 300))
        time.sleep(1)
        st.rerun()

    st.markdown("""
        <div style='text-align:center; padding: 40px 0;'>
            <h1 style='font-size: 3.5rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin:0;'>
                🚀 NEXUS BALLARTA
            </h1>
            <p style='color: #666; font-size: 1.1rem; margin-top: 10px;'>Sistema de Gestión Empresarial</p>
            <p style='color: #999; font-size: 0.85rem;'>{}</p>
        </div>
    """.format(DESARROLLADOR), unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.container():
            st.markdown("### 🔐 Acceso Seguro")
            tenants = [k for k in st.secrets if k not in ["tablas", "aws"] and not k.endswith("_emp")]
            t_sel = st.selectbox("📍 Selecciona tu Negocio:", [t.replace("_", " ") for t in tenants])
            t_key = t_sel.replace(" ", "_")

            tab_dueno, tab_empleado = st.tabs(["👑 DUEÑO", "👤 EMPLEADO"])

            with tab_dueno:
                clave = st.text_input("🔑 Contraseña:", type="password", key="clave_dueno").strip()[:30]
                if st.session_state.intentos_login > 0:
                    st.caption(f"⚠️ Intentos fallidos: {st.session_state.intentos_login}/5")
                if st.button("🔓 INGRESAR COMO DUEÑO", use_container_width=True, type="primary"):
                    if clave == str(st.secrets[t_key]["clave"]):
                        st.session_state.update({'auth':True,'tenant':t_sel,'rol':'DUEÑO','usuario':'DUEÑO','intentos_login':0})
                        st.success("✅ Acceso concedido")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.session_state.intentos_login += 1
                        if st.session_state.intentos_login >= 5:
                            st.session_state.bloqueo_hasta = datetime.now() + timedelta(minutes=5)
                            st.error("🔒 BLOQUEADO POR 5 MINUTOS")
                        else:
                            st.error(f"❌ Contraseña incorrecta. Te quedan {5 - st.session_state.intentos_login} intentos")
                        time.sleep(2)
                        st.rerun()

            with tab_empleado:
                nombre = st.text_input("👤 Tu nombre:", max_chars=20, key="nombre_emp").upper().strip()
                clave_emp = st.text_input("🔑 Contraseña:", type="password", key="clave_emp").strip()[:30]
                if st.session_state.intentos_login > 0:
                    st.caption(f"⚠️ Intentos fallidos: {st.session_state.intentos_login}/5")
                if st.button("🧑‍💼 INGRESAR COMO EMPLEADO", use_container_width=True, type="primary"):
                    if nombre and clave_emp == str(st.secrets[f"{t_key}_emp"]["clave"]):
                        st.session_state.update({'auth':True,'tenant':t_sel,'rol':'EMPLEADO','usuario':nombre,'intentos_login':0})
                        st.success("✅ Acceso concedido")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.session_state.intentos_login += 1
                        if st.session_state.intentos_login >= 5:
                            st.session_state.bloqueo_hasta = datetime.now() + timedelta(minutes=5)
                            st.error("🔒 BLOQUEADO POR 5 MINUTOS")
                        else:
                            st.error(f"❌ Datos incorrectos. Te quedan {5 - st.session_state.intentos_login} intentos")
                        time.sleep(2)
                        st.rerun()
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
        st.markdown(f"""<div style="background:white;color:black;padding:20px;border:2px solid #667eea;max-width:350px;margin:auto;font-family:monospace;border-radius:15px;box-shadow:0 8px 20px rgba(102,126,234,0.3);">
            <h3 style="text-align:center;margin:0;color:#667eea;">{st.session_state.tenant}</h3>
            <p style="text-align:center;margin:0;">{b['fecha']} {b['hora']}</p><hr style="border-color:#667eea;">
            {''.join([f'<div style="display:flex;justify-content:space-between;"><span>{i["Cantidad"]}x {i["Producto"]}</span><span>S/{float(i["Subtotal"]):.2f}</span></div>' for i in b['items']])}
            <hr style="border-color:#667eea;"><div style="display:flex;justify-content:space-between;"><span>MÉTODO:</span><span>{b['metodo']}</span></div>
            <div style="display:flex;justify-content:space-between;color:#e74c3c;"><span>DESC:</span><span>- S/{float(b['rebaja']):.2f}</span></div>
            <div style="display:flex;justify-content:space-between;font-size:18px;color:#667eea;"><b>NETO:</b><b>S/{float(b['t_neto']):.2f}</b></div></div>""", unsafe_allow_html=True)

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
        busq = st.text_input("🔍 Buscar:", key="bv", placeholder="Escribe nombre del producto...").upper()
        ops = []
        for _, f in df_inv.iterrows():
            if busq in str(f['Producto']):
                est = f"STOCK: {f['Stock']}" if f['Stock'] > 0 else "🚫 AGOTADO"
                ops.append(f"{f['Producto']} | S/ {f['Precio']:.2f} | {est}")
        col1, col2 = st.columns([3, 1])
        if ops:
            sel = col1.selectbox("Producto:", ops, key="sel_v", placeholder="Busca y selecciona producto")
            p_sel = sel.split(" | ")[0] if sel else None
        else:
            st.info("👆 Escribe arriba para buscar productos")
            sel = None
            p_sel = None
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
            for idx, item in enumerate(st.session_state.carrito):
                c1, c2, c3 = st.columns([3,1,1])
                c1.write(f"{item['Producto']}")
                c2.write(f"x{item['Cantidad']}")
                c3.write(f"S/{float(item['Subtotal']):.2f}")
            if st.button("🗑️ VACIAR", key="btn_vaciar_carrito"): st.session_state.carrito = []; st.rerun()

            st.write("**Método de Pago:**")
            col_ef, col_yape, col_plin = st.columns(3)

            with col_ef:
                st.markdown("<div style='text-align:center;font-size:40px;'>💵</div>", unsafe_allow_html=True)
                if st.button("EFECTIVO", use_container_width=True, type="primary" if st.session_state.metodo_pago=="💵 EFECTIVO" else "secondary", key="btn_efectivo"):
                    st.session_state.metodo_pago = "💵 EFECTIVO"
                    st.rerun()

            with col_yape:
                st.markdown("<div style='text-align:center;font-size:40px;'>🟣</div>", unsafe_allow_html=True)
                if st.button("YAPE", use_container_width=True, type="primary" if st.session_state.metodo_pago=="🟣 YAPE" else "secondary", key="btn_yape"):
                    st.session_state.metodo_pago = "🟣 YAPE"
                    st.rerun()

            with col_plin:
                st.markdown("<div style='text-align:center;font-size:40px;'>🔵</div>", unsafe_allow_html=True)
                if st.button("PLIN", use_container_width=True, type="primary" if st.session_state.metodo_pago=="🔵 PLIN" else "secondary", key="btn_plin"):
                    st.session_state.metodo_pago = "🔵 PLIN"
                    st.rerun()

            metodo = st.session_state.metodo_pago
            st.markdown(f"<h3 style='text-align:center;color:#667eea;'>Seleccionado: {metodo}</h3>", unsafe_allow_html=True)

            rebaja = st.number_input("💸 Descuento:", min_value=0.0, value=0.0, key="num_rebaja")
            total = max(Decimal('0.00'), sum(i['Subtotal'] for i in st.session_state.carrito) - to_decimal(rebaja))
            st.markdown(f"<h1 style='text-align:center;color:#667eea;font-size:3rem;'>S/ {float(total):.2f}</h1>", unsafe_allow_html=True)
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
# === TAB STOCK - TABLA MANUAL ANTI-BLANCO ===
with tabs[1]:
    st.subheader("📦 Inventario")

    busq = st.text_input("🔍 Buscar producto por nombre:", key="bs", placeholder="Ej: CUADERNO, LAPIZ, BORRADOR...").upper()

    col1, col2, col3 = st.columns([2,1,1])
    mostrar_todos = col1.checkbox("📋 Ver lista completa", value=False, help="Solo activa si tienes <200 productos")
    filtro_stock = col2.selectbox("Filtrar:", ["Todos", "Stock bajo <5", "Agotados", "Con stock"], key="filtro_stock")

    df_mostrar = df_inv.copy()

    if busq:
        df_mostrar = df_mostrar[df_mostrar['Producto'].str.contains(busq, na=False)]

    if filtro_stock == "Stock bajo <5":
        df_mostrar = df_mostrar[df_mostrar['Stock'] < 5]
    elif filtro_stock == "Agotados":
        df_mostrar = df_mostrar[df_mostrar['Stock'] == 0]
    elif filtro_stock == "Con stock":
        df_mostrar = df_mostrar[df_mostrar['Stock'] > 0]

    if busq or mostrar_todos:
        if not df_mostrar.empty:
            st.caption(f"Mostrando {len(df_mostrar)} de {len(df_inv)} productos totales")

            if len(df_mostrar) > 50:
                page_size = 50
                total_pages = (len(df_mostrar) - 1) // page_size + 1
                page = st.number_input("Página:", min_value=1, max_value=total_pages, value=1, key="page_stock") - 1
                start_idx = page * page_size
                end_idx = start_idx + page_size
                df_pagina = df_mostrar.iloc[start_idx:end_idx]
                st.caption(f"Página {page+1} de {total_pages}")
            else:
                df_pagina = df_mostrar

            # TABLA MANUAL QUE NUNCA FALLA EN MÓVIL
            h1, h2, h3, h4 = st.columns([3,1,1,1])
            h1.markdown("**PRODUCTO**")
            h2.markdown("**STOCK**")
            h3.markdown("**COSTO**")
            h4.markdown("**VENTA**")
            st.divider()

            for idx, row in df_pagina.iterrows():
                c1, c2, c3, c4 = st.columns([3,1,1,1])
                c1.write(row['Producto'])
                c2.write(f"{int(row['Stock'])}")
                c3.write(f"S/{row['Precio_Compra']:.2f}")
                c4.write(f"S/{row['Precio']:.2f}")

            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                df_mostrar.to_excel(w, index=False, sheet_name='Inventario')
            st.download_button(
                "📥 DESCARGAR EXCEL FILTRADO",
                buf.getvalue(),
                f"Inventario_{st.session_state.tenant}_{datetime.now(tz_peru).strftime('%Y%m%d')}.xlsx",
                use_container_width=True,
                key="btn_desc_inv"
            )

            bajo = df_mostrar[df_mostrar['Stock'] < 5]
            if not bajo.empty:
                st.warning(f"⚠️ Stock crítico: {len(bajo)} productos con menos de 5 unidades")
                with st.expander("Ver productos con stock bajo"):
                    for idx, row in bajo.iterrows():
                        st.write(f"**{row['Producto']}** - Stock: {int(row['Stock'])}")
        else:
            if busq:
                st.info(f"❌ No se encontró '{busq}'. Prueba con parte del nombre.")
            else:
                st.info("📭 No hay productos con ese filtro")
    else:
        st.info("👆 Escribe arriba para buscar o activa 'Ver lista completa'")
        st.caption(f"Total en BD: {contarProductosEnBD()} productos")

        if not df_inv.empty:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total productos", len(df_inv))
            col2.metric("Agotados", len(df_inv[df_inv['Stock'] == 0]))
            col3.metric("Stock bajo <5", len(df_inv[df_inv['Stock'] < 5]))
            col4.metric("Valor inventario", f"S/ {(df_inv['Stock'] * df_inv['Precio_Compra']).sum():.2f}")

# === TAB REPORTES - SIN CORTE NUNCA ===
with tabs[2]:
    st.subheader("📊 Reportes del Día")

    col_f1, col_f2 = st.columns([3,1])
    fecha = col_f1.date_input("Selecciona día:", value=datetime.now(tz_peru).date(), key="date_reportes_fix")
    if col_f2.button("🔄 ACTUALIZAR", use_container_width=True, key="btn_actualizar_reportes"):
        st.cache_data.clear()
        st.rerun()

    fecha_iso = fecha.strftime('%Y-%m-%d')
    fecha_sem_pasada = (fecha - timedelta(days=7)).strftime('%Y-%m-%d')

    if st.session_state.rol == "EMPLEADO":
        res_hoy = tabla_movs.query(
            IndexName='TenantID-FechaISO-index',
            KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_iso),
            FilterExpression=Attr('Usuario').eq(st.session_state.usuario) & Attr('Tipo').eq('VENTA')
        )
        res_sem = tabla_movs.query(
            IndexName='TenantID-FechaISO-index',
            KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_sem_pasada),
            FilterExpression=Attr('Usuario').eq(st.session_state.usuario) & Attr('Tipo').eq('VENTA')
        )
        st.info(f"📊 Viendo solo TUS ventas - {st.session_state.usuario}")
    else:
        res_hoy = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_iso))
        res_sem = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_sem_pasada))

    items_hoy = res_hoy.get('Items', [])
    df_v = pd.DataFrame([m for m in items_hoy if m.get('Tipo') == 'VENTA'])

    items_sem = res_sem.get('Items', [])
    df_v_sem = pd.DataFrame([m for m in items_sem if m.get('Tipo') == 'VENTA'])

    if df_v.empty:
        st.warning(f"📭 No hay ventas registradas el {fecha.strftime('%d/%m/%Y')}")
        if st.session_state.rol == "EMPLEADO":
            st.caption("Si hiciste ventas hoy, verifica que cerraste la venta correctamente.")
    else:
        df_v = df_v.sort_values('Hora', ascending=False)
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

        vt_sem = df_v_sem['Total'].sum() if not df_v_sem.empty else 0
        dif = vt - vt_sem
        pct = (dif / vt_sem * 100) if vt_sem > 0 else 0

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 💰 VENTA TOTAL")
            st.markdown(f"<h1 style='margin:0;font-size:38px;color:#667eea;'>S/ {float(vt):.2f}</h1>", unsafe_allow_html=True)
            if dif >= 0:
                st.success(f"↑ {abs(pct):.1f}% vs semana pasada")
            else:
                st.error(f"↓ {abs(pct):.1f}% vs semana pasada")

        with col2:
            st.markdown("### 📈 GANANCIA REAL")
            st.markdown(f"<h1 style='margin:0;font-size:38px;color:#2ecc71;'>S/ {float(gn_total):.2f}</h1>", unsafe_allow_html=True)
            st.info(f"Tickets: {tk} | Ticket Prom: S/{float(tp):.2f} | Margen: {(gn_total/vt*100) if vt > 0 else 0:.1f}%")

        st.write("---")

        with st.expander("🧾 VER TICKETS DEL DÍA - MÁS RECIENTE ARRIBA", expanded=True):
            h1, h2, h3, h4, h5, h6 = st.columns([1,3,1,1])
            h1.markdown("**HORA**"); h2.markdown("**PRODUCTO**"); h3.markdown("**CANT**")
            h4.markdown("**TOTAL**"); h5.markdown("**METODO**"); h6.markdown("**USUARIO**")
            st.divider()
            for idx, row in df_v.iterrows():
                c1, c2, c3, c4, c5, c6 = st.columns([1,3,1,1])
                c1.write(row['Hora'])
                c2.write(row['Producto'])
                c3.write(f"{int(row['Cantidad'])}")
                c4.write(f"S/{row['Total']:.2f}")
                c5.write(row['Metodo'])
                c6.write(row['Usuario'])

        df_ef = df_v[df_v['Metodo'].str.contains('EFECTIVO')]
        df_yape = df_v[df_v['Metodo'].str.contains('YAPE')]
        df_plin = df_v[df_v['Metodo'].str.contains('PLIN')]

        cols = st.columns(3)
        if not df_ef.empty:
            venta_ef = df_ef['Total'].sum()
            gan_ef = df_ef['Ganancia_Item'].sum()
            cols[0].metric("💵 EFECTIVO", f"S/ {float(venta_ef):.2f}", f"Ganancia: S/ {float(gan_ef):.2f}")

        if not df_yape.empty:
            venta_yape = df_yape['Total'].sum()
            gan_yape = df_yape['Ganancia_Item'].sum()
            cols[1].metric("🟣 YAPE", f"S/ {float(venta_yape):.2f}", f"Ganancia: S/ {float(gan_yape):.2f}")

        if not df_plin.empty:
            venta_plin = df_plin['Total'].sum()
            gan_plin = df_plin['Ganancia_Item'].sum()
            cols[2].metric("🔵 PLIN", f"S/ {float(venta_plin):.2f}", f"Ganancia: S/ {float(gan_plin):.2f}")
# === TAB HISTORIAL - SOLO DUEÑO ===
if st.session_state.rol == "DUEÑO" and len(tabs) > 3:
    with tabs[3]:
        st.subheader("📋 Historial Kardex")
        col_f1, col_f2 = st.columns([3,1])
        f_h = col_f1.date_input("Día:", value=datetime.now(tz_peru).date(), key="date_historial_fix")
        if col_f2.button("🔄 ACTUALIZAR", use_container_width=True, key="btn_actualizar_hist"): st.cache_data.clear(); st.rerun()

        fecha_iso_h = f_h.strftime('%Y-%m-%d')
        res_h = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_iso_h))
        df_h = pd.DataFrame(res_h.get('Items', []))

        if not df_h.empty:
            df_h = df_h.sort_values('Hora', ascending=False)
            df_h['Total'] = pd.to_numeric(df_h['Total'], errors='coerce').fillna(0)
            df_h['Precio_Compra'] = pd.to_numeric(df_h['Precio_Compra'], errors='coerce').fillna(0)
            df_h['Cantidad'] = pd.to_numeric(df_h['Cantidad'], errors='coerce').fillna(0)
            df_h['Costo'] = df_h['Precio_Compra'] * df_h['Cantidad']
            df_h['Ganancia'] = df_h.apply(lambda r: r['Total'] - r['Costo'] if r['Tipo'] == 'VENTA' else 0, axis=1)

            # TABLA MANUAL HISTORIAL - 8 COLUMNAS
            h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([1,2,1,1])
            h1.markdown("**HORA**"); h2.markdown("**PRODUCTO**"); h3.markdown("**TIPO**")
            h4.markdown("**CANT**"); h5.markdown("**TOTAL**"); h6.markdown("**COSTO**")
            h7.markdown("**GANANCIA**"); h8.markdown("**USUARIO**")
            st.divider()

            for idx, row in df_h.iterrows():
                c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1,2,1,1,1,1])
                c1.write(row['Hora'])
                c2.write(row['Producto'])
                c3.write(row['Tipo'])
                c4.write(f"{int(row['Cantidad'])}")
                c5.write(f"S/{row['Total']:.2f}")
                c6.write(f"S/{row['Costo']:.2f}")
                c7.write(f"S/{row['Ganancia']:.2f}")
                c8.write(row['Usuario'])

            df_v_h = df_h[df_h['Tipo'] == 'VENTA']
            if not df_v_h.empty:
                vt_h = df_v_h['Total'].sum()
                costo_h = df_v_h['Costo'].sum()
                gn_h = df_v_h['Ganancia'].sum()

                col1, col2, col3 = st.columns(3)
                col1.metric("💰 VENTA TOTAL", f"S/ {float(vt_h):.2f}")
                col2.metric("📉 COSTO TOTAL", f"S/ {float(costo_h):.2f}")
                col3.metric("📈 GANANCIA REAL", f"S/ {float(gn_h):.2f}")

                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as w: df_h.to_excel(w, index=False)
                st.download_button("📥 DESCARGAR EXCEL", buf.getvalue(), f"Kardex_{f_h.strftime('%Y%m%d')}.xlsx", use_container_width=True, key="btn_desc_kardex")

                if tiene_whatsapp_habilitado():
                    res = f"*REPORTE {f_h.strftime('%d/%m/%Y')}*\nVenta: S/{float(vt_h):.2f}\nCosto: S/{float(costo_h):.2f}\n*Ganancia: S/{float(gn_h):.2f}*"
                    st.link_button("📲 COMPARTIR", f"https://wa.me/?text={urllib.parse.quote(res)}", use_container_width=True)
            else:
                st.info("No hay ventas este día")
        else:
            st.info(f"📭 No hay movimientos el {f_h.strftime('%d/%m/%Y')}")

        st.write("---")
        st.subheader("🔒 Cierre de Caja")
        fecha_cierre = st.date_input("Fecha a cerrar:", value=datetime.now(tz_peru).date(), key="date_cierre_fix")
        fecha_iso_cierre = fecha_cierre.strftime('%Y-%m-%d')

        res_cierre_check = tabla_cierres.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant), FilterExpression=Attr('Fecha').eq(fecha_cierre.strftime('%d/%m/%Y')))
        ya_cerro_caja = len(res_cierre_check.get('Items', [])) > 0

        if ya_cerro_caja:
            st.success(f"✅ Caja del {fecha_cierre.strftime('%d/%m/%Y')} ya fue cerrada")
            if st.button("🔓 REABRIR CAJA", use_container_width=True, key="btn_reabrir_caja_hist"):
                for c in res_cierre_check.get('Items', []):
                    tabla_cierres.delete_item(Key={'TenantID': st.session_state.tenant, 'CierreID': c['CierreID']})
                st.success("✅ Caja reabierta"); time.sleep(1); st.rerun()
        else:
            res_cierre_calc = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_iso_cierre), FilterExpression=Attr('Tipo').eq('VENTA'))
            df_cierre = pd.DataFrame(res_cierre_calc.get('Items', []))

            if not df_cierre.empty:
                df_cierre['Total'] = pd.to_numeric(df_cierre['Total'], errors='coerce').fillna(0)
                total_cierre = df_cierre['Total'].sum()
                usuarios_turno = df_cierre['Usuario'].unique()

                st.info(f"💵 Total del día: S/ {float(total_cierre):.2f}")
                st.caption(f"Usuarios que vendieron: {', '.join(usuarios_turno)}")

                if st.button("🔒 CERRAR CAJA DEFINITIVO", use_container_width=True, type="primary", key="btn_cerrar_caja"):
                    for u in usuarios_turno:
                        registrar_cierre(total_cierre, u, "CIERRE_DIARIO", st.session_state.usuario, fecha_cierre.strftime('%d/%m/%Y'))
                    st.success(f"✅ Caja del {fecha_cierre.strftime('%d/%m/%Y')} cerrada"); time.sleep(1); st.rerun()
            else:
                st.info("No hay ventas para cerrar este día")
# === TAB CARGAR - SOLO DUEÑO ===
if st.session_state.rol == "DUEÑO" and len(tabs) > 4:
    with tabs[4]:
        st.subheader("📥 Cargar Productos")
        actual = contarProductosEnBD()
        st.info(f"Productos: {actual}/{MAX_PRODUCTOS_TOTALES} | Stock máx/producto: {MAX_STOCK_POR_PRODUCTO}")

        with st.expander("📝 AGREGAR PRODUCTO INDIVIDUAL", expanded=True):
            col1, col2 = st.columns(2)
            prod = col1.text_input("Producto:", max_chars=30, key="prod_cargar").upper().strip()
            pc = col1.number_input("Precio Compra:", min_value=0.0, value=0.0, key="pc_cargar")
            p = col2.number_input("Precio Venta:", min_value=0.01, value=1.0, key="p_cargar")
            s = col2.number_input("Stock:", min_value=0, value=0, key="s_cargar")

            if st.button("➕ AGREGAR PRODUCTO", use_container_width=True, key="btn_agregar_prod"):
                if prod and p > 0:
                    if actual >= MAX_PRODUCTOS_TOTALES:
                        st.error(f"❌ Límite de {MAX_PRODUCTOS_TOTALES} productos alcanzado")
                    elif s > MAX_STOCK_POR_PRODUCTO:
                        st.error(f"❌ Stock máximo por producto: {MAX_STOCK_POR_PRODUCTO}")
                    else:
                        try:
                            tabla_stock.put_item(Item={
                                'TenantID': st.session_state.tenant, 'Producto': prod,
                                'Precio_Compra': to_decimal(pc), 'Precio': to_decimal(p), 'Stock': int(s)
                            }, ConditionExpression='attribute_not_exists(Producto)')
                            registrar_kardex(prod, s, "CARGA_INICIAL", s * p, pc, "INVENTARIO")
                            st.success(f"✅ {prod} agregado"); time.sleep(1); st.rerun()
                        except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
                            st.error("❌ Producto ya existe")
                else:
                    st.error("❌ Completa todos los campos")

        st.write("---")
        st.subheader("📊 CARGA MASIVA EXCEL")
        st.caption("Formato: Producto | Precio_Compra | Precio | Stock")

        archivo = st.file_uploader("Sube tu Excel", type=['xlsx', 'xls'], key="upload_excel")
        if archivo:
            try:
                df_upload = pd.read_excel(archivo)
                df_upload.columns = [c.strip() for c in df_upload.columns]

                columnas_req = ['Producto', 'Precio_Compra', 'Precio', 'Stock']
                if not all(col in df_upload.columns for col in columnas_req):
                    st.error(f"❌ El Excel debe tener columnas: {', '.join(columnas_req)}")
                else:
                    df_upload['Producto'] = df_upload['Producto'].astype(str).str.upper().str.strip()
                    df_upload['Precio_Compra'] = pd.to_numeric(df_upload['Precio_Compra'], errors='coerce').fillna(0)
                    df_upload['Precio'] = pd.to_numeric(df_upload['Precio'], errors='coerce').fillna(0)
                    df_upload['Stock'] = pd.to_numeric(df_upload['Stock'], errors='coerce').fillna(0).astype(int)

                    df_upload = df_upload[df_upload['Producto']!= '']
                    df_upload = df_upload[df_upload['Precio'] > 0]
                    df_upload = df_upload[df_upload['Stock'] <= MAX_STOCK_POR_PRODUCTO]

                    if len(df_upload) + actual > MAX_PRODUCTOS_TOTALES:
                        st.error(f"❌ Excede límite. Máximo {MAX_PRODUCTOS_TOTALES - actual} productos más")
                    else:
                        st.write("**Vista previa:**")
                        for idx, row in df_upload.iterrows():
                            st.write(f"{row['Producto']} | S/{row['Precio_Compra']:.2f} | S/{row['Precio']:.2f} | {int(row['Stock'])}")

                        if st.button("🚀 CARGAR TODO", use_container_width=True, key="btn_cargar_excel"):
                            progreso = st.progress(0)
                            for idx, row in df_upload.iterrows():
                                tabla_stock.put_item(Item={
                                    'TenantID': st.session_state.tenant,
                                    'Producto': row['Producto'],
                                    'Precio_Compra': to_decimal(row['Precio_Compra']),
                                    'Precio': to_decimal(row['Precio']),
                                    'Stock': int(row['Stock'])
                                })
                                registrar_kardex(row['Producto'], row['Stock'], "CARGA_MASIVA", row['Stock'] * row['Precio'], row['Precio_Compra'], "EXCEL")
                                progreso.progress((idx + 1) / len(df_upload))
                            st.success(f"✅ {len(df_upload)} productos cargados"); time.sleep(1); st.rerun()
            except Exception as e:
                st.error(f"❌ Error al leer Excel: {e}")
# === TAB MANTENIMIENTO - SOLO DUEÑO ===
if st.session_state.rol == "DUEÑO" and len(tabs) > 5:
    with tabs[5]:
        st.subheader("🛠️ Mantenimiento")
        st.warning("⚠️ ZONA PELIGROSA - Acciones irreversibles")

        with st.expander("✏️ EDITAR PRODUCTO"):
            if not df_inv.empty:
                prod_edit = st.selectbox("Selecciona producto:", df_inv['Producto'].tolist(), key="sel_edit")
                if prod_edit:
                    df_prod = df_inv[df_inv['Producto'] == prod_edit].iloc[0]
                    col1, col2 = st.columns(2)
                    nuevo_pc = col1.number_input("Nuevo Precio Compra:", value=float(df_prod['Precio_Compra']), key="edit_pc")
                    nuevo_p = col1.number_input("Nuevo Precio Venta:", value=float(df_prod['Precio']), key="edit_p")
                    nuevo_s = col2.number_input("Nuevo Stock:", value=int(df_prod['Stock']), key="edit_s")

                    if st.button("💾 GUARDAR CAMBIOS", use_container_width=True, key="btn_guardar_edit"):
                        if nuevo_s > MAX_STOCK_POR_PRODUCTO:
                            st.error(f"❌ Stock máximo: {MAX_STOCK_POR_PRODUCTO}")
                        else:
                            tabla_stock.update_item(
                                Key={'TenantID': st.session_state.tenant, 'Producto': prod_edit},
                                UpdateExpression="SET Precio_Compra = :pc, Precio = :p, Stock = :s",
                                ExpressionAttributeValues={':pc': to_decimal(nuevo_pc), ':p': to_decimal(nuevo_p), ':s': int(nuevo_s)}
                            )
                            registrar_kardex(prod_edit, nuevo_s - int(df_prod['Stock']), "AJUSTE_MANUAL", 0, nuevo_pc, "MANTENIMIENTO")
                            st.success(f"✅ {prod_edit} actualizado"); time.sleep(1); st.rerun()

        with st.expander("🗑️ ELIMINAR PRODUCTO"):
            if not df_inv.empty:
                prod_del = st.selectbox("Selecciona producto a eliminar:", df_inv['Producto'].tolist(), key="sel_del")
                if st.button(f"🗑️ ELIMINAR {prod_del}", use_container_width=True, type="secondary", key="btn_eliminar"):
                    tabla_stock.delete_item(Key={'TenantID': st.session_state.tenant, 'Producto': prod_del})
                    registrar_kardex(prod_del, 0, "ELIMINADO", 0, 0, "MANTENIMIENTO")
                    st.success(f"✅ {prod_del} eliminado"); time.sleep(1); st.rerun()

        st.write("---")
        st.subheader("💳 Información de Plan")
        col1, col2, col3 = st.columns(3)
        col1.metric("Plan Actual", PLAN_ACTUAL)
        col2.metric("Precio Mensual", f"S/ {PRECIO_ACTUAL}")
        col3.metric("Productos", f"{contarProductosEnBD()}/{MAX_PRODUCTOS_TOTALES}")

        st.caption("💡 *Todos los planes incluyen instalación y configuración inicial sin costo adicional. Servicio por única vez al contratar.*")

        st.write("---")
        st.subheader("📲 Soporte Técnico")
        texto_soporte = f"Hola Alberto, soy {st.session_state.usuario} de {st.session_state.tenant}. Necesito ayuda con mi plan {PLAN_ACTUAL}."
        st.link_button("💬 HABLAR CON SOPORTE POR WHATSAPP", f"https://wa.me/{NUMERO_SOPORTE}?text={urllib.parse.quote(texto_soporte)}", use_container_width=True, type="primary")

# === SIDEBAR ===
with st.sidebar:
    st.markdown(f"""
        <div style='text-align:center; padding: 20px 0;'>
            <h2 style='margin:0; color:white;'>🚀 NEXUS</h2>
            <p style='margin:5px 0; color:white; opacity:0.8;'>{st.session_state.tenant}</p>
            <p style='margin:0; color:white; font-size:12px;'>{st.session_state.usuario}</p>
        </div>
    """, unsafe_allow_html=True)

    st.write("---")

    if st.button("🚪 CERRAR SESIÓN", use_container_width=True, key="btn_logout"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

    st.write("---")
    st.caption(f"Plan: {PLAN_ACTUAL}")
    st.caption(f"Versión 3.0")
    st.caption(DESARROLLADOR)
    st.caption("✨ Instalación inicial incluida en todos los planes")
