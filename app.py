import streamlit as st
import pandas as pd
import boto3
import time
import io
from datetime import datetime
import pytz

# 1. CONFIGURACIÓN Y TIEMPO PERÚ
st.set_page_config(page_title="Inventario Dental Tío", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S")

# 2. CONEXIÓN A AWS (Secretos)
try:
    aws_id = st.secrets["aws"]["aws_access_key_id"]
    aws_key = st.secrets["aws"]["aws_secret_access_key"]
    aws_region = st.secrets["aws"]["aws_region"]
    admin_pass = st.secrets["auth"]["admin_password"]
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    tabla_ventas = dynamodb.Table('VentasInventario')
    tabla_ingresos = dynamodb.Table('EntradasInventario')
except Exception as e:
    st.error(f"Error de configuración en AWS: {e}")
    st.stop()

# 3. CARGA DE DATOS LOCALES (CSV)
@st.cache_data
def cargar_datos():
    try:
        df = pd.read_csv("inventario.csv")
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame(columns=['Producto', 'Precio_Venta', 'Stock'])

df = cargar_datos()

# --- DETECCIÓN DINÁMICA DE COLUMNAS ---
# Esto evita el error de "IndexError" si las columnas cambian de nombre
try:
    col_prod_list = [c for c in df.columns if 'producto' in c.lower()][0]
    col_precio_list = [c for c in df.columns if 'precio' in c.lower()][0]
except IndexError:
    st.error("Error: No se encontraron las columnas 'Producto' o 'Precio' en el CSV.")
    st.stop()

# --- INTERFAZ DE USUARIO ---
st.title("🦷 Suministros Dentales")

# SECCIÓN A: STOCK ACTUAL
st.subheader("📦 Stock Disponible")
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

# SECCIÓN B: REGISTRO DE VENTAS
st.subheader("🛒 Realizar Venta")
col1, col2 = st.columns(2)

with col1:
    v_prod = st.selectbox("Selecciona producto:", df[col_prod_list].tolist(), key="v_prod")
    v_cant = st.number_input("Cantidad:", min_value=1, value=1, key="v_cant")
with col2:
    v_metodo = st.radio("Método de Pago:", ["Yape", "Plin", "Efectivo"], horizontal=True)

if st.button("Confirmar Venta 🚀"):
    try:
        fecha, hora = obtener_tiempo_peru()
        id_v = f"V-{fecha.replace('/', '')}-{hora.replace(':', '')}"
        
        # Obtener precio para el total
        precio_unit = df.loc[df[col_prod_list] == v_prod, col_precio_list].values[0]
        total_venta = float(precio_unit) * v_cant
        
        # GUARDAR EN AWS
        tabla_ventas.put_item(Item={
            'ID_Venta': id_v,
            'Fecha': fecha,
            'Hora': hora,
            'Producto': v_prod,
            'Cantidad': int(v_cant),
            'Metodo': v_metodo,
            'Total': str(total_venta)
        })
        
        st.balloons()
        st.success(f"✅ Venta registrada: {v_prod} x{v_cant}. Total: S/ {total_venta:.2f}")
        st.info(f"Cobrar mediante {v_metodo}")
    except Exception as e:
        st.error(f"Error al guardar venta en AWS: {e}")

# SECCIÓN C: PANEL DE ADMINISTRADOR
st.write("##")
st.divider()

with st.expander("🔐 ACCESO ADMINISTRADOR"):
    password = st.text_input("Contraseña:", type="password")
    
    if password == admin_pass:
        st.success("Panel de Gestión Activado")
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("📥 Abastecer Stock")
            p_add = st.selectbox("Producto:", df[col_prod_list].tolist(), key="p_add")
            q_add = st.number_input("Cantidad a ingresar:", min_value=1, value=1)
            
            if st.button("Actualizar Stock en AWS"):
                try:
                    fecha, hora = obtener_tiempo_peru()
                    id_i = f"I-{fecha.replace('/', '')}-{hora.replace(':', '')}"
                    
                    tabla_ingresos.put_item(Item={
                        'ID_Ingreso': id_i,
                        'Fecha': fecha,
                        'Hora': hora,
                        'Producto': p_add,
                        'Cantidad': int(q_add)
                    })
                    st.success("¡Ingreso guardado en AWS!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error en AWS: {e}")

        with c2:
            st.subheader("📜 Historial de Ingresos")
            if st.button("Ver Ingresos"):
                try:
                    items = tabla_ingresos.scan().get("Items", [])
                    if items:
                        st.dataframe(pd.DataFrame(items), hide_index=True)
                    else:
                        st.info("Sin registros aún.")
                except: st.error("Error al conectar con AWS")
        
        st.divider()
        
        # REPORTE DE CIERRE
        st.subheader("💰 Cierre de Caja")
        if st.button("🔄 GENERAR REPORTE DE HOY"):
            try:
                fecha_hoy, _ = obtener_tiempo_peru()
                ventas = tabla_ventas.scan().get("Items", [])
                ventas_hoy = [v for v in ventas if v['Fecha'] == fecha_hoy]
                
                if ventas_hoy:
                    total = sum([float(v['Total']) for v in ventas_hoy])
                    st.metric("RECAUDADO HOY", f"S/ {total:.2f}")
                    st.table(pd.DataFrame(ventas_hoy)[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']])
                else:
                    st.warning("No hay ventas hoy.")
            except: st.error("Error al generar reporte")

        if st.button("Cerrar Sesión"):
            st.rerun()
