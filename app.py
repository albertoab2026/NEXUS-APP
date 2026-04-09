import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
import io

# 1. CONFIGURACIÓN
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
    
    tabla_ventas = dynamodb.Table('VentasDentaltio')
    tabla_stock = dynamodb.Table('StockProductos')
    tabla_ingresos = dynamodb.Table('EntradasInventario')
except Exception as e:
    st.error(f"Error de conexión AWS: {e}")
    st.stop()

# 3. LÓGICA DEL CARRITO (Session State)
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# CARGAR STOCK
try:
    items = tabla_stock.scan().get('Items', [])
    df_stock = pd.DataFrame(items) if items else pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])
except:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

st.title("🦷 Sistema Dental: Punto de Venta")

# --- SECCIÓN A: STOCK ---
with st.expander("Ver Inventario Actual"):
    if not df_stock.empty:
        df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
        st.dataframe(df_stock[['Producto', 'Stock', 'Precio']], use_container_width=True, hide_index=True)

st.divider()

# --- SECCIÓN B: CARRITO DE COMPRAS ---
st.subheader("🛒 Carrito de Compras")

col_sel, col_cant, col_btn = st.columns([3, 1, 1])

if not df_stock.empty:
    with col_sel:
        prod_sel = st.selectbox("Producto:", df_stock['Producto'].tolist())
    with col_cant:
        cant_sel = st.number_input("Cant:", min_value=1, value=1)
    with col_btn:
        st.write("##") # Espaciador
        if st.button("➕ Añadir"):
            precio = float(df_stock.loc[df_stock['Producto'] == prod_sel, 'Precio'].values[0])
            st.session_state.carrito.append({
                'Producto': prod_sel,
                'Cantidad': cant_sel,
                'Precio': precio,
                'Subtotal': round(precio * cant_sel, 2)
            })

# MOSTRAR TABLA DEL CARRITO
if st.session_state.carrito:
    df_car = pd.DataFrame(st.session_state.carrito)
    st.table(df_car)
    total_car = df_car['Subtotal'].sum()
    st.markdown(f"### **TOTAL A COBRAR: S/ {total_car:.2f}**")
    
    c_v1, c_v2 = st.columns(2)
    with c_v1:
        v_metodo = st.radio("Método de Pago:", ["Yape", "Plin", "Efectivo"], horizontal=True)
    with c_v2:
        st.write("##")
        if st.button("🗑️ VACÍAR CARRITO", type="secondary"):
            st.session_state.carrito = []
            st.rerun()

    # BOTÓN FINALIZAR COMPRA
    if st.button("✅ FINALIZAR COMPRA Y DESCONTAR STOCK", type="primary", use_container_width=True):
        try:
            with st.spinner("Procesando venta..."):
                fecha, hora = obtener_tiempo_peru()
                
                for item in st.session_state.carrito:
                    # 1. Obtener Stock actual de AWS
                    res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                    stock_aws = int(res['Item']['Stock'])
                    
                    # 2. Descontar
                    nuevo_stock = stock_aws - item['Cantidad']
                    tabla_stock.update_item(
                        Key={'Producto': item['Producto']},
                        UpdateExpression="set Stock = :s",
                        ExpressionAttributeValues={':s': nuevo_stock}
                    )
                    
                    # 3. Registrar cada item en Ventas
                    id_v = f"V-{fecha.replace('/','')}-{hora.replace(':','')}-{item['Producto'][:3]}"
                    tabla_ventas.put_item(Item={
                        'ID_Venta': id_v,
                        'Fecha': fecha,
                        'Hora': hora,
                        'Producto': item['Producto'],
                        'Cantidad': int(item['Cantidad']),
                        'Total': str(item['Subtotal']),
                        'Metodo': v_metodo
                    })
                
                st.balloons()
                st.success(f"¡Venta de S/ {total_car:.2f} completada con éxito!")
                st.session_state.carrito = [] # Limpiar carrito
                time.sleep(2)
                st.rerun()
        except Exception as e:
            st.error(f"Error al procesar: {e}")
else:
    st.info("El carrito está vacío.")

# --- SECCIÓN C: ADMIN ---
st.write("##")
st.divider()
with st.expander("🔐 PANEL ADMIN (Reportes y Excel)"):
    password = st.text_input("Clave:", type="password")
    if password == admin_pass:
        t1, t2 = st.tabs(["📦 Gestión Stock", "📄 Reportes"])
        
        with t1:
            with st.form("add_p"):
                f_p = st.text_input("Nombre Producto")
                f_s = st.number_input("Stock", min_value=0)
                f_pr = st.number_input("Precio", min_value=0.0)
                if st.form_submit_button("Guardar"):
                    tabla_stock.put_item(Item={'Producto': f_p, 'Stock': int(f_s), 'Precio': str(f_pr)})
                    st.success("Guardado")
                    st.rerun()
        
        with t2:
            if st.button("Generar Excel de Hoy"):
                fecha_hoy, _ = obtener_tiempo_peru()
                ventas = tabla_ventas.scan().get('Items', [])
                df_hoy = pd.DataFrame([v for v in ventas if v['Fecha'] == fecha_hoy])
                
                if not df_hoy.empty:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_hoy.to_excel(writer, index=False)
                    st.download_button("📥 Descargar Excel", output.getvalue(), f"Ventas_{fecha_hoy}.xlsx")
                else:
                    st.warning("No hay ventas hoy.")
