import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
from boto3.dynamodb.conditions import Attr
import io

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="NEXUS BALLARTA SaaS", layout="wide", page_icon="🚀")
tz_peru = pytz.timezone('America/Lima')

def obtener_info_tiempo():
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora.strftime("%Y%m%d%H%M%S%f")

# --- 2. CONEXIÓN AWS (DYNAMODB) ---
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

# --- 5. PANEL LATERAL ---
st.sidebar.title(f"🏢 {st.session_state.tenant}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.auth = False
    st.session_state.tenant = None
    st.session_state.carrito = []
    st.rerun()

# --- 6. PESTAÑAS ---
tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGA", "🛠️ MANTENIMIENTO"])

# CONSULTA DE DATOS BASE
res_stock = t_stock.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant))
items_stock = res_stock.get('Items', [])
df_stock = pd.DataFrame(items_stock)

# Limpieza preventiva de datos numéricos para evitar errores de ventas (ROJO)
if not df_stock.empty:
    df_stock['Precio'] = pd.to_numeric(df_stock['Precio'], errors='coerce').fillna(0.0)
    df_stock['Stock'] = pd.to_numeric(df_stock['Stock'], errors='coerce').fillna(0).astype(int)

# --- PESTAÑA: VENTA ---
with tabs[0]:
    st.subheader("🛒 Punto de Venta")
    if not df_stock.empty:
        df_con_stock = df_stock[df_stock['Stock'] > 0]
        if not df_con_stock.empty:
            p_sel = st.selectbox("Buscar Producto:", df_con_stock['Producto'].tolist())
            inf_p = df_con_stock[df_con_stock['Producto'] == p_sel].iloc[0]
            
            c1, c2 = st.columns(2)
            c1.metric("Precio Unit.", f"S/ {inf_p['Precio']:.2f}")
            c2.metric("Disponible", inf_p['Stock'])
            
            cant = st.number_input("Cantidad:", min_value=1, max_value=int(inf_p['Stock']), value=1)
            
            if st.button("➕ Añadir al Carrito"):
                st.session_state.carrito.append({
                    'Producto': p_sel, 'Cantidad': int(cant), 
                    'Precio': float(inf_p['Precio']), 'Subtotal': round(float(inf_p['Precio']) * cant, 2)
                })
                st.rerun()
        else:
            st.error("⚠️ No hay productos con stock disponible.")

        if st.session_state.carrito:
            st.markdown("---")
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car)
            total_v = df_car['Subtotal'].sum()
            st.write(f"### TOTAL A COBRAR: S/ {total_v:.2f}")
            
            if st.button("🚀 FINALIZAR VENTA", type="primary"):
                f, h, uid = obtener_info_tiempo()
                t_ventas.put_item(Item={
                    'TenantID': st.session_state.tenant, 'VentaID': f"V-{uid}", 
                    'Fecha': f, 'Hora': h, 'Total': str(total_v), 'Items': df_car.to_dict('records')
                })
                for item in st.session_state.carrito:
                    t_stock.update_item(
                        Key={'TenantID': st.session_state.tenant, 'Producto': item['Producto']},
                        UpdateExpression="SET Stock = Stock - :v",
                        ExpressionAttributeValues={':v': int(item['Cantidad'])}
                    )
                st.session_state.carrito = []
                st.success("✅ Venta realizada!")
                st.rerun()
    else:
        st.info("Primero carga productos en el sistema.")

# --- PESTAÑA: STOCK ---
with tabs[1]:
    st.subheader("📦 Inventario")
    if not df_stock.empty:
        st.dataframe(df_stock[['Producto', 'Stock', 'Precio']], use_container_width=True, hide_index=True)
    else:
        st.warning("Inventario vacío.")

# --- PESTAÑA: CARGA ---
with tabs[4]:
    st.subheader("📥 Cargar Mercadería")
    opcion = st.radio("Método:", ["Individual", "Masivo (Excel/CSV)"], horizontal=True)
    
    if opcion == "Individual":
        with st.form("f_ind"):
            n = st.text_input("Nombre:").upper().strip()
            s = st.number_input("Stock Inicial:", min_value=0)
            pv = st.number_input("Precio Venta:", min_value=0.0)
            pc = st.number_input("Precio Compra (Opcional):", min_value=0.0)
            if st.form_submit_button("Guardar"):
                if n:
                    t_stock.put_item(Item={
                        'TenantID': st.session_state.tenant, 'Producto': n,
                        'Stock': int(s), 'Precio': str(pv), 'Precio_Compra': str(pc)
                    })
                    st.success("Registrado.")
                    st.rerun()
    else:
        file = st.file_uploader("Subir archivo", type=['xlsx', 'csv'])
        if file:
            df_m = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
            df_m.columns = [c.strip().replace(' ', '_') for c in df_m.columns]
            if st.button("⬆️ Iniciar Carga Masiva"):
                for _, f in df_m.iterrows():
                    t_stock.put_item(Item={
                        'TenantID': st.session_state.tenant,
                        'Producto': str(f.get('Producto', 'S/N')).upper(),
                        'Stock': int(f.get('Stock', 0)),
                        'Precio': str(f.get('Precio', 0)),
                        'Precio_Compra': str(f.get('Precio_Compra', 0))
                    })
                st.success("✅ Carga completa.")
                st.rerun()

# --- PESTAÑA: MANTENIMIENTO (EDICIÓN DIRECTA) ---
with tabs[5]:
    st.subheader("🛠️ Editar Precios y Stock")
    if not df_stock.empty:
        p_edit = st.selectbox("Seleccione producto para modificar:", df_stock['Producto'].tolist())
        datos_actuales = df_stock[df_stock['Producto'] == p_edit].iloc[0]
        
        with st.form("edit_directo"):
            col_e1, col_e2 = st.columns(2)
            nuevo_stk = col_e1.number_input("Stock Actual:", value=int(datos_actuales['Stock']))
            nuevo_pv = col_e1.number_input("Precio Venta (Público):", value=float(datos_actuales['Precio']))
            # Usamos .get() por si el campo no existe en registros antiguos
            precio_c_actual = datos_actuales.get('Precio_Compra', 0)
            nuevo_pc = col_e2.number_input("Precio Entrada (Costo):", value=float(precio_c_actual if precio_c_actual else 0))
            
            if st.form_submit_button("💾 Actualizar Producto"):
                t_stock.put_item(Item={
                    'TenantID': st.session_state.tenant,
                    'Producto': p_edit,
                    'Stock': int(nuevo_stk),
                    'Precio': str(nuevo_pv),
                    'Precio_Compra': str(nuevo_pc)
                })
                st.success("✅ Datos actualizados correctamente.")
                st.rerun()
        
        if st.button("🗑️ Eliminar Producto"):
            t_stock.delete_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_edit})
            st.rerun()
    else:
        st.write("No hay productos.")

# --- PESTAÑAS EXTRAS: REPORTES / HISTORIAL ---
res_v = t_ventas.scan(FilterExpression=Attr('TenantID').eq(st.session_state.tenant))
df_v = pd.DataFrame(res_v.get('Items', []))

with tabs[2]:
    st.subheader("📊 Reportes")
    if not df_v.empty:
        st.metric("Total Ventas", f"S/ {pd.to_numeric(df_v['Total']).sum():.2f}")
    else: st.write("Sin ventas.")

with tabs[3]:
    st.subheader("📋 Historial")
    if not df_v.empty:
        st.dataframe(df_v[['VentaID', 'Fecha', 'Hora', 'Total']], use_container_width=True)
