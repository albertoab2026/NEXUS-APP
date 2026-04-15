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
        st.error("⚠️ Error: Credenciales AWS no encontradas en Secrets.")
        st.stop()
        
    aws_id = st.secrets["aws"]["aws_access_key_id"].strip()
    aws_key = st.secrets["aws"]["aws_secret_access_key"].strip()
    aws_region = st.secrets["aws"]["aws_region"].strip()
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    # Conexión a tus tablas SaaS
    tabla_ventas = dynamodb.Table('SaaS_Ventas_Test')
    tabla_stock = dynamodb.Table('SaaS_Stock_Test')
    tabla_auditoria = dynamodb.Table('SaaS_Audit_Test')
except Exception as e:
    st.error(f"❌ Error de conexión AWS: {e}")
    st.stop()

# ==========================================
# 3. CONTROL DE ESTADOS (MEMORIA)
# ==========================================
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'tenant_id' not in st.session_state: st.session_state.tenant_id = None
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'reset_v' not in st.session_state: st.session_state.reset_v = 0
if 'df_stock_local' not in st.session_state: st.session_state.df_stock_local = None

def actualizar_stock_local():
    try:
        # Filtro de seguridad: Solo trae lo que pertenece al usuario logueado
        response = tabla_stock.scan(
            FilterExpression=Attr('TenantID').eq(st.session_state.tenant_id)
        )
        items = response.get('Items', [])
        
        if items:
            df = pd.DataFrame(items)
            for col in ['Stock', 'Precio', 'P_Compra_U']:
                if col not in df.columns: df[col] = 0
            
            df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
            df['P_Compra_U'] = pd.to_numeric(df['P_Compra_U'], errors='coerce').fillna(0.0)
            df['Producto'] = df['Producto'].astype(str).str.upper().str.strip()
            
            # Consolidación de datos
            df = df.groupby('Producto').agg({
                'Stock': 'sum', 
                'Precio': 'max', 
                'P_Compra_U': 'max'
            }).reset_index()
            
            st.session_state.df_stock_local = df.sort_values(by='Producto')
        else:
            st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])
    except Exception:
        st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])

# ==========================================
# 4. PANTALLA DE LOGIN PROFESIONAL
# ==========================================
if not st.session_state.sesion_iniciada:
    # Estilo visual Nexus
    st.markdown(f"""
        <div style='text-align: center; padding: 20px;'>
            <h1 style='color: #1A5276; font-family: sans-serif; letter-spacing: 2px;'>{MARCA_SaaS}</h1>
            <p style='color: #5499C7; font-size: 1.2em;'>Cloud Management System</p>
            <hr style='border: 1px solid #D4E6F1;'>
        </div>
    """, unsafe_allow_html=True)
    
    # Carga de clientes desde Secrets
    if "auth_multi" in st.secrets:
        locales_disponibles = list(st.secrets["auth_multi"].keys())
    else:
        st.error("Error: Configure la sección [auth_multi] en sus Secrets.")
        st.stop()

    col_l, col_r = st.columns([1, 1])
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
                with st.spinner("Verificando identidad..."):
                    time.sleep(2) # Seguridad anti-fuerza bruta
                st.error("❌ Credenciales inválidas.")
    
    with col_r:
        st.markdown(f"""
            <div style='background-color: #F4F6F7; padding: 30px; border-radius: 10px; border-left: 5px solid #1A5276;'>
                <h4>Bienvenido a Nexus Ballarta</h4>
                <p>Usted está accediendo a un entorno seguro multi-inquilino. 
                Sus datos están cifrados y aislados por <b>TenantID</b>.</p>
                <small>Soporte: ballarta.tech@soporte.com</small>
            </div>
        """, unsafe_allow_html=True)
    st.stop()

# ==========================================
# 5. INTERFAZ PRINCIPAL (DASHBOARD)
# ==========================================
with st.sidebar:
    st.markdown(f"<h2 style='color: #1A5276;'>{MARCA_SaaS}</h2>", unsafe_allow_html=True)
    st.write(f"🏢 **Local:** {st.session_state.tenant_id}")
    st.divider()
    
    if st.button("🔴 CERRAR SESIÓN", use_container_width=True):
        st.session_state.sesion_iniciada = False
        st.session_state.tenant_id = None
        st.rerun()
    
    st.info("Estado: En línea ✅")

tabs = st.tabs(["🛒 VENTAS", "📦 INVENTARIO", "📊 REPORTES", "📋 HISTORIAL"])

df_stock = st.session_state.df_stock_local

# --- PESTAÑA: VENTAS ---
with tabs[0]:
    if st.session_state.boleta:
        st.balloons()
        b = st.session_state.boleta
        ticket_html = f"""
        <div style="background-color: #FFF; color: #000; padding: 20px; border: 2px solid #333; font-family: 'Courier New', Courier, monospace; max-width: 300px; margin: auto;">
            <center><h3>{st.session_state.tenant_id}</h3><p>{b['fecha']}</p></center><hr>
        """
        for i in b['items']:
            ticket_html += f"<p>{i['Cantidad']} x {i['Producto']}<br>Subtotal: S/ {i['Subtotal']:.2f}</p>"
        ticket_html += f"<hr><h3>TOTAL: S/ {b['total_neto']:.2f}</h3><center>Nexus Ballarta SaaS</center></div>"
        
        st.markdown(ticket_html, unsafe_allow_html=True)
        if st.button("NUEVA VENTA", use_container_width=True):
            st.session_state.boleta = None
            st.rerun()
    else:
        st.subheader("🛒 Punto de Venta")
        bus_v = st.text_input("🔍 Buscar Producto:", key="bus_v").upper()
        prod_filt = [p for p in df_stock['Producto'].tolist() if bus_v in p]
        
        c1, c2 = st.columns([3, 1])
        with c1:
            if prod_filt:
                p_sel = st.selectbox("Seleccione:", prod_filt, key=f"sel_{st.session_state.reset_v}")
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                st.write(f"**Disponibilidad:** {info['Stock']} unidades | **Precio:** S/ {info['Precio']}")
            else: st.warning("Producto no disponible.")
        with c2:
            cant = st.number_input("Cantidad:", min_value=1, value=1)

        if st.button("➕ AÑADIR AL CARRITO", use_container_width=True) and prod_filt:
            if cant <= info['Stock']:
                st.session_state.carrito.append({
                    'Producto': p_sel, 'Cantidad': int(cant), 
                    'Precio': float(info['Precio']), 'P_Compra_U': float(info['P_Compra_U']),
                    'Subtotal': round(float(info['Precio']) * cant, 2),
                    'TenantID': st.session_state.tenant_id
                })
                st.session_state.reset_v += 1
                st.rerun()
            else: st.error("Stock insuficiente.")

        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c[['Producto', 'Cantidad', 'Subtotal']])
            
            if st.button("🚀 FINALIZAR Y COBRAR", use_container_width=True):
                fecha, hora, dt_obj, id_v = obtener_tiempo_peru()
                total = df_c['Subtotal'].sum()
                
                try:
                    # Guardar Venta con TenantID
                    tabla_ventas.put_item(Item={
                        'VentaID': id_v,
                        'TenantID': st.session_state.tenant_id,
                        'Fecha': fecha,
                        'Total': str(total),
                        'Items': st.session_state.carrito
                    })
                    # Actualizar Stock
                    for item in st.session_state.carrito:
                        tabla_stock.update_item(
                            Key={'Producto': item['Producto']},
                            UpdateExpression="SET Stock = Stock - :v",
                            ExpressionAttributeValues={':v': item['Cantidad']}
                        )
                    st.session_state.boleta = {'fecha': fecha, 'items': st.session_state.carrito, 'total_neto': total}
                    st.session_state.carrito = []
                    actualizar_stock_local()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error en transacción: {e}")

# --- PESTAÑA: STOCK ---
with tabs[1]:
    st.subheader("📦 Gestión de Inventario Local")
    with st.expander("➕ Registrar Nuevo Producto"):
        with st.form("form_nuevo"):
            n_prod = st.text_input("Nombre:").upper().strip()
            n_stk = st.number_input("Stock Inicial:", min_value=0)
            n_pre = st.number_input("Precio Venta (S/):", min_value=0.0)
            n_com = st.number_input("Costo Compra (S/):", min_value=0.0)
            
            if st.form_submit_button("Guardar en Nube"):
                if n_prod:
                    tabla_stock.put_item(Item={
                        'Producto': n_prod,
                        'TenantID': st.session_state.tenant_id, # IMPORTANTE: SELLA EL DUEÑO
                        'Stock': int(n_stk),
                        'Precio': str(n_pre),
                        'P_Compra_U': str(n_com)
                    })
                    st.success("Producto registrado exitosamente.")
                    actualizar_stock_local()
                    st.rerun()
    
    st.dataframe(df_stock, use_container_width=True)

# --- PESTAÑAS VACÍAS PARA TUS 100 LÍNEAS DE REPORTES ---
with tabs[2]: st.info("📊 Módulo de Analítica Nexus: Cargue sus datos de ventas aquí.")
with tabs[3]: st.info("📋 Auditoría: Registro de movimientos históricos por Tenant.")
