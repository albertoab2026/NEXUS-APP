import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
import io

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Sistema Dental Tío - TOTAL", layout="wide")

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
    st.error(f"Error AWS: {e}")
    st.stop()

# ESTADOS DE SESIÓN
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'confirmar' not in st.session_state: st.session_state.confirmar = False

# --- PANTALLA DE LOGIN ---
if not st.session_state.sesion_iniciada:
    st.title("🔐 Acceso Restringido")
    clave_entrada = st.text_input("Clave del sistema:", type="password")
    if st.button("Ingresar", use_container_width=True):
        if clave_entrada == admin_pass:
            st.session_state.sesion_iniciada = True
            st.rerun()
        else: st.error("Clave incorrecta")
    st.stop()

# --- INTERFAZ PRINCIPAL ---
if st.sidebar.button("🔴 CERRAR SISTEMA"):
    st.session_state.sesion_iniciada = False
    st.rerun()

st.title("🦷 Gestión Dental")

# CARGAR STOCK ACTUAL
items = tabla_stock.scan().get('Items', [])
df_stock = pd.DataFrame(items) if items else pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

tab_ventas, tab_admin = st.tabs(["🛒 Punto de Venta", "⚙️ Administración"])

with tab_ventas:
    if not df_stock.empty:
        df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
        
        # --- LÓGICA DE ALERTAS (STOCK BAJO < 5) ---
        stock_bajo = df_stock[df_stock['Stock'] < 5]
        if not stock_bajo.empty:
            for _, fila in stock_bajo.iterrows():
                st.error(f"⚠️ **STOCK CRÍTICO:** El producto **{fila['Producto']}** tiene solo **{fila['Stock']}** unidades.")

        with st.expander("Ver Stock Disponible"):
            # Colorear filas de stock bajo en la tabla
            def resaltar_bajo_stock(s):
                return ['background-color: #ff4b4b; color: white' if s.Stock < 5 else '' for _ in s]
            
            st.dataframe(df_stock[['Producto', 'Stock', 'Precio']].style.apply(resaltar_bajo_stock, axis=None), 
                         use_container_width=True, hide_index=True)
        
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1: prod_sel = st.selectbox("Producto:", df_stock['Producto'].tolist())
        with c2: cant_sel = st.number_input("Cantidad:", min_value=1, value=1)
        with c3:
            st.write("##")
            if st.button("➕ Añadir"):
                s_disp = int(df_stock.loc[df_stock['Producto'] == prod_sel, 'Stock'].values[0])
                if cant_sel <= s_disp:
                    p = float(df_stock.loc[df_stock['Producto'] == prod_sel, 'Precio'].values[0])
                    st.session_state.carrito.append({'Producto': prod_sel, 'Cantidad': cant_sel, 'Precio': p, 'Subtotal': round(p * cant_sel, 2)})
                    st.rerun()
                else: st.error("Stock insuficiente")

    if st.session_state.carrito:
        st.write("### 🛒 Carrito de Compras")
        df_car = pd.DataFrame(st.session_state.carrito)
        st.table(df_car)
        
        total_v = df_car['Subtotal'].sum()
        
        col_total, col_vaciar = st.columns([2, 1])
        with col_total:
            st.metric(label="Total de Venta", value=f"S/ {total_v:.2f}")
        with col_vaciar:
            st.write("##")
            if st.button("🗑️ Vaciar Carrito", use_container_width=True):
                st.session_state.carrito = []
                st.session_state.confirmar = False
                st.rerun()

        m_pago = st.radio("Método de Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)

        if st.button("🚀 PROCESAR VENTA", type="primary", use_container_width=True):
            st.session_state.confirmar = True
        
        if st.session_state.confirmar:
            st.warning("⚠️ ¿Confirmar transacción?")
            c_si, c_no = st.columns(2)
            with c_si:
                if st.button("✅ SÍ, FINALIZAR", use_container_width=True):
                    f, h, _ = obtener_tiempo_peru()
                    for item in st.session_state.carrito:
                        res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                        n_s = int(res['Item']['Stock']) - item['Cantidad']
                        tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_s})
                        tabla_ventas.put_item(Item={
                            'ID_Venta': f"V-{f}-{h}-{item['Producto'][:2]}", 
                            'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 
                            'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 
                            'Metodo': m_pago
                        })
                    st.success("¡Venta realizada con éxito!")
                    st.session_state.carrito = []
                    st.session_state.confirmar = False
                    time.sleep(1)
                    st.rerun()
            with c_no:
                if st.button("❌ CANCELAR", use_container_width=True):
                    st.session_state.confirmar = False
                    st.rerun()

with tab_admin:
    t_ganancia, t_stock = st.tabs(["💰 Reporte de Ventas", "📥 Entrada de Mercadería"])
    
    with t_ganancia:
        _, _, ahora = obtener_tiempo_peru()
        f_bus = st.date_input("Ver ventas del día:", ahora).strftime("%d/%m/%Y")
        ventas = tabla_ventas.scan().get('Items', [])
        df_v = pd.DataFrame([v for v in ventas if v['Fecha'] == f_bus])
        
        if not df_v.empty:
            df_v['Total'] = pd.to_numeric(df_v['Total'])
            st.metric("RECAUDACIÓN TOTAL", f"S/ {df_v['Total'].sum():.2f}")
            df_v = df_v.sort_values(by='Hora', ascending=False)
            st.dataframe(df_v[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_v.to_excel(writer, index=False, sheet_name='Ventas')
            st.download_button(label="📥 Descargar Reporte Excel", data=output.getvalue(), file_name=f"Ventas_{f_bus.replace('/','-')}.xlsx", mime="application/vnd.ms-excel")
        else: st.info("No hay ventas en esta fecha.")

    with t_stock:
        with st.form("form_stock"):
            st.write("### Registrar Ingreso de Mercadería")
            p_in = st.selectbox("Producto:", df_stock['Producto'].tolist()) if not df_stock.empty else st.text_input("Nombre del Producto")
            c_in = st.number_input("Cantidad entrante:", min_value=1)
            pr_in = st.number_input("Precio de venta actual:", min_value=0.0)
            if st.form_submit_button("💾 Guardar en Inventario"):
                res = tabla_stock.get_item(Key={'Producto': p_in})
                n_stock = (int(res['Item']['Stock']) if 'Item' in res else 0) + c_in
                tabla_stock.put_item(Item={'Producto': p_in, 'Stock': n_stock, 'Precio': str(pr_in)})
                
                f, h, _ = obtener_tiempo_peru()
                tabla_auditoria.put_item(Item={
                    'ID_Ingreso': f"I-{f}-{h}", 'Fecha': f, 'Hora': h, 
                    'Producto': p_in, 'Cantidad_Entrante': int(c_in), 
                    'Stock_Resultante': int(n_stock), 'Precio_Fijado': str(pr_in)
                })
                st.success(f"Stock actualizado: {p_in}")
                time.sleep(1)
                st.rerun()

        st.divider()
        st.write("### Historial de Ingresos")
        f_st_bus = st.date_input("Ver entradas de fecha:", ahora).strftime("%d/%m/%Y")
        ing_raw = tabla_auditoria.scan().get('Items', [])
        df_ing = pd.DataFrame([i for i in ing_raw if i['Fecha'] == f_st_bus])
        
        if not df_ing.empty:
            df_ing = df_ing.sort_values(by='Hora', ascending=False)
            st.dataframe(df_ing[['Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante', 'Precio_Fijado']], use_container_width=True, hide_index=True)
        else: st.info("Sin movimientos de entrada hoy.")
