import streamlit as st
import pandas as pd
import boto3
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
except Exception as e:
    st.error(f"Error de conexión con AWS: {e}")

# --- 2. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Inventario Dental Pro", layout="wide")
st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 SISTEMA DENTAL - ALBERTO BALLARTA</h1>", unsafe_allow_html=True)

def obtener_hora_peru():
    return (datetime.utcnow() - timedelta(hours=5)).strftime("%H:%M:%S")

# --- 3. FUNCIÓN PARA TRAER DATOS REALES ---
def cargar_datos_aws():
    try:
        respuesta = tabla.scan()
        items = respuesta.get('Items', [])
        if not items:
            return pd.DataFrame({
                "Producto": ["Esperando datos de AWS..."],
                "Stock_Actual": [0],
                "Precio_Venta": [0.0]
            })
        df = pd.DataFrame(items)
        df["Stock_Actual"] = pd.to_numeric(df["Stock_Actual"])
        df["Precio_Venta"] = pd.to_numeric(df["Precio_Venta"])
        return df
    except Exception as e:
        st.error(f"Error al leer la tabla: {e}")
        return pd.DataFrame()

# Inicializar sesión
if 'df_memoria' not in st.session_state:
    st.session_state.df_memoria = cargar_datos_aws()
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'ventas_dia' not in st.session_state: st.session_state.ventas_dia = []

# --- 4. MOSTRAR TABLA DE STOCK (FORMATEADA) ---
st.subheader("📋 Control de Stock Actual (Desde Amazon AWS)")

# Creamos una copia para aplicar el formato de Soles sin malograr los números originales
df_vis = st.session_state.df_memoria.copy()

if 'Precio_Venta' in df_vis.columns:
    # Aseguramos que sea número y aplicamos el formato S/ con 2 decimales
    df_vis['Precio_Venta'] = pd.to_numeric(df_vis['Precio_Venta']).map('S/ {:,.2f}'.format)

st.table(df_vis)
st.divider()

# --- 5. ARMAR PEDIDO DEL CLIENTE ---
st.subheader("🛒 Armar Pedido del Cliente")
if not st.session_state.df_memoria.empty and "Producto" in st.session_state.df_memoria.columns:
    c1, c2 = st.columns(2)
    with c1:
        lista_productos = st.session_state.df_memoria["Producto"].tolist()
        prod_sel = st.selectbox("Selecciona Producto:", lista_productos)
    with c2:
        if "contador_reset" not in st.session_state: st.session_state.contador_reset = 0
        cant_sel = st.number_input("Cantidad:", min_value=1, value=1, key=f"input_cant_{st.session_state.contador_reset}")

    if st.button("➕ Agregar al Carrito", type="primary"):
        idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == prod_sel].index[0]
        ya_en_carrito = sum(item['Cant'] for item in st.session_state.carrito if item['Producto'] == prod_sel)
        stock_disponible = st.session_state.df_memoria.at[idx, 'Stock_Actual'] - ya_en_carrito
        
        if cant_sel > stock_disponible:
            st.error(f"❌ Stock insuficiente. Quedan {stock_disponible}.")
        else:
            precio = st.session_state.df_memoria.at[idx, 'Precio_Venta']
            st.session_state.carrito.append({"Producto": prod_sel, "Cant": cant_sel, "Subtotal": float(cant_sel * precio)})
            st.success(f"✅ {prod_sel} añadido.")
            st.session_state.contador_reset += 1
            st.rerun()

# --- 6. FINALIZAR VENTA ---
if st.session_state.carrito:
    st.divider()
    st.subheader("📝 VENTA ACTUAL")
    df_car = pd.DataFrame(st.session_state.carrito)
    df_car_v = df_car.copy()
    df_car_v['Subtotal'] = df_car_v['Subtotal'].map('S/ {:,.2f}'.format)
    st.dataframe(df_car_v, use_container_width=True, hide_index=True)
    
    total_ped = df_car['Subtotal'].sum()
    st.info(f"### TOTAL A COBRAR: S/ {total_ped:,.2f}")
    metodo = st.selectbox("Pago:", ["Efectivo", "Yape", "Plin"])

    if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
        for item in st.session_state.carrito:
            idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == item['Producto']].index[0]
            st.session_state.df_memoria.at[idx, 'Stock_Actual'] -= item['Cant']
        
        st.session_state.ventas_dia.append({
            "Venta N°": len(st.session_state.ventas_dia) + 1,
            "Hora": obtener_hora_peru(),
            "Detalle": ", ".join([f"{item['Cant']}x {item['Producto']}" for item in st.session_state.carrito]),
            "Total": total_ped,
            "Pago": metodo
        })
        st.session_state.carrito = []
        st.balloons()
        st.rerun()

# --- 7. RECAUDACIÓN ---
st.divider()
if st.button("💰 MOSTRAR RECAUDACIÓN DEL DÍA", use_container_width=True):
    if st.session_state.ventas_dia:
        df_v = pd.DataFrame(st.session_state.ventas_dia)
        st.success(f"## GANANCIA TOTAL HOY: S/ {df_v['Total'].sum():,.2f}")
        df_v_v = df_v.copy()
        df_v_v['Total'] = df_v_v['Total'].map('S/ {:,.2f}'.format)
        st.dataframe(df_v_v, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay ventas hoy.")
