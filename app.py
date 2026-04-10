import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
import io

# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Sistema Dental BALLARTA", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora

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
    st.error(f"Error de conexión AWS: {e}")
    st.stop()

# 3. ESTADOS DE SESIÓN
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None

# --- PANTALLA DE LOGIN ---
if not st.session_state.sesion_iniciada:
    st.markdown("<h1 style='text-align: center;'>🦷</h1>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #2E86C1;'>Sistema Dental BALLARTA</h1>", unsafe_allow_html=True)
    col_login, _ = st.columns([1, 1])
    with col_login:
        clave = st.text_input("Clave de acceso:", type="password")
        if st.button("🔓 Ingresar", use_container_width=True):
            if clave == admin_pass:
                st.session_state.sesion_iniciada = True
                st.rerun()
            else: st.error("❌ Contraseña incorrecta")
    st.stop()

# --- BARRA LATERAL ---
if st.sidebar.button("🔴 CERRAR SESIÓN"):
    st.session_state.sesion_iniciada = False
    st.rerun()

st.markdown("<h2 style='color: #2E86C1;'>🦷 Gestión Dental BALLARTA</h2>", unsafe_allow_html=True)

# 4. CARGA DE DATOS (STOCK)
def cargar_stock():
    items = tabla_stock.scan().get('Items', [])
    if items:
        df = pd.DataFrame(items)
        df['Stock'] = pd.to_numeric(df['Stock'])
        df['Precio'] = pd.to_numeric(df['Precio'])
        return df.sort_values(by='Producto')
    return pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

df_stock = cargar_stock()

# --- DEFINICIÓN DE PESTAÑAS ---
t1, t2, t3, t4, t5, t6 = st.tabs([
    "🛒 Venta", "📦 Stock", "📊 Reportes", 
    "📋 Historial Entradas", "📥 Cargar Stock", "🛠️ Mantenimiento"
])

