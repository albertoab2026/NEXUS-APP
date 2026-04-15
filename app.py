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

TABLA_VENTAS_NAME = 'SaaS_Ventas_Test'
TABLA_STOCK_NAME = 'SaaS_Stock_Test'

tz_peru = pytz.timezone('America/Lima')

def obtener_tiempo_peru():
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora, ahora.strftime("%Y%m%d%H%M%S%f")

# ==========================================
# 2. CONEXIÓN SEGURA AWS
# ==========================================
try:
    aws_id = st.secrets["aws"]["aws_access_key_id"].strip()
    aws_key = st.secrets["aws"]["aws_secret_access_key"].strip()
    aws_region = st.secrets["aws"]["aws_region"].strip()
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    tabla_ventas = dynamodb.Table(TABLA_VENTAS_NAME)
    tabla_stock = dynamodb.Table(TABLA_STOCK_NAME)
except Exception:
    st.error("Error crítico de conexión AWS. Verifique sus Secrets.")
    st.stop()

# ==========================================
# 3. CONTROL DE ESTADOS
# ==========================================
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'tenant_id' not in st.session_state: st.session_state.tenant_id = None
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'reset_v' not in st.session_state: st.session_state.reset_v = 0
if 'df_stock_local' not in st.session_state: st.session_state.df_stock_local = None

def actualizar_stock_local():
    try:
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
# 4. LOGIN
# ==========================================
if not st.session_state.sesion_iniciada:
    st.markdown(f"<div style='text-align: center; padding: 10px;'><h1 style='color: #3498DB;'>{MARCA_SaaS}</h1><p style='color: #7FB3D5;'>Cloud Inventory System</p></div>", unsafe_allow_html=True)
    
    locales = list(st.secrets.get("auth_multi", {}).keys())
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔑 Acceso")
        local_sel = st.selectbox("Empresa:", locales)
        clave = st.text_input("Contraseña:", type="password")
        if st.button("🔓 Entrar", use_container_width=True):
            if clave == st.secrets["auth_multi"][local_sel].strip():
                st.session_state.sesion_iniciada = True
                st.session_state.tenant_id = local_sel
                actualizar_stock_local()
                st.rerun()
            else: st.error("Clave incorrecta.")
    with col2:
        st.markdown(f"<div style='background-color: rgba(52, 152, 219, 0.1); padding: 25px; border-radius: 10px; border: 1px solid #3498DB;'><h4>Bienvenido</h4><p>Datos protegidos para: <b>{local_sel if local_sel else '...'}</b></p></div>", unsafe_allow_html=True)
    st.stop()

# ==========================================
# 5. INTERFAZ PRINCIPAL
# ==========================================
with st.sidebar:
    st.markdown(f"### {MARCA_SaaS}")
    st.write(f"🏢 {st.session_state.tenant_id}")
    if st.button("🔴 CERRAR SESIÓN", use_container_width=True):
        st.session_state.sesion_iniciada = False
        st.rerun()

tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])
df_stock = st.session_state.df_stock_local

# --- PESTAÑA CARGAR (INDIVIDUAL Y MASIVO CON LIMPIEZA) ---
with tabs[4]:
    st.subheader("📥 Entrada de Mercadería")
    col_i, col_m = st.columns(2)
    with col_i:
        st.write("✍️ Registro Individual")
        with st.form("f_ind"):
            ni = st.text_input("Nombre:").upper().strip()
            si = st.number_input("Stock:", min_value=0)
            pi = st.number_input("Precio Venta:", min_value=0.0)
            ci = st.number_input("Precio Compra:", min_value=0.0)
            if st.form_submit_button("Guardar Producto"):
                if ni:
                    tabla_stock.put_item(Item={'Producto': ni, 'TenantID': st.session_state.tenant_id, 'Stock': int(si), 'Precio': str(pi), 'P_Compra_U': str(ci)})
                    st.success("Cargado"); actualizar_stock_local(); st.rerun()
    with col_m:
        st.write("📂 Carga Masiva (Excel/CSV)")
        archivo = st.file_uploader("Subir archivo:", type=['xlsx', 'csv'])
        if archivo:
            try:
                # Lectura flexible
                df_m = pd.read_csv(archivo) if archivo.name.endswith('.csv') else pd.read_excel(archivo)
                
                # --- LIMPIEZA ANTIFALLO (Elimina los 'None' de tu imagen) ---
                df_m['Producto'] = df_m['Producto'].fillna("SIN NOMBRE").astype(str).str.upper()
                df_m['Stock'] = pd.to_numeric(df_m['Stock'], errors='coerce').fillna(0).astype(int)
                df_m['Precio'] = pd.to_numeric(df_m['Precio'], errors='coerce').fillna(0)
                df_m['P_Compra_U'] = pd.to_numeric(df_m['P_Compra_U'], errors='coerce').fillna(0)
                
                st.dataframe(df_m.head())
                
                if st.button("🚀 SUBIR TODO"):
                    pb = st.progress(0)
                    for i, r in df_m.iterrows():
                        tabla_stock.put_item(Item={
                            'Producto': r['Producto'], 
                            'TenantID': st.session_state.tenant_id, 
                            'Stock': int(r['Stock']), 
                            'Precio': str(r['Precio']), 
                            'P_Compra_U': str(r['P_Compra_U'])
                        })
                        pb.progress((i+1)/len(df_m))
                    st.success("¡Carga terminada con éxito!"); actualizar_stock_local(); st.rerun()
            except Exception as e:
                st.error(f"Error procesando el archivo: {e}")

