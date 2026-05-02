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
import pytesseract
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

st.set_page_config(
    page_title="NEXUS BALLARTA - Sistema POS",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "NEXUS BALLARTA v3.0 - Sistema de Punto de Venta Empresarial"
    }
)
tz_peru = pytz.timezone(F'America/Lima')
ayer = datetime.now(tz_peru) - timedelta(days=1)  # ← BIEN: usas tz_peru

# === CSS - PALETA ENTERPRISE ===
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
        * {font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;}

    html, body, [class*="stApp"], [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            color-scheme: light only!important;
            forced-color-adjust: none!important;
            -webkit-forced-color-adjust: none!important;
        }

.main {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)!important;}

.block-container {
            background: #ffffff!important;
            color: #0f172a!important;
            border-radius: 24px;
            padding: 3rem;
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04);
            border: 1px solid rgba(255,255,255,0.3);
            margin-top: 2rem;
            backdrop-filter: blur(10px);
        }

.block-container p,.block-container h1,.block-container h2,.block-container h3,
.block-container h4,.block-container label,.block-container span,
.stMarkdown,.stText,.stCaption {
            color: #0f172a!important;
        }

    h1 {font-weight: 900!important; letter-spacing: -0.03em; font-size: 3rem!important;}
    h2 {font-weight: 800!important; letter-spacing: -0.02em; font-size: 2rem!important;}
    h3 {font-weight: 700!important; letter-spacing: -0.02em; font-size: 1.5rem!important;}

    /* HERO LOGIN */
.hero-login {
            text-align: center;
            padding: 60px 20px 40px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 20px;
            margin: -3rem -3rem 2rem -3rem;
            color: white;
        }
.hero-login h1 {
            font-size: 4rem!important;
            font-weight: 900!important;
            margin: 0;
            color: white!important;
            text-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
.hero-login p {
            font-size: 1.25rem;
            opacity: 0.95;
            margin: 10px 0 0 0;
            color: white!important;
            font-weight: 500;
        }
.hero-badge {
            display: inline-block;
            background: rgba(255,255,255,0.2);
            backdrop-filter: blur(10px);
            padding: 8px 20px;
            border-radius: 50px;
            font-size: 0.9rem;
            font-weight: 600;
            margin-top: 15px;
            border: 1px solid rgba(255,255,255,0.3);
        }

    /* MÉTRICAS */
    div[data-testid="stMetric"] {
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)!important;
            padding: 28px;
            border-radius: 16px;
            box-shadow: 0 10px 15px -3px rgba(59,130,246,0.3);
            border: none;
        }
    div[data-testid="stMetric"] label {
            color: rgba(255,255,255,0.9)!important;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: white!important;
            font-size: 42px;
            font-weight: 800;
            letter-spacing: -0.03em;
        }
    div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
            color: #86efac!important;
            font-size: 15px;
            font-weight: 700;
        }

    /* BOTONES */
.stButton>button {
            border-radius: 10px;
            font-weight: 700;
            border: none;
            background: #3b82f6!important;
            color: white!important;
            box-shadow: 0 1px 3px 0 rgba(0,0,0,0.1), 0 1px 2px 0 rgba(0,0,0,0.06);
            height: 52px!important;
            font-size: 16px!important;
            letter-spacing: -0.01em;
            transition: all 0.15s ease;
        }
.stButton>button:hover {
            background: #2563eb!important;
            box-shadow: 0 10px 15px -3px rgba(59,130,246,0.4);
            transform: translateY(-2px);
        }