# --- PESTAÑA 1: PUNTO DE VENTA ---
with t1:
    if st.session_state.boleta:
        st.balloons()
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: black; padding: 20px; border: 2px solid black; border-radius: 10px; font-family: monospace;">
            <center><h2>🦷 BALLARTA</h2><p>Carabayllo, Lima</p></center>
            <hr>
            <p><b>Fecha:</b> {b['fecha']} | {b['hora']}</p>
            <table style="width:100%">
                <tr><td><b>Cant.</b></td><td><b>Producto</b></td><td style="text-align:right"><b>Total</b></td></tr>
        """
        for i in b['items']:
            ticket += f"<tr><td>{i['Cantidad']}</td><td>{i['Producto']}</td><td style='text-align:right'>S/ {i['Subtotal']:.2f}</td></tr>"
        ticket += f"""
            </table>
            <hr>
            <h3 style="text-align:right">TOTAL: S/ {b['total']:.2f}</h3>
            <p>Método: {b['metodo']}</p>
        </div>
        """
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA"):
            st.session_state.boleta = None
            st.rerun()
    else:
        if not df_stock.empty:
            c1, c2 = st.columns([3, 1])
            with c1:
                p_sel = st.selectbox("Producto:", df_stock['Producto'].tolist())
                info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
                st.info(f"Stock: {info['Stock']:.0f} | Precio: S/ {info['Precio']:.2f}")
            with c2:
                cant = st.number_input("Cant:", min_value=1, value=1)
            
            if st.button("➕ AÑADIR"):
                if cant <= info['Stock']:
                    st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': cant, 'Precio': info['Precio'], 'Subtotal': round(info['Precio'] * cant, 2)})
                    st.rerun()
                else: st.error("No hay stock suficiente")

        if st.session_state.carrito:
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car.style.format({"Precio": "{:.2f}", "Subtotal": "{:.2f}"}))
            total_v = df_car['Subtotal'].sum()
            
            # PRECIO GRANDE
            st.success(f"### TOTAL A COBRAR: S/ {total_v:.2f}")
            
            metodo = st.radio("Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
            if st.button("🚀 FINALIZAR VENTA", type="primary"):
                f, h, _ = obtener_tiempo_peru()
                st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total_v, 'metodo': metodo}
                for item in st.session_state.carrito:
                    # Actualizar Stock
                    n_s = int(df_stock[df_stock['Producto'] == item['Producto']]['Stock'].values[0]) - item['Cantidad']
                    tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                    # Guardar Venta
                    tabla_ventas.put_item(Item={'ID_Venta': f"V-{f}-{h}-{item['Producto'][:2]}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': metodo})
                st.session_state.carrito = []
                st.rerun()

# --- PESTAÑA 2: STOCK ACTUAL ---
with t2:
    st.subheader("📦 Inventario en tiempo real")
    st.dataframe(df_stock.style.format({"Precio": "S/ {:.2f}", "Stock": "{:,.0f}"}), use_container_width=True, hide_index=True)

# --- PESTAÑA 3: REPORTE VENTAS ---
with t3:
    st.subheader("📊 Reporte Diario")
    _, _, ahora = obtener_tiempo_peru()
    f_bus = st.date_input("Fecha:", ahora).strftime("%d/%m/%Y")
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        df_v_dia = df_v[df_v['Fecha'] == f_bus].copy()
        if not df_v_dia.empty:
            df_v_dia['Total'] = pd.to_numeric(df_v_dia['Total'])
            st.metric("Total del día", f"S/ {df_v_dia['Total'].sum():.2f}")
            st.dataframe(df_v_dia[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], hide_index=True)
            
            # EXCEL REPORTE
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_v_dia.to_excel(writer, index=False, sheet_name='Ventas')
            st.download_button("📥 Descargar Ventas (Excel)", output.getvalue(), f"Ventas_{f_bus}.xlsx")
        else: st.info("Sin ventas hoy.")

# --- PESTAÑA 4: HISTORIAL ENTRADAS ---
with t4:
    st.subheader("📋 Registro de Ingresos (Stock)")
    ingresos = tabla_auditoria.scan().get('Items', [])
    if ingresos:
        df_ing = pd.DataFrame(ingresos)
        df_ing = df_ing.sort_values(by=['Fecha', 'Hora'], ascending=False)
        st.dataframe(df_ing[['Fecha', 'Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante']], use_container_width=True, hide_index=True)
        
        # EXCEL HISTORIAL
        out_ing = io.BytesIO()
        with pd.ExcelWriter(out_ing, engine='xlsxwriter') as writer:
            df_ing.to_excel(writer, index=False, sheet_name='Ingresos')
        st.download_button("📥 Descargar Historial (Excel)", out_ing.getvalue(), "Historial_Entradas.xlsx")
    else: st.info("No hay registros de entrada.")

# --- PESTAÑA 5: CARGAR STOCK ---
with t5:
    st.subheader("📥 Ingreso de Mercadería")
    with st.form("carga_stock"):
        p_ex = st.selectbox("Producto existente:", [""] + df_stock['Producto'].tolist())
        p_nu = st.text_input("O Producto Nuevo (Nombre):").upper()
        p_final = p_nu if p_nu else p_ex
        cant_in = st.number_input("Cantidad que entra:", min_value=1)
        prec_in = st.number_input("Precio de venta:", min_value=0.1)
        if st.form_submit_button("💾 REGISTRAR"):
            if p_final:
                f, h, _ = obtener_tiempo_peru()
                # Calcular nuevo stock
                s_actual = int(df_stock[df_stock['Producto'] == p_final]['Stock'].values[0]) if p_final in df_stock['Producto'].values else 0
                nuevo_s = s_actual + cant_in
                # Guardar en tablas
                tabla_stock.put_item(Item={'Producto': p_final, 'Stock': nuevo_s, 'Precio': str(prec_in)})
                tabla_auditoria.put_item(Item={'ID': f"I-{f}-{h}", 'Fecha': f, 'Hora': h, 'Producto': p_final, 'Cantidad_Entrante': int(cant_in), 'Stock_Resultante': int(nuevo_s)})
                st.success("Ingreso registrado"); time.sleep(1); st.rerun()

# --- PESTAÑA 6: MANTENIMIENTO ---
with t6:
    st.subheader("🛠️ Configuración de Productos")
    if not df_stock.empty:
        p_borrar = st.selectbox("Seleccionar producto para ELIMINAR:", df_stock['Producto'].tolist())
        if st.button("🗑️ ELIMINAR PRODUCTO", type="secondary"):
            tabla_stock.delete_item(Key={'Producto': p_borrar})
            st.warning(f"Se eliminó {p_borrar}")
            time.sleep(1); st.rerun()