# --- PESTAÑA MANTENIMIENTO ---
with tabs[5]:
    st.subheader("🛠️ Gestión de Precios y Borrado")
    p_lista = df_stock['Producto'].tolist()
    if p_lista:
        pm = st.selectbox("Elegir producto:", p_lista)
        im = df_stock[df_stock['Producto'] == pm].iloc[0]
        c_m1, c_m2 = st.columns(2)
        with c_m1:
            uv = st.number_input("Nuevo Precio Venta:", value=float(im['Precio']))
            uc = st.number_input("Nuevo Precio Compra:", value=float(im['P_Compra_U']))
            if st.button("🔄 ACTUALIZAR PRECIOS"):
                tabla_stock.update_item(Key={'Producto': pm}, UpdateExpression="SET Precio = :v, P_Compra_U = :c", ExpressionAttributeValues={':v': str(uv), ':c': str(uc)})
                st.success("Precios actualizados"); actualizar_stock_local(); st.rerun()
        with c_m2:
            st.warning("⚠️ Eliminar permanentemente")
            if st.button("🗑️ BORRAR PRODUCTO"):
                tabla_stock.delete_item(Key={'Producto': pm})
                st.error("Producto eliminado"); actualizar_stock_local(); st.rerun()

# --- PESTAÑA VENTA ---
with tabs[0]:
    if st.session_state.boleta:
        b = st.session_state.boleta
        st.success("✅ VENTA REALIZADA")
        st.markdown(f"<div style='background-color: white; color: black; padding: 20px; border: 2px solid black; max-width: 320px; margin: auto; font-family: monospace;'><center><b>{st.session_state.tenant_id}</b><br>{b['fecha']}</center><hr>{''.join([f'<p>{i["Cantidad"]} x {i["Producto"]} - S/ {i["Subtotal"]:.2f}</p>' for i in b['items']])}<hr><h3>TOTAL: S/ {b['total_neto']:.2f}</h3></div>", unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA"): st.session_state.boleta = None; st.rerun()
    else:
        st.subheader("Ventas")
        bus_v = st.text_input("🔍 Buscar:", key="bus_v").upper()
        prod_filt = [p for p in df_stock['Producto'].tolist() if bus_v in p]
        c1, c2 = st.columns(2)
        with c1:
            if prod_filt:
                p_sel = st.selectbox("Seleccionar:", prod_filt, key=f"v_{st.session_state.reset_v}")
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                st.write(f"Stock: **{info['Stock']}** | Precio: **S/ {info['Precio']:.2f}**")
            else: st.warning("Sin resultados.")
        with c2: cant = st.number_input("Cantidad:", min_value=1, value=1, key=f"c_{st.session_state.reset_v}")
        
        if st.button("➕ AÑADIR", use_container_width=True) and prod_filt:
            if cant <= info['Stock']:
                st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': float(info['Precio']), 'P_Compra_U': float(info['P_Compra_U']), 'Subtotal': round(float(info['Precio']) * cant, 2), 'TenantID': st.session_state.tenant_id})
                st.session_state.reset_v += 1; st.rerun()
            else: st.error("Stock insuficiente.")
        
        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c[['Producto', 'Cantidad', 'Subtotal']])
            if st.button("🚀 FINALIZAR"):
                f, h, dt, idv = obtener_tiempo_peru()
                total = df_c['Subtotal'].sum()
                try:
                    tabla_ventas.put_item(Item={'VentaID': idv, 'TenantID': st.session_state.tenant_id, 'Fecha': f, 'Total': str(total), 'Items': st.session_state.carrito})
                    for item in st.session_state.carrito:
                        tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="SET Stock = Stock - :v", ExpressionAttributeValues={':v': item['Cantidad']})
                    st.session_state.boleta = {'fecha': f, 'items': st.session_state.carrito, 'total_neto': total}
                    st.session_state.carrito = []; actualizar_stock_local(); st.rerun()
                except Exception as e: st.error(f"Error AWS: {e}")

# --- PESTAÑAS STOCK, REPORTES, HISTORIAL ---
with tabs[1]: st.dataframe(df_stock, use_container_width=True)
with tabs[2]: st.info("📊 Reportes Nexus próximamente.")
with tabs[3]: st.info("📋 Historial de Movimientos.")
