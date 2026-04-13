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
    st.error(f"Error de conexión AWS: {e}")
    st.stop()

# 3. CONTROL DE ESTADOS (CACHÉ LOCAL)
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'reset_v' not in st.session_state: st.session_state.reset_v = 0
if 'df_stock_local' not in st.session_state: st.session_state.df_stock_local = None

def actualizar_stock_local():
    try:
        items = tabla_stock.scan().get('Items', [])
        if items:
            df = pd.DataFrame(items)
            # BLINDAJE: Aseguramos que existan las columnas necesarias
            for col in ['Stock', 'Precio', 'P_Compra_U']:
                if col not in df.columns: df[col] = 0
            
            df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
            df['P_Compra_U'] = pd.to_numeric(df['P_Compra_U'], errors='coerce').fillna(0.0)
            df['Producto'] = df['Producto'].astype(str)
            st.session_state.df_stock_local = df[['Producto', 'Stock', 'Precio', 'P_Compra_U']].sort_values(by='Producto')
        else:
            st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])
    except:
        st.session_state.df_stock_local = pd.DataFrame(columns=['Producto', 'Stock', 'Precio', 'P_Compra_U'])

if st.session_state.df_stock_local is None:
    actualizar_stock_local()

df_stock = st.session_state.df_stock_local

# --- LOGIN ---
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

tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])

