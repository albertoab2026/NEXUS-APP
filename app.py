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
st.markdown("""
    <style>
    .titulo-seccion { font-size:30px !important; font-weight: bold; color: #00acc1; margin-bottom: 20px; }
    [data-testid="stMetricValue"] { color: #00acc1 !important; font-size: 45px !important; }
    [data-testid="stMetricLabel"] { color: grey !important; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 SISTEMA DENTAL - ALBERTO BALLARTA</h1>", unsafe_allow_html=True)

def obtener_hora_peru():
    return (datetime.utcnow() - timedelta(hours=5)).strftime("%H:%M:%S")

def cargar_datos_aws():
    try:
        respuesta = tabla.scan()
        items = respuesta.get('Items', [])
        if not items: return pd.DataFrame()
        df = pd.DataFrame(items)
        df["Stock_Actual"] = pd.to_numeric(df["Stock_Actual"])
        df["Precio_Venta"] = pd.to_numeric(df["Precio_Venta"])
        return df.sort_values(by="ID_Producto").reset_index(drop=True)
    except: return pd.DataFrame()

if 'df_memoria' not in st.session_state: st.session_state.df_memoria = cargar_datos_aws()
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'ventas_dia' not in st.session_state: st.session_state.ventas_dia = []

# --- 3. TABLA DE STOCK ---
st.markdown("<p class='titulo-seccion'>📋 Inventario en Tiempo Real (AWS)</p>", unsafe_allow_html=True)
df_vis = st.session_state.df_memoria.copy()
if not df_vis.empty:
    df_vis['Stock_Actual'] = df_vis['Stock_Actual'].astype(int)
    df_vis['Precio_Venta'] = df_vis['Precio_Venta'].map('S/ {:,.2f}'.format)
    st.table(df_vis)

# --- 4. REGISTRAR VENTA ---
st.divider()
st.markdown("<p class='titulo-seccion'>🛒 Armar Pedido</p>", unsafe_allow_html=True)
c1, c2 = st.columns(2)

with c1:
    lista_prods = sorted(st.session_state.df_memoria["Producto"].tolist())
    prod_sel = st.selectbox("Selecciona Producto:", lista_prods)

with c2:
    fila_prod = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == prod_sel].iloc[0]
    stock_real = int(fila_prod['Stock_Actual'])
    en_carrito = sum(item['Cant'] for item in st.session_state.carrito if item['Producto'] == prod_sel)
    disponible_ahora = stock_real - en_carrito
    cant_sel = st.number_input(f"Cantidad (Disponible: {disponible_ahora}):", min_value=1, value=1)

if st.button("➕ AGREGAR AL CARRITO", use_container_width=True):
    if cant_sel > disponible_ahora:
        st.warning(f"⚠️ No se puede agregar: Solo quedan {disponible_ahora} unidades.")
    else:
        precio = float(fila_prod['Precio_Venta'])
        st.session_state.carrito.append({"Producto": prod_sel, "Cant": cant_sel, "Subtotal": cant_sel * precio})
        st.rerun()

# --- 5. CARRITO Y COBRO ---
if st.session_state.carrito:
    st.divider()
    st.markdown("<p class='titulo-seccion'>📝 Resumen de Cobro</p>", unsafe_allow_html=True)
    
    df_c = pd.DataFrame(st.session_state.carrito)
    total_venta = df_c['Subtotal'].sum()
    st.metric(label="TOTAL NETO A COBRAR", value=f"S/ {total_venta:,.2f}")

    df_c_vista = df_c.copy()
    df_c_vista['Subtotal'] = df_c_vista['Subtotal'].map('S/ {:,.2f}'.format)
    st.dataframe(df_c_vista, use_container_width=True, hide_index=True)
    
    col_v1, col_v2, col_v3 = st.columns(3)
    with col_v1:
        metodo_pago = st.radio("Medio de Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)
        if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
            for item in st.session_state.carrito:
                st.session_state.df_memoria.loc[st.session_state.df_memoria['Producto'] == item['Producto'], 'Stock_Actual'] -= item['Cant']
            st.session_state.ventas_dia.append({"Hora": obtener_hora_peru(), "Total": total_venta, "Pago": metodo_pago})
            st.session_state.carrito = []
            st.balloons()
            st.rerun()
    with col_v2:
        st.write("")
        st.write("")
        if st.button("⬅️ BORRAR ÚLTIMO", use_container_width=True):
            st.session_state.carrito.pop() # Borra el último elemento
            st.rerun()
    with col_v3:
        st.write("")
        st.write("")
        if st.button("🗑️ CANCELAR TODO", use_container_width=True):
            st.session_state.carrito = []
            st.rerun()

# --- 6. PANEL DE ADMINISTRADOR ---
st.divider()
with st.expander("🔐 PANEL DE ADMINISTRADOR"):
    clave = st.text_input("Contraseña:", type="password")
    if clave == "admin123":
        if st.session_state.ventas_dia:
            df_recaudacion = pd.DataFrame(st.session_state.ventas_dia)
            st.success(f"### 💰 CAJA TOTAL: S/ {df_recaudacion['Total'].sum():,.2f}")
            st.table(df_recaudacion)
            if st.button("Limpiar Caja"):
                st.session_state.ventas_dia = []
                st.rerun()
        else:
            st.info("Caja vacía.")
