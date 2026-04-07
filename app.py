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

# --- 2. CONFIGURACIÓN ---
st.set_page_config(page_title="Inventario Dental Pro", layout="wide")

def obtener_tiempo_peru():
    ahora = datetime.utcnow() - timedelta(hours=5)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S")

def cargar_datos():
    try:
        data = tabla_inventario.scan()["Items"]
        df = pd.DataFrame(data)
        if not df.empty:
            df["Stock_Actual"] = pd.to_numeric(df["Stock_Actual"]).astype(int)
            df["Precio_Venta"] = pd.to_numeric(df["Precio_Venta"])
            return df.sort_values(by="ID_Producto").reset_index(drop=True)
        return pd.DataFrame()
    except: return pd.DataFrame()

if "df" not in st.session_state: st.session_state.df = cargar_datos()
if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 3. INTERFAZ ---
st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 SISTEMA DENTAL - ALBERTO</h1>", unsafe_allow_html=True)

df = st.session_state.df
if not df.empty:
    # CORRECCIÓN AQUÍ: Usamos .map() en lugar de .applymap() para evitar el error de la imagen
    def resaltar_stock(val):
        color = 'red' if val <= 5 else 'white'
        return f'color: {color}; font-weight: bold'

    st.subheader("📋 Inventario Real")
    st.dataframe(
        df[['Producto', 'Stock_Actual', 'Precio_Venta']].style.map(resaltar_stock, subset=['Stock_Actual']), 
        use_container_width=True, hide_index=True
    )

# --- 4. LÓGICA DE VENTA ---
st.divider()
if not df.empty:
    c1, c2 = st.columns([2,1])
    p_sel = c1.selectbox("Seleccione Producto:", df["Producto"].tolist())
    fila = df[df["Producto"] == p_sel].iloc[0]
    cant = c2.number_input("Cant:", min_value=1, max_value=int(fila["Stock_Actual"]), value=1)
    
    if st.button("➕ AGREGAR", use_container_width=True):
        st.session_state.carrito.append({
            "id": fila["ID_Producto"], "nombre": p_sel, 
            "cantidad": int(cant), "precio": Decimal(str(fila["Precio_Venta"]))
        })
        st.rerun()

if st.session_state.carrito:
    st.markdown("### 🛒 Detalle del Pedido")
    df_c = pd.DataFrame(st.session_state.carrito)
    total_v = sum(df_c["cantidad"] * df_c["precio"])
    st.table(df_c[["nombre", "cantidad"]])
    st.metric("TOTAL", f"S/ {float(total_v):.2f}")
    
    if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
        f, h = obtener_tiempo_peru()
        try:
            # Graba en DynamoDB
            tabla_ventas.put_item(Item={
                "ID_Venta": f"V-{int(time.time())}", "Fecha": f, "Hora": h, 
                "Total": Decimal(str(total_v)), "Productos": st.session_state.carrito
            })
            # Descuenta Stock
            for item in st.session_state.carrito:
                tabla_inventario.update_item(
                    Key={"ID_Producto": item["id"]},
                    UpdateExpression="SET Stock_Actual = Stock_Actual - :q",
                    ExpressionAttributeValues={":q": item["cantidad"]}
                )
            st.success("✅ Venta registrada con éxito.")
            st.session_state.carrito = []
            st.session_state.df = cargar_datos()
            time.sleep(2)
            st.rerun()
        except: st.error("Error al subir a la nube.")

# --- 5. EXCEL SEPARADO POR CADA COMPRA ---
st.divider()
with st.expander("🔐 REPORTE PARA EL TÍO"):
    if st.text_input("Clave:", type="password") == "admin123":
        if st.button("GENERAR EXCEL"):
            res = tabla_ventas.scan()
            items = res.get("Items", [])
            if items:
                # CREAMOS FILAS INDIVIDUALES POR PRODUCTO
                filas_excel = []
                for v in items:
                    for p in v.get('Productos', []):
                        filas_excel.append({
                            "Fecha": v['Fecha'],
                            "Hora": v['Hora'],
                            "Producto": p['nombre'],
                            "Cantidad": int(p['cantidad']),
                            "Precio Unit": float(p['precio']),
                            "Subtotal": int(p['cantidad']) * float(p['precio']),
                            "BOLETA TOTAL": float(v['Total'])
                        })
                
                df_reporte = pd.DataFrame(filas_excel)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_reporte.to_excel(writer, index=False, sheet_name='Ventas')
                    # Formato para que no se vea pegado
                    worksheet = writer.sheets['Ventas']
                    for i, col in enumerate(df_reporte.columns):
                        worksheet.set_column(i, i, 18)
                
                st.download_button("📥 Descargar Excel Detallado", output.getvalue(), "Reporte_Dental.xlsx")
