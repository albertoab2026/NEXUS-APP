import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
from boto3.dynamodb.conditions import Attr

# ==========================================
# 1. CONFIGURACIÓN DE MARCA Y PÁGINA
# ==========================================
MARCA_SaaS = "NEXUS BALLARTA SaaS"
st.set_page_config(page_title=MARCA_SaaS, layout="wide", page_icon="🚀")

# Nombres de tus nuevas tablas en AWS
TABLA_VENTAS_NAME = 'SaaS_Ventas_Test'
TABLA_STOCK_NAME = 'SaaS_Stock_Test'
TABLA_AUDITORIA_NAME = 'SaaS_Audit_Test'

# --- AJUSTE GLOBAL DE TIEMPO PERÚ ---
tz_peru = pytz.timezone('America/Lima')

def obtener_tiempo_peru():
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora, ahora.strftime("%Y%m%d%H%M%S%f")

# ==========================================
# 2. CONEXIÓN SEGURA AWS
# ==========================================
try:
    if "aws" not in st.secrets:
        st.error("⚠️ Error: Credenciales AWS no configuradas en Secrets.")
        st.stop()
        
    aws_id = st.secrets["aws"]["aws_access_key_id"].strip()
    aws_key = st.secrets["aws"]["aws_secret_access_key"].strip()
    aws_region = st.secrets["aws"]["aws_region"].strip()
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    tabla_ventas = dynamodb.Table(TABLA_VENTAS_NAME)
    tabla_stock = dynamodb.Table(TABLA_STOCK_NAME)
except Exception as e:
    st.error(f"❌ Error de conexión AWS: {e}")
    st.stop()

# ==========================================
# 3. CONTROL DE ESTADOS (TU METODOLOGÍA)
# ==========================================
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'tenant_id' not in st.session_state: st.session_state.tenant_id = None
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'reset_v' not in st.session_state: st.session_state.reset_v = 0
if 'df_stock_local' not in st.session_state: st.session_state.df_stock_local = None

def actualizar_stock_local():
    try:
        # FILTRO SaaS: Solo trae los productos del local logueado
        response = tabla_stock.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant_id))
        items = response.get('Items', [])
        if items:
            df = pd.DataFrame(items)
            for col in ['Stock', 'Precio', 'P_Compra_U']:
                if col not in df.columns: df[col] = 0
            df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
            df['P_Compra_U'] = pd.to_numeric(df['P_Compra_U'], errors='coerce').fillna(0.0)
            df['Producto'] = df['Producto'].astype(str).str.upper().strip()
            
            st.session_state.df_stock_local = df.groupby('Producto').agg({
                'Stock': 'sum', 'Precio': 'max', 'P_Compra_U': 'max'
            }).reset_index().sort_values(by='Producto')
        else:
            st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])
    except:
        st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])

# ==========================================
# 4. LOGIN ADAPTABLE (LIGHT/DARK)
# ==========================================
if not st.session_state.sesion_iniciada:
    st.markdown(f"""
        <div style='text-align: center; padding: 10px;'>
            <h1 style='color: #3498DB; font-family: sans-serif; margin-bottom: 0;'>{MARCA_SaaS}</h1>
            <p style='color: #7FB3D5;'>Cloud Inventory Management</p>
        </div>
    """, unsafe_allow_html=True)
    
    locales_disponibles = list(st.secrets.get("auth_multi", {}).keys())
    
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("🔑 Acceso Seguro")
        local_sel = st.selectbox("Seleccione su Empresa:", locales_disponibles)
        clave = st.text_input("Contraseña de Acceso:", type="password")
        
        if st.button("🔓 Entrar al Sistema", use_container_width=True):
            pass_correcta = st.secrets["auth_multi"][local_sel].strip()
            if clave == pass_correcta:
                st.session_state.sesion_iniciada = True
                st.session_state.tenant_id = local_sel
                actualizar_stock_local()
                st.rerun()
            else:
                with st.spinner("Validando..."): time.sleep(1)
                st.error("❌ Credenciales inválidas.")
    
    with col_r:
        st.markdown(f"""
            <div style='background-color: rgba(52, 152, 219, 0.1); padding: 25px; border-radius: 10px; border: 1px solid #3498DB;'>
                <h4 style='color: #3498DB; margin-top: 0;'>Bienvenido</h4>
                <p style='font-size: 0.95em;'>Entorno <b>SaaS Multi-inquilino</b>.</p>
                <p style='font-size: 0.8em; color: #7FB3D5;'>ID de Sesión: {local_sel if local_sel else "Esperando..."}</p>
            </div>
        """, unsafe_allow_html=True)
    st.stop()

# ==========================================
# 5. INTERFAZ PRINCIPAL (LOGUEADO)
# ==========================================
with st.sidebar:
    st.markdown(f"<h2 style='color: #3498DB;'>{MARCA_SaaS}</h2>", unsafe_allow_html=True)
    st.write(f"🏢 **Local:** {st.session_state.tenant_id}")
    st.divider()
    if st.button("🔴 CERRAR SESIÓN", use_container_width=True):
        st.session_state.sesion_iniciada = False
        st.rerun()

