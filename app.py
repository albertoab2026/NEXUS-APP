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
    # Tabla para registrar los ingresos de mercadería al sistema
    tabla_ingresos = dynamodb.Table('EntradasInventario') 
except Exception as e:
    st.error(f"Error de conexión con AWS: {e}")

# --- 2. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Dental Alberto", layout="wide")

def obtener_tiempo_peru():
    ahora = datetime.utcnow() - timedelta(hours=5)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S")

def cargar_datos():
    try:
        data = tabla_inventario.scan()["Items"]
        df = pd.DataFrame(data)
        if not df.empty:
            # Limpieza de datos para evitar decimales largos en la vista
            df["Stock_Actual"] = pd.to_numeric(df["Stock_Actual"]).astype(int)
            df["Precio_Venta"] = pd.to_numeric(df["Precio_Venta"]).astype(float).round(2)
            return df.sort_values(by="ID_Producto").reset_index(drop=True)
        return pd.DataFrame()
    except: return pd.DataFrame()

# Inicialización de estados de sesión
if "df" not in st.session_state: st.session_state.df = cargar_datos()
if "carrito" not in st.session_state: st.session_state.carrito = []
if "admin_auth" not in st.session_state: st.session_state.admin_auth = False

# --- 3. INTERFAZ DE VENTAS ---
st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 CONTROL DENTAL - ALBERTO</h1>", unsafe_allow_html=True)

df = st.session_state.df
if not df.empty:
    st.subheader("📋 Inventario Actual")
    # Formato de tabla limpio con 2 decimales
    st.dataframe(df[['Producto', 'Stock_Actual', 'Precio_Venta']].style.format({"Precio_Venta": "{:.2f}"}), 
                 use_container_width=True, hide_index=True)

st.divider()
if not df.empty:
    c1, c2 = st.columns([2,1])
    # Uso de llaves únicas (keys) para evitar errores de duplicado
    p_sel = c1.selectbox("Producto a vender:", df["Producto"].tolist(), key="sel_venta")
    fila_p = df[df["Producto"] == p_sel].iloc[0]
    cant = c2.number_input("Cantidad:", min_value=1, max_value=int(fila_p["Stock_Actual"]), value=1, key="cant_venta")
    
    if st.button("➕ AGREGAR AL CARRITO", use_container_width=True):
        st.session_state.carrito.append({
            "id": fila_p["ID_Producto"], "nombre": p_sel, 
            "cantidad": int(cant), "precio": Decimal(str(fila_p["Precio_Venta"]))
        })
        st.rerun()

