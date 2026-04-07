import streamlit as st
import pandas as pd
import boto3
import time
import io
from datetime import datetime, timedelta
from decimal import Decimal

# --- 1. CONEXIÓN AWS ---
try:
    session = boto3.Session(
        aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
        aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
        region_name=st.secrets["aws"]["aws_region"]
    )
    dynamodb = session.resource('dynamodb')
    tabla_inventario = dynamodb.Table('Inventariodentaltio')
    tabla_ventas = dynamodb.Table('VentasDentaltio')
except Exception as e:
    st.error(f"Error AWS: {e}")

# --- 2. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Inventario Dental Pro", layout="wide")
st.markdown("""
    <style>
    .titulo-seccion { font-size:28px !important; font-weight: bold; color: #00acc1; margin-top: 20px; }
    .stButton>button { border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 CONTROL DE VENTAS - DYNAMODB</h1>", unsafe_allow_html=True)

# --- 3. FUNCIONES AUXILIARES ---
def obtener_tiempo_peru():
    ahora = datetime.utcnow() - timedelta(hours=5)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S")

def cargar_datos():
    try:
        data = tabla_inventario.scan()["Items"]
        df = pd.DataFrame(data)
        if not df.empty:
            df["Stock_Actual"] = pd.to_numeric(df["Stock_Actual"], errors='coerce').fillna(0).astype(int)
            df["Precio_Venta"] = pd.to_numeric(df["Precio_Venta"], errors='coerce').fillna(0)
            return df.sort_values(by="ID_Producto").reset_index(drop=True)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 4. ESTADO DE SESIÓN ---
if "df" not in st.session_state: st.session_state.df = cargar_datos()
if "carrito" not in st.session_state: st.session_state.carrito = []
if "admin_logueado" not in st.session_state: st.session_state.admin_logueado = False

# --- 5. MOSTRAR INVENTARIO (LO QUE HABÍA DESAPARECIDO) ---
st.markdown("<p class='titulo-seccion'>📋 Inventario Actual</p>", unsafe_allow_html=True)
df = st.session_state.df

if not df.empty:
    def resaltar_stock(row):
        return ['color: #ff1744; font-weight: bold' if row.Stock_Actual <= 5 else '' for _ in row]

    df_view = df.copy()
    df_view["Precio_Venta"] = df_view["Precio_Venta"].map("S/ {:.2f}".format)
    st.dataframe(df_view[['ID_Producto', 'Producto', 'Stock_Actual', 'Precio_Venta']].style.apply(resaltar_stock, axis=1), 
                 use_container_width=True, hide_index=True)
    
    if (df["Stock_Actual"] <= 5).any():
        st.warning("⚠️ Reponer productos resaltados en rojo.")

# --- 6. REGISTRO DE VENTA ---
st.divider()
st.markdown("<p class='titulo-seccion'>🛒 Nueva Venta</p>", unsafe_allow_html=True)

if not df.empty:
    c_sel, c_cant = st.columns([2, 1])
    with c_sel:
        prod_sel = st.selectbox("Elegir Producto:", sorted(df["Producto"].tolist()))
    with c_cant:
        fila = df[df["Producto"] == prod_sel].iloc[0]
        disp = int(fila["Stock_Actual"]) - sum(i["cantidad"] for i in st.session_state.carrito if i["nombre"] == prod_sel)
        cant = st.number_input(f"Cant. (Disp: {disp})", min_value=1, max_value=max(1, disp), value=1)

    if st.button("➕ AGREGAR AL CARRITO", use_container_width=True):
        if disp >= cant:
            st.session_state.carrito.append({
                "id": fila["ID_Producto"], "nombre": prod_sel, 
                "cantidad": int(cant), "precio": Decimal(str(fila["Precio_Venta"]))
            })
            st.rerun()

# --- 7. CARRITO Y GUARDADO EN NUBE ---
if st.session_state.carrito:
    st.divider()
    df_c = pd.DataFrame(st.session_state.carrito)
    total_v = sum(df_c["cantidad"] * df_c["precio"])
    st.table(df_c[["nombre", "cantidad"]])
    st.metric("TOTAL A COBRAR", f"S/ {float(total_v):.2f}")
    
    metodo = st.radio("Método de Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)

    if st.button("✅ FINALIZAR Y GUARDAR EN NUBE", type="primary", use_container_width=True):
        f, h = obtener_tiempo_peru()
        with st.spinner("Guardando en DynamoDB..."):
            try:
                # 1. Grabar Venta
                tabla_ventas.put_item(Item={
                    "ID_Venta": f"V-{int(time.time())}", "Fecha": f, "Hora": h, 
                    "Total": Decimal(str(total_v)), "Metodo": metodo, "Productos": st.session_state.carrito
                })
                # 2. Descontar Stock
                for item in st.session_state.carrito:
                    tabla_inventario.update_item(
                        Key={"ID_Producto": item["id"]},
                        UpdateExpression="SET Stock_Actual = Stock_Actual - :q",
                        ExpressionAttributeValues={":q": item["cantidad"]}
                    )
                st.success("✨ ¡Venta registrada exitosamente!")
                st.session_state.carrito = []
                st.session_state.df = cargar_datos()
                time.sleep(2)
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

# --- 8. PANEL DE CONTROL (PARA ABASTECER Y EXCEL) ---
st.divider()
with st.expander("🔐 PANEL DE ADMINISTRADOR"):
    if not st.session_state.admin_logueado:
        if st.text_input("Clave:", type="password") == "admin123":
            if st.button("Entrar"):
                st.session_state.admin_logueado = True
                st.rerun()
    else:
        if st.button("Cerrar Sesión Admin"):
            st.session_state.admin_logueado = False
            st.rerun()
            
        st.markdown("### 📦 Abastecer Stock")
        p_repo = st.selectbox("Producto:", df["Producto"].tolist())
        c_repo = st.number_input("Cantidad nueva:", min_value=1, value=10)
        if st.button("Cargar Inventario"):
            id_p = df[df["Producto"] == p_repo].iloc[0]["ID_Producto"]
            tabla_inventario.update_item(Key={"ID_Producto": id_p}, UpdateExpression="SET Stock_Actual = Stock_Actual + :q", ExpressionAttributeValues={":q": int(c_repo)})
            st.session_state.df = cargar_datos()
            st.success("Stock actualizado.")
            st.rerun()

        st.divider()
        st.markdown("### 📊 Reportes Excel")
        # Aquí puedes poner el código del Excel Pro que te pasé antes
