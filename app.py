import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
import io

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Sistema Dental Tío - PROTEGIDO", layout="wide")

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

# ESTADOS DE SESIÓN (SEGURIDAD)
if 'sesion_iniciada' not in st.session_state: st.session_state.sesion_iniciada = False
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'confirmar' not in st.session_state: st.session_state.confirmar = False

# --- PANTALLA DE LOGIN INICIAL ---
if not st.session_state.sesion_iniciada:
    st.title("🔐 Acceso Restringido")
    st.info("Bienvenido al Sistema de Gestión Dental. Por favor, identifíquese.")
    
    with st.container():
        clave_entrada = st.text_input("Ingrese la clave del sistema:", type="password")
        if st.button("Ingresar al Sistema", use_container_width=True):
            if clave_entrada == admin_pass:
                st.session_state.sesion_iniciada = True
                st.success("Acceso concedido...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Clave incorrecta. Acceso denegado.")
    st.stop() # Bloquea todo el resto del código si no ha iniciado sesión

# --- TODO LO DE ABAJO SOLO SE EJECUTA SI LA CLAVE ES CORRECTA ---

# BOTÓN CERRAR TODO (Para que nadie use el celular si tu tío lo deja abierto)
if st.sidebar.button("🔴 CERRAR SISTEMA (SALIR)"):
    st.session_state.sesion_iniciada = False
    st.rerun()

st.title("🦷 Gestión Dental: Panel de Operaciones")

# CARGAR STOCK
items = tabla_stock.scan().get('Items', [])
df_stock = pd.DataFrame(items) if items else pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

# --- TABS DE TRABAJO ---
tab_ventas, tab_admin = st.tabs(["🛒 Punto de Venta", "⚙️ Administración y Reportes"])

with tab_ventas:
    st.subheader("Registrar Nueva Venta")
    if not df_stock.empty:
        df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
        # Mostrar stock solo como referencia rápida
        with st.expander("Ver Stock Disponible"):
            st.dataframe(df_stock[['Producto', 'Stock', 'Precio']], use_container_width=True, hide_index=True)
        
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            prod_sel = st.selectbox("Elegir Producto:", df_stock['Producto'].tolist())
        with c2:
            cant_sel = st.number_input("Cantidad:", min_value=1, value=1)
        with c3:
            st.write("##")
            if st.button("➕ Añadir"):
                stock_disp = int(df_stock.loc[df_stock['Producto'] == prod_sel, 'Stock'].values[0])
                if cant_sel <= stock_disp:
                    precio = float(df_stock.loc[df_stock['Producto'] == prod_sel, 'Precio'].values[0])
                    st.session_state.carrito.append({'Producto': prod_sel, 'Cantidad': cant_sel, 'Precio': precio, 'Subtotal': round(precio * cant_sel, 2)})
                else: st.error(f"¡Solo hay {stock_disp}!")

    if st.session_state.carrito:
        df_car = pd.DataFrame(st.session_state.carrito)
        st.table(df_car)
        total_car = df_car['Subtotal'].sum()
        st.markdown(f"### **TOTAL: S/ {total_car:.2f}**")
        
        v_metodo = st.radio("Pago:", ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], horizontal=True)
        
        cv1, cv2 = st.columns(2)
        with cv1:
            if st.button("🚀 PROCESAR VENTA", type="primary", use_container_width=True): st.session_state.confirmar = True
        with cv2:
            if st.button("🗑️ VACÍAR", use_container_width=True): st.session_state.carrito = []; st.rerun()

        if st.session_state.confirmar:
            st.warning(f"¿Confirmar cobro de S/ {total_car:.2f}?")
            if st.button("✅ SÍ, FINALIZAR"):
                f, h, _ = obtener_tiempo_peru()
                for item in st.session_state.carrito:
                    res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                    n_stock = int(res['Item']['Stock']) - item['Cantidad']
                    tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_stock})
                    id_v = f"V-{f.replace('/','')}-{h.replace(':','')}-{item['Producto'][:3]}"
                    tabla_ventas.put_item(Item={'ID_Venta': id_v, 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': v_metodo})
                st.balloons(); st.session_state.carrito = []; st.session_state.confirmar = False; st.rerun()

with tab_admin:
    st.subheader("Área Reservada")
    sub_t1, sub_t2 = st.tabs(["💰 Ganancias", "📥 Stock"])
    
    with sub_t1:
        _, _, ahora = obtener_tiempo_peru()
        fecha_busqueda = st.date_input("Fecha:", ahora)
        f_formateada = fecha_busqueda.strftime("%d/%m/%Y")
        ventas_all = tabla_ventas.scan().get('Items', [])
        df_ventas = pd.DataFrame([v for v in ventas_all if v['Fecha'] == f_formateada])
        
        if not df_ventas.empty:
            df_ventas['Total'] = pd.to_numeric(df_ventas['Total'])
            st.metric("RECAUDACIÓN", f"S/ {df_ventas['Total'].sum():.2f}")
            st.dataframe(df_ventas.sort_values(by='Hora', ascending=False)[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
        else: st.info("Sin registros.")

    with sub_t2:
        with st.form("abastecer"):
            p_ab = st.selectbox("Producto:", df_stock['Producto'].tolist()) if not df_stock.empty else st.text_input("Nombre")
            c_ab = st.number_input("Cantidad:", min_value=1)
            pr_ab = st.number_input("Precio:", min_value=0.0)
            if st.form_submit_button("Guardar"):
                res = tabla_stock.get_item(Key={'Producto': p_ab})
                s_fin = (int(res['Item']['Stock']) if 'Item' in res else 0) + c_ab
                tabla_stock.put_item(Item={'Producto': p_ab, 'Stock': s_fin, 'Precio': str(pr_ab)})
                f, h, _ = obtener_tiempo_peru()
                tabla_auditoria.put_item(Item={'ID_Ingreso': f"IN-{f.replace('/','')}-{h.replace(':','')}", 'Fecha': f, 'Hora': h, 'Producto': p_ab, 'Cantidad_Entrante': int(c_ab), 'Stock_Resultante': int(s_fin), 'Precio_Fijado': str(pr_ab)})
                st.success("OK"); st.rerun()
