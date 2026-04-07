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

# --- 5. TABLA INVENTARIO ---
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
        st.warning("⚠️ ¡Atención! Reponer productos en rojo.")

# --- 6. REGISTRO DE VENTA ---
st.divider()
st.markdown("<p class='titulo-seccion'>🛒 Nueva Venta</p>", unsafe_allow_html=True)

if not df.empty:
    c_sel, c_cant = st.columns([2, 1])
    with c_sel:
        prod_sel = st.selectbox("Producto:", sorted(df["Producto"].tolist()), key="sel_prod")
    with c_cant:
        fila = df[df["Producto"] == prod_sel].iloc[0]
        stock_r = int(fila["Stock_Actual"])
        cant_carro = sum(i["cantidad"] for i in st.session_state.carrito if i["nombre"] == prod_sel)
        disp = stock_r - cant_carro
        cant = st.number_input(f"Cant. (Disp: {disp})", min_value=1, max_value=max(1, disp), value=1, key="num_cant")

    if st.button("➕ AGREGAR", use_container_width=True):
        if disp > 0:
            st.session_state.carrito.append({
                "id": fila["ID_Producto"], "nombre": prod_sel, 
                "cantidad": int(cant), "precio": Decimal(str(fila["Precio_Venta"]))
            })
            st.rerun()

# --- 7. PROCESAR COMPRA ---
if st.session_state.carrito:
    st.divider()
    df_c = pd.DataFrame(st.session_state.carrito)
    df_c["Subtotal"] = df_c["cantidad"] * df_c["precio"]
    total = df_c["Subtotal"].sum()
    
    st.table(df_c[['nombre', 'cantidad', 'Subtotal']])
    st.metric("TOTAL", f"S/ {float(total):.2f}")
    metodo = st.radio("Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Vaciar", use_container_width=True):
            st.session_state.carrito = []
            st.session_state.confirmar_final = False
            st.rerun()
    with col2:
        if st.button("🚀 FINALIZAR", type="primary", use_container_width=True):
            st.session_state.confirmar_final = True

    if st.session_state.confirmar_final:
        st.info("💡 Confirma la operación para grabar en la nube.")
        if st.button("✅ SÍ, GRABAR VENTA", use_container_width=True):
            f, h = obtener_tiempo_peru()
            try:
                tabla_ventas.put_item(Item={
                    "ID_Venta": f"V-{int(time.time())}",
                    "Fecha": f, "Hora": h, "Total": Decimal(str(total)),
                    "Metodo": metodo, "Productos": st.session_state.carrito
                })
                for item in st.session_state.carrito:
                    tabla_inventario.update_item(
                        Key={"ID_Producto": item["id"]},
                        UpdateExpression="SET Stock_Actual = Stock_Actual - :q",
                        ExpressionAttributeValues={":q": item["cantidad"]}
                    )
                st.session_state.carrito = []
                st.session_state.confirmar_final = False
                st.session_state.df = cargar_datos()
                st.success("✨ ¡Venta registrada exitosamente!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Error AWS: {e}")

# --- 8. PANEL ADMIN (CON EXCEL PROFESIONAL RECUPERADO) ---
st.divider()
with st.expander("🔐 PANEL DE CONTROL"):
    if not st.session_state.admin_logueado:
        clave = st.text_input("Contraseña:", type="password")
        if st.button("Ingresar"):
            if clave == "admin123":
                st.session_state.admin_logueado = True
                st.rerun()
            else:
                st.error("Clave incorrecta")
    else:
        if st.button("🔒 Cerrar Sesión Admin", use_container_width=True):
            st.session_state.admin_logueado = False
            st.rerun()
            
        st.markdown("### 📦 Reposición de Mercadería")
        with st.form("abastecer"):
            p_abast = st.selectbox("Elegir producto:", df["Producto"].tolist())
            c_abast = st.number_input("Cantidad recibida:", min_value=1, value=10)
            if st.form_submit_button("✅ CARGAR STOCK"):
                id_p = df[df["Producto"] == p_abast].iloc[0]["ID_Producto"]
                tabla_inventario.update_item(Key={"ID_Producto": id_p}, UpdateExpression="SET Stock_Actual = Stock_Actual + :q", ExpressionAttributeValues={":q": int(c_abast)})
                st.session_state.df = cargar_datos()
                st.success(f"Stock de {p_abast} actualizado.")
                time.sleep(1)
                st.rerun()

        st.divider()
        st.markdown("### 📊 Reporte de Ventas")
        try:
            res = tabla_ventas.scan()
            v_data = res.get("Items", [])
            if v_data:
                df_h = pd.DataFrame(v_data)
                df_h["Total"] = pd.to_numeric(df_h["Total"]).fillna(0)
                df_h['Sort'] = pd.to_datetime(df_h['Fecha'] + ' ' + df_h['Hora'], dayfirst=True)
                df_h = df_h.sort_values(by='Sort', ascending=False)

                st.write(f"**Caja Total:** S/ {df_h['Total'].sum():,.2f}")
                
                # --- LÓGICA DE EXCEL PRO (BORDES, COLORES Y TOTAL ÚNICO) ---
                filas_ex = []
                for _, v in df_h.iterrows():
                    first = True
                    for p in v['Productos']:
                        filas_ex.append({
                            "ID": v['ID_Venta'], "Fecha": v['Fecha'], "Hora": v['Hora'],
                            "Producto": p['nombre'], "Cant": int(p['cantidad']),
                            "Subtotal": float(p['precio']) * int(p['cantidad']),
                            "TOTAL CLIENTE": float(v['Total']) if first else "",
                            "Metodo": v['Metodo']
                        })
                        first = False
                
                df_ex = pd.DataFrame(filas_ex)
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                    df_ex.to_excel(wr, index=False, sheet_name='Ventas')
                    workbook, worksheet = wr.book, wr.sheets['Ventas']
                    
                    # Formatos
                    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#00acc1', 'font_color': 'white', 'border': 1})
                    money_fmt = workbook.add_format({'num_format': '"S/" #,##0.00', 'border': 1})
                    total_fmt = workbook.add_format({'bold': True, 'bg_color': '#E0F7FA', 'border': 1, 'num_format': '"S/" #,##0.00'})
                    
                    for i, col in enumerate(df_ex.columns):
                        worksheet.write(0, i, col, header_fmt)
                        worksheet.set_column(i, i, 18)

                    toggle, last_id = True, ""
                    for row in range(1, len(df_ex) + 1):
                        curr_id = df_ex.iloc[row-1]['ID']
                        if curr_id != last_id:
                            toggle, last_id = not toggle, curr_id
                        
                        fmt = workbook.add_format({'border': 1, 'bg_color': '#F9F9F9' if toggle else '#FFFFFF'})
                        for col in range(len(df_ex.columns)):
                            val = df_ex.iloc[row-1, col]
                            if col == 6 and val != "": # TOTAL CLIENTE
                                worksheet.write(row, col, val, total_fmt)
                            elif col == 5: # Subtotal
                                worksheet.write(row, col, val, money_fmt)
                            else:
                                worksheet.write(row, col, val, fmt)

                st.download_button("📥 DESCARGAR EXCEL PRO", buf.getvalue(), "Reporte_Ventas.xlsx", "application/vnd.ms-excel", use_container_width=True)
            else:
                st.info("Sin ventas.")
        except:
            st.warning("Cargando...")
