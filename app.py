import streamlit as st
import pandas as pd
import boto3
import time
from datetime import datetime, timedelta

# --- 1. CONEXIÓN CON AMAZON DYNAMODB ---
try:
    session = boto3.Session(
        aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
        aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
        region_name=st.secrets["aws"]["aws_region"]
    )
    dynamodb = session.resource('dynamodb')
    tabla = dynamodb.Table('Inventariodentaltio')
    tabla_ventas = dynamodb.Table('VentasDentaltio')
except Exception as e:
    st.error(f"Error de conexión con AWS: {e}")

# --- 2. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Inventario Dental Pro", layout="wide")

st.markdown("""
<style>
.titulo-seccion { font-size:30px !important; font-weight: bold; color: #00acc1; margin-bottom: 20px; }
[data-testid="stMetricValue"] { color: #00acc1 !important; font-size: 45px !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 SISTEMA DENTAL - ALBERTO BALLARTA</h1>", unsafe_allow_html=True)

def obtener_tiempo_peru():
    ahora = datetime.utcnow() - timedelta(hours=5)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S")

def cargar_datos_aws():
    try:
        respuesta = tabla.scan()
        items = respuesta.get('Items', [])
        if not items:
            return pd.DataFrame()
        df = pd.DataFrame(items)
        df["Stock_Actual"] = pd.to_numeric(df["Stock_Actual"])
        df["Precio_Venta"] = pd.to_numeric(df["Precio_Venta"])
        return df.sort_values(by="ID_Producto").reset_index(drop=True)
    except:
        return pd.DataFrame()

# --- ESTADOS ---
if 'df_memoria' not in st.session_state:
    st.session_state.df_memoria = cargar_datos_aws()
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# --- INVENTARIO ---
st.markdown("### 📋 Inventario en Tiempo Real")
df_vis = st.session_state.df_memoria.copy()

if not df_vis.empty:
    df_vis['Stock_Actual'] = df_vis['Stock_Actual'].astype(int)
    df_vis['Precio_Venta'] = df_vis['Precio_Venta'].map('S/ {:,.2f}'.format)
    st.table(df_vis[['ID_Producto', 'Producto', 'Stock_Actual', 'Precio_Venta']])

# --- VENTA ---
st.markdown("### 🛒 Venta")

lista_prods = st.session_state.df_memoria["Producto"].tolist()
prod_sel = st.selectbox("Producto", lista_prods)

fila_prod = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == prod_sel].iloc[0]

stock_real = int(fila_prod['Stock_Actual'])
en_carrito = sum(item['cantidad'] for item in st.session_state.carrito if item['nombre'] == prod_sel)

cant_sel = st.number_input(f"Cantidad (Disponible: {stock_real - en_carrito})", min_value=1, value=1)

if st.button("➕ Agregar"):
    if cant_sel > (stock_real - en_carrito):
        st.warning("Sin stock suficiente")
    else:
        st.session_state.carrito.append({
            "id": fila_prod["ID_Producto"],
            "nombre": prod_sel,
            "cantidad": cant_sel,
            "precio": float(fila_prod['Precio_Venta'])
        })
        st.rerun()

# --- CARRITO ---
if st.session_state.carrito:
    df_c = pd.DataFrame(st.session_state.carrito)
    df_c["Subtotal"] = df_c["cantidad"] * df_c["precio"]

    total = df_c["Subtotal"].sum()

    st.write("### 🧾 Carrito")
    st.dataframe(df_c)

    st.metric("Total", f"S/ {total:.2f}")

    metodo = st.radio("Pago", ["Efectivo", "Yape", "Plin"])

    if st.button("🚀 FINALIZAR VENTA"):
        fecha, hora = obtener_tiempo_peru()

        try:
            # Guardar venta
            tabla_ventas.put_item(Item={
                "ID_Venta": str(time.time()),
                "Fecha": fecha,
                "Hora": hora,
                "Total": float(total),
                "Metodo": metodo,
                "Productos": st.session_state.carrito
            })

            # Descontar stock
            for item in st.session_state.carrito:
                tabla.update_item(
                    Key={'ID_Producto': item['id']},
                    UpdateExpression="SET Stock_Actual = Stock_Actual - :c",
                    ExpressionAttributeValues={":c": item['cantidad']}
                )

            st.success("✅ Venta guardada")

            st.session_state.carrito = []
            st.session_state.df_memoria = cargar_datos_aws()

            st.balloons()
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")