.stButton>button:active {
            transform: translateY(0px);
        }

    button[kind="primary"] {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%)!important;
            box-shadow: 0 4px 6px -1px rgba(16,185,129,0.3)!important;
        }
    button[kind="primary"]:hover {
            background: linear-gradient(135deg, #059669 0%, #047857 100%)!important;
            box-shadow: 0 10px 15px -3px rgba(16,185,129,0.4)!important;
        }

    /* TABS */
.stTabs [data-baseweb="tab-list"] {
            gap: 6px;
            background: #f1f5f9!important;
            padding: 8px;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
        }
.stTabs [data-baseweb="tab"] {
            border-radius: 8px;
            padding: 12px 24px;
            font-weight: 600;
            color: #64748b!important;
            font-size: 15px;
            transition: all 0.15s;
        }
.stTabs [data-baseweb="tab"]:hover {
            color: #334155!important;
            background: rgba(255,255,255,0.5);
        }
.stTabs [aria-selected="true"] {
            background: white!important;
            color: #0f172a!important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

    /* BOTONES DE PAGO */
    button[key="btn_yape"] {
            background: linear-gradient(135deg, #720e9e 0%, #5a0b7a 100%)!important;
            color: white!important;
            font-size: 24px!important;
            font-weight: 800!important;
            height: 100px!important;
            border: none!important;
            border-radius: 16px!important;
            box-shadow: 0 10px 15px -3px rgba(114,14,158,0.4)!important;
        }
    button[key="btn_plin"] {
            background: linear-gradient(135deg, #00b9e5 0%, #0094b8 100%)!important;
            color: white!important;
            font-size: 24px!important;
            font-weight: 800!important;
            height: 100px!important;
            border: none!important;
            border-radius: 16px!important;
            box-shadow: 0 10px 15px -3px rgba(0,185,229,0.4)!important;
        }
    button[key="btn_efectivo"] {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%)!important;
            color: white!important;
            font-size: 24px!important;
            font-weight: 800!important;
            height: 100px!important;
            border: none!important;
            border-radius: 16px!important;
            box-shadow: 0 10px 15px -3px rgba(16,185,129,0.4)!important;
        }
    button[key="btn_yape"]:hover, button[key="btn_plin"]:hover, button[key="btn_efectivo"]:hover {
            transform: translateY(-3px);
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3)!important;
        }

    /* INPUTS */
.stSelectbox>div {
            background: white!important;
            border: 1px solid #cbd5e1!important;
            border-radius: 10px!important;
            font-weight: 500;
            transition: all 0.15s;
        }
.stSelectbox>div:hover {
            border-color: #94a3b8!important;
        }
.stSelectbox>div:focus-within {
            border-color: #3b82f6!important;
            box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
        }
.stSelectbox>div>div>div {color: #0f172a!important; font-weight: 500;}
.stSelectbox svg {fill: #64748b!important;}

    [data-baseweb="select"] {background-color: white!important;}
    [data-baseweb="select"] > div {background-color: white!important; color: #0f172a!important;}
    [data-baseweb="popover"] {
            background-color: white!important;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04);
        }
    [data-baseweb="menu"] {background-color: white!important; padding: 8px;}
    [data-baseweb="menu"] li {
            background-color: white!important;
            color: #0f172a!important;
            font-weight: 500;
            border-radius: 8px;
            margin: 2px 0;
        }
    [data-baseweb="menu"] li:hover {background-color: #f1f5f9!important;}

.stTextInput>div>input,.stNumberInput>div>div>input,.stDateInput input {
            border-radius: 10px;
            border: 1px solid #cbd5e1!important;
            padding: 14px 18px;
            background: white!important;
            color: #0f172a!important;
            font-weight: 500;
            font-size: 15px;
            transition: all 0.15s;
        }
.stTextInput>div>input:hover,.stNumberInput>div>div>input:hover,.stDateInput input:hover {
            border-color: #94a3b8!important;
        }
.stTextInput>div>input:focus,.stNumberInput>div>div>input:focus,.stDateInput input:focus {
            border-color: #3b82f6!important;
            box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
            outline: none;
        }

    [data-testid="stNumberInput"] {background: white!important;}
    [data-testid="stNumberInput"] input {
            background-color: white!important;
            color: #0f172a!important;
            font-weight: 500;
        }
    [data-testid="stNumberInput"] button {
            background-color: #f8fafc!important;
            color: #64748b!important;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
        }
    [data-testid="stNumberInput"] button:hover {
            background-color: #f1f5f9!important;
            border-color: #cbd5e1;
        }

.stSelectbox label,.stTextInput label,.stNumberInput label,.stDateInput label,.stRadio label {
            color: #334155!important;
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 8px;
            display: block;
        }

    /* SIDEBAR */
    [data-testid="stSidebar"] {
            background: #0f172a!important;
            border-right: 1px solid #1e293b;
        }
    [data-testid="stSidebar"] * {color: white!important;}
    [data-testid="stSidebar"].stButton>button {
            background: #3b82f6!important;
            color: white!important;
            font-weight: 600;
            border: none;
            box-shadow: 0 4px 6px -1px rgba(59,130,246,0.3);
        }
    [data-testid="stSidebar"].stButton>button:hover {
            background: #2563eb!important;
            box-shadow: 0 10px 15px -3px rgba(59,130,246,0.4);
        }

    /* EXPANDERS */
    [data-testid="stExpander"] {
            background-color: white!important;
            border: 1px solid #e2e8f0!important;
            border-radius: 14px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
    [data-testid="stExpander"] summary {
            background: #f8fafc!important;
            color: #0f172a!important;
            font-weight: 600;
            border-radius: 14px;
            padding: 16px 20px;
            border: none;
            transition: all 0.15s;
        }
    [data-testid="stExpander"] summary:hover {
            background: #f1f5f9!important;
        }
    [data-testid="stExpander"] > div {
            background-color: white!important;
            padding: 8px 20px 20px 20px;
        }

.streamlit-expanderHeader {
            background: #f8fafc!important;
            border-radius: 14px;
            font-weight: 600;
            color: #0f172a!important;
            border: 1px solid #e2e8f0;
        }

    /* ALERTAS */
.stAlert {
            border-radius: 12px;
            border-left: 4px solid;
            font-weight: 500;
            padding: 18px 20px;
        }
    div[data-testid="stAlert"][data-baseweb="notification"] {
            background-color: #eff6ff;
            border-left-color: #3b82f6;
            color: #1e40af;
        }

    /* DATAFRAME */
.stDataFrame {
            border: 1px solid #e2e8f0!important;
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
.stDataFrame [data-testid="stTable"] {
            font-size: 14px;
            font-weight: 500;
        }

    /* CHECKBOX */
.stCheckbox {
            font-weight: 500;
            color: #334155;
        }

    /* SUCCESS/ERROR/WARNING */
.stSuccess {
            background-color: #f0fdf4;
            border-left: 4px solid #10b981;
            color: #065f46;
            border-radius: 12px;
            padding: 16px 20px;
            font-weight: 500;
        }
.stError {
            background-color: #fef2f2;
            border-left: 4px solid #ef4444;
            color: #991b1b;
            border-radius: 12px;
            padding: 16px 20px;
            font-weight: 500;
        }
.stWarning {
            background-color: #fffbeb;
            border-left: 4px solid #f59e0b;
            color: #92400e;
            border-radius: 12px;
            padding: 16px 20px;
            font-weight: 500;
        }
.stInfo {
            background-color: #eff6ff;
            border-left: 4px solid #3b82f6;
            color: #1e40af;
            border-radius: 12px;
            padding: 16px 20px;
            font-weight: 500;
        }
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

    if fecha:
        f = fecha

    tabla_cierres.put_item(Item={
        'TenantID': st.session_state.tenant,
        'CierreID': f"C-{uid}",
        'Fecha': f,  # formato normal (02/05/2026)

        # ✅ ESTA ES LA LÍNEA CLAVE
        'FechaISO': datetime.strptime(f, "%d/%m/%Y").strftime('%Y-%m-%d'),

        'UsuarioTurno': u_turno,
        'Total': total,
        'Estado': 'CERRADO'
    })
def obtener_limites_tenant():
    item = tabla_tenants.get_item(Key={'TenantID': st.session_state.tenant}).get('Item', {})
    if not item: st.error("Tenant no existe"); st.stop()
    if item.get('EstadoPago') == 'SUSPENDIDO': st.error(f"⛔ SUSPENDIDO. WhatsApp +{NUMERO_SOPORTE}"); st.stop()
    fc = datetime.strptime(item.get('ProximoCobro', '01/01/2000'), '%d/%m/%Y').date()
    if fc < datetime.now(tz_peru).date() - timedelta(days=5): st.error(f"⛔ VENCIÓ {item.get('ProximoCobro')}"); st.stop()
    max_p, max_s = int(item.get('MaxProductos', 0)), int(item.get('MaxStock', 0))
    if max_p == 0: st.error("Configura MaxProductos"); st.stop()
    
            # === BLOQUEO 700 PRODUCTOS SOLO BALLARTA ===
    if st.session_state.tenant == "BALLARTA" and contarProductosEnBD() >= 700:
        st.error("⛔ Límite de 700 productos alcanzado. Elimina productos o upgradea tu plan al +51914282688")
        st.stop()
        
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

# === PARCHE: SISTEMA VENCIMIENTO INTELIGENTE ===
def sistema_vencimiento_inteligente():
    """Avisos de vencimiento + 5 días de gracia + bloqueo total"""

    try:
        t = tabla_tenants.get_item(Key={'TenantID': st.session_state.tenant}).get('Item', {})
        if not t or 'ProximoCobro' not in t:
            return

        # Acepta formato 20/04/2026 o 2026-04-20
        fecha_str = str(t['ProximoCobro'])
        if '/' in fecha_str:
            fc = datetime.strptime(fecha_str, '%d/%m/%Y').date()
        else:
            fc = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            
        hoy = datetime.now(tz_peru).date()
        dias = (fc - hoy).days

        if 1 <= dias <= 3:
            st.warning(f"⚠️ Tu plan vence en {dias} días el {fecha_str}. Renueva al +{NUMERO_SOPORTE}")

        elif dias == 0:
            st.error(f"🚨 Tu plan vence HOY {fecha_str}. Tienes 5 días de gracia. Renueva ya al +{NUMERO_SOPORTE}")

        elif -5 < dias < 0:
            dias_gracia = 5 + dias
            st.error(f"🚨 PERÍODO DE GRACIA: Te quedan {dias_gracia} días. Renueva al +{NUMERO_SOPORTE}")
            
        # === ESTO ES LO NUEVO: BLOQUEO TOTAL DESPUÉS DE 5 DÍAS ===
        elif dias <= -5:
            st.markdown(f"""
            <style>
            .block-container {{padding: 0 !important;}}
            [data-testid="stHeader"] {{display: none;}}
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            </style>
            <div style="position:fixed; top:0; left:0; width:100vw; height:100vh; 
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        display:flex; align-items:center; justify-content:center; z-index:9999;">
                <div style="background:white; padding:50px; border-radius:20px; text-align:center; 
                            box-shadow:0 20px 60px rgba(0,0,0,0.3); max-width:400px;">
                    <div style="font-size:70px; margin-bottom:20px;">🔒</div>
                    <h1 style="color:#764ba2; margin:0 0 10px 0;">Suscripción Vencida</h1>
                    <p style="color:#666; font-size:18px;">Tu acceso expiró el <b>{fecha_str}</b></p>
                    <p style="color:#666; margin:20px 0;">Renueva tu plan para continuar</p>
                    <a href="https://wa.me/{NUMERO_SOPORTE}?text=Hola, quiero renovar NEXUS" 
                       target="_blank"
                       style="display:inline-block; background:#25D366; color:white; padding:15px 35px; 
                              border-radius:50px; text-decoration:none; font-weight:bold; font-size:18px;">
                        💬 WhatsApp Soporte
                    </a>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.stop()
            
    except Exception as e:
        pass

# === ESTADO ===
for k in ['auth','rol','tenant','usuario','carrito','boleta','confirmar','modo_lectura','intentos_login','bloqueo_hasta','metodo_pago']:
    if k not in st.session_state:
        if k in ['carrito']: st.session_state[k] = []
        elif k in ['auth','confirmar','modo_lectura']: st.session_state[k] = False
        elif k in ['intentos_login']: st.session_state[k] = 0
        elif k in ['bloqueo_hasta']: st.session_state[k] = None
        elif k == 'metodo_pago': st.session_state[k] = "💵 EFECTIVO"
        else: st.session_state[k] = None

# === LOGIN CON SEGURIDAD + HERO PREMIUM ===
if not st.session_state.auth:
    if st.session_state.bloqueo_hasta and datetime.now() < st.session_state.bloqueo_hasta:
        tiempo_restante = (st.session_state.bloqueo_hasta - datetime.now()).seconds
        st.error(f"🔒 BLOQUEADO POR SEGURIDAD")
        st.warning(f"⏱️ Espera {tiempo_restante} segundos para intentar de nuevo")
        st.progress(1 - (tiempo_restante / 300))
        time.sleep(1)
        st.rerun()

    # LOGO CON FALLBACK
    import os
    logo_path = "assets/logo.png"
    if os.path.exists(logo_path):
        col_logo1, col_logo2, col_logo3 = st.columns([1,2,1])
        with col_logo2:
            st.image(logo_path, width=200)

    # HERO SECTION PREMIUM
    st.markdown("""
        <div class='hero-login'>
            <h1>💎 NEXUS BALLARTA</h1>
            <p>Sistema de Punto de Venta Empresarial</p>
            <div class='hero-badge'>🚀 Tecnología de Alto Rendimiento</div>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.container():
            st.markdown("### 🔐 Acceso Seguro a tu Negocio")
            tenants = [k for k in st.secrets if k not in ["tablas", "aws"] and not k.endswith("_emp")]
            t_sel = st.selectbox("📍 Selecciona tu Negocio:", [t.replace("_", " ") for t in tenants], label_visibility="collapsed")
            t_key = t_sel.replace(" ", "_")

            tab_dueno, tab_empleado = st.tabs(["👑 DUEÑO", "👤 EMPLEADO"])

            with tab_dueno:
                st.markdown("##### Acceso Administrador")
                clave = st.text_input("🔑 Contraseña:", type="password", key="clave_dueno", placeholder="Ingresa tu contraseña").strip()[:30]
                if st.session_state.intentos_login > 0:
                    st.caption(f"⚠️ Intentos fallidos: {st.session_state.intentos_login}/5")
                if st.button("🔓 INGRESAR COMO DUEÑO", use_container_width=True, type="primary"):
                    if clave == str(st.secrets[t_key]["clave"]):
                        st.session_state.update({'auth':True,'tenant':t_sel,'rol':'DUEÑO','usuario':'DUEÑO','intentos_login':0})
                        st.success("✅ Bienvenido de vuelta")
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
                st.markdown("##### Acceso Operativo")
                nombre = st.text_input("👤 Tu nombre:", max_chars=20, key="nombre_emp", placeholder="Ej: JUAN").upper().strip()
                clave_emp = st.text_input("🔑 Contraseña:", type="password", key="clave_emp", placeholder="Contraseña del equipo").strip()[:30]
                if st.session_state.intentos_login > 0:
                    st.caption(f"⚠️ Intentos fallidos: {st.session_state.intentos_login}/5")
                if st.button("🧑‍💼 INGRESAR COMO EMPLEADO", use_container_width=True, type="primary"):
                    if nombre and clave_emp == str(st.secrets[f"{t_key}_emp"]["clave"]):
                        st.session_state.update({'auth':True,'tenant':t_sel,'rol':'EMPLEADO','usuario':nombre,'intentos_login':0})
                        st.success(f"✅ Bienvenido {nombre}")
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

            st.write("")
            st.caption("🔒 Conexión segura SSL | 💎 NEXUS v3.0 Enterprise")
            st.caption("Soporte 24/7: +51 914 282 688")
    st.stop()

# === POST LOGIN ===
sistema_vencimiento_inteligente()
MAX_PRODUCTOS_TOTALES, MAX_STOCK_POR_PRODUCTO, PLAN_ACTUAL, PRECIO_ACTUAL = obtener_limites_tenant()
df_inv = obtener_datos()
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state.usuario}")
    st.write(f"**Rol:** {st.session_state.rol}")
    
    # El contador que querías (11/700)
    cant_actual = len(df_inv) 
    st.metric(f"📊 {PLAN_ACTUAL}", f"{cant_actual}/{MAX_PRODUCTOS_TOTALES}")
    
    st.divider()
    
    st.markdown(f"👨‍💻 **{DESARROLLADOR}**")
    st.caption("Versión 3.0")
    
    if st.button("🚪 Cerrar Sesión", key="logout_sidebar"):
        st.session_state.clear()
        st.rerun()
# ----------------------
if st.session_state.get('modo_lectura', False): st.warning(st.session_state.mensaje_lectura)

# === TABS === EMPLEADO AHORA VE HISTORIAL
tabs_list = ["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL"]
if st.session_state.rol == "DUEÑO" and not st.session_state.get('modo_lectura', False):
    tabs_list += ["📥 CARGAR", "🛠️ MANT."]
tabs = st.tabs(tabs_list)
# === TAB VENTA ===
with tabs[0]:
    # 🔒 VALIDACIÓN PROFESIONAL DE CAJA
    hoy = datetime.now(tz_peru).date()
    hoy_iso = hoy.strftime('%Y-%m-%d')

    # 🔍 Verificar caja de HOY (apertura)
    res = tabla_cierres.query(
        KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant),
        FilterExpression=Attr('FechaISO').eq(hoy_iso)
    )

    items = res.get('Items', [])
    caja_abierta = any(i.get('Estado') == 'ABIERTA' for i in items)

    if not caja_abierta:
        st.warning("⚠️ Debes abrir caja antes de vender")

        if st.button("🔓 ABRIR CAJA"):
            tabla_cierres.put_item(Item={
                'TenantID': st.session_state.tenant,
                'CierreID': f"APERTURA#{hoy_iso}",
                'FechaISO': hoy_iso,
                'Fecha': hoy.strftime('%d/%m/%Y'),
                'UsuarioTurno': st.session_state.usuario,
                'Estado': 'ABIERTA',
                'Total': 0
            })
            st.success("Caja abierta")
            st.rerun()

        st.stop()

    # 🔒 BLOQUEAR SI AYER NO SE CERRÓ (Orden corregido)
    # 1. Definimos las fechas antes de la consulta
    ayer_dt = datetime.now(tz_peru) - timedelta(days=1)
    f_ayer = ayer_dt.strftime('%d/%m/%Y') 
    f_hoy = datetime.now(tz_peru).strftime('%d/%m/%Y')
    f_hoy_iso = datetime.now(tz_peru).strftime('%Y-%m-%d')

    # 2. Consulta eficiente con Query
        res_ayer = tabla_cierres.query(
            KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant),
            FilterExpression=Attr('Fecha').eq(f_ayer)
        )
    
    # 3. Validación de cierre
    items_ayer = res_ayer.get('Items', [])
    cerrado_ayer = any(i.get('Estado') == 'CERRADO' for i in items_ayer)

    if not cerrado_ayer:
        st.warning(f"⚠️ Ayer {f_ayer} no se cerró caja. Cierra cuando puedas.")

    # 4. Verificar si ya se cerró hoy para no duplicar
    res_hoy = tabla_cierres.query(
        KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant),
        FilterExpression=Attr('FechaISO').eq(f_hoy_iso) & Attr('Estado').eq('CERRADO')
    )
    ya_cerro_hoy = len(res_hoy.get('Items', [])) > 0

if ya_cerro_hoy:
    st.warning(f"⚠️ YA CERRASTE CAJA HOY A LAS {hora_cierre}")
    if st.button("🔓 REABRIR CAJA - SOLO ADMIN"):
        try:
            for c in res_cierre.get('Items', []):
                tabla_cierres.delete_item(
                    Key={'TenantID': st.session_state.tenant, 'CierreID': c['CierreID']}
                )
            st.success("✅ Caja reabierta correctamente")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al reabrir: {e}")
else:
    if st.session_state.boleta:
        b = st.session_state.boleta
        st.success("✅ VENTA REALIZADA")
        st.markdown(f"""<div style="background:white;color:black;padding:20px;border:2px solid #3b82f6;max-width:350px;margin:auto;font-family:monospace;border-radius:16px;box-shadow:0 10px 15px -3px rgba(59,130,246,0.3);">
            <h3 style="text-align:center;margin:0;color:#3b82f6;">{st.session_state.tenant}</h3>
            <p style="text-align:center;margin:0;">{b['fecha']} {b['hora']}</p><hr style="border-color:#3b82f6;">
            {''.join([f'<div style="display:flex;justify-content:space-between;"><span>{i["Cantidad"]}x {i["Producto"]}</span><span>S/{float(i["Subtotal"]):.2f}</span></div>' for i in b['items']])}
            <hr style="border-color:#3b82f6;"><div style="display:flex;justify-content:space-between;"><span>MÉTODO:</span><span>{b['metodo']}</span></div>
            <div style="display:flex;justify-content:space-between;color:#ef4444;"><span>DESC:</span><span>- S/{float(b['rebaja']):.2f}</span></div>
            <div style="display:flex;justify-content:space-between;font-size:18px;color:#3b82f6;"><b>NETO:</b><b>S/{float(b['t_neto']):.2f}</b></div>""", unsafe_allow_html=True)

        # PDF 80mm
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

        # EXCEL
        df_boleta = pd.DataFrame(b['items'])
        df_boleta['Fecha'] = b['fecha']
        df_boleta['Hora'] = b['hora']
        df_boleta['Metodo'] = b['metodo']
        df_boleta['Descuento'] = float(b['rebaja'])
        df_boleta['Total_Neto'] = float(b['t_neto'])
        buf_excel = io.BytesIO()
        with pd.ExcelWriter(buf_excel, engine='openpyxl') as w:
            df_boleta[['Fecha', 'Hora', 'Producto', 'Cantidad', 'Precio', 'Subtotal', 'Metodo', 'Descuento', 'Total_Neto']].to_excel(w, index=False, sheet_name='Ticket')

        # BOTONES DESCARGA
        col1, col2 = st.columns(2)
        col1.download_button("📄 PDF 80mm", pdf_output, f"Ticket_{b['fecha'].replace('/','')}.pdf", "application/pdf", use_container_width=True, key="btn_pdf_boleta")
        col2.download_button("📊 EXCEL", buf_excel.getvalue(), f"Ticket_{b['fecha'].replace('/','')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="btn_excel_boleta")

        # WHATSAPP
        if tiene_whatsapp_habilitado():
            texto = f"*TICKET - {st.session_state.tenant}*\n{b['fecha']} {b['hora']}\n---\n" + "\n".join([f"{i['Cantidad']}x {i['Producto']} - S/{float(i['Subtotal']):.2f}" for i in b['items']]) + f"\n---\n*TOTAL: S/{float(b['t_neto']):.2f}*\nMetodo: {b['metodo']}"
            st.link_button("📲 WhatsApp", f"https://wa.me/?text={urllib.parse.quote(texto)}", use_container_width=True)
# VERIFICAR CIERRE DE AYER
f_hoy, h_hoy, _ = obtener_tiempo_peru()
ayer = datetime.now(tz_peru) - timedelta(days=1)
f_ayer = ayer.strftime("%Y-%m-%d")

res_ayer = tabla_cierres.query(
    KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('Fecha').eq(f_ayer),
    FilterExpression=Attr('FechaISO').eq(f_ayer)
)
cerrado_ayer = any(i.get('Estado') == 'CERRADO' for i in res_ayer.get('Items', []))

if not cerrado_ayer:
    st.warning(f"⚠️ Ayer {f_ayer} no se cerró caja. Cierra cuando puedas.")
    st.info("Cierra caja de ayer antes de vender.")
# NUEVA VENTA
if st.button("⬅️ NUEVA VENTA", use_container_width=True, key="btn_nueva_venta"):
    st.session_state.boleta = None
    st.rerun()
else:
    tab_vender, tab_ingreso_emp = st.tabs(["🛒 VENDER", "📦 INGRESAR MERCADERÍA"])
    with tab_vender:
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
            st.info("No hay productos")
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
                c1, c2 = st.columns([3,1])
                c1.write(f"{item['Producto']} x{item['Cantidad']}")
                c2.write(f"S/{float(item['Subtotal']):.2f}")
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
            st.markdown(f"<h3 style='text-align:center;color:#3b82f6;'>Seleccionado: {metodo}</h3>", unsafe_allow_html=True)
            rebaja = st.number_input("💸 Descuento:", min_value=0.0, value=0.0, key="num_rebaja")
            total = max(Decimal('0.00'), sum(i['Subtotal'] for i in st.session_state.carrito) - to_decimal(rebaja))
            st.markdown(f"<h1 style='text-align:center;color:#3b82f6;font-size:3rem;'>S/ {float(total):.2f}</h1>", unsafe_allow_html=True)
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
    with tab_ingreso_emp:
        st.subheader("📦 Registrar Ingreso de Mercadería")
        st.caption("Busca y haz click en el producto")
        if not df_inv.empty:
            busq_ingreso = st.text_input("🔍 Buscar producto:", key="busq_ingreso_emp", placeholder="Ej: CUADERNO, LAPIZ...").upper()
            if busq_ingreso:
                df_filtrado = df_inv[df_inv['Producto'].str.contains(busq_ingreso, na=False)]
            else:
                df_filtrado = df_inv.head(20)
                st.caption("Mostrando primeros 20 productos. Escribe para buscar más.")
            if not df_filtrado.empty:
                st.write("**Click en la fila para seleccionar:**")
                df_tabla_busq = df_filtrado[['Producto', 'Stock', 'Precio_Compra']].copy()
                df_tabla_busq.columns = ['PRODUCTO', 'STOCK', 'COSTO']
                df_tabla_busq['STOCK'] = df_tabla_busq['STOCK'].astype(int)
            evento = st.dataframe(
                df_tabla_busq,
                use_container_width=True,
                hide_index=True,
                height=300,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "PRODUCTO": st.column_config.TextColumn("PRODUCTO", width="large"),
                    "STOCK": st.column_config.NumberColumn("STOCK", width="small"),
                    "COSTO": st.column_config.NumberColumn("COSTO", width="small", format="S/ %.2f")
                }
            )
            if evento.selection.rows:
                idx = evento.selection.rows[0]
                prod_ingreso = df_filtrado.iloc[idx]['Producto']
                df_prod = df_inv[df_inv['Producto'] == prod_ingreso].iloc[0]
                st.success(f"Seleccionado: **{prod_ingreso}**")
                st.info(f"Stock actual: {int(df_prod['Stock'])} unidades | Costo actual: S/{df_prod['Precio_Compra']:.2f}")
                st.markdown("**📦 DATOS DE LA COMPRA:**")
col1, col2, col3 = st.columns(3)
unidad_medida = col1.selectbox("Unidad:", ["Unidades", "Docenas", "Cajas", "Paquetes", "Millares"], key="unidad_medida_emp")
cantidad = col2.number_input(f"Cantidad:", min_value=1, value=1, key="cant_lote_emp")
costo_x_unidad = col3.number_input(f"Costo x unidad S/:", min_value=0.0, value=0.0, key="costo_x_unidad_emp")
multiplicador = {"Unidades": 1, "Docenas": 12, "Cajas": 1, "Paquetes": 1, "Millares": 1000}[unidad_medida]
if unidad_medida in ["Cajas", "Paquetes"]:
    unid_x_bulto = st.number_input(f"¿Cuántas unidades trae cada {unidad_medida[:-1]}?", min_value=1, value=50, key="unid_bulto_emp")
    multiplicador = unid_x_bulto
cant_ingreso = cantidad * multiplicador
nuevo_pc = costo_x_unidad
st.success(f"✅ Total: {cant_ingreso} unidades | Costo unitario: S/{nuevo_pc:.2f}")
stock_final = int(df_prod['Stock']) + cant_ingreso
st.metric("Stock nuevo", f"{stock_final} unidades")
if st.button("📥 REGISTRAR", use_container_width=True, type="primary", key="btn_ingreso_stock_emp"):
    if stock_final > MAX_STOCK_POR_PRODUCTO:
        st.error(f"❌ Stock máximo: {MAX_STOCK_POR_PRODUCTO}")
    else:
        stock_viejo = int(df_prod['Stock'])
        pc_viejo = float(df_prod['Precio_Compra'])
        pc_promedio = ((stock_viejo * pc_viejo) + (cant_ingreso * nuevo_pc)) / stock_final if stock_viejo > 0 else nuevo_pc
        tabla_stock.update_item(
            Key={'TenantID': st.session_state.tenant, 'Producto': prod_ingreso},
            UpdateExpression="SET Stock = :s, Precio_Compra = :pc",
            ExpressionAttributeValues={':s': stock_final, ':pc': to_decimal(pc_promedio)}
        )
        registrar_kardex(prod_ingreso, cant_ingreso, "INGRESO_STOCK", cant_ingreso * nuevo_pc, nuevo_pc, f"INGRESO_{st.session_state.usuario}")
        st.success(f"✅ {st.session_state.usuario} ingresó {cant_ingreso} {prod_ingreso} | Nuevo costo: S/{pc_promedio:.2f}")
        time.sleep(1)
        st.rerun()
else:
    st.info("👆 Haz click en una fila de la tabla para seleccionar")

# === TAB STOCK - SIN SCROLL + COSTO SOLO DUEÑO ===
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

            if st.session_state.rol == "DUEÑO":
                df_tabla = df_pagina[['Producto', 'Stock', 'Precio_Compra', 'Precio']].copy()
                df_tabla.columns = ['PROD', 'STOCK', 'COSTO', 'VENTA']
                df_tabla['STOCK'] = df_tabla['STOCK'].astype(int)
                column_config = {
                    "PROD": st.column_config.TextColumn("PROD", width="medium"),
                    "STOCK": st.column_config.NumberColumn("STOCK", width="small", format="%d"),
                    "COSTO": st.column_config.NumberColumn("COSTO", width="small", format="S/ %.2f"),
                    "VENTA": st.column_config.NumberColumn("VENTA", width="small", format="S/ %.2f")
                }
                col_order = ["PROD", "STOCK", "COSTO", "VENTA"]
            else:
                df_tabla = df_pagina[['Producto', 'Stock', 'Precio']].copy()
                df_tabla.columns = ['PROD', 'STOCK', 'VENTA']
                df_tabla['STOCK'] = df_tabla['STOCK'].astype(int)
                column_config = {
                    "PROD": st.column_config.TextColumn("PROD", width="large"),
                    "STOCK": st.column_config.NumberColumn("STOCK", width="small", format="%d"),
                    "VENTA": st.column_config.NumberColumn("VENTA", width="medium", format="S/ %.2f")
                }
                col_order = ["PROD", "STOCK", "VENTA"]

            st.dataframe(
                df_tabla,
                use_container_width=True,
                hide_index=True,
                height=400,
                column_config=column_config,
                column_order=col_order
            )

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

# === TAB REPORTES - GANANCIA SOLO DUEÑO ===
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
            st.markdown(f"<h1 style='margin:0;font-size:38px;color:#3b82f6;'>S/ {float(vt):.2f}</h1>", unsafe_allow_html=True)
            if dif >= 0:
                st.success(f"↑ {abs(pct):.1f}% vs semana pasada")
            else:
                st.error(f"↓ {abs(pct):.1f}% vs semana pasada")

        with col2:
            if st.session_state.rol == "DUEÑO":
                st.markdown("### 📈 GANANCIA REAL")
                st.markdown(f"<h1 style='margin:0;font-size:38px;color:#10b981;'>S/ {float(gn_total):.2f}</h1>", unsafe_allow_html=True)
                st.info(f"Tickets: {tk} | Ticket Prom: S/{float(tp):.2f} | Margen: {(gn_total/vt*100) if vt > 0 else 0:.1f}%")
            else:
                st.markdown("### 📊 RESUMEN")
                st.markdown(f"<h1 style='margin:0;font-size:38px;color:#10b981;'>{tk} Tickets</h1>", unsafe_allow_html=True)
                st.info(f"Ticket Promedio: S/{float(tp):.2f}")

        st.write("---")

        with st.expander("🧾 VER TICKETS DEL DÍA - MÁS RECIENTE ARRIBA", expanded=True):
            df_tickets = df_v[['Hora', 'Producto', 'Cantidad', 'Total']].copy()
            df_tickets['Cantidad'] = df_tickets['Cantidad'].astype(int)
            df_tickets.columns = ['HORA', 'PROD', 'CANT', 'TOTAL']
            st.dataframe(
                df_tickets,
                use_container_width=True,
                hide_index=True,
                height=350,
                column_config={
                    "HORA": st.column_config.TextColumn("HORA", width="small"),
                    "PROD": st.column_config.TextColumn("PROD", width="medium"),
                    "CANT": st.column_config.NumberColumn("CANT", width="small"),
                    "TOTAL": st.column_config.NumberColumn("TOTAL", width="small", format="S/ %.2f")
                }
            )

        df_ef = df_v[df_v['Metodo'].str.contains('EFECTIVO')]
        df_yape = df_v[df_v['Metodo'].str.contains('YAPE')]
        df_plin = df_v[df_v['Metodo'].str.contains('PLIN')]

        cols = st.columns(3)
        if not df_ef.empty:
            venta_ef = df_ef['Total'].sum()
            gan_ef = df_ef['Ganancia_Item'].sum()
            if st.session_state.rol == "DUEÑO":
                cols[0].metric("💵 EFECTIVO", f"S/ {float(venta_ef):.2f}", f"Ganancia: S/ {float(gan_ef):.2f}")
            else:
                cols[0].metric("💵 EFECTIVO", f"S/ {float(venta_ef):.2f}")

        if not df_yape.empty:
            venta_yape = df_yape['Total'].sum()
            gan_yape = df_yape['Ganancia_Item'].sum()
            if st.session_state.rol == "DUEÑO":
                cols[1].metric("🟣 YAPE", f"S/ {float(venta_yape):.2f}", f"Ganancia: S/ {float(gan_yape):.2f}")
            else:
                cols[1].metric("🟣 YAPE", f"S/ {float(venta_yape):.2f}")

        if not df_plin.empty:
            venta_plin = df_plin['Total'].sum()
            gan_plin = df_plin['Ganancia_Item'].sum()
            if st.session_state.rol == "DUEÑO":
                cols[2].metric("🔵 PLIN", f"S/ {float(venta_plin):.2f}", f"Ganancia: S/ {float(gan_plin):.2f}")
            else:
                cols[2].metric("🔵 PLIN", f"S/ {float(venta_plin):.2f}")

# === TAB HISTORIAL - DUEÑO Y EMPLEADO - CIERRE PARA AMBOS ===
with tabs[3]:
    st.subheader("📋 Historial Kardex")
    col_f1, col_f2 = st.columns([3,1])
    f_h = col_f1.date_input("Día:", value=datetime.now(tz_peru).date(), key="date_historial_fix")
    if col_f2.button("🔄 ACTUALIZAR", use_container_width=True, key="btn_actualizar_hist"): st.cache_data.clear(); st.rerun()

    fecha_iso_h = f_h.strftime('%Y-%m-%d')

    if st.session_state.rol == "EMPLEADO":
        res_h = tabla_movs.query(
            IndexName='TenantID-FechaISO-index',
            KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_iso_h),
            FilterExpression=Attr('Usuario').eq(st.session_state.usuario)
        )
        st.info(f"📊 Viendo solo TUS movimientos - {st.session_state.usuario}")
    else:
        res_h = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_iso_h))

    df_h = pd.DataFrame(res_h.get('Items', []))

    if not df_h.empty:
        df_h = df_h.sort_values('Hora', ascending=False)
        df_h['Total'] = pd.to_numeric(df_h['Total'], errors='coerce').fillna(0)
        df_h['Precio_Compra'] = pd.to_numeric(df_h['Precio_Compra'], errors='coerce').fillna(0)
        df_h['Cantidad'] = pd.to_numeric(df_h['Cantidad'], errors='coerce').fillna(0)
        df_h['Usuario'] = df_h['Usuario'].fillna('SISTEMA')
        df_h['Costo'] = df_h['Precio_Compra'] * df_h['Cantidad']
        df_h['Ganancia'] = df_h.apply(lambda r: r['Total'] - r['Costo'] if r['Tipo'] == 'VENTA' else 0, axis=1)

        df_tabla_h = df_h[['Hora', 'Producto', 'Tipo', 'Cantidad', 'Usuario']].copy()
        df_tabla_h['Cantidad'] = df_tabla_h['Cantidad'].astype(int)
        df_tabla_h.columns = ['HORA', 'PROD', 'TIPO', 'CANT', 'USUARIO']

        st.dataframe(
            df_tabla_h,
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "HORA": st.column_config.TextColumn("HORA", width="small"),
                "PROD": st.column_config.TextColumn("PROD", width="medium"),
                "TIPO": st.column_config.TextColumn("TIPO", width="small"),
                "CANT": st.column_config.NumberColumn("CANT", width="small"),
                "USUARIO": st.column_config.TextColumn("QUIÉN", width="small")
            }
        )

        df_v_h = df_h[df_h['Tipo'] == 'VENTA']
        if not df_v_h.empty:
            vt_h = df_v_h['Total'].sum()
            costo_h = df_v_h['Costo'].sum()
            gn_h = df_v_h['Ganancia'].sum()

            if st.session_state.rol == "DUEÑO":
                col1, col2, col3 = st.columns(3)
                col1.metric("💰 VENTA TOTAL", f"S/ {float(vt_h):.2f}")
                col2.metric("📉 COSTO TOTAL", f"S/ {float(costo_h):.2f}")
                col3.metric("📈 GANANCIA REAL", f"S/ {float(gn_h):.2f}")
            else:
                col1, col2 = st.columns(2)
                col1.metric("💰 VENTA TOTAL", f"S/ {float(vt_h):.2f}")
                col2.metric("📊 TICKETS", len(df_v_h))

            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w: df_h.to_excel(w, index=False)
            st.download_button("📥 DESCARGAR EXCEL", buf.getvalue(), f"Kardex_{f_h.strftime('%Y%m%d')}.xlsx", use_container_width=True, key="btn_desc_kardex")

            if tiene_whatsapp_habilitado():
                if st.session_state.rol == "DUEÑO":
                    res = f"*REPORTE {f_h.strftime('%d/%m/%Y')}*\nVenta: S/{float(vt_h):.2f}\nCosto: S/{float(costo_h):.2f}\n*Ganancia: S/{float(gn_h):.2f}*"
                else:
                    res = f"*REPORTE {f_h.strftime('%d/%m/%Y')} - {st.session_state.usuario}*\nVenta: S/{float(vt_h):.2f}\nTickets: {len(df_v_h)}"
                st.link_button("📲 COMPARTIR", f"https://wa.me/?text={urllib.parse.quote(res)}", use_container_width=True)
            else:
                st.caption("💡 WhatsApp solo disponible en Plan PRO/PREMIUM")
        else:
            st.info("No hay ventas este día")
    else:
        st.info(f"📭 No hay movimientos el {f_h.strftime('%d/%m/%Y')}")

    st.write("---")
    st.subheader("🔒 Cierre de Caja")
    st.caption(f"Usuario actual: {st.session_state.usuario}")

    fecha_cierre = st.date_input("Fecha a cerrar:", value=datetime.now(tz_peru).date(), key="date_cierre_fix")
    fecha_iso_cierre = fecha_cierre.strftime('%Y-%m-%d')

    if st.session_state.rol == "EMPLEADO":
        res_cierre_check = tabla_cierres.query(
            KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant),
            FilterExpression=Attr('Fecha').eq(fecha_cierre.strftime('%d/%m/%Y')) & Attr('UsuarioTurno').eq(st.session_state.usuario)
        )
    else:
        res_cierre_check = tabla_cierres.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant), FilterExpression=Attr('Fecha').eq(fecha_cierre.strftime('%d/%m/%Y')))

    ya_cerro_caja = len(res_cierre_check.get('Items', [])) > 0

    if ya_cerro_caja:
        st.success(f"✅ Caja del {fecha_cierre.strftime('%d/%m/%Y')} ya fue cerrada")
        if st.session_state.rol == "DUEÑO":
            if st.button("🔓 REABRIR CAJA", use_container_width=True, key="btn_reabrir_caja_hist"):
                for c in res_cierre_check.get('Items', []):
                    tabla_cierres.delete_item(Key={'TenantID': st.session_state.tenant, 'CierreID': c['CierreID']})
                st.success("✅ Caja reabierta"); time.sleep(1); st.rerun()
    else:
        if st.session_state.rol == "EMPLEADO":
            res_cierre_calc = tabla_movs.query(
                IndexName='TenantID-FechaISO-index',
                KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_iso_cierre),
                FilterExpression=Attr('Tipo').eq('VENTA') & Attr('Usuario').eq(st.session_state.usuario)
            )
        else:
            res_cierre_calc = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_iso_cierre), FilterExpression=Attr('Tipo').eq('VENTA'))

        df_cierre = pd.DataFrame(res_cierre_calc.get('Items', []))

        if not df_cierre.empty:
            df_cierre['Total'] = pd.to_numeric(df_cierre['Total'], errors='coerce').fillna(0)
            total_cierre = df_cierre['Total'].sum()

            if st.session_state.rol == "EMPLEADO":
                st.info(f"💵 Total de TUS ventas: S/ {float(total_cierre):.2f}")
            else:
                usuarios_turno = df_cierre['Usuario'].unique()
                st.info(f"💵 Total del día: S/ {float(total_cierre):.2f}")
                st.caption(f"Usuarios que vendieron: {', '.join(usuarios_turno)}")

            if st.button("🔒 CERRAR CAJA", use_container_width=True, type="primary", key="btn_cerrar_caja"):
                registrar_cierre(total_cierre, st.session_state.usuario, "CIERRE_DIARIO", st.session_state.usuario, fecha_cierre.strftime('%d/%m/%Y'))
                st.success(f"✅ Caja del {fecha_cierre.strftime('%d/%m/%Y')} cerrada por {st.session_state.usuario}"); time.sleep(1); st.rerun()
        else:
            st.info("No hay ventas para cerrar este día")

