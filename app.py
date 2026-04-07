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
st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 CONTROL DE VENTAS - DYNAMODB</h1>", unsafe_allow_html=True)

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
if "admin_logueado" not in st.session_state: st.session_state.admin_logueado = False

# --- 3. INVENTARIO CON ALERTA SUTIL (TEXTO ROJO) ---
st.markdown("### 📋 Stock Actual")
df = st.session_state.df

if not df.empty:
    # Solo resalta el texto de la celda Stock_Actual si es bajo
    def color_stock(val):
        color = 'red' if val <= 5 else 'white'
        weight = 'bold' if val <= 5 else 'normal'
        return f'color: {color}; font-weight: {weight}'

    st.dataframe(
        df[['ID_Producto', 'Producto', 'Stock_Actual', 'Precio_Venta']].style.map(color_stock, subset=['Stock_Actual']),
        use_container_width=True, hide_index=True
    )
    
    # Aviso de texto si hay stock bajo
    if (df["Stock_Actual"] <= 5).any():
        st.warning("⚠️ Hay productos con stock crítico (5 o menos).")

# --- 4. SELECCIÓN Y VENTA ---
st.divider()
if not df.empty:
    c1, c2 = st.columns([2,1])
    prod_sel = c1.selectbox("Elegir Producto:", df["Producto"].tolist())
    fila = df[df["Producto"] == prod_sel].iloc[0]
    cant = c2.number_input("Cantidad:", min_value=1, max_value=int(fila["Stock_Actual"]), value=1)
    
    if st.button("➕ AGREGAR AL CARRITO", use_container_width=True):
        st.session_state.carrito.append({
            "id": fila["ID_Producto"], "nombre": prod_sel, 
            "cantidad": int(cant), "precio": Decimal(str(fila["Precio_Venta"]))
        })
        st.rerun()

if st.session_state.carrito:
    st.markdown("### 🛒 Tu Pedido")
    df_c = pd.DataFrame(st.session_state.carrito)
    total_v = sum(df_c["cantidad"] * df_c["precio"])
    st.table(df_c[["nombre", "cantidad"]])
    st.metric("TOTAL", f"S/ {float(total_v):.2f}")
    
    col_v, col_f = st.columns(2)
    if col_v.button("🗑️ VACIAR TODO", use_container_width=True):
        st.session_state.carrito = []
        st.rerun()

    if col_f.button("✅ FINALIZAR Y GUARDAR", type="primary", use_container_width=True):
        f, h = obtener_tiempo_peru()
        try:
            tabla_ventas.put_item(Item={
                "ID_Venta": f"V-{int(time.time())}", "Fecha": f, "Hora": h, 
                "Total": Decimal(str(total_v)), "Metodo": "Efectivo", "Productos": st.session_state.carrito
            })
            for item in st.session_state.carrito:
                tabla_inventario.update_item(
                    Key={"ID_Producto": item["id"]},
                    UpdateExpression="SET Stock_Actual = Stock_Actual - :q",
                    ExpressionAttributeValues={":q": item["cantidad"]}
                )
            st.success("✨ Venta guardada correctamente.")
            st.session_state.carrito = []
            st.session_state.df = cargar_datos()
            time.sleep(1.5)
            st.rerun()
        except: st.error("Error al conectar con la nube.")

# --- 5. PANEL ADMIN Y EXCEL ORDENADO ---
st.divider()
with st.expander("🔐 PANEL DE ADMINISTRADOR"):
    if not st.session_state.admin_logueado:
        clave = st.text_input("Ingresa la clave maestra:", type="password")
        if st.button("Desbloquear"):
            if clave == "admin123":
                st.session_state.admin_logueado = True
                st.rerun()
            else:
                st.error("Clave incorrecta")
    else:
        if st.button("Cerrar Sesión Admin"):
            st.session_state.admin_logueado = False
            st.rerun()
            
        st.markdown("### 📊 Reportes Excel")
        res = tabla_ventas.scan()
        ventas = res.get("Items", [])
        if ventas:
            # Reorganizamos los datos para que el Excel no esté "pegado"
            filas_reporte = []
            for v in ventas:
                for p in v.get('Productos', []):
                    filas_reporte.append({
                        "Fecha": v['Fecha'], "Hora": v['Hora'],
                        "Producto": p['nombre'], "Cantidad": int(p['cantidad']),
                        "Precio Unit": float(p['precio']), "Subtotal": int(p['cantidad']) * float(p['precio']),
                        "TOTAL VENTA": float(v['Total'])
                    })
            
            df_excel = pd.DataFrame(filas_reporte)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                df_excel.to_excel(writer, index=False, sheet_name='Reporte')
                # Ajuste de ancho de columnas automático
                worksheet = writer.sheets['Reporte']
                for i, col in enumerate(df_excel.columns):
                    column_len = max(df_excel[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.set_column(i, i, column_len)
            
            st.download_button(
                label="📥 DESCARGAR REPORTE PARA EL TÍO",
                data=buf.getvalue(),
                file_name=f"Ventas_Dental_{datetime.now().strftime('%d_%m')}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )
