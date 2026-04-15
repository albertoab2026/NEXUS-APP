import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
from boto3.dynamodb.conditions import Attr

# 1. CONFIGURACIÓN E INTERFAZ
st.set_page_config(page_title="Sistema SaaS Dental Pro", layout="wide", page_icon="🦷")

# --- AJUSTE GLOBAL DE TIEMPO PERÚ ---
tz_peru = pytz.timezone('America/Lima')

def obtener_tiempo_peru():
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora, ahora.strftime("%Y%m%d%H%M%S%f")

# 2. CONEXIÓN SEGURA AWS
try:
    if "aws" not in st.secrets:
        st.error("⚠️ Error crítico: Credenciales AWS no configuradas en Secrets.")
        st.stop()
        
    aws_id = st.secrets["aws"]["aws_access_key_id"].strip()
    aws_key = st.secrets["aws"]["aws_secret_access_key"].strip()
    aws_region = st.secrets["aws"]["aws_region"].strip()
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    # Tablas SaaS Test (Según tu configuración de AWS)
    tabla_ventas = dynamodb.Table('SaaS_Ventas_Test')
    tabla_stock = dynamodb.Table('SaaS_Stock_Test')
    tabla_auditoria = dynamodb.Table('SaaS_Audit_Test')
except Exception as e:
    st.error(f"❌ Error de conexión AWS: {e}")
    st.stop()

# 3. CONTROL DE ESTADOS
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'tenant_id' not in st.session_state: st.session_state.tenant_id = None
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'reset_v' not in st.session_state: st.session_state.reset_v = 0
if 'df_stock_local' not in st.session_state: st.session_state.df_stock_local = None

def actualizar_stock_local():
    try:
        # Filtramos el Stock para que solo traiga lo del cliente logueado (TenantID)
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
            
            # Agrupar por si hay duplicados
            df = df.groupby('Producto').agg({
                'Stock': 'sum', 
                'Precio': 'max', 
                'P_Compra_U': 'max'
            }).reset_index()
            
            st.session_state.df_stock_local = df.sort_values(by='Producto')
        else:
            st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])
    except Exception as e:
        st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])

# --- LOGIN MULTI-TENANT ---
if not st.session_state.sesion_iniciada:
    st.markdown("<h1 style='text-align: center;'>🦷 SaaS Dental Login</h1>", unsafe_allow_html=True)
    
    # Carga automática de locales desde Secrets
    if "auth_multi" in st.secrets:
        locales_disponibles = list(st.secrets["auth_multi"].keys())
    else:
        st.error("Error: No se encontró la sección [auth_multi] en Secrets.")
        st.stop()

    col_login, _ = st.columns([1, 1])
    with col_login:
        local_sel = st.selectbox("Seleccione su Clínica:", locales_disponibles)
        clave = st.text_input("Clave de acceso:", type="password")
        
        if st.button("🔓 Ingresar", use_container_width=True):
            pass_correcta = st.secrets["auth_multi"][local_sel].strip()
            
            if clave == pass_correcta:
                st.session_state.sesion_iniciada = True
                st.session_state.tenant_id = local_sel
                actualizar_stock_local()
                st.rerun()
            else: 
                with st.spinner("Verificando..."):
                    time.sleep(2) # Seguridad anti-fuerza bruta
                st.error("❌ Acceso denegado.")
    st.stop()

# --- INTERFAZ PRINCIPAL (LOGUEADO) ---
with st.sidebar:
    st.title(f"🦷 {st.session_state.tenant_id}")
    if st.button("🔴 CERRAR SESIÓN", use_container_width=True):
        st.session_state.sesion_iniciada = False
        st.session_state.tenant_id = None
        st.rerun()
    st.divider()
    st.info(f"Usuario: Administrador\nLocal: {st.session_state.tenant_id}")

tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR"])

df_stock = st.session_state.df_stock_local

