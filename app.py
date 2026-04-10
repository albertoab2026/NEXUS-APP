import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
import io

# 1. CONFIGURACIÓN
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
    # Usamos el nombre de tabla que tienes en tu código: EntradasInventario
    tabla_auditoria = dynamodb.Table('EntradasInventario') 
except Exception as e:
    st.error(f"Error AWS: {e}")
    st.stop()

# ESTADOS DE SESIÓN
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'boleta' not in st.session_state: st.session_state.boleta = None

# --- LOGIN ---
if not st.session_state.sesion_iniciada:
    st.title("🔐 Acceso Sistema BALLARTA")
    clave = st.text_input("Clave del sistema:", type="password")
    if st.button("Ingresar", use_container_width=True):
        if clave == admin_pass:
            st.session_state.sesion_iniciada = True
            st.rerun()
        else: st.error("Clave incorrecta")
    st.stop()

# Botón de cerrar en la barra lateral
if st.sidebar.button("🔴 CERRAR SISTEMA"):
    st.session_state.sesion_iniciada = False
    st.rerun()

st.title("🦷 Gestión Dental BALLARTA")

# CARGAR STOCK ACTUAL
items = tabla_stock.scan().get('Items', [])
if items:
    df_stock = pd.DataFrame(items)
    df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
    df_stock['Precio'] = pd.to_numeric(df_stock['Precio'])
    # Orden solicitado: Producto | Stock | Precio
    df_stock = df_stock[['Producto', 'Stock', 'Precio']].sort_values(by='Producto')
else:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

# --- SISTEMA DE PESTAÑAS ---
t1, t2, t3, t4, t5, t6 = st.tabs([
    "🛒 Punto de Venta", 
    "📦 Stock Actual", 
    "📊 Reporte Ventas", 
    "📋 Historial Entradas", 
    "📥 Cargar Stock", 
    "🛠️ Mantenimiento"
])

