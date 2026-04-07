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
if "admin_logueado" not in st.session_state: st.session_state.admin_logueado = False
if "confirmar_final" not in st.session_state: st.session_state.confirmar_final = False

# --- 5. INVENTARIO ---
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
        st.warning("⚠️ Reponer productos en rojo.")

# --- 6. REGISTRO DE VENTA ---
st.divider()
if not df.empty:
    c_sel, c_cant = st.columns([2, 1])
    with c_sel:
        prod_sel = st.selectbox("Producto:", sorted(df["Producto"].tolist()), key="sel_prod")
    with c_cant:
        fila = df[df["Producto"] == prod_sel].iloc[0]
        disp = int(fila["Stock_Actual"]) - sum(i["cantidad"] for i in st.session_state.carrito if i["nombre"] == prod_sel)
        cant = st.number_input(f"Cant. (Disp: {disp})", min_value=1, max_value=max(1, disp), value=1)

    if st.button("➕ AGREGAR AL PEDIDO", use_container_width=True):
        if disp > 0:
            st.session_state.carrito.append({"id": fila["ID_Producto"], "nombre": prod_sel, "cantidad": int(cant), "precio": Decimal(str(fila["Precio_Venta"]))})
            st.rerun()

# --- 7. PROCESAR COMPRA ---
if st.session_state.carrito:
    df_c = pd.DataFrame(st.session_state.carrito)
    total_v = (df_c["cantidad"] * df_c["precio"]).sum()
    st.table(df_c[['nombre', 'cantidad']])
    st.metric("TOTAL", f"S/ {float(total_v):.2f}")
    metodo = st.radio("Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)

    if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
        st.session_state.confirmar_final = True

    if st.session_state.confirmar_final:
        if st.button("✅ CONFIRMAR GRABACIÓN", use_container_width=True):
            f, h = obtener_tiempo_peru()
            try:
                tabla_ventas.put_item(Item={"ID_Venta": f"V-{int(time.time())}", "Fecha": f, "Hora": h, "Total": Decimal(str(total_v)), "Metodo": metodo, "Productos": st.session_state.carrito})
                for item in st.session_state.carrito:
                    tabla_inventario.update_item(Key={"ID_Producto": item["id"]}, UpdateExpression="SET Stock_Actual = Stock_Actual - :q", ExpressionAttributeValues={":q": item["cantidad"]})
                st.session_state.carrito, st.session_state.confirmar_final = [], False
                st.session_state.df = cargar_datos()
                st.success("Venta Exitosa")
                time.sleep(1)
                st.rerun()
            except: st.error("Error al guardar")

# --- 8. PANEL ADMIN (ESTA ES LA PARTE CLAVE) ---
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

        # Reporte de Ventas con Excel Pro Protegido
        try:
            res_v = tabla_ventas.scan()
            items = res_v.get("Items", [])
            if items:
                df_h = pd.DataFrame(items)
                df_h['Fecha_dt'] = pd.to_datetime(df_h['Fecha'] + ' ' + df_h['Hora'], dayfirst=True)
                df_h = df_h.sort_values(by='Fecha_dt', ascending=False)
                st.write(f"💰 **Caja Total:** S/ {pd.to_numeric(df_h['Total']).sum():.2f}")

                # INTENTO DE EXCEL PROFESIONAL
                excel_listo = False
                buf = io.BytesIO()
                try:
                    import xlsxwriter
                    filas = []
                    for _, v in df_h.iterrows():
                        primero = True
                        for p in v.get('Productos', []):
                            filas.append({
                                "ID": v['ID_Venta'], "Fecha": v['Fecha'], "Hora": v['Hora'],
                                "Producto": p['nombre'], "Cant": int(p['cantidad']), "Subtotal": float(p['precio']) * int(p['cantidad']),
                                "TOTAL": float(v['Total']) if primero else "", "Metodo": v['Metodo']
                            })
                            primero = False
                    
                    df_ex = pd.DataFrame(filas)
                    with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                        df_ex.to_excel(wr, index=False, sheet_name='Reporte')
                        wb, ws = wr.book, wr.sheets['Reporte']
                        # Formato básico para asegurar que descargue
                        header = wb.add_format({'bold': True, 'bg_color': '#00acc1', 'font_color': 'white'})
                        for i, col in enumerate(df_ex.columns): ws.write(0, i, col, header)
                    excel_listo = True
                except:
                    # Si falla xlsxwriter, hacemos un Excel básico con Pandas
                    df_h.drop(columns=['Fecha_dt']).to_excel(buf, index=False)
                    excel_listo = True

                if excel_listo:
                    st.download_button("📥 DESCARGAR REPORTE EXCEL", buf.getvalue(), "Ventas.xlsx", "application/vnd.ms-excel", use_container_width=True)
            else: st.info("No hay ventas.")
        except Exception as e: st.error(f"Error: {e}")