# --- 4. CARRITO Y FINALIZACIÓN ---
if st.session_state.carrito:
    st.markdown("### 🛒 Detalle del Pedido")
    df_c = pd.DataFrame(st.session_state.carrito)
    total_v = sum(df_c["cantidad"] * df_c["precio"])
    st.table(df_c[["nombre", "cantidad"]])
    
    metodo_pago = st.radio("Forma de Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)
    st.metric("TOTAL A COBRAR", f"S/ {float(total_v):.2f}")
    
    if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
        f, h = obtener_tiempo_peru()
        # Registro de venta en la nube
        tabla_ventas.put_item(Item={
            "ID_Venta": f"V-{int(time.time())}", "Fecha": f, "Hora": h, 
            "Total": Decimal(str(total_v)), "Metodo": metodo_pago, "Productos": st.session_state.carrito
        })
        # Descuento de stock en inventario
        for i in st.session_state.carrito:
            tabla_inventario.update_item(
                Key={"ID_Producto": i["id"]}, 
                UpdateExpression="SET Stock_Actual = Stock_Actual - :q", 
                ExpressionAttributeValues={":q": int(i["cantidad"])}
            )
        
        st.balloons() # Animación de éxito
        st.success(f"Venta guardada exitosamente ({metodo_pago}).")
        st.session_state.carrito = []
        st.session_state.df = cargar_datos()
        time.sleep(1.5)
        st.rerun()

# --- 5. PANEL DE ADMINISTRADOR (INGRESOS Y CIERRE) ---
st.divider()
with st.expander("🔐 PANEL DE ADMINISTRADOR"):
    if not st.session_state.admin_auth:
        with st.form("login"):
            clave = st.text_input("Contraseña de Administrador:", type="password")
            if st.form_submit_button("Ingresar"):
                if clave == "admin123": 
                    st.session_state.admin_auth = True
                    st.rerun()
                else: st.error("Clave incorrecta")
    else:
        if st.button("🔒 CERRAR SESIÓN ADMIN", use_container_width=True): 
            st.session_state.admin_auth = False
            st.rerun()

        # ABASTECIMIENTO CON REGISTRO DE FECHA Y HORA
        st.subheader("📦 Abastecimiento de Mercadería")
        c_adm1, c_adm2 = st.columns(2)
        
        with c_adm1:
            p_abast = st.selectbox("Elegir producto que ingresa:", df["Producto"].tolist(), key="sel_admin")
            c_abast = st.number_input("Cantidad recibida:", min_value=1, value=10, key="cant_admin")
            
            if st.button("Registrar Entrada de Stock", use_container_width=True):
                id_a = df[df["Producto"] == p_abast].iloc[0]["ID_Producto"]
                f_ing, h_ing = obtener_tiempo_peru()
                
                # Actualización de Stock Actual
                tabla_inventario.update_item(Key={"ID_Producto": id_a}, UpdateExpression="SET Stock_Actual = Stock_Actual + :q", ExpressionAttributeValues={":q": int(c_abast)})
                
                # Registro histórico de la entrada
                tabla_ingresos.put_item(Item={
                    "ID_Ingreso": f"IN-{int(time.time())}",
                    "Fecha": f_ing,
                    "Hora": h_ing,
                    "Producto": p_abast,
                    "Cantidad": int(c_abast)
                })
                
                st.success(f"Ingreso registrado: {c_abast} unidades de {p_abast}")
                st.session_state.df = cargar_datos()
                time.sleep(1)
                st.rerun()

        with c_adm2:
            st.subheader("📜 Últimos Ingresos")
            if st.button("Cargar Historial de Entradas"):
                ingresos = tabla_ingresos.scan().get("Items", [])
                if ingresos:
                    df_ingresos = pd.DataFrame(ingresos).sort_values(by=["Fecha", "Hora"], ascending=False)
                    st.dataframe(df_ingresos[["Fecha", "Hora", "Producto", "Cantidad"]], use_container_width=True, hide_index=True)
                else:
                    st.info("No hay registros de entradas aún.")

        st.divider()
        
        # CIERRE DE CAJA DIARIO (DISEÑO COMPACTO)
        st.subheader("💰 Cierre de Caja del Día")
        fecha_hoy, _ = obtener_tiempo_peru()
        
        if st.button("Ver Resumen de Ventas de Hoy"):
            ventas_lista = tabla_ventas.scan().get("Items", [])
            ventas_hoy = [v for v in ventas_lista if v['Fecha'] == fecha_hoy]
            ventas_hoy = sorted(ventas_hoy, key=lambda x: x['Hora'], reverse=True)

            if ventas_hoy:
                total_dia = sum([float(v['Total']) for v in ventas_hoy])
                st.metric("RECAUDACIÓN TOTAL HOY", f"S/ {total_dia:.2f}")

                filas_reporte = []
                for v in ventas_hoy:
                    es_primero = True
                    for p in v['Productos']:
                        # Formato compacto: datos de cliente solo en la primera fila
                        filas_reporte.append({
                            "Hora": v['Hora'] if es_primero else "",
                            "Producto": p['nombre'],
                            "Cant": int(p['cantidad']),
                            "Pago": v.get('Metodo', 'Efectivo') if es_primero else "",
                            "Total Venta": f"S/ {float(v['Total']):.2f}" if es_primero else ""
                        })
                        es_primero = False
                
                st.table(pd.DataFrame(filas_reporte))
                
                # Exportación a Excel para el tío
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                    pd.DataFrame(filas_reporte).to_excel(writer, index=False, sheet_name='Cierre')
                st.download_button("📥 Descargar Reporte Diario (Excel)", out.getvalue(), f"Cierre_{fecha_hoy.replace('/','-')}.xlsx")
            else:
                st.warning("No se encontraron ventas para la fecha de hoy.")
