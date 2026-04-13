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
    st.info("Conectado a AWS DynamoDB")

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

# 1. PESTAÑA DE VENTAS (CON BUSCADOR)
with tabs[0]:
    if st.session_state.boleta:
        st.balloons()
        st.success("✅ ¡VENTA REALIZADA CON ÉXITO!")
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
        busqueda_v = st.text_input("🔍 Escribe el nombre del producto para vender:").upper()
        productos_filtrados = [p for p in df_stock['Producto'].tolist() if busqueda_v in p]
        
        c1, c2 = st.columns([3, 1])
        with c1:
            if productos_filtrados:
                p_sel = st.selectbox("Seleccionar Producto encontrado:", productos_filtrados, 
                                   on_change=lambda: st.session_state.update({"reset_v": st.session_state.reset_v + 1}))
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                st.info(f"💰 Precio: S/ {info['Precio']:.2f} | 📦 Stock: {info['Stock']}")
            else:
                st.error("No se encontraron productos.")
                st.stop()
                
        with c2:
            cant = st.number_input("Cantidad:", min_value=1, value=1, key=f"v_{st.session_state.reset_v}")
        
        if st.button("➕ AÑADIR AL CARRITO", use_container_width=True):
            if cant <= info['Stock']:
                st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': float(info['Precio']), 'Subtotal': round(float(info['Precio']) * cant, 2)})
                st.session_state.reset_v += 1
                st.rerun()
            else: st.error("No hay stock suficiente")

        if st.session_state.carrito:
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c.style.format({"Precio": "{:.2f}", "Subtotal": "{:.2f}"}))
            t_bruto = df_c['Subtotal'].sum()
            rebaja = st.number_input("Rebaja/Descuento (S/):", min_value=0.0, value=0.0)
            t_final = max(0.0, t_bruto - rebaja)
            st.markdown(f"<h2 style='text-align:center; color:#2ECC71;'>TOTAL: S/ {t_final:.2f}</h2>", unsafe_allow_html=True)
            metodo = st.radio("Método de Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)

            with st.popover("🚀 FINALIZAR VENTA", use_container_width=True):
                if st.button("SÍ, CONFIRMAR", type="primary", use_container_width=True):
                    f, h, _, uid = obtener_tiempo_peru()
                    st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total_bruto': t_bruto, 'rebaja_total': rebaja, 'total_neto': t_final, 'metodo': metodo}
                    for idx, item in enumerate(st.session_state.carrito):
                        nuevo_s = int(df_stock[df_stock['Producto'] == item['Producto']]['Stock'].values[0]) - item['Cantidad']
                        tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': nuevo_s})
                        val_db = item['Subtotal'] - rebaja if idx == 0 else item['Subtotal']
                        tabla_ventas.put_item(Item={'ID_Venta': f"V-{uid}-{idx}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(round(max(0, val_db), 2)), 'Metodo': metodo})
                    st.session_state.carrito = []
                    st.rerun()

# 2. STOCK (CON BUSCADOR)
with tabs[1]:
    st.subheader("📦 Inventario Actual")
    busqueda_s = st.text_input("🔍 Buscar producto en inventario (ej: Resina):").upper()
    if not df_stock.empty:
        df_filtrado = df_stock[df_stock['Producto'].str.contains(busqueda_s, na=False)]
        st.dataframe(df_filtrado.style.map(lambda x: 'color: red; font-weight: bold' if x <= 5 else '', subset=['Stock']).format({"Precio": "S/ {:.2f}"}), use_container_width=True, hide_index=True)

# 3. REPORTES
with tabs[2]:
    st.subheader("📊 Resumen de Caja Diaria")
    f_bus = st.date_input("Consultar Fecha:").strftime("%d/%m/%Y")
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        df_hoy = df_v[df_v['Fecha'] == f_bus].copy() if not df_v.empty else pd.DataFrame()
        if not df_hoy.empty:
            df_hoy['Total'] = pd.to_numeric(df_hoy['Total'])
            m1, m2, m3, m4 = st.columns(4)
            with m1: st.metric("TOTAL DÍA", f"S/ {df_hoy['Total'].sum():.2f}")
            with m2: st.subheader(f"💵 S/ {df_hoy[df_hoy['Metodo'] == 'Efectivo']['Total'].sum():.2f}")
            with m3: st.subheader(f"📱 Yape S/ {df_hoy[df_hoy['Metodo'] == 'Yape']['Total'].sum():.2f}")
            with m4: st.subheader(f"📱 Plin S/ {df_hoy[df_hoy['Metodo'] == 'Plin']['Total'].sum():.2f}")
            st.dataframe(df_hoy.sort_values(by='Hora', ascending=False)[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], hide_index=True, use_container_width=True)

# 4. HISTORIAL
with tabs[3]:
    st.subheader("📋 Historial de Movimientos")
    h_data = tabla_auditoria.scan().get('Items', [])
    if h_data:
        df_h = pd.DataFrame(h_data).sort_values(by=['Fecha', 'Hora'], ascending=False)
        st.dataframe(df_h[['Fecha', 'Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante']], use_container_width=True, hide_index=True)

# 5. CARGAR STOCK (CON CARGA MASIVA)
with tabs[4]:
    st.subheader("📥 Cargar Stock")
    with st.expander("🚀 CARGA MASIVA (Subir Excel/CSV)"):
        st.write("Sube tu archivo .csv con: Producto, Stock, Precio")
        archivo = st.file_uploader("Subir archivo", type="csv")
        if archivo:
            df_m = pd.read_csv(archivo)
            if st.button("SUBIR TODO A LA NUBE"):
                f, h, _, uid = obtener_tiempo_peru()
                barra = st.progress(0)
                for i, row in df_m.iterrows():
                    tabla_stock.put_item(Item={'Producto': str(row['Producto']).upper(), 'Stock': int(row['Stock']), 'Precio': str(row['Precio'])})
                    barra.progress((i + 1) / len(df_m))
                st.success("¡Carga masiva completa!"); st.rerun()

    st.divider()
    modo = st.radio("Carga Manual:", ["Existente", "Nuevo"], horizontal=True)
    with st.form("form_c"):
        if modo == "Existente":
            p_final = st.selectbox("Producto:", df_stock['Producto'].tolist())
            p_p_base = df_stock[df_stock['Producto'] == p_final]['Precio'].values[0] if p_final in df_stock['Producto'].values else 10.0
        else:
            p_final = st.text_input("Nuevo Producto:").upper().strip()
            p_p_base = 1.0
        p_cant = st.number_input("Cantidad:", min_value=1, value=1)
        p_precio = st.number_input("Precio:", min_value=0.1, value=float(p_p_base))
        if st.form_submit_button("REGISTRAR"):
            f, h, _, uid = obtener_tiempo_peru()
            s_ant = int(df_stock[df_stock['Producto'] == p_final]['Stock'].values[0]) if p_final in df_stock['Producto'].values else 0
            n_t = s_ant + p_cant
            tabla_stock.put_item(Item={'Producto': p_final, 'Stock': n_t, 'Precio': str(round(p_precio, 2))})
            tabla_auditoria.put_item(Item={'ID_Ingreso': f"I-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_final, 'Cantidad_Entrante': int(p_cant), 'Stock_Resultante': int(n_t)})
            st.success("Registrado"); time.sleep(0.5); st.rerun()

# 6. MANTENIMIENTO
with tabs[5]:
    st.subheader("🛠️ Mantenimiento")
    p_b = st.selectbox("Eliminar:", [""] + df_stock['Producto'].tolist())
    if st.button("🗑️ ELIMINAR") and p_b:
        tabla_stock.delete_item(Key={'Producto': p_b})
        st.warning(f"Eliminado: {p_b}"); time.sleep(1); st.rerun()
