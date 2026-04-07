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
    tabla_ingresos = dynamodb.Table('EntradasInventario') 
except Exception as e:
    st.error(f"Error de conexión con AWS: {e}")

# --- 2. CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Dental Alberto", layout="wide")

def obtener_tiempo_peru():
    ahora = datetime.utcnow() - timedelta(hours=5)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S")

def cargar_datos():
    try:
        data = tabla_inventario.scan()["Items"]
        df = pd.DataFrame(data)
        if not df.empty:
            df["Stock_Actual"] = pd.to_numeric(df["Stock_Actual"]).astype(int)
            df["Precio_Venta"] = pd.to_numeric(df["Precio_Venta"]).astype(float).round(2)
            return df.sort_values(by="ID_Producto").reset_index(drop=True)
        return pd.DataFrame()
    except: return pd.DataFrame()

if "df" not in st.session_state: st.session_state.df = cargar_datos()
if "carrito" not in st.session_state: st.session_state.carrito = []
if "admin_auth" not in st.session_state: st.session_state.admin_auth = False
if "confirmar_venta" not in st.session_state: st.session_state.confirmar_venta = False

# --- 3. INTERFAZ PRINCIPAL ---
st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 CONTROL DENTAL - ALBERTO</h1>", unsafe_allow_html=True)

df = st.session_state.df
if not df.empty:
    st.subheader("📋 Inventario Disponible")
    st.dataframe(df[['Producto', 'Stock_Actual', 'Precio_Venta']].style.format({"Precio_Venta": "{:.2f}"}), 
                 use_container_width=True, hide_index=True)

st.divider()
if not df.empty:
    c1, c2 = st.columns([2,1])
    p_sel = c1.selectbox("Producto a vender:", df["Producto"].tolist(), key="sel_venta")
    fila_p = df[df["Producto"] == p_sel].iloc[0]
    cant = c2.number_input("Cantidad:", min_value=1, max_value=int(fila_p["Stock_Actual"]), value=1, key="cant_venta")
    
    if st.button("➕ AGREGAR AL CARRITO", use_container_width=True):
        st.session_state.carrito.append({
            "id": fila_p["ID_Producto"], "nombre": p_sel, 
            "cantidad": int(cant), "precio": Decimal(str(fila_p["Precio_Venta"]))
        })
        st.session_state.confirmar_venta = False
        st.rerun()

