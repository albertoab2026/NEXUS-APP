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

def cargar_datos_aws():
    try:
        respuesta = tabla.scan()
        items = respuesta.get('Items', [])
        df = pd.DataFrame(items)
        if not items: return pd.DataFrame()
        df["Stock_Actual"] = pd.to_numeric(df["Stock_Actual"])
        df["Precio_Venta"] = pd.to_numeric(df["Precio_Venta"])
        return df.sort_values(by="ID_Producto").reset_index(drop=True)
    except: return pd.DataFrame()

# Inicializar sesión
if 'df_memoria' not in st.session_state: st.session_state.df_memoria = cargar_datos_aws()
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'ventas_dia' not in st.session_state: st.session_state.ventas_dia = []

# --- 3. TABLA DE STOCK ---
st.subheader("📋 Inventario Real en Nube")
df_vis = st.session_state.df_memoria.copy()
if not df_vis.empty:
    df_vis['Stock_Actual'] = df_vis['Stock_Actual'].astype(int)
    df_vis['Precio_Venta'] = df_vis['Precio_Venta'].map('S/ {:,.2f}'.format)
    st.table(df_vis)

# --- 4. VENTA (SIEMPRE REAL) ---
st.divider()
st.subheader("🛒 Registrar Nueva Venta")
c1, c2 = st.columns(2)
with c1:
    prod_sel = st.selectbox("Producto:", sorted(st.session_state.df_memoria["Producto"].tolist()))
with c2:
    cant_sel = st.number_input("Cantidad:", min_value=1, value=1)

if st.button("➕ Añadir al Carrito"):
    fila = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == prod_sel].iloc[0]
    if cant_sel > fila['Stock_Actual']:
        st.error("❌ No hay suficiente stock en Amazon.")
    else:
        st.session_state.carrito.append({"Producto": prod_sel, "Cant": cant_sel, "Subtotal": float(cant_sel * fila['Precio_Venta'])})
        st.success("Añadido.")

if st.session_state.carrito:
    df_c = pd.DataFrame(st.session_state.carrito)
    st.dataframe(df_c)
    if st.button("🚀 FINALIZAR VENTA Y DESCONTAR DE AWS"):
        for item in st.session_state.carrito:
            # AQUÍ DESCONTAMOS EN LA MEMORIA (Luego pondremos el código de AWS)
            st.session_state.df_memoria.loc[st.session_state.df_memoria['Producto'] == item['Producto'], 'Stock_Actual'] -= item['Cant']
        
        st.session_state.ventas_dia.append({"Hora": obtener_hora_peru(), "Total": df_c['Subtotal'].sum()})
        st.session_state.carrito = []
        st.balloons()
        st.rerun()

# --- 5. PANEL DE CONTROL (CON CONTRASEÑA) ---
st.divider()
with st.expander("🔐 PANEL DE ADMINISTRADOR (Solo Alberto y Tío)"):
    clave = st.text_input("Ingrese Clave para ver opciones:", type="password")
    
    if clave == "admin123":
        st.success("Acceso Concedido")
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("🗑️ BORRAR TODAS LAS VENTAS (Cerrar Caja)"):
                st.session_state.ventas_dia = []
                st.warning("Ventas del día borradas.")
        
        with col_b:
            st.write("Para recargar stock, usa la consola de AWS DynamoDB por ahora.")
    elif clave != "":
        st.error("Clave incorrecta")
