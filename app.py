import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time

# 0. CONFIGURACIÓN DEL CLIENTE (SaaS READY)
# Esta sección permite clonar el sistema para otros negocios
CLIENTE_NOMBRE = "BALLARTA DENTAL"
CLIENTE_EMOJI = "🦷"
TABLA_VENTAS_NAME = 'VentasDentaltio'
TABLA_STOCK_NAME = 'StockProductos'
TABLA_AUDITORIA_NAME = 'EntradasInventario'


# 1. CONFIGURACIÓN E INTERFAZ
st.set_page_config(page_title=f"Sistema {CLIENTE_NOMBRE}", layout="wide")


# --- AJUSTE GLOBAL DE TIEMPO PERÚ ---
tz_peru = pytz.timezone('America/Lima')


def obtener_tiempo_peru():
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora, ahora.strftime("%Y%m%d%H%M%S%f")


# 2. CONEXIÓN SEGURA AWS (BLINDAJE DE CREDENCIALES)
try:
    # Verificación de integridad de secretos
    if "aws" not in st.secrets or "auth" not in st.secrets:
        st.error("⚠️ Error crítico: Credenciales [aws] o [auth] no configuradas.")
        st.stop()
        
    # .strip() elimina espacios invisibles que causan el error de token inválido
    aws_id = st.secrets["aws"]["aws_access_key_id"].strip()
    aws_key = st.secrets["aws"]["aws_secret_access_key"].strip()
    aws_region = st.secrets["aws"]["aws_region"].strip()
    admin_pass = st.secrets["auth"]["admin_password"].strip()
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    tabla_ventas = dynamodb.Table(TABLA_VENTAS_NAME)
    tabla_stock = dynamodb.Table(TABLA_STOCK_NAME)
    tabla_auditoria = dynamodb.Table(TABLA_AUDITORIA_NAME)
except Exception as e:
    st.error(f"Error de conexión AWS: {e}")
    st.stop()


# 3. CONTROL DE ESTADOS
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
            for col in ['Stock', 'Precio', 'P_Compra_U']:
                if col not in df.columns: df[col] = 0
            df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
            df['P_Compra_U'] = pd.to_numeric(df['P_Compra_U'], errors='coerce').fillna(0.0)
            
            # NORMALIZACIÓN ANTI-HACK Y DUPLICADOS
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


if st.session_state.df_stock_local is None:
    actualizar_stock_local()

df_stock = st.session_state.df_stock_local


# --- LOGIN SEGURO (ANTI-FUERZA BRUTA CON FRENO DE 3 SEGUNDOS) ---
if not st.session_state.sesion_iniciada:
    st.markdown(f"<h1 style='text-align: center;'>{CLIENTE_EMOJI}</h1><h1 style='text-align: center; color: #2E86C1;'>Sistema {CLIENTE_NOMBRE}</h1>", unsafe_allow_html=True)
    col_login, _ = st.columns([1, 1])
    with col_login:
        clave = st.text_input("Clave de acceso:", type="password")
        if st.button("🔓 Ingresar", use_container_width=True):
            if clave == admin_pass:
                st.session_state.sesion_iniciada = True
                st.rerun()
            else: 
                with st.spinner("Validando acceso..."):
                    time.sleep(3) # Freno de seguridad anti-hackers
                st.error("❌ Acceso denegado: Credenciales incorrectas")
    st.stop()


with st.sidebar:
    st.title(f"{CLIENTE_EMOJI} Panel")
    if st.button("🔴 CERRAR SESIÓN", use_container_width=True):
        st.session_state.sesion_iniciada = False
        st.rerun()
    st.divider()
    st.info(f"Empresa: {CLIENTE_NOMBRE}\nEstado: Conexión Segura")


tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])