# --- 4. CARRITO Y CONFIRMACIÓN ---
if st.session_state.carrito:
    st.markdown("### 🛒 Detalle del Pedido")
    df_c = pd.DataFrame(st.session_state.carrito)
    total_v = sum(df_c["cantidad"] * df_c["precio"])
    st.table(df_c[["nombre", "cantidad"]])
    
    metodo_pago = st.radio("Forma de Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)
    st.metric("TOTAL A COBRAR", f"S/ {float(total_v):.2f}")
    
    col_v1, col_v2 = st.columns(2)
    
    if col_v1.button("🗑️ VACIAR CARRITO", use_container_width=True):
        st.session_state.carrito = []
        st.session_state.confirmar_venta = False
        st.rerun()

    if not st.session_state.confirmar_venta:
        if col_v2.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
            st.session_state.confirmar_venta = True
            st.rerun()
    else:
        st.warning(f"⚠️ ¿Confirmar venta por S/ {float(total_v):.2f}?")
        cc1, cc2 = st.columns(2)
        if cc1.button("✅ SÍ, CONFIRMAR", type="primary", use_container_width=True):
            f, h = obtener_tiempo_peru()
            tabla_ventas.put_item(Item={
                "ID_Venta": f"V-{int(time.time())}", "Fecha": f, "Hora": h, 
                "Total": Decimal(str(total_v)), "Metodo": metodo_pago, "Productos": st.session_state.carrito
            })
            for i in st.session_state.carrito:
                tabla_inventario.update_item(Key={"ID_Producto": i["id"]}, UpdateExpression="SET Stock_Actual = Stock_Actual - :q", ExpressionAttributeValues={":q": int(i["cantidad"])})
            st.balloons()
            st.session_state.carrito = []
            st.session_state.confirmar_venta = False
            st.session_state.df = cargar_datos()
            st.rerun()
        
        if cc2.button("❌ CANCELAR", use_container_width=True):
            st.session_state.confirmar_venta = False
            st.rerun()

# --- 5. PANEL DE ADMINISTRADOR ---
st.divider()
with st.expander("🔐 PANEL DE ADMINISTRADOR"):
    if not st.session_state.admin_auth:
        with st.form("login"):
            clave = st.text_input("Contraseña:", type="password")
            if st.form_submit_button("Ingresar"):
                if clave == "admin123": st.session_state.admin_auth = True; st.rerun()
                else: st.error("Incorrecto")
    else:
        if st.button("🔒 CERRAR SESIÓN ADMIN", use_container_width=True): 
            st.session_state.admin_auth = False; st.rerun()

        # ABASTECIMIENTO
        st.subheader("📦 Abastecimiento")
        c_adm1, c_adm2 = st.columns(2)
        with c_adm1:
            p_abast = st.selectbox("Elegir producto:", df["Producto"].tolist(), key="sel_admin")
            c_abast = st.number_input("Cantidad:", min_value=1, value=10, key="cant_admin")
            if st.button("Registrar Entrada", use_container_width=True):
                try:
                    id_a = df[df["Producto"] == p_abast].iloc[0]["ID_Producto"]
                    f_ing, h_ing = obtener_tiempo_peru()
                    tabla_inventario.update_item(Key={"ID_Producto": id_a}, UpdateExpression="SET Stock_Actual = Stock_Actual + :q", ExpressionAttributeValues={":q": int(c_abast)})
                    tabla_ingresos.put_item(Item={
                        "ID_Ingreso": f"IN-{int(time.time())}", "Fecha": f_ing, "Hora": h_ing,
                        "Producto": p_abast, "Cantidad": int(c_abast)
                    })
                    st.success("¡Stock actualizado!")
                    st.session_state.df = cargar_datos()
                    time.sleep(1); st.rerun()
                except: st.error("Error en AWS.")

        with c_adm2:
            st.subheader("📜 Historial de Ingresos")
            if st.button("Cargar Historial"):
                try:
                    ingresos = tabla_ingresos.scan().get("Items", [])
                    if ingresos:
                        df_ingresos = pd.DataFrame(ingresos).sort_values(by=["Fecha", "Hora"], ascending=False)
                        st.dataframe(df_ingresos[["Fecha", "Hora", "Producto", "Cantidad"]], use_container_width=True, hide_index=True)
                except: st.info("Sin historial.")

        st.divider()
        # CIERRE DE CAJA Y EXCEL
        st.subheader("💰 Cierre de Caja del Día")
        fecha_hoy, _ = obtener_tiempo_peru()
        
        if st.button("Generar Reporte de Hoy"):
            ventas_lista = tabla_ventas.scan().get("Items", [])
            ventas_hoy = [v for v in ventas_lista if v['Fecha'] == fecha_hoy]
            
            if ventas_hoy:
                total_recaudado = sum([float(v['Total']) for v in ventas_hoy])
                st.metric("TOTAL RECAUDADO", f"S/ {total_recaudado:.2f}")
                
                filas_para_tabla = []
                filas_para_excel = [] # Excel lleva todos los datos en cada fila para que sea útil
                
                for v in sorted(ventas_hoy, key=lambda x: x['Hora'], reverse=True):
                    es_primero = True
                    for p in v['Productos']:
                        # Para la tabla visual (bonita)
                        filas_para_tabla.append({
                            "Hora": v['Hora'] if es_primero else "",
                            "Producto": p['nombre'],
                            "Cant": p['cantidad'],
                            "Pago": v.get('Metodo', 'Efectivo') if es_primero else "",
                            "Total Cliente": f"S/ {float(v['Total']):.2f}" if es_primero else ""
                        })
                        # Para el Excel (completo para contabilidad)
                        filas_para_excel.append({
                            "Fecha": v['Fecha'],
                            "Hora": v['Hora'],
                            "Producto": p['nombre'],
                            "Cantidad": p['cantidad'],
                            "Precio Unit": float(p['precio']),
                            "Subtotal": float(p['precio'] * p['cantidad']),
                            "Total Venta": float(v['Total']),
                            "Metodo": v.get('Metodo', 'Efectivo')
                        })
                        es_primero = False
                
                st.table(pd.DataFrame(filas_para_tabla))
                
                # --- LÓGICA DE EXCEL ---
                df_excel = pd.DataFrame(filas_para_excel)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_excel.to_excel(writer, index=False, sheet_name='Ventas_Hoy')
                    # Auto-ajustar columnas
                    worksheet = writer.sheets['Ventas_Hoy']
                    for i, col in enumerate(df_excel.columns):
                        column_len = max(df_excel[col].astype(str).map(len).max(), len(col)) + 2
                        worksheet.set_column(i, i, column_len)
                
                st.download_button(
                    label="📥 DESCARGAR REPORTE EXCEL",
                    data=output.getvalue(),
                    file_name=f"Reporte_Dental_{fecha_hoy.replace('/','_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.warning("No hay ventas registradas para hoy.")