# CREACIÓN DE PESTAÑAS
tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])
df_stock = st.session_state.df_stock_local

# --- 1. PESTAÑA: VENTAS ---
with tabs[0]:
    if st.session_state.boleta:
        b = st.session_state.boleta
        st.success("✅ VENTA REALIZADA")
        st.markdown(f"""
            <div style="background-color: white; color: black; padding: 20px; border: 2px solid #333; font-family: monospace; max-width: 320px; margin: auto;">
                <center><h3>{st.session_state.tenant_id}</h3><p>{b['fecha']}</p></center><hr>
                {"".join([f"<p>{i['Cantidad']} x {i['Producto']} - S/ {i['Subtotal']:.2f}</p>" for i in b['items']])}
                <hr><h3>TOTAL: S/ {b['total_neto']:.2f}</h3>
            </div>
        """, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA"): st.session_state.boleta = None; st.rerun()
    else:
        st.subheader("🛒 Registro de Venta")
        bus_v = st.text_input("🔍 Buscar Producto:", key="bus_v").upper()
        prod_filt = [p for p in df_stock['Producto'].tolist() if bus_v in p]
        
        c1, c2 = st.columns(2)
        with c1:
            if prod_filt:
                p_sel = st.selectbox("Seleccionar:", prod_filt, key=f"sel_{st.session_state.reset_v}")
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                st.write(f"Stock: **{info['Stock']}** | Precio: **S/ {info['Precio']:.2f}**")
            else: st.warning("Sin resultados.")
        with c2:
            cant = st.number_input("Cantidad:", min_value=1, value=1, key=f"cant_{st.session_state.reset_v}")

        if st.button("➕ AÑADIR AL CARRITO", use_container_width=True) and prod_filt:
            if cant <= info['Stock']:
                st.session_state.carrito.append({
                    'Producto': p_sel, 'Cantidad': int(cant), 'Precio': float(info['Precio']),
                    'P_Compra_U': float(info['P_Compra_U']), 'Subtotal': round(float(info['Precio']) * cant, 2),
                    'TenantID': st.session_state.tenant_id
                })
                st.session_state.reset_v += 1; st.rerun()
            else: st.error("No hay stock suficiente.")

        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c[['Producto', 'Cantidad', 'Subtotal']])
            if st.button("🚀 FINALIZAR VENTA", use_container_width=True):
                f, h, dt, idv = obtener_tiempo_peru()
                total = df_c['Subtotal'].sum()
                try:
                    tabla_ventas.put_item(Item={'VentaID': idv, 'TenantID': st.session_state.tenant_id, 'Fecha': f, 'Total': str(total), 'Items': st.session_state.carrito})
                    for item in st.session_state.carrito:
                        tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="SET Stock = Stock - :v", ExpressionAttributeValues={':v': item['Cantidad']})
                    st.session_state.boleta = {'fecha': f, 'items': st.session_state.carrito, 'total_neto': total}
                    st.session_state.carrito = []; actualizar_stock_local(); st.rerun()
                except Exception as e: st.error(f"Error AWS: {e}")

# --- 2. PESTAÑA: STOCK (FORMULARIO PARA AGREGAR PRODUCTO) ---
with tabs[1]:
    st.subheader("📦 Gestión de Inventario")
    
    # Este es el formulario que faltaba en la foto
    with st.expander("➕ REGISTRAR / ACTUALIZAR PRODUCTO", expanded=True):
        with st.form("f_stock"):
            col1, col2 = st.columns(2)
            with col1:
                np = st.text_input("Nombre del Producto:").upper().strip()
                ns = st.number_input("Stock Inicial:", min_value=0)
            with col2:
                nv = st.number_input("Precio de Venta (S/):", min_value=0.0)
                nc = st.number_input("Costo de Compra (S/):", min_value=0.0)
            
            if st.form_submit_button("💾 GUARDAR"):
                if np:
                    tabla_stock.put_item(Item={
                        'Producto': np,
                        'TenantID': st.session_state.tenant_id, # SELLO DE DUEÑO
                        'Stock': int(ns),
                        'Precio': str(nv),
                        'P_Compra_U': str(nc)
                    })
                    st.success(f"'{np}' guardado en {st.session_state.tenant_id}")
                    actualizar_stock_local(); st.rerun()
                else: st.error("Falta el nombre.")

    st.markdown("### 📋 Lista de Precios y Stock Actual")
    st.dataframe(df_stock, use_container_width=True)

# --- RESTO DE PESTAÑAS (REPORTES E HISTORIAL) ---
with tabs[2]: st.info("📊 Módulo de Reportes Nexus.")
with tabs[3]: st.info("📋 Historial de Movimientos.")
with tabs[4]: st.info("📥 Carga de Inventario Masiva.")
with tabs[5]: 
    st.subheader("🛠️ Herramientas de Mantenimiento")
    st.write("Configuración del sistema.")