# --- TAB 1: VENTA ---
with t1:
    if st.session_state.boleta:
        st.balloons()
        b = st.session_state.boleta
        ticket = f"""
        <div style="background-color: white; color: black; padding: 25px; border: 5px solid black; border-radius: 10px; max-width: 450px; margin: auto; font-family: Arial;">
            <div style="text-align: center;">
                <h1 style="margin: 0;">🦷 BALLARTA</h1>
                <p>Insumos Dentales</p>
                <hr style="border: 1px solid black;">
            </div>
            <p><b>FECHA:</b> {b['fecha']} | {b['hora']}</p>
            <table style="width: 100%;">
                <tr style="border-bottom: 2px solid black; text-align: left;"><th>Cant.</th><th>Producto</th><th style="text-align: right;">Total</th></tr>
        """
        for i in b['items']:
            ticket += f"<tr><td>{i['Cantidad']}</td><td>{i['Producto']}</td><td style='text-align: right;'>S/ {float(i['Subtotal']):.2f}</td></tr>"
        ticket += f"""
            </table>
            <hr style="border: 1px solid black;">
            <div style="text-align: right; font-size: 24px; font-weight: bold;">TOTAL: S/ {b['total']:.2f}</div>
            <p><b>MÉTODO:</b> {b['metodo']}</p>
        </div>
        """
        st.markdown(ticket, unsafe_allow_html=True)
        if st.button("⬅️ NUEVA VENTA"):
            st.session_state.boleta = None
            st.rerun()
        st.stop()

    if not df_stock.empty:
        c1, c2 = st.columns([3, 1])
        with c1:
            prod_sel = st.selectbox("Seleccione Producto:", df_stock['Producto'].tolist())
            s_disp = df_stock.loc[df_stock['Producto'] == prod_sel, 'Stock'].values[0]
            p_disp = df_stock.loc[df_stock['Producto'] == prod_sel, 'Precio'].values[0]
            
            if s_disp <= 5:
                st.error(f"⚠️ **STOCK CRÍTICO:** Solo quedan {s_disp:.0f} unidades.")
            else:
                st.info(f"📦 Disponible: {s_disp:.0f} | 💰 Precio: S/ {p_disp:.2f}")

        with c2:
            cant_sel = st.number_input("Cantidad:", min_value=1, value=1)
        
        if st.button("➕ AÑADIR AL CARRITO", use_container_width=True):
            if cant_sel <= s_disp:
                st.session_state.carrito.append({
                    'Producto': prod_sel, 'Cantidad': cant_sel, 
                    'Precio': p_disp, 'Subtotal': round(p_disp * cant_sel, 2)
                })
                st.rerun()
            else:
                st.error("No hay suficiente stock")

    if st.session_state.carrito:
        st.write("### 🛒 Carrito")
        df_car = pd.DataFrame(st.session_state.carrito)
        st.table(df_car)
        total_v = df_car['Subtotal'].sum()
        
        m_pago = st.radio("Método de Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
        st.warning(f"Total a cobrar: S/ {total_v:.2f}")
        
        confirma = st.checkbox("Confirmar recepción de pago")
        
        if st.button("🚀 FINALIZAR VENTA", disabled=not confirma, type="primary", use_container_width=True):
            f, h, _ = obtener_tiempo_peru()
            st.session_state.boleta = {
                'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 
                'total': total_v, 'metodo': m_pago
            }
            for item in st.session_state.carrito:
                res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                n_s = int(res['Item']['Stock']) - item['Cantidad']
                tabla_stock.update_item(
                    Key={'Producto': item['Producto']}, 
                    UpdateExpression="set Stock = :s", 
                    ExpressionAttributeValues={':s': n_s}
                )
                tabla_ventas.put_item(Item={
                    'ID_Venta': f"V-{f}-{h}-{item['Producto'][:2]}", 
                    'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 
                    'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 
                    'Metodo': m_pago
                })
            st.session_state.carrito = []
            st.rerun()

# --- TAB 2: STOCK ACTUAL ---
with t2:
    st.subheader("📦 Inventario Completo")
    if not df_stock.empty:
        def estilo_stock(val):
            return 'background-color: #ff4b4b; color: white; font-weight: bold' if val <= 5 else ''
        
        st.dataframe(
            df_stock.style.map(estilo_stock, subset=['Stock'])
            .format({"Precio": "S/ {:.2f}", "Stock": "{:,.0f}"}),
            use_container_width=True, hide_index=True
        )
    else: st.info("No hay productos.")

# --- TAB 3: REPORTE VENTAS ---
with t3:
    st.subheader("📊 Ventas del Día")
    _, _, ahora_dt = obtener_tiempo_peru()
    f_bus = st.date_input("Consultar fecha:", ahora_dt).strftime("%d/%m/%Y")
    
    ventas = tabla_ventas.scan().get('Items', [])
    if ventas:
        df_v = pd.DataFrame(ventas)
        df_v_dia = df_v[df_v['Fecha'] == f_bus].copy()
        if not df_v_dia.empty:
            df_v_dia['Total'] = pd.to_numeric(df_v_dia['Total'])
            df_v_dia = df_v_dia.sort_values(by='Hora', ascending=False)
            
            st.metric("Total Recaudado", f"S/ {df_v_dia['Total'].sum():.2f}")
            st.dataframe(df_v_dia[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_v_dia.to_excel(writer, index=False)
            st.download_button("📥 Descargar Excel", output.getvalue(), f"Ventas_{f_bus}.xlsx")
        else: st.info("No hay ventas en esta fecha.")

# --- TAB 4: HISTORIAL ENTRADAS ---
with t4:
    st.subheader("📋 Registro de Ingresos (Auditoría)")
    ing_raw = tabla_auditoria.scan().get('Items', [])
    if ing_raw:
        df_ing = pd.DataFrame(ing_raw)
        df_ing['DT'] = pd.to_datetime(df_ing['Fecha'] + ' ' + df_ing['Hora'], format='%d/%m/%Y %H:%M:%S')
        df_ing = df_ing.sort_values(by='DT', ascending=False)
        st.dataframe(
            df_ing[['Fecha', 'Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante', 'Precio_Fijado']], 
            use_container_width=True, hide_index=True
        )
    else: st.info("No hay ingresos registrados.")

# --- TAB 5: CARGAR STOCK ---
with t5:
    st.subheader("📥 Cargar Mercadería")
    with st.form("form_carga"):
        p_in = st.selectbox("Producto Existente:", df_stock['Producto'].tolist()) if not df_stock.empty else ""
        p_nuevo = st.text_input("O escribir Producto Nuevo (USAR MAYÚSCULAS):").strip().upper()
        p_final = p_nuevo if p_nuevo else p_in
        
        c_in = st.number_input("Cantidad entrante:", min_value=1)
        pr_in = st.number_input("Precio de venta (S/):", min_value=0.1, step=0.50)
        
        if st.form_submit_button("💾 GUARDAR INGRESO"):
            if not p_final:
                st.error("Debe indicar un producto.")
            else:
                f, h, _ = obtener_tiempo_peru()
                res = tabla_stock.get_item(Key={'Producto': p_final})
                n_stock = (int(res['Item']['Stock']) if 'Item' in res else 0) + c_in
                
                # Actualizar Stock
                tabla_stock.put_item(Item={'Producto': p_final, 'Stock': n_stock, 'Precio': str(pr_in)})
                
                # Guardar Auditoría
                tabla_auditoria.put_item(Item={
                    'ID_Ingreso': f"I-{f}-{h}-{p_final[:2]}", 
                    'Fecha': f, 'Hora': h, 'Producto': p_final, 
                    'Cantidad_Entrante': int(c_in), 'Stock_Resultante': int(n_stock), 
                    'Precio_Fijado': str(pr_in)
                })
                st.success(f"Stock actualizado: {p_final}")
                time.sleep(1)
                st.rerun()

# --- TAB 6: MANTENIMIENTO ---
with t6:
    st.subheader("🛠️ Mantenimiento de Datos")
    if not df_stock.empty:
        prod_mant = st.selectbox("Seleccione producto:", df_stock['Producto'].tolist())
        if st.button("🗑️ ELIMINAR PERMANENTEMENTE", use_container_width=True):
            tabla_stock.delete_item(Key={'Producto': prod_mant})
            st.warning(f"Eliminado: {prod_mant}")
            time.sleep(1); st.rerun()
