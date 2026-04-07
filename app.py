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
    .stock-bajo { color: #ff1744 !important; font-weight: bold; }
    .stButton>button { border-radius: 8px; }
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
            df["Stock_Actual"] = pd.to_numeric(df["Stock_Actual"], errors='coerce').fillna(0).astype(int)
            df["Precio_Venta"] = pd.to_numeric(df["Precio_Venta"], errors='coerce').fillna(0)
            return df.sort_values(by="ID_Producto").reset_index(drop=True)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 4. ESTADO DE SESIÓN ---
if "df" not in st.session_state: st.session_state.df = cargar_datos()
if "carrito" not in st.session_state: st.session_state.carrito = []
if "admin_autenticado" not in st.session_state: st.session_state.admin_autenticado = False
if "confirmar_final" not in st.session_state: st.session_state.confirmar_final = False

# --- 5. TABLA INVENTARIO CON ALERTAS ---
st.markdown("<p class='titulo-seccion'>📋 Inventario en la Nube</p>", unsafe_allow_html=True)
df = st.session_state.df

if not df.empty:
    # Función para dar formato al stock (Poner rojo si es <= 5)
    def resaltar_stock(row):
        color = 'color: #ff1744; font-weight: bold;' if row.Stock_Actual <= 5 else 'color: white;'
        return [color] * len(row)

    df_view = df.copy()
    df_view["Precio_Venta"] = df_view["Precio_Venta"].map("S/ {:.2f}".format)
    
    # Usamos st.dataframe con estilo para que se vea el rojo
    st.dataframe(
        df_view[['ID_Producto', 'Producto', 'Stock_Actual', 'Precio_Venta']].style.apply(resaltar_stock, axis=1),
        use_container_width=True,
        hide_index=True
    )
    
    # Aviso visual simple
    if (df["Stock_Actual"] <= 5).any():
        st.warning("⚠️ ¡Atención! Hay productos con stock bajo (5 unidades o menos).")
else:
    st.info("Cargando inventario...")

# --- 6. REGISTRO DE VENTA ---
st.divider()
st.markdown("<p class='titulo-seccion'>🛒 Registrar Nueva Venta</p>", unsafe_allow_html=True)

if not df.empty:
    col_sel, col_cant = st.columns([2, 1])
    with col_sel:
        producto_sel = st.selectbox("Selecciona Producto:", sorted(df["Producto"].tolist()))
    with col_cant:
        fila = df[df["Producto"] == producto_sel].iloc[0]
        stock_real = int(fila["Stock_Actual"])
        en_carro = sum(item["cantidad"] for item in st.session_state.carrito if item["nombre"] == producto_sel)
        disponible = stock_real - en_carro
        cantidad = st.number_input(f"Cantidad (Disponible: {disponible})", min_value=1, max_value=max(1, disponible), value=1)

    if st.button("➕ AGREGAR AL PEDIDO", use_container_width=True):
        if disponible > 0:
            st.session_state.carrito.append({
                "id": fila["ID_Producto"],
                "nombre": producto_sel,
                "cantidad": int(cantidad),
                "precio": Decimal(str(fila["Precio_Venta"]))
            })
            st.rerun()

# --- 7. CARRITO Y COBRO ---
if st.session_state.carrito:
    st.divider()
    st.markdown("<p class='titulo-seccion'>📝 Resumen de la Venta</p>", unsafe_allow_html=True)
    df_c = pd.DataFrame(st.session_state.carrito)
    df_c["Subtotal"] = df_c["cantidad"] * df_c["precio"]
    total_neto = df_c["Subtotal"].sum()
    st.table(df_c[['nombre', 'cantidad', 'Subtotal']])
    st.metric("TOTAL A PAGAR", f"S/ {float(total_neto):.2f}")
    metodo = st.radio("Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑️ Vaciar Todo", use_container_width=True):
            st.session_state.carrito = []
            st.rerun()
    with c2:
        if st.button("🚀 FINALIZAR COMPRA", type="primary", use_container_width=True):
            st.session_state.confirmar_final = True

    if st.session_state.confirmar_final:
        st.warning("⚠️ ¿CONFIRMAS ESTA VENTA?")
        csi, cno = st.columns(2)
        with csi:
            if st.button("✅ SÍ, CONFIRMAR", use_container_width=True):
                f_v, h_v = obtener_tiempo_peru()
                try:
                    tabla_ventas.put_item(Item={
                        "ID_Venta": f"V-{int(time.time())}",
                        "Fecha": f_v, "Hora": h_v, "Total": Decimal(str(total_neto)),
                        "Metodo": metodo, "Productos": st.session_state.carrito
                    })
                    for item in st.session_state.carrito:
                        tabla_inventario.update_item(
                            Key={"ID_Producto": item["id"]},
                            UpdateExpression="SET Stock_Actual = Stock_Actual - :qty",
                            ExpressionAttributeValues={":qty": item["cantidad"]}
                        )
                    st.success("Venta Exitosa")
                    st.session_state.carrito = []
                    st.session_state.confirmar_final = False
                    st.session_state.df = cargar_datos()
                    st.rerun()
                except: st.error("Error al grabar")
        with cno:
            if st.button("❌ CANCELAR", use_container_width=True):
                st.session_state.confirmar_final = False
                st.rerun()

# --- 8. PANEL ADMIN (ABASTECER + HISTORIAL) ---
st.divider()
with st.expander("🔐 PANEL DE ADMINISTRADOR"):
    if not st.session_state.admin_autenticado:
        pass_in = st.text_input("Clave:", type="password")
        if pass_in == "admin123":
            st.session_state.admin_autenticado = True
            st.rerun()
    else:
        st.markdown("### 📦 Abastecer Inventario")
        with st.form("form_abastecer"):
            prod_abast = st.selectbox("Selecciona producto:", df["Producto"].tolist())
            cant_abast = st.number_input("Cantidad que llegó:", min_value=1, value=10)
            btn_abast = st.form_submit_button("✅ CARGAR STOCK")
            
            if btn_abast:
                id_prod = df[df["Producto"] == prod_abast].iloc[0]["ID_Producto"]
                try:
                    tabla_inventario.update_item(
                        Key={"ID_Producto": id_prod},
                        UpdateExpression="SET Stock_Actual = Stock_Actual + :q",
                        ExpressionAttributeValues={":q": int(cant_abast)}
                    )
                    st.success(f"Stock actualizado para {prod_abast}")
                    st.session_state.df = cargar_datos()
                    st.rerun()
                except: st.error("Error")

        st.divider()
        st.markdown("### 📊 Historial de Ventas")
        try:
            res = tabla_ventas.scan()
            ventas_data = res.get("Items", [])
            if ventas_data:
                df_h = pd.DataFrame(ventas_data)
                df_h["Total"] = pd.to_numeric(df_h["Total"], errors='coerce').fillna(0)
                df_h['Temp_Sort'] = pd.to_datetime(df_h['Fecha'] + ' ' + df_h['Hora'], dayfirst=True)
                df_h = df_h.sort_values(by='Temp_Sort', ascending=False)

                st.write(f"**Caja Total:** S/ {df_h['Total'].sum():,.2f}")
                
                filas_ex = []
                for _, v in df_h.iterrows():
                    first = True
                    for p in v['Productos']:
                        filas_ex.append({
                            "ID_Venta": v['ID_Venta'], "Fecha": v['Fecha'], "Hora": v['Hora'],
                            "Producto": p['nombre'], "Cant": int(p['cantidad']), "P.Unit": float(p['precio']),
                            "TOTAL CLIENTE": float(v['Total']) if first else "", "Metodo": v['Metodo']
                        })
                        first = False
                
                df_ex = pd.DataFrame(filas_ex)
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                    df_ex.to_excel(wr, index=False, sheet_name='Reporte')
                
                st.download_button("📥 DESCARGAR EXCEL", buf.getvalue(), "Reporte.xlsx", "application/vnd.ms-excel", use_container_width=True)
        except: st.info("Sin ventas aún.")

        if st.button("Cerrar Sesión Admin"):
            st.session_state.admin_autenticado = False
            st.rerun()