# --- PESTAÑA 1: VENTAS ---
with tabs[0]:
    if st.session_state.boleta:
        st.balloons(); st.success("✅ VENTA EXITOSA")
        b = st.session_state.boleta
        # Formato de Ticket HTML
        ticket = f"""
        <div style="background-color: white; color: black; padding: 15px; border: 1px solid black; font-family: monospace;">
            <center><b>{st.session_state.tenant_id}</b><br>{b['fecha']}</center><hr>
        """
        for i in b['items']:
            ticket += f"{i['Cantidad']} x {i['Producto']} - S/ {i['Subtotal']:.2f}<br>"
        ticket += f"<hr><b>TOTAL: S/ {b['total_neto']:.2f}</b></div>"
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("NUEVA VENTA"): st.session_state.boleta = None; st.rerun()
    else:
        st.subheader("Punto de Venta")
        bus_v = st.text_input("🔍 Buscar:", key="bus_v").upper()
        prod_filt = [p for p in df_stock['Producto'].tolist() if bus_v in p]
        
        col1, col2 = st.columns([3,1])
        with col1:
            if prod_filt:
                p_sel = st.selectbox("Producto:", prod_filt, key=f"s_{st.session_state.reset_v}")
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                st.write(f"Stock: {info['Stock']} | Precio: S/ {info['Precio']}")
            else: st.warning("No encontrado")
        with col2:
            cant = st.number_input("Cant:", min_value=1, value=1)

        if st.button("➕ AGREGAR", use_container_width=True) and prod_filt:
            if cant <= info['Stock']:
                st.session_state.carrito.append({
                    'Producto': p_sel, 'Cantidad': int(cant), 
                    'Precio': float(info['Precio']), 'P_Compra_U': float(info['P_Compra_U']),
                    'Subtotal': round(float(info['Precio']) * cant, 2),
                    'TenantID': st.session_state.tenant_id
                })
                st.session_state.reset_v += 1; st.rerun()
            else: st.error("Sin stock suficiente")

        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c[['Producto', 'Cantidad', 'Subtotal']])
            
            if st.button("🔥 FINALIZAR VENTA"):
                fecha, hora, dt_obj, id_v = obtener_tiempo_peru()
                total = df_c['Subtotal'].sum()
                
                # GUARDAR EN AWS CON TENANTID
                try:
                    tabla_ventas.put_item(Item={
                        'VentaID': id_v,
                        'TenantID': st.session_state.tenant_id,
                        'Fecha': fecha,
                        'Total': str(total),
                        'Items': st.session_state.carrito
                    })
                    # Descontar Stock
                    for item in st.session_state.carrito:
                        tabla_stock.update_item(
                            Key={'Producto': item['Producto']},
                            UpdateExpression="set Stock = Stock - :val",
                            ExpressionAttributeValues={':val': item['Cantidad']}
                        )
                    st.session_state.boleta = {'fecha': fecha, 'items': st.session_state.carrito, 'total_neto': total}
                    st.session_state.carrito = []
                    actualizar_stock_local()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

# --- PESTAÑA 2: STOCK (Añadir/Editar) ---
with tabs[1]:
    st.subheader("Gestión de Inventario")
    with st.form("nuevo_prod"):
        n_prod = st.text_input("Nombre del Producto:").upper().strip()
        n_stock = st.number_input("Stock Inicial:", min_value=0)
        n_precio = st.number_input("Precio Venta:", min_value=0.0)
        n_compra = st.number_input("Precio Compra:", min_value=0.0)
        
        if st.form_submit_button("💾 GUARDAR PRODUCTO"):
            if n_prod:
                tabla_stock.put_item(Item={
                    'Producto': n_prod,
                    'TenantID': st.session_state.tenant_id, # Se guarda el dueño
                    'Stock': int(n_stock),
                    'Precio': str(n_precio),
                    'P_Compra_U': str(n_compra)
                })
                st.success("Guardado"); actualizar_stock_local(); st.rerun()

    st.dataframe(df_stock, use_container_width=True)

# Pestañas de Reportes e Historial (Pendientes de implementar según tu lógica)
with tabs[2]: st.write("📊 Gráficos de ventas por local próximamente...")
with tabs[3]: st.write("📋 Listado de movimientos históricos...")
