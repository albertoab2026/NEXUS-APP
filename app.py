import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
import io

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Sistema Dental BALLARTA", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora, ahora.strftime("%Y%m%d%H%M%S%f")

# 2. CONEXIÓN AWS
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

# 3. ESTADOS DE SESIÓN
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None
if 'form_contador' not in st.session_state: st.session_state.form_contador = 0

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

# SIDEBAR
if st.sidebar.button("🔴 CERRAR SESIÓN"):
    st.session_state.sesion_iniciada = False
    st.rerun()

# CARGAR STOCK
def get_df_stock():
    try:
        items = tabla_stock.scan().get('Items', [])
        if items:
            df = pd.DataFrame(items)
            for col in ['Stock', 'Precio', 'Producto']:
                if col not in df.columns: df[col] = 0 if col != 'Producto' else "Sin Nombre"
            df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0)
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
            return df[['Producto', 'Stock', 'Precio']].sort_values(by='Producto')
    except: pass
    return pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

df_stock = get_df_stock()

tabs = st.tabs(["🛒 Venta", "📦 Stock", "📊 Reportes", "📋 Historial", "📥 Cargar", "🛠️ Mant."])

# --- TAB 1: VENTA (BOLETA Y CONFIRMACIÓN) ---
with tabs[0]:
    if st.session_state.boleta:
        st.balloons()
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: black; padding: 20px; border: 2px solid #333; border-radius: 10px; max-width: 400px; margin: auto; font-family: 'Courier New', Courier, monospace;">
            <center>
                <p style="margin:0; font-size: 14px; letter-spacing: 3px; color: #555;">TIENDA DENTAL</p>
                <h1 style="margin:0; color: #2E86C1; font-size: 35px; font-weight: bold;">BALLARTA</h1>
                <p style="margin-bottom: 10px; font-size: 12px;">Insumos Profesionales</p>
            </center>
            <hr style="border: 1px dashed #333;">
            <p style="font-size: 13px;"><b>FECHA:</b> {b['fecha']} | {b['hora']}</p>
            <table style="width: 100%; font-size: 14px;">
        """
        for i in b['items']: ticket += f"<tr><td>{i['Cantidad']} x {i['Producto']}</td><td style='text-align: right;'>S/ {float(i['Subtotal']):.2f}</td></tr>"
        ticket += f"</table><hr style='border: 1px dashed #333;'><h2 style='text-align: right; margin: 5px 0;'>TOTAL: S/ {b['total']:.2f}</h2><p style='font-size: 13px;'><b>PAGO:</b> {b['metodo']}</p></div>"
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA"):
            st.session_state.boleta = None
            st.rerun()
    else:
        if not df_stock.empty:
            c1, c2 = st.columns([3, 1])
            with c1:
                p_sel = st.selectbox("Elegir Producto:", df_stock['Producto'].tolist())
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                if info['Stock'] <= 5: st.error(f"⚠️ ¡STOCK CRÍTICO: {info['Stock']:.0f} UNIDADES!")
                else: st.info(f"📦 Stock disponible: {info['Stock']:.0f} | S/ {info['Precio']:.2f}")
            with c2: cant = st.number_input("Cant:", min_value=1, value=1)
            if st.button("➕ AÑADIR AL CARRITO", use_container_width=True):
                if cant <= info['Stock']:
                    st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': float(info['Precio']), 'Subtotal': round(float(info['Precio']) * cant, 2)})
                    st.rerun()
                else: st.error("No hay suficiente stock")

        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito))
            total_v = sum(i['Subtotal'] for i in st.session_state.carrito)
            st.markdown(f"<h1 style='color: #2ECC71; text-align: center; border: 2px solid #2ECC71; border-radius: 10px; padding: 10px;'>TOTAL: S/ {total_v:.2f}</h1>", unsafe_allow_html=True)
            
            metodo = st.radio("Método de Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
            confirmar_pago = st.checkbox("✅ Confirmo que he recibido el dinero")
            
            if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True, disabled=not confirmar_pago):
                f, h, _, uid = obtener_tiempo_peru()
                st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total_v, 'metodo': metodo}
                for item in st.session_state.carrito:
                    n_s = int(df_stock[df_stock['Producto'] == item['Producto']]['Stock'].values[0]) - item['Cantidad']
                    tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                    tabla_ventas.put_item(Item={'ID_Venta': f"V-{uid}-{item['Producto'][:2]}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': metodo})
                st.session_state.carrito = []
                st.rerun()

# --- TAB 2: STOCK (CON COLOR ROJO) ---
with tabs[1]:
    st.subheader("📦 Stock en Almacén")
    if not df_stock.empty:
        def color_rojo(val):
            color = '#ff4b4b' if val <= 5 else ''
            return f'background-color: {color}; color: {"white" if color else "black"}; font-weight: {"bold" if color else "normal"}'
        
        try:
            st.dataframe(df_stock.style.map(color_rojo, subset=['Stock']).format({"Precio": "S/ {:.2f}", "Stock": "{:.0f}"}), use_container_width=True, hide_index=True)
        except:
            st.dataframe(df_stock, use_container_width=True, hide_index=True)

# --- TAB 3: REPORTES (SEPARACIÓN RESTAURADA) ---
with tabs[2]:
    st.subheader("📊 Reporte Diario de Ventas")
    _, _, ahora_dt, _ = obtener_tiempo_peru()
    f_bus = st.date_input("Consultar fecha:", ahora_dt).strftime("%d/%m/%Y")
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        if 'Fecha' in df_v.columns:
            df_dia = df_v[df_v['Fecha'] == f_bus].copy()
            if not df_dia.empty:
                df_dia['Total'] = pd.to_numeric(df_dia['Total'], errors='coerce').fillna(0)
                
                # CÁLCULOS SEPARADOS POR MÉTODO
                ce = df_dia[df_dia['Metodo'] == "💵 Efectivo"]['Total'].sum()
                cy = df_dia[df_dia['Metodo'] == "🟢 Yape"]['Total'].sum()
                cp = df_dia[df_dia['Metodo'] == "🟣 Plin"]['Total'].sum()
                total_dia = df_dia['Total'].sum()
                
                # MOSTRAR MÉTRICAS
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("💵 EFECTIVO", f"S/ {ce:.2f}")
                c2.metric("🟢 YAPE", f"S/ {cy:.2f}")
                c3.metric("🟣 PLIN", f"S/ {cp:.2f}")
                c4.metric("💰 TOTAL DÍA", f"S/ {total_dia:.2f}")
                
                st.dataframe(df_dia.sort_values(by='Hora', ascending=False)[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_dia.to_excel(writer, index=False, sheet_name='Ventas')
                st.download_button(label="📥 Descargar Reporte Excel", data=output.getvalue(), file_name=f"Ventas_{f_bus.replace('/','-')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else: st.info("No hay registros de ventas para este día.")

# --- TAB 4: HISTORIAL ---
with tabs[3]:
    st.subheader("📋 Historial de Movimientos")
    h_data = tabla_auditoria.scan().get('Items', [])
    if h_data:
        df_h = pd.DataFrame(h_data)
        df_h['Sort'] = pd.to_datetime(df_h['Fecha'] + ' ' + df_h['Hora'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        df_h = df_h.sort_values(by='Sort', ascending=False)
        col1, col2 = st.columns(2)
        with col1:
            st.write("### 📥 Entradas")
            st.dataframe(df_h[df_h.get('Tipo', '') != 'ELIMINADO'][['Fecha', 'Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante']], use_container_width=True, hide_index=True)
        with col2:
            st.write("### 🗑️ Eliminados")
            st.dataframe(df_h[df_h.get('Tipo', '') == 'ELIMINADO'][['Fecha', 'Hora', 'Producto', 'Stock_Resultante']], use_container_width=True, hide_index=True)

# --- TAB 5: CARGAR STOCK ---
with tabs[4]:
    st.subheader("📥 Cargar Stock")
    with st.form(key=f"fc_{st.session_state.form_contador}"):
        p_ex = st.selectbox("Elegir Producto Existente:", [""] + df_stock['Producto'].tolist())
        p_nu = st.text_input("O escribir Producto Nuevo:").upper().strip()
        p_f = p_ex if p_ex != "" else p_nu
        c_i = st.number_input("Cantidad:", min_value=1)
        pr_i = st.number_input("Precio Venta (S/):", min_value=0.1)
        if st.form_submit_button("💾 GUARDAR REGISTRO"):
            if p_f:
                f, h, _, uid = obtener_tiempo_peru()
                s_a = int(df_stock[df_stock['Producto'] == p_f]['Stock'].values[0]) if p_f in df_stock['Producto'].values else 0
                tabla_stock.put_item(Item={'Producto': p_f, 'Stock': s_a + c_i, 'Precio': str(round(pr_i, 2))})
                tabla_auditoria.put_item(Item={'ID_Ingreso': f"I-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_f, 'Cantidad_Entrante': int(c_i), 'Stock_Resultante': int(s_a + c_i), 'Tipo': 'INGRESO'})
                st.success(f"✅ Registrado."); st.session_state.form_contador += 1
                time.sleep(1); st.rerun()

# --- TAB 6: MANTENIMIENTO ---
with tabs[5]:
    st.subheader("🛠️ Mantenimiento")
    if not df_stock.empty:
        p_del = st.selectbox("Eliminar producto del sistema:", df_stock['Producto'].tolist())
        if st.button("🗑️ ELIMINAR PERMANENTEMENTE"):
            f, h, _, uid = obtener_tiempo_peru()
            s_del = int(df_stock[df_stock['Producto'] == p_del]['Stock'].values[0])
            tabla_stock.delete_item(Key={'Producto': p_del})
            tabla_auditoria.put_item(Item={'ID_Ingreso': f"D-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_del, 'Cantidad_Entrante': 0, 'Stock_Resultante': s_del, 'Tipo': 'ELIMINADO'})
            st.success("Eliminado."); time.sleep(1); st.rerun()
