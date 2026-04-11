import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time

# 1. CONFIGURACIÓN VISUAL
st.set_page_config(page_title="Dental BALLARTA", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora, ahora.strftime("%Y%m%d%H%M%S%f")

# 2. CONEXIÓN AWS (Usando tus secretos configurados)
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

# --- LOGIN ---
if not st.session_state.sesion_iniciada:
    st.markdown("<h1 style='text-align: center;'>🦷</h1><h2 style='text-align: center;'>Sistema BALLARTA</h2>", unsafe_allow_html=True)
    clave = st.text_input("Contraseña del sistema:", type="password")
    if st.button("🔓 INGRESAR", use_container_width=True):
        if clave == admin_pass:
            st.session_state.sesion_iniciada = True
            st.rerun()
        else: st.error("Clave incorrecta")
    st.stop()

# CARGAR DATOS
def get_df_stock():
    try:
        items = tabla_stock.scan().get('Items', [])
        if items:
            df = pd.DataFrame(items)
            for col in ['Stock', 'Precio', 'Producto']:
                if col not in df.columns: df[col] = 0 if col != 'Producto' else "Sin Nombre"
            df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
            return df[['Producto', 'Stock', 'Precio']].sort_values(by='Producto')
    except: pass
    return pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

df_stock = get_df_stock()

tabs = st.tabs(["🛒 VENTA", "📦 STOCK", "📊 HOY", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."])

# --- TAB 1: VENTA (ARREGLO DE BOLETA) ---
with tabs[0]:
    if st.session_state.boleta:
        b = st.session_state.boleta
        
        # DISEÑO DE BOLETA (HTML FORZADO A SER BLANCO Y NEGRO)
        ticket_html = f"""
        <div style="background-color: white; color: black; padding: 15px; border: 2px solid black; border-radius: 10px; font-family: 'Courier New', Courier, monospace; width: 100%; max-width: 350px; margin: auto; box-shadow: 2px 2px 10px rgba(0,0,0,0.1);">
            <center>
                <h2 style='margin:0; color: black;'>BALLARTA DENTAL</h2>
                <p style='margin:0; font-size: 12px; color: black;'>Santa Isabel, Carabayllo</p>
                <p style='margin:0; font-size: 12px; color: black;'>{b['fecha']} | {b['hora']}</p>
            </center>
            <hr style='border: 1px dashed black; margin: 10px 0;'>
            <table style='width: 100%; font-size: 12px; border-collapse: collapse; color: black;'>
                <thead>
                    <tr style='border-bottom: 1px solid black;'>
                        <th style='text-align: left;'>Cant.</th>
                        <th style='text-align: left;'>Producto</th>
                        <th style='text-align: right;'>P.U.</th>
                        <th style='text-align: right;'>Total</th>
                    </tr>
                </thead>
                <tbody>
        """
        for i in b['items']:
            ticket_html += f"""
                <tr>
                    <td style='padding: 4px 0;'>{i['Cantidad']}</td>
                    <td style='padding: 4px 0;'>{i['Producto']}</td>
                    <td style='text-align: right;'>{i['Precio']:.2f}</td>
                    <td style='text-align: right;'>{i['Subtotal']:.2f}</td>
                </tr>
            """
        
        ticket_html += f"""
                </tbody>
            </table>
            <hr style='border: 1px dashed black; margin: 10px 0;'>
            <div style='text-align: right;'>
                <p style='margin: 0; font-size: 16px; color: black;'><b>TOTAL: S/ {b['total']:.2f}</b></p>
                <p style='margin: 0; font-size: 12px; color: black;'>Pago: {b['metodo']}</p>
            </div>
            <br>
            <center><p style='margin:0; font-weight: bold; color: black;'>¡Gracias por su preferencia!</p></center>
        </div>
        """
        # ESTA ES LA CLAVE: st.markdown dibuja el HTML real
        st.markdown(ticket_html, unsafe_allow_html=True)
        
        st.write("") # Espacio
        if st.button("⬅️ NUEVA VENTA", use_container_width=True):
            st.session_state.boleta = None
            st.rerun()
    else:
        if not df_stock.empty:
            p_sel = st.selectbox("Elegir Producto:", df_stock['Producto'].tolist())
            info = df_stock[df_stock['Producto'] == p_sel].iloc[0]
            st.info(f"Stock: {info['Stock']} | Precio: S/ {info['Precio']:.2f}")
            
            c1, c2 = st.columns(2)
            with c1: precio_u = st.number_input("Precio Cobrar:", value=float(info['Precio']), step=1.0)
            with c2: cant = st.number_input("Cant:", min_value=1, value=1)
            
            sub_total = precio_u * cant
            st.markdown(f"<div style='background-color:#E8F8F5; padding:10px; border-radius:5px; text-align:center; border: 1px solid #A9DFBF;'><h2 style='color:#145A32; margin:0;'>S/ {sub_total:.2f}</h2></div>", unsafe_allow_html=True)
            
            nota = st.text_input("Nota (opcional)")

            if st.button("➕ AÑADIR A LA LISTA", use_container_width=True):
                if cant <= info['Stock']:
                    st.session_state.carrito.append({'Producto': f"{p_sel} ({nota})" if nota else p_sel, 'Original': p_sel, 'Cantidad': int(cant), 'Precio': float(precio_u), 'Subtotal': round(sub_total, 2)})
                    st.rerun()
                else: st.error("Sin stock")

        if st.session_state.carrito:
            st.divider()
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c[['Producto', 'Cantidad', 'Subtotal']])
            total_f = df_c['Subtotal'].sum()
            
            metodo = st.radio("Método:", ["Efectivo", "Yape", "Plin"], horizontal=True)
            if st.button(f"🚀 COBRAR S/ {total_f:.2f}", type="primary", use_container_width=True):
                f, h, _, uid = obtener_tiempo_peru()
                st.session_state.boleta = {'fecha': f, 'hora': h, 'items': list(st.session_state.carrito), 'total': total_f, 'metodo': metodo}
                for item in st.session_state.carrito:
                    s_act = int(df_stock[df_stock['Producto'] == item['Original']]['Stock'].values[0])
                    tabla_stock.update_item(Key={'Producto': item['Original']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': s_act - item['Cantidad']})
                    tabla_ventas.put_item(Item={'ID_Venta': f"V-{uid}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': metodo})
                st.session_state.carrito = []
                st.rerun()

# --- TAB 3: HOY (DETALLE DE CAJA) ---
with tabs[2]:
    st.subheader("📊 Reporte del Día")
    _, _, ahora_dt, _ = obtener_tiempo_peru()
    f_bus = st.date_input("Fecha:", ahora_dt).strftime("%d/%m/%Y")
    
    v_data = tabla_ventas.scan().get('Items', [])
    if v_data:
        df_v = pd.DataFrame(v_data)
        df_dia = df_v[df_v['Fecha'] == f_bus].copy()
        if not df_dia.empty:
            df_dia['Total'] = pd.to_numeric(df_dia['Total'])
            ef = df_dia[df_dia['Metodo'] == 'Efectivo']['Total'].sum()
            ya = df_dia[df_dia['Metodo'] == 'Yape']['Total'].sum()
            pl = df_dia[df_dia['Metodo'] == 'Plin']['Total'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("💵 EFECTIVO", f"S/ {ef:.2f}")
            c2.metric("🟢 YAPE", f"S/ {ya:.2f}")
            c3.metric("🟣 PLIN", f"S/ {pl:.2f}")
            
            # Cuadro de total legible
            st.markdown(f"""
                <div style='text-align:center; background-color:white; border:2px solid #2E86C1; padding:10px; border-radius:10px; margin-top:10px;'>
                    <h1 style='color:#1B4F72; margin:0;'>TOTAL: S/ {df_dia['Total'].sum():.2f}</h1>
                </div>
            """, unsafe_allow_html=True)
            
            st.divider()
            st.dataframe(df_dia[['Hora', 'Producto', 'Total', 'Metodo']], use_container_width=True, hide_index=True)

# (STOCK, HISTORIAL, CARGAR y MANTENIMIENTO se mantienen igual para seguridad)
with tabs[1]:
    st.subheader("📦 Almacén")
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[3]:
    st.subheader("📋 Historial")
    h_data = tabla_auditoria.scan().get('Items', [])
    if h_data:
        df_h = pd.DataFrame(h_data).rename(columns={'Fecha':'FECHA','Hora':'HORA','Producto':'PRODUCTO','Cantidad_Entrante':'ENTRÓ','Stock_Resultante':'TOTAL'})
        st.dataframe(df_h[['FECHA', 'HORA', 'PRODUCTO', 'ENTRÓ', 'TOTAL']], use_container_width=True, hide_index=True)

with tabs[4]:
    st.subheader("📥 Cargar Stock")
    with st.form("fc"):
        p_n = st.text_input("Producto:").upper().strip()
        c_n = st.number_input("Cantidad:", min_value=1)
        pr_n = st.number_input("Precio S/:", min_value=1.0)
        if st.form_submit_button("GUARDAR"):
            f, h, _, uid = obtener_tiempo_peru()
            s_ant = int(df_stock[df_stock['Producto'] == p_n]['Stock'].values[0]) if p_n in df_stock['Producto'].values else 0
            tabla_stock.put_item(Item={'Producto': p_n, 'Stock': s_ant + c_n, 'Precio': str(pr_n)})
            tabla_auditoria.put_item(Item={'ID_Ingreso': f"I-{uid}", 'Fecha': f, 'Hora': h, 'Producto': p_n, 'Cantidad_Entrante': int(c_n), 'Stock_Resultante': int(s_ant + c_n), 'Tipo': 'INGRESO'})
            st.success("Cargado"); time.sleep(1); st.rerun()

with tabs[5]:
    st.subheader("🛠️ Eliminar")
    if not df_stock.empty:
        p_del = st.selectbox("Borrar:", df_stock['Producto'].tolist())
        if st.button("BORRAR PRODUCTO"):
            tabla_stock.delete_item(Key={'Producto': p_del})
            st.success("Borrado"); time.sleep(1); st.rerun()
