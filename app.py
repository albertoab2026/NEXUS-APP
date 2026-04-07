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
            # LIMPIEZA DE STOCK: Forzamos a que sean números enteros (quita el .0000)
            df["Stock_Actual"] = pd.to_numeric(df["Stock_Actual"], errors='coerce').fillna(0).astype(int)
            df["Precio_Venta"] = pd.to_numeric(df["Precio_Venta"], errors='coerce').fillna(0)
            return df.sort_values(by="ID_Producto").reset_index(drop=True)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error cargando inventario: {e}")
        return pd.DataFrame()

# --- 4. ESTADO DE SESIÓN ---
if "df" not in st.session_state: st.session_state.df = cargar_datos()
if "carrito" not in st.session_state: st.session_state.carrito = []
if "admin_autenticado" not in st.session_state: st.session_state.admin_autenticado = False
if "confirmar_final" not in st.session_state: st.session_state.confirmar_final = False

# --- 5. TABLA INVENTARIO ---
st.markdown("<p class='titulo-seccion'>📋 Inventario en la Nube</p>", unsafe_allow_html=True)
df = st.session_state.df
if not df.empty:
    df_view = df.copy()
    df_view["Precio_Venta"] = df_view["Precio_Venta"].map("S/ {:.2f}".format)
    # Mostramos el stock como texto limpio para asegurar que no salgan decimales
    df_view["Stock_Actual"] = df_view["Stock_Actual"].astype(str)
    st.table(df_view[['ID_Producto', 'Producto', 'Stock_Actual', 'Precio_Venta']])

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

# --- 7. RESUMEN Y COBRO ---
if st.session_state.carrito:
    st.divider()
    st.markdown("<p class='titulo-seccion'>📝 Resumen de la Venta</p>", unsafe_allow_html=True)
    
    df_c = pd.DataFrame(st.session_state.carrito)
    df_c["Subtotal"] = df_c["cantidad"] * df_c["precio"]
    total_neto = df_c["Subtotal"].sum()

    st.table(df_c[['nombre', 'cantidad', 'Subtotal']])
    st.metric("TOTAL A PAGAR", f"S/ {float(total_neto):.2f}")

    metodo = st.radio("Medio de Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🗑️ Vaciar Todo", use_container_width=True):
            st.session_state.carrito = []
            st.session_state.confirmar_final = False
            st.rerun()
    with col_btn2:
        if st.button("🚀 FINALIZAR COMPRA", type="primary", use_container_width=True):
            st.session_state.confirmar_final = True

    if st.session_state.confirmar_final:
        st.warning("⚠️ ¿CONFIRMAS EL REGISTRO DE ESTA VENTA?")
        c_si, c_no = st.columns(2)
        with c_si:
            if st.button("✅ SÍ, PROCESAR", use_container_width=True):
                f_v, h_v = obtener_tiempo_peru()
                try:
                    tabla_ventas.put_item(Item={
                        "ID_Venta": f"V-{int(time.time())}",
                        "Fecha": f_v, "Hora": h_v,
                        "Total": Decimal(str(total_neto)),
                        "Metodo": metodo,
                        "Productos": st.session_state.carrito
                    })
                    for item in st.session_state.carrito:
                        tabla_inventario.update_item(
                            Key={"ID_Producto": item["id"]},
                            UpdateExpression="SET Stock_Actual = Stock_Actual - :qty",
                            ExpressionAttributeValues={":qty": item["cantidad"]}
                        )
                    st.balloons()
                    st.success(f"✅ Venta guardada con éxito")
                    st.session_state.carrito = []
                    st.session_state.confirmar_final = False
                    st.session_state.df = cargar_datos()
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        with c_no:
            if st.button("❌ CANCELAR", use_container_width=True):
                st.session_state.confirmar_final = False
                st.rerun()

# --- 8. PANEL ADMIN (HISTORIAL Y EXCEL ORDENADO) ---
st.divider()
with st.expander("🔐 PANEL DE ADMINISTRADOR"):
    if not st.session_state.admin_autenticado:
        pass_in = st.text_input("Ingresa Clave Admin:", type="password")
        if pass_in == "admin123":
            st.session_state.admin_autenticado = True
            st.rerun()
    else:
        try:
            res = tabla_ventas.scan()
            ventas_data = res.get("Items", [])
            if ventas_data:
                df_h = pd.DataFrame(ventas_data)
                df_h["Total"] = pd.to_numeric(df_h["Total"], errors='coerce').fillna(0)
                
                # Ordenar por fecha/hora (más reciente arriba)
                if 'Fecha' in df_h.columns and 'Hora' in df_h.columns:
                    df_h['Temp_Sort'] = pd.to_datetime(df_h['Fecha'] + ' ' + df_h['Hora'], dayfirst=True)
                    df_h = df_h.sort_values(by='Temp_Sort', ascending=False)

                st.write(f"### 💰 Caja Total: S/ {df_h['Total'].sum():,.2f}")
                st.dataframe(df_h[['Fecha', 'Hora', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
                
                # --- PROCESO PARA EXCEL DETALLADO ---
                filas_excel = []
                for _, venta in df_h.iterrows():
                    for p in venta['Productos']:
                        filas_excel.append({
                            "Fecha": venta['Fecha'],
                            "Hora": venta['Hora'],
                            "Producto": p['nombre'],
                            "Cantidad": int(p['cantidad']),
                            "Precio Unit.": float(p['precio']),
                            "Subtotal": int(p['cantidad']) * float(p['precio']),
                            "Total Venta": float(venta['Total']),
                            "Metodo": venta['Metodo']
                        })
                
                df_excel_final = pd.DataFrame(filas_excel)

                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                    df_excel_final.to_excel(wr, index=False, sheet_name='Ventas_Detalladas')
                    # Ajuste de diseño en Excel
                    workbook = wr.book
                    worksheet = wr.sheets['Ventas_Detalladas']
                    header_format = workbook.add_format({'bold': True, 'bg_color': '#00ACC1', 'font_color': 'white'})
                    for i, col in enumerate(df_excel_final.columns):
                        worksheet.set_column(i, i, 18)
                
                st.download_button(
                    label="📥 DESCARGAR REPORTE EXCEL DETALLADO",
                    data=buf.getvalue(),
                    file_name=f"Reporte_Dental_{datetime.now().strftime('%d_%m')}.xlsx",
                    mime="application/vnd.ms-excel",
                    use_container_width=True
                )
            else:
                st.info("Sin ventas registradas.")
        except Exception as e:
            st.error(f"Error en historial: {e}")
            
        if st.button("Cerrar Sesión Admin", use_container_width=True):
            st.session_state.admin_autenticado = False
            st.rerun()
