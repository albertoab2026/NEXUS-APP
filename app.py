import streamlit as st
import pandas as pd
import boto3
import time
import io
from datetime import datetime, timedelta
from decimal import Decimal

# --- 1. CONEXIÓN AWS (Configurada en st.secrets) ---
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
    st.error(f"Error de conexión AWS: {e}")

# --- 2. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="Inventario Dental Pro", layout="wide")

st.markdown("""
    <style>
    .titulo-seccion { font-size:28px !important; font-weight: bold; color: #00acc1; margin-top: 20px; }
    [data-testid="stMetricValue"] { color: #00acc1 !important; font-size: 40px !important; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 SISTEMA DENTAL - ALBERTO BALLARTA</h1>", unsafe_allow_html=True)

# --- 3. FUNCIONES ---
def obtener_tiempo_peru():
    ahora = datetime.utcnow() - timedelta(hours=5)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S")

def cargar_datos():
    try:
        data = tabla_inventario.scan()["Items"]
        df = pd.DataFrame(data)
        if not df.empty:
            df["Stock_Actual"] = pd.to_numeric(df["Stock_Actual"])
            df["Precio_Venta"] = pd.to_numeric(df["Precio_Venta"])
            return df.sort_values(by="ID_Producto").reset_index(drop=True)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 4. ESTADO DE SESIÓN ---
if "df" not in st.session_state:
    st.session_state.df = cargar_datos()

if "carrito" not in st.session_state:
    st.session_state.carrito = []

if "admin_autenticado" not in st.session_state:
    st.session_state.admin_autenticado = False

# --- 5. TABLA DE INVENTARIO ---
st.markdown("<p class='titulo-seccion'>📋 Inventario en la Nube</p>", unsafe_allow_html=True)
df = st.session_state.df

if not df.empty:
    df_view = df.copy()
    df_view["Precio_Venta"] = df_view["Precio_Venta"].map("S/ {:.2f}".format)
    st.table(df_view[['ID_Producto', 'Producto', 'Stock_Actual', 'Precio_Venta']])
else:
    st.info("Cargando datos o inventario vacío...")

# --- 6. REGISTRO DE VENTA (ESTA SECCIÓN YA NO SE ESCONDE) ---
st.divider()
st.markdown("<p class='titulo-seccion'>🛒 Registrar Nueva Venta</p>", unsafe_allow_html=True)

if not df.empty:
    col_sel, col_cant = st.columns([2, 1])
    
    with col_sel:
        lista_nombres = sorted(df["Producto"].tolist())
        producto_sel = st.selectbox("Selecciona Producto:", lista_nombres)
    
    with col_cant:
        fila = df[df["Producto"] == producto_sel].iloc[0]
        stock_real = int(fila["Stock_Actual"])
        
        # Calcular cuánto queda quitando lo que ya está en el carrito
        en_carro = sum(item["cantidad"] for item in st.session_state.carrito if item["nombre"] == producto_sel)
        disponible = stock_real - en_carro
        
        cantidad = st.number_input(f"Cantidad (Disponible: {disponible})", min_value=1, max_value=max(1, disponible), value=1)

    if st.button("➕ AGREGAR AL PEDIDO", use_container_width=True):
        if disponible <= 0:
            st.warning("⚠️ No hay suficiente stock disponible.")
        else:
            st.session_state.carrito.append({
                "id": fila["ID_Producto"],
                "nombre": producto_sel,
                "cantidad": int(cantidad),
                "precio": Decimal(str(fila["Precio_Venta"]))
            })
            st.rerun()

# --- 7. RESUMEN DEL CARRITO Y COBRO ---
if st.session_state.carrito:
    st.divider()
    st.markdown("<p class='titulo-seccion'>📝 Resumen de la Venta</p>", unsafe_allow_html=True)
    
    df_c = pd.DataFrame(st.session_state.carrito)
    df_c["Subtotal"] = df_c["cantidad"] * df_c["precio"]
    total_neto = df_c["Subtotal"].sum()

    st.table(df_c[['nombre', 'cantidad', 'precio', 'Subtotal']])
    st.metric("TOTAL A PAGAR", f"S/ {float(total_neto):.2f}")

    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        metodo = st.radio("Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)
    with col_btn2:
        if st.button("⬅️ Borrar Último", use_container_width=True):
            st.session_state.carrito.pop()
            st.rerun()
    with col_btn3:
        if st.button("🗑️ Vaciar Todo", use_container_width=True):
            st.session_state.carrito = []
            st.rerun()

    if st.button("🚀 FINALIZAR VENTA (GUARDAR EN AWS)", type="primary", use_container_width=True):
        f_v, h_v = obtener_tiempo_peru()
        try:
            # 1. Guardar en Tabla Ventas
            tabla_ventas.put_item(Item={
                "ID_Venta": f"V-{int(time.time())}",
                "Fecha": f_v,
                "Hora": h_v,
                "Total": Decimal(str(total_neto)),
                "Metodo": metodo,
                "Productos": st.session_state.carrito
            })

            # 2. Descontar Stock en Tabla Inventario
            for item in st.session_state.carrito:
                tabla_inventario.update_item(
                    Key={"ID_Producto": item["id"]},
                    UpdateExpression="SET Stock_Actual = Stock_Actual - :qty",
                    ExpressionAttributeValues={":qty": item["cantidad"]}
                )

            st.balloons()
            st.success("✅ Venta procesada y guardada en la nube.")
            st.session_state.carrito = []
            st.session_state.df = cargar_datos() # Actualiza la tabla de arriba
            time.sleep(2)
            st.rerun()
        except Exception as err:
            st.error(f"Error al procesar: {err}")

# --- 8. PANEL ADMIN ---
st.divider()
with st.expander("🔐 PANEL DE ADMINISTRADOR"):
    if not st.session_state.admin_autenticado:
        pass_in = st.text_input("Clave:", type="password")
        if pass_in == "admin123":
            st.session_state.admin_autenticado = True
            st.rerun()
    else:
        try:
            ventas_data = tabla_ventas.scan()["Items"]
            if ventas_data:
                df_hist = pd.DataFrame(ventas_data)
                df_hist["Total"] = df_hist["Total"].apply(float)
                st.write(f"**Ventas totales:** S/ {df_hist['Total'].sum():.2f}")
                st.dataframe(df_hist[['Fecha', 'Hora', 'Total', 'Metodo']], use_container_width=True)
                
                # Exportar Excel
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                    df_hist.to_excel(wr, index=False)
                st.download_button("📥 Descargar Excel", buf.getvalue(), "Reporte_Ventas.xlsx", "application/vnd.ms-excel")
            else:
                st.write("Sin historial aún.")
        except:
            st.error("Error cargando historial.")
            
        if st.button("Cerrar Sesión Admin"):
            st.session_state.admin_autenticado = False
            st.rerun()
