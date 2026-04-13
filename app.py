import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time

# 1. CONFIGURACIÓN E INTERFAZ
st.set_page_config(page_title="Sistema Dental BALLARTA", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora, ahora.strftime("%Y%m%d%H%M%S%f")

# 2. CONEXIÓN AWS DYNAMODB
try:
    aws_id = st.secrets["aws"]["aws_access_key_id"]
    aws_key = st.secrets["aws"]["aws_secret_access_key"]
    aws_region = st.secrets["aws"]["aws_region"]
    admin_pass = st.secrets["auth"]["admin_password"]
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    tabla_ventas = dynamodb.Table('VentasDentaltio')
    tabla_stock = dynamodb.Table('StockProductos')
    tabla_auditoria = dynamodb.Table('EntradasInventario') 
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# 3. CONTROL DE ESTADOS
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'reset_v' not in st.session_state: st.session_state.reset_v = 0
if 'reset_c' not in st.session_state: st.session_state.reset_c = 0

# --- LÓGICA DE LOGIN ---
if not st.session_state.sesion_iniciada:
    st.markdown("<h1 style='text-align: center;'>🦷</h1><h1 style='text-align: center; color: #2E86C1;'>Sistema Dental BALLARTA</h1>", unsafe_allow_html=True)
    col_login, _ = st.columns([1, 1])
    with col_login:
        clave = st.text_input("Clave del sistema:", type="password")
        if st.button("🔓 Ingresar", use_container_width=True):
            if clave == admin_pass:
                st.session_state.sesion_iniciada = True
                st.rerun()
            else: st.error("❌ Contraseña incorrecta")
    st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("⚙️ Panel")
    if st.button("🔴 CERRAR SESIÓN", use_container_width=True):
        st.session_state.sesion_iniciada = False
        st.rerun()
    st.divider()
    st.info("Conectado a AWS")

def get_df_stock():
    try:
        items = tabla_stock.scan().get('Items', [])
        if items:
            df = pd.DataFrame(items)
            df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
            return df[['Producto', 'Stock', 'Precio']].sort_values(by='Producto')
    except: pass
    return pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

df_stock = get_df_stock()
tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])