# 1. PESTAÑA DE VENTAS
with tabs[0]:
    if st.session_state.boleta:
        st.balloons(); st.success("✅ ¡VENTA REALIZADA!")
        b = st.session_state.boleta
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
            <div style="text-align: right; font-size: 13px; color: red;">Rebaja: - S/ {b['rebaja_total']:.2f}</div>
            <div style="text-align: right; font-size: 17px;"><b>TOTAL NETO: S/ {b['total_neto']:.2f}</b></div>
            <hr style="border-top: 1px dashed black;">
            <center>PAGO: {b['metodo']}<br>¡Gracias!</center>
        </div>
        """
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA", use_container_width=True):
            st.session_state.boleta = None; st.rerun()
    else:
        st.subheader("🛒 Realizar Venta")
        bus_v = st.text_input("🔍 Buscar producto:", key="bus_v").strip().upper()
        prod_filt_v = [p for p in df_stock['Producto'].tolist() if bus_v in str(p).upper()]
        
        c1, c2 = st.columns([3, 1])
        with c1:
            if prod_filt_v:
                p_sel = st.selectbox("Seleccionar:", prod_filt_v, key=f"sel_v_{st.session_state.reset_v}")
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                st.info(f"💰 S/ {info['Precio']:.2f} | 📦 Stock: {info['Stock']}")
            else: st.warning("No encontrado")
        with c2: cant = st.number_input("Cant:", min_value=1, value=1, key=f"c_v_{st.session_state.reset_v}")
        
        if st.button("➕ AÑADIR AL CARRITO", use_container_width=True) and prod_filt_v:
            if cant <= info['Stock']:
                st.session_state.carrito.append({
                    'Producto': p_sel, 'Cantidad': int(cant), 
                    'Precio': float(info['Precio']), 'P_Compra_U': float(info['P_Compra_U']),
                    'Subtotal': round(float(info['Precio']) * cant, 2)
                })
                st.session_state.reset_v += 1; st.rerun()
            else: st.error("Stock insuficiente")

        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c[['Producto', 'Cantidad', 'Precio', 'Subtotal']].style.format({"Precio": "{:.2f}", "Subtotal": "{:.2f}"}))
            t_bruto = df_c['Subtotal'].sum()
            rebaja = st.number_input("Rebaja (S/):", min_value=0.0, value=0.0)
            t_final = max(0.0, t_bruto - rebaja)
            st.markdown(f"<h2 style='text-align:center; color:#2ECC71;'>TOTAL: S/ {t_final:.2f}</h2>", unsafe_allow_html=True)
            met_sel = st.radio("Método de Pago:", ["💵 Efectivo", "🟣 Yape", "🔵 Plin"], horizontal=True)
            metodo = met_sel.split(" ")[1]
            if st.button("🚀 FINALIZAR Y REGISTRAR VENTA", type="primary", use_container_width=True):
                f, h, _, uid = obtener_tiempo_peru()
                st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total_bruto': t_bruto, 'rebaja_total': rebaja, 'total_neto': t_final, 'metodo': metodo}
                for idx, item in enumerate(st.session_state.carrito):
                    nuevo_s = int(df_stock[df_stock['Producto'] == item['Producto']]['Stock'].values[0]) - item['Cantidad']
                    tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': nuevo_s})
                    val_db = item['Subtotal'] - rebaja if idx == 0 else item['Subtotal']
                    tabla_ventas.put_item(Item={
                        'ID_Venta': f"V-{uid}-{idx}", 'Fecha': f, 'Hora': h, 
                        'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 
                        'Total': str(round(max(0, val_db), 2)), 'Metodo': metodo,
                        'P_Compra_U': str(item['P_Compra_U'])
                    })
                st.session_state.carrito = []; actualizar_stock_local(); st.rerun()

# 2. STOCK
with tabs[1]:
    st.subheader("📦 Inventario Actual")
    bus_s = st.text_input("🔍 Buscar:", key="bus_stock_p").strip().upper()
    df_f = df_stock[df_stock['Producto'].astype(str).str.upper().str.contains(bus_s, na=False)].copy()
    if not df_f.empty:
        def color_stock(val):
            return 'color: #FF4B4B; font-weight: bold;' if val < 5 else 'color: white;'
        st.dataframe(df_f.style.map(color_stock, subset=['Stock']).format({"Precio": "S/ {:.2f}", "P_Compra_U": "S/ {:.2f}"}), use_container_width=True, hide_index=True)

# 3. REPORTES
with tabs[2]:
    st.subheader("📊 Caja y Ganancias")
    f_bus = st.date_input("Consultar Fecha:").strftime("%d/%m/%Y")
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        df_hoy = df_v[df_v['Fecha'] == f_bus].copy() if not df_v.empty else pd.DataFrame()
        if not df_hoy.empty:
            if 'P_Compra_U' not in df_hoy.columns: df_hoy['P_Compra_U'] = 0
            df_hoy['Total'] = pd.to_numeric(df_hoy['Total'], errors='coerce').fillna(0.0)
            df_hoy['Cantidad'] = pd.to_numeric(df_hoy['Cantidad'], errors='coerce').fillna(0)
            df_hoy['P_Compra_U'] = pd.to_numeric(df_hoy['P_Compra_U'], errors='coerce').fillna(0.0)
            
            df_hoy['Ganancia'] = df_hoy['Total'] - (df_hoy['P_Compra_U'] * df_hoy['Cantidad'])
            
            t_efe = df_hoy[df_hoy['Metodo'] == 'Efectivo']['Total'].sum()
            t_yap = df_hoy[df_hoy['Metodo'] == 'Yape']['Total'].sum()
            t_pli = df_hoy[df_hoy['Metodo'] == 'Plin']['Total'].sum()
            t_ganancia = df_hoy['Ganancia'].sum()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💵 EFECTIVO", f"S/ {t_efe:.2f}")
            c2.metric("🟣 YAPE", f"S/ {t_yap:.2f}")
            c3.metric("🔵 PLIN", f"S/ {t_pli:.2f}")
            c4.metric("📈 GANANCIA REAL", f"S/ {t_ganancia:.2f}")
            
            st.divider()
            st.dataframe(df_hoy.sort_values(by='Hora', ascending=False)[['Hora', 'Producto', 'Cantidad', 'Total', 'Ganancia', 'Metodo']], use_container_width=True, hide_index=True)

# 4. HISTORIAL
with tabs[3]:
    st.subheader("📋 Historial")
    f_hist = st.date_input("Filtrar Fecha:", key="f_hist_k").strftime("%d/%m/%Y")
    h_data = tabla_auditoria.scan().get('Items', [])
    if h_data:
        df_h = pd.DataFrame(h_data)
        df_h_filt = df_h[df_h['Fecha'] == f_hist].copy()
        if not df_h_filt.empty:
            st.dataframe(df_h_filt[['Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante']], use_container_width=True, hide_index=True)

# 5. CARGAR STOCK (CON LISTA DE EJEMPLOS)
with tabs[4]:
    st.subheader("📥 Cargar Mercadería")
    ejemplos = {
        "RESINA FILTEK Z250": {"c": 45.0, "v": 65.0},
        "GUANTES DE LATEX (CAJA)": {"c": 18.0, "v": 25.0},
        "ALGINATO JELTRATE": {"c": 22.0, "v": 35.0},
        "ANESTESIA LIDOCAINA": {"c": 60.0, "v": 85.0},
        "AGUJAS DENTALES (CAJA)": {"c": 25.0, "v": 40.0},
        "EUGENOL 20ML": {"c": 12.0, "v": 20.0},
        "IONOMERO DE VIDRIO": {"c": 55.0, "v": 80.0},
        "PUNTAS DE SUCCION": {"c": 10.0, "v": 18.0},
        "BANDA MATRIZ (ROLLO)": {"c": 15.0, "v": 28.0},
        "MASCARILLAS QUIRURGICAS": {"c": 8.0, "v": 15.0}
    }
    m_man = st.radio("Tipo:", ["Existente", "Nuevo/Ejemplo"], horizontal=True)
    with st.form("f_cargar"):
        if m_man == "Existente":
            bus_c = st.text_input("🔍 Buscar:").strip().upper()
            filt_c = [p for p in df_stock['Producto'].tolist() if bus_c in str(p).upper()]
            p_f = st.selectbox("Producto:", filt_c) if filt_c else None
            p_v_s = float(df_stock[df_stock['Producto'] == p_f].iloc[0]['Precio']) if p_f else 10.0
            p_c_s = float(df_stock[df_stock['Producto'] == p_f].iloc[0]['P_Compra_U']) if p_f else 5.0
        else:
            op_ej = st.selectbox("Ejemplos Rápidos:", ["Manual"] + list(ejemplos.keys()))
            nom_m = st.text_input("Nombre Manual:").upper().strip()
            p_f = op_ej if op_ej != "Manual" else nom_m
            p_c_s = ejemplos[op_ej]["c"] if op_ej != "Manual" else 1.0
            p_v_s = ejemplos[op_ej]["v"] if op_ej != "Manual" else 2.0
        
        c1, c2, c3 = st.columns(3)
        cant_c = c1.number_input("Cantidad:", min_value=1, value=1)
        pr_c = c2.number_input("Costo Unitario:", min_value=0.0, value=p_c_s)
        pr_v = c3.number_input("Precio Venta:", min_value=0.1, value=p_v_s)
        
        if st.form_submit_button("📥 REGISTRAR"):
            if p_f:
                f, h, _, uid = obtener_tiempo_peru()
                s_a = int(df_stock[df_stock['Producto'] == p_f]['Stock'].values[0]) if p_f in df_stock['Producto'].values else 0
                n_t = s_a + cant_c
                tabla_stock.put_item(Item={'Producto': p_f, 'Stock': n_t, 'Precio': str(round(pr_v, 2)), 'P_Compra_U': str(round(pr_c, 2))})
                tabla_auditoria.put_item(Item={'ID_Ingreso': f"I-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_f, 'Cantidad_Entrante': int(cant_c), 'Stock_Resultante': int(n_t)})
                actualizar_stock_local(); st.success("✅ Actualizado"); time.sleep(1); st.rerun()

# 6. MANTENIMIENTO
with tabs[5]:
    st.subheader("🛠️ Mantenimiento")
    p_edit = st.selectbox("Selecciona para corregir costo:", df_stock['Producto'].unique())
    c_n = st.number_input("Nuevo Costo Unitario:", min_value=0.0, step=0.1)
    if st.button("💾 Guardar Nuevo Costo"):
        tabla_stock.update_item(Key={'Producto': p_edit}, UpdateExpression="set P_Compra_U = :c", ExpressionAttributeValues={':c': str(round(c_n, 2))})
        actualizar_stock_local(); st.success("Costo actualizado"); time.sleep(1); st.rerun()
    st.divider()
    p_del = st.selectbox("Borrar producto:", [""] + df_stock['Producto'].tolist())
    if st.button("🗑️ ELIMINAR") and p_del:
        tabla_stock.delete_item(Key={'Producto': p_del})
        actualizar_stock_local(); st.rerun()
