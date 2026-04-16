import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
from boto3.dynamodb.conditions import Attr
import io

# --- 1. CONFIGURACIÓN DE PÁGINA Y TIEMPO ---
st.set_page_config(page_title="NEXUS BALLARTA SaaS", layout="wide", page_icon="🚀")
tz_peru = pytz.timezone('America/Lima')

def obtener_info_tiempo():
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora.strftime("%Y%m%d%H%M%S%f")

# --- 2. CONEXIÓN AWS (Usando tus Secrets) ---
try:
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=st.secrets["aws"]["aws_region"],
        aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
        aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"]
    )
    t_stock = dynamodb.Table('SaaS_Stock_Test')
    t_ventas = dynamodb.Table('SaaS_Ventas_Test')
except Exception as e:
    st.error(f"❌ Error de conexión AWS: {e}")
    st.stop()

# --- 3. ESTADOS DE SESIÓN ---
if 'auth' not in st.session_state: st.session_state.auth = False
if 'tenant' not in st.session_state: st.session_state.tenant = None
if 'carrito' not in st.session_state: st.session_state.carrito = []

# --- 4. LOGIN SISTEMA ---
if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center;'>🚀 NEXUS BALLARTA SaaS</h1>", unsafe_allow_html=True)
    # Lista de locales desde secrets
    locales = list(st.secrets.get("auth_multi", {"Empresa_Default": ""}).keys())
    local_sel = st.selectbox("Seleccione su Local/Empresa:", locales)
    clave = st.text_input("Contraseña de Acceso:", type="password")
    
    if st.button("🔓 Iniciar Sesión", use_container_width=True):
        if clave == "tiotuinventario":
            st.session_state.auth = True
            st.session_state.tenant = local_sel
            st.rerun()
        else:
            st.error("❌ Contraseña incorrecta.")
    st.stop()

# --- 5. PANEL DE CONTROL (SIDEBAR) ---
st.sidebar.title(f"🏢 {st.session_state.tenant}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.auth = False
    st.session_state.tenant = None
    st.session_state.carrito = []
    st.rerun()

# --- 6. PESTAÑAS PRINCIPALES ---
tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGA", "🛠️ MANTENIMIENTO"])

# --- CONSULTA DE DATOS (Aislado por TenantID) ---
res_stock = t_stock.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant))
df_stock = pd.DataFrame(res_stock.get('Items', []))

# --- PESTAÑA: CARGA (Individual y Masiva) ---
with tabs[4]:
    st.subheader("📥 Registro de Mercadería")
    modo = st.radio("Seleccione método:", ["Individual", "Masivo (Excel/CSV)"], horizontal=True)

    if modo == "Individual":
        with st.form("form_registro"):
            col1, col2 = st.columns(2)
            with col1:
                nom = st.text_input("Nombre del Producto:").upper().strip()
                stk = st.number_input("Stock Inicial:", min_value=0, step=1)
            with col2:
                p_v = st.number_input("Precio Venta (S/):", min_value=0.0)
                p_c = st.number_input("Precio Compra (S/):", min_value=0.0)
            
            if st.form_submit_button("🚀 Guardar Producto"):
                if nom:
                    t_stock.put_item(Item={
                        'TenantID': st.session_state.tenant,
                        'Producto': nom, 'Stock': int(stk),
                        'Precio': str(p_v), 'Precio_Compra': str(p_c)
                    })
                    st.success(f"✅ {nom} guardado correctamente.")
                    st.rerun()
    else:
        st.info("💡 Asegúrate que el Excel tenga las columnas: Producto, Stock, Precio, Precio_Compra")
        archivo = st.file_uploader("Subir archivo Excel o CSV", type=['xlsx', 'csv'])
        if archivo:
            try:
                df_m = pd.read_excel(archivo) if archivo.name.endswith('.xlsx') else pd.read_csv(archivo)
                # Limpieza automática de nombres de columnas
                df_m.columns = [c.strip().replace(' ', '_') for c in df_m.columns]
                
                st.write("Vista previa:")
                st.dataframe(df_m.head())

                if st.button("⬆️ Iniciar Carga a la Nube"):
                    with st.spinner("Procesando..."):
                        for _, f in df_m.iterrows():
                            t_stock.put_item(Item={
                                'TenantID': st.session_state.tenant,
                                'Producto': str(f.get('Producto', 'SIN_NOMBRE')).upper(),
                                'Stock': int(f.get('Stock', 0)),
                                'Precio': str(f.get('Precio', '0')),
                                'Precio_Compra': str(f.get('Precio_Compra', '0'))
                            })
                    st.success("✅ Carga masiva exitosa.")
                    st.rerun()
            except Exception as e:
                st.error(f"Error en archivo: {e}")

