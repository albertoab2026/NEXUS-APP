import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
from io import BytesIO

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
    st.error(f"Error de conexión (Revisa Secrets en Streamlit): {e}")
    st.stop()

def convertir_a_excel(df, nombre_hoja):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=nombre_hoja)
    return output.getvalue()

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

# --- TAB 1: VENTA (CON REBAJAS Y FRACCIONAMIENTO) ---
with tabs[0]:
    if st.session_state.boleta:
        st.balloons()
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: #000; padding: 20px; border: 2px solid #000; border-radius: 10px; max-width: 350px; margin: auto; font-family: monospace;">
            <center><h2 style="margin:0;">BALLARTA</h2><p>TIENDA DENTAL</p></center>
            <hr>
            <p><b>FECHA:</b> {b['fecha']} {b['hora']}</p>
            <table style="width:100%">
        """
        for i in b['items']:
            ticket += f"<tr><td>{i['Cantidad']} {i['Producto']}</td><td style='text-align:right'>S/ {i['Subtotal']:.2f}</td></tr>"
        ticket += f"</table><hr><h3 style='text-align:right'>TOTAL: S/ {b['total']:.2f}</h3><p>Pago: {b['metodo']}</p></div>"
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA"):
            st.session_state.boleta = None
            st.rerun()
    else:
        if not df_stock.empty:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                p_sel = st.selectbox("Producto:", df_stock['Producto'].tolist())
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                st.caption(f"Stock actual: {info['Stock']}")
            with col2:
                # PRECIO EDITABLE PARA REBAJAS
                precio_final = st.number_input("Precio S/:", value=float(info['Precio']), step=0.1)
            with col3:
                # CANTIDAD CON DECIMALES PARA COSAS SUELTAS
                cant = st.number_input("Cantidad:", min_value=0.01, value=1.0, step=0.1)
            
            nota = st.text_input("Nota (opcional: 'Suelto', 'Rebaja', etc.)")

            if st.button("➕ AÑADIR AL CARRITO", use_container_width=True):
                if cant <= info['Stock']:
                    nombre_prod = f"{p_sel} ({nota})" if nota else p_sel
                    st.session_state.carrito.append({
                        'Producto': nombre_prod, 
                        'Original': p_sel,
                        'Cantidad': cant, 
                        'Precio': precio_final, 
                        'Subtotal': round(precio_final * cant, 2)
                    })
                    st.rerun()
                else: st.error("Stock insuficiente")

        if st.session_state.carrito:
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car[['Producto', 'Cantidad', 'Precio', 'Subtotal']])
            total_v = sum(i['Subtotal'] for i in st.session_state.carrito)
            st.subheader(f"Total a Cobrar: S/ {total_v:.2f}")
            
            if st.button("🗑️ VACÍAR"):
                st.session_state.carrito = []
                st.rerun()

            metodo = st.radio("Método:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
            if st.button("🚀 FINALIZAR VENTA", type="primary"):
                f, h, _, uid = obtener_tiempo_peru()
                st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total_v, 'metodo': metodo}
                for item in st.session_state.carrito:
                    s_actual = float(df_stock[df_stock['Producto'] == item['Original']]['Stock'].values[0])
                    # Actualiza stock (soporta decimales)
                    tabla_stock.update_item(Key={'Producto': item['Original']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': str(round(s_actual - item['Cantidad'], 2))})
                    tabla_ventas.put_item(Item={'ID_Venta': f"V-{uid}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': str(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': metodo})
                st.session_state.carrito = []
                st.rerun()

# --- TAB 2: STOCK ---
with tabs[1]:
    st.subheader("📦 Inventario Actual")
    if not df_stock.empty:
        st.dataframe(df_stock, use_container_width=True, hide_index=True)
        excel_s = convertir_a_excel(df_stock, "Stock")
        st.download_button("📥 Descargar Excel Stock", excel_s, "Stock_Dental.xlsx")

# --- TAB 3: REPORTES ---
with tabs[2]:
    st.subheader("📊 Reporte de Ventas")
    _, _, ahora_dt, _ = obtener_tiempo_peru()
    f_bus = st.date_input("Ver día:", ahora_dt).strftime("%d/%m/%Y")
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        df_dia = df_v[df_v['Fecha'] == f_bus].copy()
        if not df_dia.empty:
            df_dia['Total'] = pd.to_numeric(df_dia['Total'])
            st.metric("VENTA TOTAL", f"S/ {df_dia['Total'].sum():.2f}")
            st.dataframe(df_dia[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True)
            excel_v = convertir_a_excel(df_dia, "Ventas")
            st.download_button("📥 Descargar Ventas del Día", excel_v, f"Ventas_{f_bus}.xlsx")

# --- TAB 4: HISTORIAL ---
with tabs[3]:
    st.subheader("📋 Historial de Movimientos")
    h_data = tabla_auditoria.scan().get('Items', [])
    if h_data:
        df_h = pd.DataFrame(h_data)
        if 'Fecha' in df_h.columns:
            df_h['TS'] = pd.to_datetime(df_h['Fecha'] + ' ' + df_h['Hora'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
            df_h = df_h.sort_values('TS', ascending=False)
        st.dataframe(df_h[['Fecha', 'Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante', 'Tipo']], use_container_width=True)

# --- TAB 5: CARGAR ---
with tabs[4]:
    st.subheader("📥 Cargar Nuevo Stock")
    with st.form("carga"):
        p_n = st.text_input("Producto:").upper().strip()
        c_n = st.number_input("Cantidad:", min_value=0.1, step=0.1)
        pr_n = st.number_input("Precio Venta:", min_value=0.1, step=0.1)
        if st.form_submit_button("💾 GUARDAR"):
            if p_n:
                f, h, _, uid = obtener_tiempo_peru()
                s_ant = float(df_stock[df_stock['Producto'] == p_n]['Stock'].values[0]) if p_n in df_stock['Producto'].values else 0
                tabla_stock.put_item(Item={'Producto': p_n, 'Stock': str(s_ant + c_n), 'Precio': str(pr_n)})
                tabla_auditoria.put_item(Item={'ID_Ingreso': f"I-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_n, 'Cantidad_Entrante': str(c_n), 'Stock_Resultante': str(s_ant + c_n), 'Tipo': 'INGRESO'})
                st.success("Registrado"); time.sleep(1); st.rerun()

# --- TAB 6: MANTENIMIENTO ---
with tabs[5]:
    st.subheader("🛠️ Eliminar Producto")
    if not df_stock.empty:
        p_del = st.selectbox("Seleccione para borrar:", df_stock['Producto'].tolist())
        if st.button("🗑️ ELIMINAR PERMANENTE"):
            tabla_stock.delete_item(Key={'Producto': p_del})
            st.success(f"{p_del} eliminado"); time.sleep(1); st.rerun()
