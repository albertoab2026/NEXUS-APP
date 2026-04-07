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
    st.error(f"Error de Configuración AWS: {e}")

# --- 2. FUNCIONES ---
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

# Inicialización
if "carrito" not in st.session_state: st.session_state.carrito = []
df = cargar_datos()

# --- 3. INTERFAZ ---
st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 SISTEMA DENTAL PRO</h1>", unsafe_allow_html=True)

# Tabla de Inventario con Alerta Roja
if not df.empty:
    st.subheader("📋 Stock")
    def resaltar(s):
        return ['background-color: #ffcccc' if s.Stock_Actual <= 5 else '' for _ in s]
    st.dataframe(df[['Producto', 'Stock_Actual', 'Precio_Venta']].style.apply(resaltar, axis=1), use_container_width=True)

# Venta
c1, c2 = st.columns([3,1])
with c1:
    p_sel = st.selectbox("Producto:", df["Producto"].tolist() if not df.empty else [])
with c2:
    cant = st.number_input("Cant:", min_value=1, value=10 if "Resina" in str(p_sel) else 1)

if st.button("➕ AGREGAR"):
    fila = df[df["Producto"] == p_sel].iloc[0]
    st.session_state.carrito.append({
        "id": fila["ID_Producto"], "nombre": p_sel, 
        "cantidad": int(cant), "precio": Decimal(str(fila["Precio_Venta"]))
    })
    st.rerun()

# --- 4. PROCESAR VENTA ---
if st.session_state.carrito:
    st.divider()
    df_c = pd.DataFrame(st.session_state.carrito)
    total = sum(df_c["cantidad"] * df_c["precio"])
    st.table(df_c[["nombre", "cantidad"]])
    st.metric("TOTAL", f"S/ {float(total):.2f}")
    
    col_v, col_g = st.columns(2)
    if col_v.button("🗑️ VACIAR"):
        st.session_state.carrito = []
        st.rerun()

    if col_g.button("🚀 GUARDAR VENTA", type="primary"):
        with st.spinner("Subiendo a la nube..."):
            try:
                f, h = obtener_tiempo_peru()
                # Registro en Dynamo
                tabla_ventas.put_item(Item={
                    "ID_Venta": f"V-{int(time.time())}",
                    "Fecha": f, "Hora": h, "Total": Decimal(str(total)),
                    "Productos": st.session_state.carrito
                })
                # Descuento de stock
                for item in st.session_state.carrito:
                    tabla_inventario.update_item(
                        Key={"ID_Producto": item["id"]},
                        UpdateExpression="SET Stock_Actual = Stock_Actual - :q",
                        ExpressionAttributeValues={":q": item["cantidad"]}
                    )
                st.success("✅ Venta guardada correctamente.")
                st.session_state.carrito = []
                time.sleep(2)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al conectar: {e}")

# --- 5. EXCEL DETALLADO EN PANEL ADMIN ---
with st.expander("📊 Reporte para el Tío"):
    if st.button("Generar Excel"):
        items = tabla_ventas.scan().get("Items", [])
        if items:
            rows = []
            for v in items:
                for p in v.get('Productos', []):
                    rows.append({
                        "Fecha": v['Fecha'], "Producto": p['nombre'], 
                        "Cant": int(p['cantidad']), "Subtotal": float(p['precio']) * int(p['cantidad'])
                    })
            df_ex = pd.DataFrame(rows)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_ex.to_excel(writer, index=False, sheet_name='Ventas')
            st.download_button("📥 Descargar Excel Ordenado", output.getvalue(), "Reporte.xlsx")