# --- PESTAÑA: STOCK ---
with tabs[1]:
    st.subheader("📦 Inventario Actual")
    if not df_stock.empty:
        # Formatear columnas para visualización
        df_ver = df_stock[['Producto', 'Stock', 'Precio']].copy()
        st.dataframe(df_ver, use_container_width=True, hide_index=True)
    else:
        st.warning("Inventario vacío. Sube productos en la pestaña CARGA.")

# --- PESTAÑA: VENTA ---
with tabs[0]:
    st.subheader("🛒 Punto de Venta")
    if not df_stock.empty:
        # Solo mostrar productos con stock real
        df_disp = df_stock[df_stock['Stock'].astype(int) > 0]
        
        if not df_disp.empty:
            p_sel = st.selectbox("Buscar Producto:", df_disp['Producto'].tolist())
            inf_p = df_disp[df_disp['Producto'] == p_sel].iloc[0]
            
            c1, c2 = st.columns(2)
            c1.metric("Precio Unit.", f"S/ {inf_p['Precio']}")
            c2.metric("Disponible", inf_p['Stock'])
            
            cant = st.number_input("Cantidad:", min_value=1, max_value=int(inf_p['Stock']), value=1)
            
            if st.button("➕ Añadir al Carrito"):
                st.session_state.carrito.append({
                    'Producto': p_sel, 'Cantidad': int(cant), 
                    'Precio': float(inf_p['Precio']), 'Subtotal': round(float(inf_p['Precio']) * cant, 2)
                })
                st.rerun()
        else:
            st.error("No hay productos con stock para vender.")

        if st.session_state.carrito:
            st.markdown("---")
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car)
            total_v = df_car['Subtotal'].sum()
            st.write(f"### TOTAL A COBRAR: S/ {total_v:.2f}")
            
            if st.button("🚀 FINALIZAR VENTA", type="primary"):
                f, h, uid = obtener_info_tiempo()
                # 1. Guardar Venta
                t_ventas.put_item(Item={
                    'TenantID': st.session_state.tenant,
                    'VentaID': f"V-{uid}", 'Fecha': f, 'Hora': h, 
                    'Total': str(total_v), 'Items': df_car.to_dict('records')
                })
                # 2. Descontar Stock
                for item in st.session_state.carrito:
                    t_stock.update_item(
                        Key={'TenantID': st.session_state.tenant, 'Producto': item['Producto']},
                        UpdateExpression="SET Stock = Stock - :v",
                        ExpressionAttributeValues={':v': int(item['Cantidad'])}
                    )
                st.session_state.carrito = []
                st.success("✅ Venta realizada correctamente.")
                st.rerun()
    else:
        st.info("Primero carga productos en el sistema.")

# --- PESTAÑA: REPORTES E HISTORIAL ---
res_v = t_ventas.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant))
df_v = pd.DataFrame(res_v.get('Items', []))

with tabs[2]:
    st.subheader("📊 Reportes de Ventas")
    if not df_v.empty:
        tot = pd.to_numeric(df_v['Total']).sum()
        st.metric("Venta Total Acumulada", f"S/ {tot:.2f}")
    else:
        st.write("Sin datos de ventas.")

with tabs[3]:
    st.subheader("📋 Historial de Movimientos")
    if not df_v.empty:
        st.dataframe(df_v[['VentaID', 'Fecha', 'Hora', 'Total']], use_container_width=True)

# --- PESTAÑA: MANTENIMIENTO ---
with tabs[5]:
    st.subheader("🛠️ Administración de Datos")
    if not df_stock.empty:
        p_del = st.selectbox("Seleccione producto para eliminar:", df_stock['Producto'].tolist(), key="del")
        if st.button("🗑️ Eliminar Producto Definitivamente"):
            t_stock.delete_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_del})
            st.warning(f"Producto {p_del} eliminado del sistema.")
            st.rerun()
    else:
        st.write("Nada que administrar.")
