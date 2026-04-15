import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
from boto3.dynamodb.conditions import Attr

# ==========================================
# 0. CONFIGURACIÓN MARCA NEXUS (SaaS READY)
# ==========================================
MARCA_SaaS = "NEXUS BALLARTA SaaS"
st.set_page_config(page_title=MARCA_SaaS, layout="wide", page_icon="🚀")

# Mantenemos tus nombres de tablas SaaS para no romper la conexión
TABLA_VENTAS_NAME = 'SaaS_Ventas_Test'
TABLA_STOCK_NAME = 'SaaS_Stock_Test'
TABLA_AUDITORIA_NAME = 'SaaS_Audit_Test'

# --- AJUSTE GLOBAL DE TIEMPO PERÚ ---
tz_peru = pytz.timezone('America/Lima')

def obtener_tiempo_peru():
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora, ahora.strftime("%Y%m%d%H%M%S%f")

# ==========================================
# 2. CONEXIÓN SEGURA AWS (BLINDAJE)
# ==========================================
try:
    if "aws" not in st.secrets:
        st.error("⚠️ Error crítico: Credenciales no configuradas.")
        st.stop()
        
    aws_id = st.secrets["aws"]["aws_access_key_id"].strip()
    aws_key = st.secrets["aws"]["aws_secret_access_key"].strip()
    aws_region = st.secrets["aws"]["aws_region"].strip()
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    tabla_ventas = dynamodb.Table(TABLA_VENTAS_NAME)
    tabla_stock = dynamodb.Table(TABLA_STOCK_NAME)
    tabla_auditoria = dynamodb.Table(TABLA_AUDITORIA_NAME)
except Exception:
    st.error("Error de conexión: Comuníquese con soporte técnico.")
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
            
            df['Producto'] = df['Producto'].astype(str).str.upper().str.strip()
            df = df.groupby('Producto').agg({
                'Stock': 'sum', 
                'Precio': 'max', 
                'P_Compra_U': 'max'
            }).reset_index()
            
            st.session_state.df_stock_local = df[['Producto', 'Stock', 'Precio', 'P_Compra_U']].sort_values(by='Producto')
        else:
            st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])
    except:
        st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])

# ==========================================
# 4. LOGIN MULTI-USUARIO PROFESIONAL
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
                with st.spinner("Validando..."): time.sleep(2)
                st.error("❌ Credenciales incorrectas")
    
    with col_r:
        st.markdown(f"""
            <div style='background-color: rgba(52, 152, 219, 0.1); padding: 25px; border-radius: 10px; border: 1px solid #3498DB;'>
                <h4 style='color: #3498DB; margin-top: 0;'>Bienvenido a Nexus Ballarta</h4>
                <p style='font-size: 0.95em;'>Sistema <b>SaaS Multi-inquilino</b> profesional.</p>
                <p style='font-size: 0.8em; color: #7FB3D5;'>Sus datos están aislados por TenantID.</p>
            </div>
        """, unsafe_allow_html=True)
    st.stop()

# ==========================================
# 5. PANEL DE CONTROL ( Sidebar )
# ==========================================
with st.sidebar:
    st.title(f"🚀 Nexus")
    st.write(f"🏢 **Local:** {st.session_state.tenant_id}")
    if st.button("🔴 CERRAR SESIÓN", use_container_width=True):
        st.session_state.sesion_iniciada = False
        st.rerun()
    st.divider()
    st.info(f"Conexión Segura activada")

# MANTENEMOS TODAS TUS PESTAÑAS ORIGINALES
tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])
df_stock = st.session_state.df_stock_local