# 1. PESTAÑA DE VENTAS
with tabs[0]:
    if st.session_state.boleta:
        st.balloons()
        st.success("✅ ¡VENTA REALIZADA CON ÉXITO!")
        b = st.session_state.boleta
        # ... (código del ticket igual) ...
        ticket = f"""
        <div style="background-color: white; color: #000; padding: 20px; border: 2px solid #000; border-radius: 10px; max-width: 350px; margin: auto; font-family: monospace;">
            <center><b>BALLARTA DENTAL</b><br>{b['fecha']} {b['hora']}</center>
            <hr style="border-top: 1px dashed black;">
            <table style="width: 100%;">
                <tr><td><b>Cant</b></td><td><b>Prod</b></td><td style="text-align: right;"><b>Tot</b></td></tr>
        """
        for i in b['items']:
            ticket += f"<tr><td>{i['Cantidad']}</td><td>{i['Producto']}</td><td style='text-align: right;'>S/ {i['Subtotal']:.2f}</td></tr>"
        ticket += f"""
            </table>
            <hr style="border-top: 1px dashed black;">
            <div style="text-align: right; font-size: 13px;">Bruto: S/ {b['total_bruto']:.2f}</div>
            <div style="text-align: right; font-size: 13px; color: red;">Rebaja: - S/ {b['rebaja_total']:.2f}</div>
            <div style="text-align: right; font-size: 17px;"><b>TOTAL NETO: S/ {b['total_neto']:.2f}</b></div>
            <hr style="border-top: 1px dashed black;">
            <center>PAGO: {b['metodo']}<br>¡Gracias!</center>
        </div>
        """
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA", use_container_width=True):
            st.session_state.boleta = None
            st.rerun()
    else:
        st.subheader("🛒 Realizar Venta")
        bus_v = st.text_input("🔍 Buscar producto para vender:", key="bus_v").strip().upper()
        prod_filt_v = [p for p in df_stock['Producto'].tolist() if bus_v in p.upper()]
        
        c1, c2 = st.columns([3, 1])
        with c1:
            if prod_filt_v:
                p_sel = st.selectbox("Seleccionar:", prod_filt_v, key=f"sel_v_{st.session_state.reset_v}")
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                st.info(f"💰 S/ {info['Precio']:.2f} | 📦 Stock: {info['Stock']}")
            else: st.warning("No encontrado")
        with c2: cant = st.number_input("Cant:", min_value=1, value=1, key=f"c_v_{st.session_state.reset_v}")
        
        if st.button("➕ AÑADIR", use_container_width=True) and prod_filt_v:
            if cant <= info['Stock']:
                st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': float(info['Precio']), 'Subtotal': round(float(info['Precio']) * cant, 2)})
                st.session_state.reset_v += 1
                st.rerun()
            else: st.error("Stock insuficiente")

        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c)
            t_bruto = df_c['Subtotal'].sum()
            rebaja = st.number_input("Rebaja (S/):", min_value=0.0, value=0.0)
            t_final = max(0.0, t_bruto - rebaja)
            st.markdown(f"<h2 style='text-align:center; color:#2ECC71;'>TOTAL: S/ {t_final:.2f}</h2>", unsafe_allow_html=True)
            metodo = st.radio("Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)
            if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
                f, h, _, uid = obtener_tiempo_peru()
                st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total_bruto': t_bruto, 'rebaja_total': rebaja, 'total_neto': t_final, 'metodo': metodo}
                for idx, item in enumerate(st.session_state.carrito):
                    nuevo_s = int(df_stock[df_stock['Producto'] == item['Producto']]['Stock'].values[0]) - item['Cantidad']
                    tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': nuevo_s})
                    val_db = item['Subtotal'] - rebaja if idx == 0 else item['Subtotal']
                    tabla_ventas.put_item(Item={'ID_Venta': f"V-{uid}-{idx}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(round(max(0, val_db), 2)), 'Metodo': metodo})
                st.session_state.carrito = []
                st.rerun()

# 2. STOCK
with tabs[1]:
    st.subheader("📦 Inventario Actual")
    bus_s = st.text_input("🔍 Buscar en inventario:", key="bus_s").strip().upper()
    df_f = df_stock[df_stock['Producto'].str.upper().str.contains(bus_s, na=False)]
    st.dataframe(df_f[['Producto', 'Stock', 'Precio']].style.format({"Precio": "S/ {:.2f}"}), use_container_width=True, hide_index=True)

# 3. REPORTES (CAJA DIARIA)
with tabs[2]:
    st.subheader("📊 Caja Diaria")
    f_bus = st.date_input("Consultar Fecha:").strftime("%d/%m/%Y")
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        df_hoy = df_v[df_v['Fecha'] == f_bus].copy() if not df_v.empty else pd.DataFrame()
        if not df_hoy.empty:
            df_hoy['Total'] = pd.to_numeric(df_hoy['Total'])
            st.metric("TOTAL DEL DÍA", f"S/ {df_hoy['Total'].sum():.2f}")
            st.dataframe(df_hoy.sort_values(by='Hora', ascending=False)[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)

# 4. HISTORIAL (CON FILTRO DE FECHA)
with tabs[3]:
    st.subheader("📋 Historial de Movimientos")
    # Buscador por fecha para que no se llene
    f_hist = st.date_input("Filtrar Historial por Fecha:", value=datetime.now()).strftime("%d/%m/%Y")
    h_data = tabla_auditoria.scan().get('Items', [])
    if h_data:
        df_h = pd.DataFrame(h_data)
        # Filtramos por la fecha seleccionada
        df_h_filt = df_h[df_h['Fecha'] == f_hist].sort_values(by='Hora', ascending=False)
        if not df_h_filt.empty:
            st.dataframe(df_h_filt[['Fecha', 'Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante']], use_container_width=True, hide_index=True)
        else:
            st.info(f"No hubo movimientos el día {f_hist}")

# 5. CARGAR STOCK (CON BUSCADOR)
with tabs[4]:
    st.subheader("📥 Cargar Mercadería")
    with st.expander("🚀 CARGA MASIVA (Excel/CSV)"):
        archivo = st.file_uploader("Subir archivo .csv", type="csv")
        if archivo and st.button("SUBIR TODO"):
            df_m = pd.read_csv(archivo)
            for _, r in df_m.iterrows():
                tabla_stock.put_item(Item={'Producto': str(r['Producto']).upper(), 'Stock': int(r['Stock']), 'Precio': str(r['Precio'])})
            st.success("Carga completa"); st.rerun()
    
    st.divider()
    m_man = st.radio("Tipo de Carga:", ["Existente", "Nuevo"], horizontal=True)
    with st.form("f_cargar"):
        if m_man == "Existente":
            # BUSCADOR DENTRO DE CARGAR
            bus_c = st.text_input("🔍 Escribe para buscar producto a cargar:").strip().upper()
            prod_filt_c = [p for p in df_stock['Producto'].tolist() if bus_c in p.upper()]
            p_f = st.selectbox("Confirmar Producto:", prod_filt_c) if prod_filt_c else None
            p_b = df_stock[df_stock['Producto'] == p_f]['Precio'].values[0] if p_f else 10.0
        else:
            p_f = st.text_input("Nombre del Nuevo Producto:").upper().strip()
            p_b = 1.0
        
        c1, c2 = st.columns(2)
        c_f = c1.number_input("Cantidad que entra:", min_value=1, value=1)
        pr_f = c2.number_input("Precio Unitario:", min_value=0.1, value=float(p_b))
        
        if st.form_submit_button("📥 REGISTRAR ENTRADA"):
            if p_f:
                f, h, _, uid = obtener_tiempo_peru()
                s_a = int(df_stock[df_stock['Producto'] == p_f]['Stock'].values[0]) if p_f in df_stock['Producto'].values else 0
                n_t = s_a + c_f
                tabla_stock.put_item(Item={'Producto': p_f, 'Stock': n_t, 'Precio': str(round(pr_f, 2))})
                tabla_auditoria.put_item(Item={'ID_Ingreso': f"I-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_f, 'Cantidad_Entrante': int(c_f), 'Stock_Resultante': int(n_t)})
                st.success("¡Stock actualizado!"); time.sleep(0.5); st.rerun()

# 6. MANTENIMIENTO
with tabs[5]:
    st.subheader("🛠️ Eliminar Productos")
    p_del = st.selectbox("Seleccionar producto a borrar:", [""] + df_stock['Producto'].tolist())
    if st.button("🗑️ BORRAR DEFINITIVAMENTE") and p_del:
        tabla_stock.delete_item(Key={'Producto': p_del})
        st.warning(f"Eliminado: {p_del}"); time.sleep(1); st.rerun()