# 1. PESTAÑA DE VENTAS
with tabs[0]:
    if st.session_state.boleta:
        st.balloons(); st.success("✅ ¡VENTA REALIZADA!")
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: #000; padding: 20px; border: 2px solid #000; border-radius: 10px; max-width: 350px; margin: auto; font-family: monospace;">
            <center><b>{CLIENTE_NOMBRE}</b><br>{b['fecha']} {b['hora']}</center>
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
        st.subheader("🛒 Registro de Venta")
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
            
            st.warning("⚠️ ¿Estás seguro de finalizar la venta?")
            confirmar_venta = st.checkbox("Confirmar operación")

            if st.button("🚀 FINALIZAR Y REGISTRAR VENTA", type="primary", use_container_width=True, disabled=not confirmar_venta):
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
    bus_s = st.text_input("🔍 Filtrar Inventario:", key="bus_stock_p").strip().upper()
    df_f = df_stock[df_stock['Producto'].astype(str).str.contains(bus_s, na=False)].copy()
    if not df_f.empty:
        def color_stock(val): return 'color: #FF4B4B; font-weight: bold;' if val < 5 else 'color: white;'
        st.dataframe(df_f.style.map(color_stock, subset=['Stock']).format({"Precio": "S/ {:.2f}", "P_Compra_U": "S/ {:.2f}"}), use_container_width=True, hide_index=True)


# 3. REPORTES
with tabs[2]:
    st.subheader("📊 Caja y Ganancias")
    f_bus = st.date_input("Consultar Fecha:", value=datetime.now(tz_peru)).strftime("%d/%m/%Y")
    # Cambiado a .scan() para evitar errores de Index en tablas nuevas
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        df_hoy = df_v[df_v['Fecha'] == f_bus].copy() if not df_v.empty else pd.DataFrame()
        if not df_hoy.empty:
            for c in ['Total', 'Cantidad', 'P_Compra_U']: df_hoy[c] = pd.to_numeric(df_hoy[c], errors='coerce').fillna(0.0)
            df_hoy['Ganancia'] = df_hoy['Total'] - (df_hoy['P_Compra_U'] * df_hoy['Cantidad'])
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💵 EFECTIVO", f"S/ {df_hoy[df_hoy['Metodo'] == 'Efectivo']['Total'].sum():.2f}")
            c2.metric("🟣 YAPE", f"S/ {df_hoy[df_hoy['Metodo'] == 'Yape']['Total'].sum():.2f}")
            c3.metric("🔵 PLIN", f"S/ {df_hoy[df_hoy['Metodo'] == 'Plin']['Total'].sum():.2f}")
            c4.metric("📈 GANANCIA REAL", f"S/ {df_hoy['Ganancia'].sum():.2f}")
            st.divider()
            st.dataframe(df_hoy.sort_values(by='Hora', ascending=False)[['Hora', 'Producto', 'Cantidad', 'Total', 'Ganancia', 'Metodo']], use_container_width=True, hide_index=True)


# 4. HISTORIAL (ORDENADO)
with tabs[3]:
    st.subheader("📋 Movimientos de Inventario")
    f_hist = st.date_input("Fecha de movimientos:", value=datetime.now(tz_peru), key="f_hist_k").strftime("%d/%m/%Y")
    # Cambiado a .scan() para máxima estabilidad
    h_data = tabla_auditoria.scan().get('Items', [])
    if h_data:
        df_h = pd.DataFrame(h_data)
        df_h_filt = df_h[df_h['Fecha'] == f_hist].copy()
        if not df_h_filt.empty:
            df_h_filt = df_h_filt.sort_values(by='Hora', ascending=False)
            st.dataframe(df_h_filt[['Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante']], use_container_width=True, hide_index=True)


