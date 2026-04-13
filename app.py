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
            df['Producto'] = df['Producto'].astype(str).str.upper().str.strip()
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
        clave = st.text_input("Clave:", type="password")
        if st.button("🔓 Ingresar", use_container_width=True):
            if clave == admin_pass:
                st.session_state.sesion_iniciada = True
                st.rerun()
            else: st.error("❌ Incorrecta")
    st.stop()

with st.sidebar:
    st.title("⚙️ Panel")
    if st.button("🔴 CERRAR SESIÓN", use_container_width=True):
        st.session_state.sesion_iniciada = False
        st.rerun()
    st.divider()
    st.success("AWS Conectado")

tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 REPORTES", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])

# --- PESTAÑAS (Resumen de lógica corregida) ---

with tabs[0]: # VENTA
    if st.session_state.boleta:
        st.balloons()
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: #000; padding: 20px; border: 2px solid #000; border-radius: 10px; max-width: 350px; margin: auto; font-family: monospace;">
            <center><b>BALLARTA DENTAL</b><br>{b['fecha']} {b['hora']}</center>
            <hr style="border-top: 1px dashed black;">
            <table style="width: 100%;">
                <tr><td><b>Cant</b></td><td><b>Prod</b></td><td style="text-align: right;"><b>Tot</b></td></tr>
        """
        for i in b['items']:
            ticket += f"<tr><td>{int(i['Cantidad'])}</td><td>{i['Producto']}</td><td style='text-align: right;'>S/ {i['Subtotal']:.2f}</td></tr>"
        ticket += f"""
            </table>
            <hr style="border-top: 1px dashed black;">
            <div style="text-align: right; font-size: 13px; color: red;">Rebaja: - S/ {b['rebaja_total']:.2f}</div>
            <div style="text-align: right; font-size: 17px;"><b>TOTAL: S/ {b['total_neto']:.2f}</b></div>
            <hr style="border-top: 1px dashed black;">
            <center>PAGO: {b['metodo']}<br>¡Gracias!</center>
        </div>
        """
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA"):
            st.session_state.boleta = None; st.rerun()
    else:
        st.subheader("🛒 Caja")
        bus_v = st.text_input("🔍 Buscar:", key="bus_v").strip().upper()
        prod_filt_v = [p for p in df_stock['Producto'].tolist() if bus_v in str(p).upper()]
        
        c1, c2 = st.columns([3, 1])
        with c1:
            if prod_filt_v:
                p_sel = st.selectbox("Producto:", prod_filt_v, key=f"sel_v_{st.session_state.reset_v}")
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                st.info(f"💰 S/ {info['Precio']:.2f} | 📦 Stock: {int(info['Stock'])}")
            else: st.warning("No encontrado")
        with c2: cant = st.number_input("Cant:", min_value=1, value=1, key=f"c_v_{st.session_state.reset_v}")
        
        if st.button("➕ AGREGAR", use_container_width=True) and prod_filt_v:
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
            st.table(df_c[['Producto', 'Cantidad', 'Precio', 'Subtotal']])
            t_bruto = df_c['Subtotal'].sum()
            rebaja = st.number_input("Rebaja (S/):", min_value=0.0, value=0.0)
            t_final = max(0.0, t_bruto - rebaja)
            st.markdown(f"<h2 style='text-align:center; color:#2ECC71;'>TOTAL: S/ {t_final:.2f}</h2>", unsafe_allow_html=True)
            met_sel = st.radio("Pago:", ["💵 Efectivo", "🟣 Yape", "🔵 Plin"], horizontal=True)
            metodo = met_sel.split(" ")[1]
            
            if st.checkbox("✅ CONFIRMO PAGO"):
                if st.button("🚀 FINALIZAR VENTA", type="primary"):
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

with tabs[1]: # STOCK
    st.subheader("📦 Inventario")
    df_f = df_stock.copy()
    def resaltar_bajo_stock(s):
        return ['color: #FF4B4B; font-weight: bold' if val < 5 else '' for val in s]
    st.dataframe(df_f.style.apply(resaltar_bajo_stock, subset=['Stock']).format({"Precio": "S/ {:.2f}", "P_Compra_U": "S/ {:.2f}"}), use_container_width=True, hide_index=True)

with tabs[2]: # REPORTES
    st.subheader("📊 Reportes")
    f_bus = st.date_input("Fecha:", value=datetime.now(pytz.timezone('America/Lima'))).strftime("%d/%m/%Y")
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        df_hoy = df_v[df_v['Fecha'] == f_bus].copy() if not df_v.empty else pd.DataFrame()
        if not df_hoy.empty:
            df_hoy['Total'] = pd.to_numeric(df_hoy['Total']).fillna(0.0)
            df_hoy['Cantidad'] = pd.to_numeric(df_hoy['Cantidad']).astype(int)
            df_hoy['P_Compra_U'] = pd.to_numeric(df_hoy['P_Compra_U']).fillna(0.0)
            df_hoy['Ganancia'] = df_hoy['Total'] - (df_hoy['P_Compra_U'] * df_hoy['Cantidad'])
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💵 EFECTIVO", f"S/ {df_hoy[df_hoy['Metodo'] == 'Efectivo']['Total'].sum():.2f}")
            c2.metric("🟣 YAPE", f"S/ {df_hoy[df_hoy['Metodo'] == 'Yape']['Total'].sum():.2f}")
            c3.metric("🔵 PLIN", f"S/ {df_hoy[df_hoy['Metodo'] == 'Plin']['Total'].sum():.2f}")
            c4.metric("📈 GANANCIA", f"S/ {df_hoy['Ganancia'].sum():.2f}")
            st.table(df_hoy[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']])

with tabs[3]: # HISTORIAL
    st.subheader("📋 Auditoría")
    h_data = tabla_auditoria.scan().get('Items', [])
    if h_data:
        df_h = pd.DataFrame(h_data)
        df_h['sort_date'] = pd.to_datetime(df_h['Fecha'], format='%d/%m/%Y')
        df_h = df_h.sort_values(by=['sort_date', 'Hora'], ascending=False)
        st.dataframe(df_h[['Fecha', 'Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante']], use_container_width=True, hide_index=True)

with tabs[4]: # CARGAR
    st.subheader("📥 Cargar Stock")
    p_rep = st.selectbox("Producto:", df_stock['Producto'].unique())
    if p_rep:
        info_r = df_stock[df_stock['Producto'] == p_rep].iloc[0]
        st.write(f"Stock actual: {int(info_r['Stock'])}")
        cant_r = st.number_input("Entrada:", min_value=1, value=1)
        if st.button("📥 ACTUALIZAR"):
            f, h, _, uid = obtener_tiempo_peru()
            n_s = int(info_r['Stock']) + cant_r
            tabla_stock.update_item(Key={'Producto': p_rep}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
            tabla_auditoria.put_item(Item={'ID_Ingreso': f"I-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_rep, 'Cantidad_Entrante': int(cant_r), 'Stock_Resultante': int(n_s)})
            actualizar_stock_local(); st.success("Stock aumentado"); time.sleep(1); st.rerun()

with tabs[5]: # MANTENIMIENTO (ESCUDO ANTI-DUPLICADOS)
    st.subheader("🛠️ Administración")
    
    with st.expander("✨ Registrar Producto Nuevo"):
        with st.form("f_nuevo"):
            n_p = st.text_input("Nombre del producto:").upper().strip()
            c1, c2, c3 = st.columns(3)
            s_i = c1.number_input("Stock Inicial:", min_value=0)
            c_i = c2.number_input("Costo:", min_value=0.0)
            v_i = c3.number_input("Venta:", min_value=0.0)
            
            if st.form_submit_button("🆕 CREAR"):
                # --- VALIDACIÓN CLAVE ---
                if n_p in df_stock['Producto'].values:
                    st.error(f"❌ ERROR: El producto '{n_p}' ya existe. Usa la pestaña CARGAR para reponer o EDITAR abajo para cambiar precios.")
                elif not n_p:
                    st.warning("Escribe un nombre.")
                else:
                    f, h, _, uid = obtener_tiempo_peru()
                    tabla_stock.put_item(Item={'Producto': n_p, 'Stock': s_i, 'Precio': str(round(v_i, 2)), 'P_Compra_U': str(round(c_i, 2))})
                    tabla_auditoria.put_item(Item={'ID_Ingreso': f"N-{uid}", 'Fecha': f, 'Hora': h, 'Producto': f"NUEVO: {n_p}", 'Cantidad_Entrante': int(s_i), 'Stock_Resultante': int(s_i)})
                    actualizar_stock_local(); st.success("Producto creado con éxito."); time.sleep(1); st.rerun()

    st.divider()
    st.write("### 🗑️ Eliminar Producto")
    p_del = st.selectbox("Borrar:", [""] + df_stock['Producto'].tolist())
    if st.button("🗑️ ELIMINAR") and p_del:
        f, h, _, uid = obtener_tiempo_peru()
        tabla_auditoria.put_item(Item={'ID_Ingreso': f"DEL-{uid}", 'Fecha': f, 'Hora': h, 'Producto': f"ELIMINADO: {p_del}", 'Cantidad_Entrante': 0, 'Stock_Resultante': 0})
        tabla_stock.delete_item(Key={'Producto': p_del})
        actualizar_stock_local(); st.warning("Eliminado."); time.sleep(1); st.rerun()
