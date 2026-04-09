import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time

# 1. CONFIGURACIÓN Y TIEMPO PERÚ
st.set_page_config(page_title="Gestión Dental Tío - PRO", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S")

# 2. CONEXIÓN AWS
try:
    aws_id = st.secrets["aws"]["aws_access_key_id"]
    aws_key = st.secrets["aws"]["aws_secret_access_key"]
    aws_region = st.secrets["aws"]["aws_region"]
    admin_pass = st.secrets["auth"]["admin_password"]
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    tabla_ventas = dynamodb.Table('VentasInventario')
    tabla_stock = dynamodb.Table('StockProductos') 
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# 3. INTERFAZ PRINCIPAL
st.title("🦷 Sistema de Ventas e Inventario")

# Cargar Stock desde AWS
try:
    res = tabla_stock.scan()
    items = res.get('Items', [])
    df_stock = pd.DataFrame(items) if items else pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])
except:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

# A. VISTA DE INVENTARIO
st.subheader("📦 Stock en la Nube")
if not df_stock.empty:
    # Convertir a numérico para ordenar bien
    df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
    st.dataframe(df_stock[['Producto', 'Stock', 'Precio']], use_container_width=True, hide_index=True)
else:
    st.info("La base de datos está vacía. Agregue productos en el Panel Admin.")

st.divider()

# B. REALIZAR VENTA (CON DESCUENTO REAL)
st.subheader("🛒 Registrar Nueva Venta")
if not df_stock.empty:
    c1, c2 = st.columns(2)
    with c1:
        v_prod = st.selectbox("Producto:", df_stock['Producto'].tolist())
        v_cant = st.number_input("Cantidad a vender:", min_value=1, value=1)
    with c2:
        v_metodo = st.radio("Pago:", ["Yape", "Plin", "Efectivo"], horizontal=True)

    if st.button("Finalizar Venta 💰"):
        try:
            # Obtener datos actuales
            prod_data = tabla_stock.get_item(Key={'Producto': v_prod}).get('Item')
            stock_actual = int(prod_data['Stock'])
            precio = float(prod_data['Precio'])

            if stock_actual >= v_cant:
                nuevo_stock = stock_actual - v_cant
                fecha, hora = obtener_tiempo_peru()
                id_v = f"V-{fecha.replace('/','')}-{hora.replace(':','')}"

                # 1. DESCONTAR EN AWS
                tabla_stock.update_item(
                    Key={'Producto': v_prod},
                    UpdateExpression="set Stock = :s",
                    ExpressionAttributeValues={':s': nuevo_stock}
                )

                # 2. REGISTRAR VENTA
                tabla_ventas.put_item(Item={
                    'ID_Venta': id_v,
                    'Fecha': fecha,
                    'Hora': hora,
                    'Producto': v_prod,
                    'Cantidad': v_cant,
                    'Total': str(round(precio * v_cant, 2)),
                    'Metodo': v_metodo
                })

                st.balloons()
                st.success(f"Venta registrada. Nuevo stock de {v_prod}: {nuevo_stock}")
                time.sleep(2)
                st.rerun()
            else:
                st.error(f"¡Error! Solo quedan {stock_actual} unidades.")
        except Exception as e:
            st.error(f"Error en la transacción: {e}")

# C. PANEL ADMINISTRADOR
st.write("##")
with st.expander("🔐 PANEL DE CONTROL (ADMIN)"):
    password = st.text_input("Contraseña:", type="password")
    if password == admin_pass:
        st.subheader("Cargar/Actualizar Productos")
        with st.form("form_admin"):
            f_prod = st.text_input("Nombre del Producto")
            f_stock = st.number_input("Stock Inicial", min_value=0)
            f_precio = st.number_input("Precio de Venta (S/)", min_value=0.0)
            if st.form_submit_button("Guardar en Nube"):
                tabla_stock.put_item(Item={
                    'Producto': f_prod, 
                    'Stock': int(f_stock), 
                    'Precio': str(f_precio)
                })
                st.success("Producto guardado correctamente.")
                st.rerun()