# === TAB CARGAR - SOLO DUEÑO ===
if st.session_state.rol == "DUEÑO":
    with tabs[4]:
        st.subheader("📥 Cargar Productos")
        st.info(f"Productos: {contarProductosEnBD()}/{MAX_PRODUCTOS_TOTALES} | Stock máx/producto: {MAX_STOCK_POR_PRODUCTO}")

        tab_nuevo, tab_stock, tab_masiva = st.tabs(["➕ PRODUCTO NUEVO", "📦 INGRESO DE STOCK", "📤 CARGAR MASIVA"])

        # === PRODUCTO NUEVO ===
        with tab_nuevo:
            st.markdown("#### Crear producto desde cero")
            coll, col2 = st.columns(2)
            prod_nuevo = coll.text_input("Nombre producto:", key="prod_nuevo_carga").upper().strip()
            precio_compra_nuevo = col2.number_input("Costo S/:", min_value=0.0, value=0.0, key="pc_nuevo")
            
        col3, col4 = st.columns(2)
        precio_venta_nuevo = col3.number_input("Precio venta S/:", min_value=0.01, value=1.0, key="pv_nuevo")
        stock_inicial = col4.number_input("Stock inicial:", min_value=0, value=0, key="stock_nuevo")
        
        if st.button("💾 CREAR PRODUCTO", use_container_width=True, type="primary", key="btn_crear_nuevo"):
            if not prod_nuevo:
                st.error("❌ Pon nombre al producto")
            elif df_inv['Producto'].str.upper().eq(prod_nuevo).any():
                st.error(f"❌ {prod_nuevo} ya existe. Usa INGRESO DE STOCK para aumentar")
            elif contarProductosEnBD() >= MAX_PRODUCTOS_TOTALES:
                st.error(f"⛔ Límite {MAX_PRODUCTOS_TOTALES} productos alcanzado")
            elif stock_inicial > MAX_STOCK_POR_PRODUCTO:
                st.error(f"❌ Stock máximo por producto: {MAX_STOCK_POR_PRODUCTO}")
            else:
                tabla_stock.put_item(Item={
                    'TenantID': st.session_state.tenant,
                    'Producto': prod_nuevo,
                    'Precio_Compra': to_decimal(precio_compra_nuevo),
                    'Precio': to_decimal(precio_venta_nuevo),
                    'Stock': int(stock_inicial)
                })
                if stock_inicial > 0:
                    registrar_kardex(prod_nuevo, stock_inicial, "INGRESO_INICIAL", stock_inicial * precio_compra_nuevo, precio_compra_nuevo, "CREACION")
                st.success(f"✅ {prod_nuevo} creado")
                time.sleep(1)
                st.rerun()
    
    # === INGRESO DE STOCK ===
    with tab_stock:
        st.markdown("#### Aumentar stock de producto existente")
        busq_ing = st.text_input("🔍 Buscar:", key="busq_ing_carga").upper()
        df_busq = df_inv[df_inv['Producto'].str.contains(busq_ing, na=False)] if busq_ing else df_inv.head(20)
        
        if not df_busq.empty:
            evento = st.dataframe(df_busq[['Producto', 'Stock', 'Precio_Compra']], use_container_width=True, 
                                  hide_index=True, on_select="rerun", selection_mode="single-row", height=250)
            
            if evento.selection.rows:
                prod_sel = df_busq.iloc[evento.selection.rows[0]]['Producto']
                df_prod = df_inv[df_inv['Producto'] == prod_sel].iloc[0]
                st.success(f"Seleccionado: **{prod_sel}** | Stock: {int(df_prod['Stock'])}")
                
                col1, col2 = st.columns(2)
                cant_add = col1.number_input("Cantidad a ingresar:", min_value=1, value=1, key="cant_add_carga")
                costo_lote = col2.number_input("Costo x unidad S/:", min_value=0.0, value=float(df_prod['Precio_Compra']), key="costo_add_carga")
                
                stock_final = int(df_prod['Stock']) + cant_add
                st.metric("Stock nuevo", f"{stock_final} unidades")
                
                if st.button("📥 INGRESAR STOCK", use_container_width=True, type="primary", key="btn_ing_stock"):
                    if stock_final > MAX_STOCK_POR_PRODUCTO:
                        st.error(f"❌ Stock máximo: {MAX_STOCK_POR_PRODUCTO}")
                    else:
                        stock_viejo = int(df_prod['Stock'])
                        pc_viejo = float(df_prod['Precio_Compra'])
                        pc_promedio = ((stock_viejo * pc_viejo) + (cant_add * costo_lote)) / stock_final if stock_viejo > 0 else costo_lote
                        
                        tabla_stock.update_item(
                            Key={'TenantID': st.session_state.tenant, 'Producto': prod_sel},
                            UpdateExpression="SET Stock = :s, Precio_Compra = :pc",
                            ExpressionAttributeValues={':s': stock_final, ':pc': to_decimal(pc_promedio)}
                        )
                        registrar_kardex(prod_sel, cant_add, "INGRESO_STOCK", cant_add * costo_lote, costo_lote, "CARGA")
                        st.success(f"✅ {cant_add} unidades ingresadas | Nuevo costo prom: S/{pc_promedio:.2f}")
                        time.sleep(1)
                        st.rerun()
        else:
            st.warning("No se encontró producto")
    
    # === CARGA MASIVA SOLO NUEVOS ===
    with tab_masiva:
        st.markdown("#### 📤 Cargar Excel con productos NUEVOS")
        st.warning("⚠️ SOLO crea productos que NO existan. Los existentes se ignoran.")
        
        st.markdown("""
        **Formato Excel requerido:**
        | Producto | Precio_Compra | Precio | Stock |
        |---|---|---|---|
        | CUADERNO A4 | 2.50 | 4.00 | 100 |
        """)
        
        archivo = st.file_uploader("Subir Excel", type=['xlsx'], key="upload_masiva")
        
        if archivo:
            df_excel = pd.read_excel(archivo)
            df_excel.columns = df_excel.columns.str.strip()
            cols_req = ['Producto', 'Precio_Compra', 'Precio', 'Stock']
            
            if not all(c in df_excel.columns for c in cols_req):
                st.error(f"❌ Excel debe tener columnas: {cols_req}")
            else:
                productos_existentes = df_inv['Producto'].str.upper().tolist()
                df_excel['Producto'] = df_excel['Producto'].str.upper().str.strip()
                
                # SOLO NUEVOS
                df_nuevos = df_excel[~df_excel['Producto'].isin(productos_existentes)].copy()
                df_duplicados = df_excel[df_excel['Producto'].isin(productos_existentes)]
                
                total_actual = contarProductosEnBD()
                total_nuevos = len(df_nuevos)
                
                st.info(f"📊 Excel: {len(df_excel)} filas | Nuevos: {total_nuevos} | Duplicados: {len(df_duplicados)} | Actual BD: {total_actual}/{MAX_PRODUCTOS_TOTALES}")
                
                if len(df_duplicados) > 0:
                    with st.expander(f"⚠️ {len(df_duplicados)} productos ya existen - SE IGNORARÁN"):
                        st.dataframe(df_duplicados[['Producto']], hide_index=True)
                
                if total_actual + total_nuevos > MAX_PRODUCTOS_TOTALES:
                    st.error(f"⛔ Con estos {total_nuevos} nuevos pasarías el límite de {MAX_PRODUCTOS_TOTALES}")
                elif total_nuevos == 0:
                    st.warning("No hay productos nuevos para cargar")
                else:
                    # Validar stock máximo
                    df_stock_alto = df_nuevos[df_nuevos['Stock'] > MAX_STOCK_POR_PRODUCTO]
                    if not df_stock_alto.empty:
                        st.error(f"❌ {len(df_stock_alto)} productos superan stock máximo {MAX_STOCK_POR_PRODUCTO}")
                        st.dataframe(df_stock_alto[['Producto', 'Stock']], hide_index=True)
                    else:
                        st.success(f"✅ Listo para cargar {total_nuevos} productos nuevos")
                        if st.button(f"🚀 CARGAR {total_nuevos} PRODUCTOS", use_container_width=True, type="primary", key="btn_carga_masiva"):
                            with st.spinner(f"Cargando {total_nuevos} productos en bloques de 25..."):
                                # === BATCH WRITE DE 25 EN 25 ===
                                BATCH_SIZE = 25
                                total_cargados = 0
                                
                                for i in range(0, len(df_nuevos), BATCH_SIZE):
                                    batch = df_nuevos.iloc[i:i+BATCH_SIZE]
                                    
                                    with tabla_stock.batch_writer() as writer:
                                        for _, row in batch.iterrows():
                                            writer.put_item(Item={
                                                'TenantID': st.session_state.tenant,
                                                'Producto': str(row['Producto']),
                                                'Precio_Compra': to_decimal(row['Precio_Compra']),
                                                'Precio': to_decimal(row['Precio']),
                                                'Stock': int(row['Stock'])
                                            })
                                            total_cargados += 1
                                    
                                    # Pausa de 0.2 seg entre batches para no saturar DynamoDB
                                    time.sleep(0.2)
                                    st.toast(f"Cargados {min(i+BATCH_SIZE, total_nuevos)}/{total_nuevos}", icon="📦")
                                
                                # Registrar kardex después de cargar todo
                                for _, row in df_nuevos.iterrows():
                                    if int(row['Stock']) > 0:
                                        registrar_kardex(str(row['Producto']), int(row['Stock']), "INGRESO_MASIVO", 
                                                       int(row['Stock']) * float(row['Precio_Compra']), float(row['Precio_Compra']), "CARGA_MASIVA")
                            
                            st.success(f"✅ {total_cargados} productos creados en {len(df_nuevos)//BATCH_SIZE + 1} bloques")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()