# 5. CARGAR STOCK (CON INTEGRIDAD DE DATOS)
with tabs[4]:
    st.subheader("📥 Registro de Mercadería")
    opcion_carga = st.radio("Método de carga:", ["Individual", "Masiva (Excel/CSV)"], horizontal=True)
    
    if opcion_carga == "Individual":
        m_tipo = st.radio("Tipo de ingreso:", ["Existente (Reponer)", "Producto Nuevo"], horizontal=True)
        with st.form("f_cargar"):
            if m_tipo == "Existente (Reponer)":
                bus_c = st.text_input("🔍 Buscar producto en sistema:").strip().upper()
                filt_c = [p for p in df_stock['Producto'].tolist() if bus_c in str(p).upper()]
                p_final = st.selectbox("Confirmar selección:", filt_c) if filt_c else None
                p_c_sug, p_v_sug = (float(df_stock[df_stock['Producto'] == p_final].iloc[0]['P_Compra_U']), 
                                    float(df_stock[df_stock['Producto'] == p_final].iloc[0]['Precio'])) if p_final else (0.0, 0.0)
            else:
                p_final = st.text_input("Nombre del Producto Nuevo:").upper().strip()
                p_c_sug, p_v_sug = 0.0, 0.0
            c1, c2, c3 = st.columns(3)
            cant_c = c1.number_input("Cantidad:", min_value=1, value=1)
            pr_compra = c2.number_input("Costo Unitario (S/):", min_value=0.0, value=p_c_sug)
            pr_venta = c3.number_input("Precio Venta (S/):", min_value=0.0, value=p_v_sug)
            if st.form_submit_button("📥 REGISTRAR CARGA"):
                if p_final:
                    p_limpio = p_final.upper().strip()
                    f, h, _, uid = obtener_tiempo_peru()
                    s_act = int(df_stock[df_stock['Producto'] == p_limpio]['Stock'].values[0]) if p_limpio in df_stock['Producto'].values else 0
                    n_total = s_act + cant_c
                    tabla_stock.put_item(Item={'Producto': p_limpio, 'Stock': n_total, 'Precio': str(round(pr_venta, 2)), 'P_Compra_U': str(round(pr_compra, 2))})
                    tabla_auditoria.put_item(Item={'ID_Ingreso': f"I-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_limpio, 'Cantidad_Entrante': int(cant_c), 'Stock_Resultante': int(n_total)})
                    actualizar_stock_local(); st.success("✅ Stock actualizado!"); time.sleep(1); st.rerun()

    else:
        st.info("Sube un archivo Excel o CSV con las columnas: **Producto**, **Stock**, **Precio**, **P_Compra_U**")
        archivo = st.file_uploader("Seleccionar archivo", type=['xlsx', 'csv'])
        if archivo and st.button("🚀 PROCESAR CARGA MASIVA"):
            df_masivo = pd.read_excel(archivo) if archivo.name.endswith('xlsx') else pd.read_csv(archivo)
            f, h, _, uid = obtener_tiempo_peru()
            for i, row in df_masivo.iterrows():
                p_nom = str(row['Producto']).upper().strip()
                tabla_stock.put_item(Item={'Producto': p_nom, 'Stock': int(row['Stock']), 'Precio': str(round(float(row['Precio']), 2)), 'P_Compra_U': str(round(float(row['P_Compra_U']), 2))})
            st.success("✅ Carga masiva exitosa."); actualizar_stock_local(); time.sleep(2); st.rerun()


# 6. MANTENIMIENTO
with tabs[5]:
    st.subheader("🛠️ Administración")
    st.write("### 💰 Editar Precios")
    p_edit = st.selectbox("Selecciona producto:", df_stock['Producto'].unique(), key="p_m_edit")
    if p_edit:
        info_e = df_stock[df_stock['Producto'] == p_edit].iloc[0]
        col1, col2 = st.columns(2)
        c_act = col1.number_input("Nuevo Costo Compra:", value=float(info_e['P_Compra_U']))
        v_act = col2.number_input("Nuevo Precio Venta:", value=float(info_e['Precio']))
        if st.button("💾 Guardar Cambios"):
            tabla_stock.update_item(Key={'Producto': p_edit}, UpdateExpression="set P_Compra_U = :c, Precio = :p", ExpressionAttributeValues={':c': str(round(c_act, 2)), ':p': str(round(v_act, 2))})
            actualizar_stock_local(); st.success("✅ Precios actualizados"); time.sleep(1); st.rerun()
            
    st.divider()
    st.write("### 🗑️ Eliminar Producto")
    p_del = st.selectbox("Producto a eliminar:", [""] + df_stock['Producto'].tolist())
    if st.button("🗑️ ELIMINAR") and p_del:
        f, h, _, uid = obtener_tiempo_peru()
        tabla_auditoria.put_item(Item={'ID_Ingreso': f"DEL-{uid}", 'Fecha': f, 'Hora': h, 'Producto': f"❌ ELIMINADO: {p_del}", 'Cantidad_Entrante': 0, 'Stock_Resultante': 0})
        tabla_stock.delete_item(Key={'Producto': p_del})
        actualizar_stock_local(); st.error(f"{p_del} eliminado."); time.sleep(1.5); st.rerun()


# --- FIN DEL CODIGO (305 LINEAS EXACTAS) ---
# SaaS Engine Ballarta Cloud 2026