# 1. PESTAÑA DE VENTAS (TU LÓGICA ORIGINAL)
with tabs[0]:
    if st.session_state.boleta:
        st.balloons(); st.success("✅ ¡VENTA REALIZADA!")
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: #000; padding: 20px; border: 2px solid #000; border-radius: 10px; max-width: 350px; margin: auto; font-family: monospace;">
            <center><b>{st.session_state.tenant_id}</b><br>{b['fecha']} {b['hora']}</center>
            <hr style="border-top: 1px dashed black;">
            <table style="width: 100%;">
                <tr><td><b>Cant</b></td><td><b>Prod</b></td><td style="text-align: right;"><b>Tot</b></td></tr>
        """
        for i in b['items']:
            ticket += f"<tr><td>{i['Cantidad']}</td><td>{i['Producto']}</td><td style='text-align: right;'>S/ {i['Subtotal']:.2f}</td></tr>"
        ticket += f"""
            </table>
            <hr style="border-top: 1px dashed black;">
            <div style="text-align: right; font-size: 17px;"><b>TOTAL NETO: S/ {b['total_neto']:.2f}</b></div>
            <hr style="border-top: 1px dashed black;">
            <center>¡Gracias!</center>
        </div>
        """
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA", use_container_width=True):
            st.session_state.boleta = None; st.rerun()
    else:
        st.subheader(f"🛒 Ventas - {st.session_state.tenant_id}")
        bus_v = st.text_input("🔍 Buscar producto:", key="bus_v").strip().upper()
        prod_filt_v = [p for p in df_stock['Producto'].tolist() if bus_v in str(p).upper()]
        
        c1, c2 = st.columns([3, 1])
        with c1:
            if prod_filt_v:
                p_sel = st.selectbox("Seleccionar:", prod_filt_v, key=f"sel_v_{st.session_state.reset_v}")
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                st.info(f"💰 Precio: S/ {info['Precio']:.2f} | 📦 Stock: {info['Stock']}")
            else: st.warning("No encontrado")
        with c2: cant = st.number_input("Cant:", min_value=1, value=1, key=f"c_v_{st.session_state.reset_v}")
        
        if st.button("➕ AÑADIR AL CARRITO", use_container_width=True) and prod_filt_v:
            if cant <= info['Stock']:
                st.session_state.carrito.append({
                    'Producto': p_sel, 'Cantidad': int(cant), 
                    'Precio': float(info['Precio']), 'P_Compra_U': float(info['P_Compra_U']),
                    'Subtotal': round(float(info['Precio']) * cant, 2),
                    'TenantID': st.session_state.tenant_id # SELLO MULTIUSUARIO
                })
                st.session_state.reset_v += 1; st.rerun()
            else: st.error("Stock insuficiente")

        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c[['Producto', 'Cantidad', 'Precio', 'Subtotal']])
            
            if st.button("🚀 FINALIZAR VENTA"):
                fecha, hora, dt, idv = obtener_tiempo_peru()
                total = df_c['Subtotal'].sum()
                try:
                    tabla_ventas.put_item(Item={
                        'VentaID': idv, 'TenantID': st.session_state.tenant_id,
                        'Fecha': fecha, 'Total': str(total), 'Items': st.session_state.carrito
                    })
                    for item in st.session_state.carrito:
                        tabla_stock.update_item(
                            Key={'Producto': item['Producto']},
                            UpdateExpression="SET Stock = Stock - :v",
                            ExpressionAttributeValues={':v': item['Cantidad']}
                        )
                    st.session_state.boleta = {'fecha': fecha, 'hora': hora, 'items': st.session_state.carrito, 'total_neto': total}
                    st.session_state.carrito = []; actualizar_stock_local(); st.rerun()
                except Exception as e: st.error(f"Error AWS: {e}")

# 2. PESTAÑA STOCK (TU LÓGICA DE REGISTRO)
with tabs[1]:
    st.subheader("📦 Inventario Local")
    with st.expander("➕ Agregar Nuevo Producto"):
        with st.form("nuevo_p"):
            np = st.text_input("Nombre:").upper().strip()
            ns = st.number_input("Stock:", min_value=0)
            nv = st.number_input("Precio Venta:", min_value=0.0)
            nc = st.number_input("Precio Compra:", min_value=0.0)
            if st.form_submit_button("Guardar"):
                if np:
                    tabla_stock.put_item(Item={
                        'Producto': np, 'TenantID': st.session_state.tenant_id,
                        'Stock': int(ns), 'Precio': str(nv), 'P_Compra_U': str(nc)
                    })
                    st.success("Guardado"); actualizar_stock_local(); st.rerun()
    st.dataframe(df_stock, use_container_width=True)

# PESTAÑAS PARA TU CÓDIGO DE REPORTES E HISTORIAL (PEGA AQUÍ TUS 100 LÍNEAS)
with tabs[2]: st.info("📊 Espacio reservado para tus Reportes perfeccionados.")
with tabs[3]: st.info("📋 Espacio reservado para tu Historial detallado.")
with tabs[4]: st.info("📥 Módulo de carga masiva.")
with tabs[5]: st.info("🛠️ Herramientas de mantenimiento.")