# === TAB MANTENIMIENTO - BORRAR Y CORREGIR ===
if st.session_state.rol == "DUEÑO":
    
    with tabs[5]:
        
        st.subheader("🛠️ Mantenimiento de Inventario")
        tab_editar, tab_borrar = st.tabs(["✏️ EDITAR", "🗑️ ELIMINAR"])
    
        with tab_editar:
            
            st.markdown("#### Corregir producto existente")
        busq_edit = st.text_input("🔍 Buscar:", key="busq_edit").upper()
        df_edit = df_inv[df_inv['Producto'].str.contains(busq_edit, na=False)] if busq_edit else df_inv.head(20)
        
        if not df_edit.empty:
            evento_edit = st.dataframe(df_edit, use_container_width=True, hide_index=True, 
                                       on_select="rerun", selection_mode="single-row", height=250)
            
            if evento_edit.selection.rows:
                prod_edit = df_edit.iloc[evento_edit.selection.rows[0]]
                st.info(f"Editando: **{prod_edit['Producto']}**")
                
                col1, col2 = st.columns(2)
                nuevo_nombre = col1.text_input("Nombre:", value=prod_edit['Producto'], key="edit_nombre").upper()
                nuevo_pc = col2.number_input("Costo S/:", value=float(prod_edit['Precio_Compra']), key="edit_pc")
                col3, col4 = st.columns(2)
                nuevo_pv = col3.number_input("Precio venta S/:", value=float(prod_edit['Precio']), key="edit_pv")
                nuevo_stock = col4.number_input("Stock:", value=int(prod_edit['Stock']), min_value=0, key="edit_stock")
                
                if st.button("💾 GUARDAR CAMBIOS", use_container_width=True, type="primary", key="btn_guardar_edit"):
                    # Si cambió nombre, borrar viejo y crear nuevo
                    if nuevo_nombre!= prod_edit['Producto']:
                        if df_inv['Producto'].str.upper().eq(nuevo_nombre).any():
                            st.error(f"❌ Ya existe un producto llamado {nuevo_nombre}")
                        else:
                            tabla_stock.delete_item(Key={'TenantID': st.session_state.tenant, 'Producto': prod_edit['Producto']})
                            tabla_stock.put_item(Item={
                                'TenantID': st.session_state.tenant,
                                'Producto': nuevo_nombre,
                                'Precio_Compra': to_decimal(nuevo_pc),
                                'Precio': to_decimal(nuevo_pv),
                                'Stock': int(nuevo_stock)
                            })
                            registrar_kardex(nuevo_nombre, nuevo_stock, "EDICION_NOMBRE", 0, nuevo_pc, f"ANTES:{prod_edit['Producto']}")
                            st.success(f"✅ Renombrado a {nuevo_nombre}")
                    else:
                        tabla_stock.update_item(
                            Key={'TenantID': st.session_state.tenant, 'Producto': prod_edit['Producto']},
                            UpdateExpression="SET Precio_Compra = :pc, Precio = :pv, Stock = :s",
                            ExpressionAttributeValues={':pc': to_decimal(nuevo_pc), ':pv': to_decimal(nuevo_pv), ':s': int(nuevo_stock)}
                        )
                        registrar_kardex(prod_edit['Producto'], nuevo_stock, "EDICION", 0, nuevo_pc, "MANTENIMIENTO")
                        st.success(f"✅ {prod_edit['Producto']} actualizado")
                    time.sleep(1)
                    st.rerun()
    
    # === ELIMINAR ===
    with tab_borrar:
        st.markdown("#### ⚠️ Eliminar producto permanentemente")
        st.error("CUIDADO: Esto borra el producto y su historial de stock. No se puede deshacer.")
        
        busq_del = st.text_input("🔍 Buscar para eliminar:", key="busq_del").upper()
        df_del = df_inv[df_inv['Producto'].str.contains(busq_del, na=False)] if busq_del else pd.DataFrame()
        
        if not df_del.empty:
            evento_del = st.dataframe(df_del[['Producto', 'Stock']], use_container_width=True, hide_index=True,
                                      on_select="rerun", selection_mode="single-row", height=200)
            
            if evento_del.selection.rows:
                prod_del = df_del.iloc[evento_del.selection.rows[0]]['Producto']
                st.warning(f"Vas a eliminar: **{prod_del}**")
                confirmar = st.text_input(f"Escribe ELIMINAR para confirmar:", key="confirm_del")
                
                if st.button("🗑️ ELIMINAR DEFINITIVAMENTE", use_container_width=True, key="btn_eliminar"):
                    if confirmar == "ELIMINAR":
                        tabla_stock.delete_item(Key={'TenantID': st.session_state.tenant, 'Producto': prod_del})
                        registrar_kardex(prod_del, 0, "ELIMINADO", 0, 0, "MANTENIMIENTO")
                        st.success(f"✅ {prod_del} eliminado")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Escribe ELIMINAR exacto para confirmar")
