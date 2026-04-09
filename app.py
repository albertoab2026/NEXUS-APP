import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Gestión Dental Tío - PRO", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S")

# 2. CONEXIÓN AWS CON TUS TABLAS REALES
try:
    aws_id = st.secrets["aws"]["aws_access_key_id"]
    aws_key = st.secrets["aws"]["aws_secret_access_key"]
    aws_region = st.secrets["aws"]["aws_region"]
    admin_pass = st.secrets["auth"]["admin_password"]
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    # NOMBRES CORREGIDOS SEGÚN TU FOTO image_6301a7.png
    tabla_ventas = dynamodb.Table('VentasDentaltio')
    tabla_stock = dynamodb.Table('StockProductos')
    tabla_ingresos = dynamodb.Table('EntradasInventario')
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

st.title("🦷 Sistema de Ventas e Inventario")

# 3. CARGAR STOCK DESDE AWS
try:
    items = tabla_stock.scan().get('Items', [])
    df_stock = pd.DataFrame(items) if items else pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])
except:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

# A. VISTA DE INVENTARIO
st.subheader("📦 Stock Actual en la Nube")
if not df_stock.empty:
    # Aseguramos que los números se vean bien
    df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
    st.dataframe(df_stock[['Producto', 'Stock', 'Precio']], use_container_width=True, hide_index=True)
else:
    st.info("La base de datos está vacía. Agregue productos en el Panel Admin.")

st.divider()

# B. REGISTRO DE VENTAS (DESCUENTO AUTOMÁTICO)
st.subheader("🛒 Realizar Venta")
if not df_stock.empty:
    c1, c2 = st.columns(2)
    with c1:
        v_prod = st.selectbox("Producto a vender:", df_stock['Producto'].tolist())
        v_cant = st.number_input("Cantidad:", min_value=1, value=1)
    with c2:
        v_metodo = st.radio("Método de Pago:", ["Yape", "Plin", "Efectivo"], horizontal=True)

    if st.button("Finalizar Venta 💰"):
        try:
            # Sacamos el stock y precio actual
            prod_data = tabla_stock.get_item(Key={'Producto': v_prod}).get('Item')
            stock_actual = int(prod_data['Stock'])
            precio = float(prod_data['Precio'])

            if stock_actual >= v_cant:
                nuevo_stock = stock_actual - v_cant
                fecha, hora = obtener_tiempo_peru()
                # Usamos ID_Venta como pide tu tabla
                id_v = f"V-{fecha.replace('/','')}-{hora.replace(':','')}"

                # 1. ACTUALIZAR STOCK EN AWS
                tabla_stock.update_item(
                    Key={'Producto': v_prod},
                    UpdateExpression="set Stock = :s",
                    ExpressionAttributeValues={':s': nuevo_stock}
                )

                # 2. GUARDAR VENTA EN AWS
                tabla_ventas.put_item(Item={
                    'ID_Venta': id_v,
                    'Fecha': fecha,
                    'Hora': hora,
                    'Producto': v_prod,
                    'Cantidad': int(v_cant),
                    'Total': str(round(precio * v_cant, 2)),
                    'Metodo': v_metodo
                })

                st.balloons()
                st.success(f"✅ Venta confirmada. Stock restante: {nuevo_stock}")
                time.sleep(2)
                st.rerun()
            else:
                st.error(f"Stock insuficiente. Solo quedan {stock_actual} unidades.")
        except Exception as e:
            st.error(f"Error técnico: {e}")

# C. PANEL ADMINISTRADOR
st.write("##")
with st.expander("🔐 PANEL DE CONTROL (ADMIN)"):
    password = st.text_input("Contraseña de acceso:", type="password")
    if password == admin_pass:
        st.subheader("Cargar o Editar Productos")
        with st.form("admin_form"):
            f_prod = st.text_input("Nombre del Producto (Ej: Resina Z350)")
            f_stock = st.number_input("Stock Inicial", min_value=0)
            f_precio = st.number_input("Precio de Venta (S/)", min_value=0.0)
            if st.form_submit_button("Guardar en AWS"):
                tabla_stock.put_item(Item={
                    'Producto': f_prod, 
                    'Stock': int(f_stock), 
                    'Precio': str(f_precio)
                })
                st.success("Producto guardado.")
                st.rerun()
        
        st.divider()
        if st.button("🔄 Ver Reporte de Ventas de Hoy"):
            try:
                fecha_hoy, _ = obtener_tiempo_peru()
                todas = tabla_ventas.scan().get('Items', [])
                hoy = [v for v in todas if v['Fecha'] == fecha_hoy]
                if hoy:
                    df_hoy = pd.DataFrame(hoy)
                    total_dinero = sum(float(v['Total']) for v in hoy)
                    st.metric("RECAUDADO HOY", f"S/ {total_dinero:.2f}")
                    st.dataframe(df_hoy, hide_index=True)
                else:
                    st.info("No hay ventas registradas hoy.")
            except:
                st.error("Aún no hay datos de ventas.")
