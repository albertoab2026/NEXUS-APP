import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
import io

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Sistema Dental Tío - PRO", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), ahora

# 2. CONEXIÓN AWS
try:
    aws_id = st.secrets["aws"]["aws_access_key_id"]
    aws_key = st.secrets["aws"]["aws_secret_access_key"]
    aws_region = st.secrets["aws"]["aws_region"]
    admin_pass = st.secrets["auth"]["admin_password"]
    
    dynamodb = boto3.resource('dynamodb', region_name=aws_region,
                              aws_access_key_id=aws_id,
                              aws_secret_access_key=aws_key)
    
    tabla_ventas = dynamodb.Table('VentasDentaltio')
    tabla_stock = dynamodb.Table('StockProductos')
    tabla_auditoria = dynamodb.Table('EntradasInventario')
except Exception as e:
    st.error(f"Error AWS: {e}")
    st.stop()

# ESTADOS DE SESIÓN
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'confirmar' not in st.session_state: st.session_state.confirmar = False
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

# CARGAR STOCK
try:
    items = tabla_stock.scan().get('Items', [])
    df_stock = pd.DataFrame(items) if items else pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])
except:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

st.title("🦷 Gestión Dental: Control Histórico")

# --- SECCIÓN VENTA ---
with st.expander("📦 Consultar Stock Actual"):
    if not df_stock.empty:
        df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
        st.dataframe(df_stock[['Producto', 'Stock', 'Precio']], use_container_width=True, hide_index=True)

st.divider()

# --- CARRITO ---
st.subheader("🛒 Punto de Venta")
if not df_stock.empty:
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        prod_sel = st.selectbox("Producto:", df_stock['Producto'].tolist())
    with c2:
        cant_sel = st.number_input("Cantidad:", min_value=1, value=1)
    with c3:
        st.write("##")
        if st.button("➕ Añadir"):
            stock_disp = int(df_stock.loc[df_stock['Producto'] == prod_sel, 'Stock'].values[0])
            if cant_sel <= stock_disp:
                precio = float(df_stock.loc[df_stock['Producto'] == prod_sel, 'Precio'].values[0])
                st.session_state.carrito.append({'Producto': prod_sel, 'Cantidad': cant_sel, 'Precio': precio, 'Subtotal': round(precio * cant_sel, 2)})
            else:
                st.error(f"¡Solo quedan {stock_disp}!")

if st.session_state.carrito:
    df_car = pd.DataFrame(st.session_state.carrito)
    st.table(df_car)
    total_car = df_car['Subtotal'].sum()
    st.markdown(f"### **TOTAL A COBRAR: S/ {total_car:.2f}**")
    
    # --- ORDEN DE PAGOS PERSONALIZADO ---
    v_metodo = st.radio(
        "Seleccione Método de Pago:",
        ["💵 Efectivo", "🟢 Yape", "🟣 Plin"], 
        horizontal=True
    )
    
    cv1, cv2 = st.columns(2)
    with cv1:
        if st.button("🚀 PROCESAR VENTA", type="primary", use_container_width=True): st.session_state.confirmar = True
    with cv2:
        if st.button("🗑️ VACÍAR", use_container_width=True): st.session_state.carrito = []; st.rerun()

    if st.session_state.confirmar:
        st.warning(f"¿Confirmar cobro en {v_metodo} por S/ {total_car:.2f}?")
        if st.button("✅ SÍ, FINALIZAR"):
            f, h, _ = obtener_tiempo_peru()
            for item in st.session_state.carrito:
                res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                n_stock = int(res['Item']['Stock']) - item['Cantidad']
                tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': n_stock})
                id_v = f"V-{f.replace('/','')}-{h.replace(':','')}-{item['Producto'][:3]}"
                tabla_ventas.put_item(Item={'ID_Venta': id_v, 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': str(item['Subtotal']), 'Metodo': v_metodo})
            st.balloons(); st.session_state.carrito = []; st.session_state.confirmar = False; st.rerun()

st.divider()

# --- PANEL ADMIN CON FILTROS ---
if not st.session_state.autenticado:
    with st.expander("🔐 Acceso Administrador"):
        ingreso = st.text_input("Contraseña:", type="password")
        if st.button("Entrar"):
            if ingreso == admin_pass:
                st.session_state.autenticado = True
                st.rerun()
            else: st.error("Clave Incorrecta")
else:
    if st.button("🔓 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

    t1, t2 = st.tabs(["💰 Consultar Ventas", "📥 Mercadería e Ingresos"])
    
    with t1:
        _, _, ahora = obtener_tiempo_peru()
        fecha_busqueda = st.date_input("Seleccionar fecha para ver ventas:", ahora)
        f_formateada = fecha_busqueda.strftime("%d/%m/%Y")
        
        st.subheader(f"Ventas del día: {f_formateada}")
        ventas_all = tabla_ventas.scan().get('Items', [])
        df_ventas = pd.DataFrame([v for v in ventas_all if v['Fecha'] == f_formateada])
        
        if not df_ventas.empty:
            df_ventas['Total'] = pd.to_numeric(df_ventas['Total'])
            st.metric("RECAUDACIÓN", f"S/ {df_ventas['Total'].sum():.2f}")
            df_ventas = df_ventas.sort_values(by='Hora', ascending=False)
            st.dataframe(df_ventas[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
        else:
            st.info(f"No se encontraron ventas el {f_formateada}")

    with t2:
        st.write("### Registrar nueva llegada")
        with st.form("abastecer"):
            p_ab = st.selectbox("Producto:", df_stock['Producto'].tolist()) if not df_stock.empty else st.text_input("Nombre")
            c_ab = st.number_input("Cantidad nueva:", min_value=1)
            pr_ab = st.number_input("Precio venta actual (S/):", min_value=0.0)
            if st.form_submit_button("Guardar en Nube"):
                res = tabla_stock.get_item(Key={'Producto': p_ab})
                s_fin = (int(res['Item']['Stock']) if 'Item' in res else 0) + c_ab
                tabla_stock.put_item(Item={'Producto': p_ab, 'Stock': s_fin, 'Precio': str(pr_ab)})
                f, h, _ = obtener_tiempo_peru()
                tabla_auditoria.put_item(Item={'ID_Ingreso': f"IN-{f.replace('/','')}-{h.replace(':','')}", 'Fecha': f, 'Hora': h, 'Producto': p_ab, 'Cantidad_Entrante': int(c_ab), 'Stock_Resultante': int(s_fin), 'Precio_Fijado': str(pr_ab)})
                st.success("Inventario actualizado"); time.sleep(1); st.rerun()

        st.divider()
        st.write("### Historial de Ingresos")
        fecha_ing_busqueda = st.date_input("Ver ingresos de esta fecha:", ahora)
        f_ing_formateada = fecha_ing_busqueda.strftime("%d/%m/%Y")
        
        ing_raw = tabla_auditoria.scan().get('Items', [])
        df_ing = pd.DataFrame([i for i in ing_raw if i['Fecha'] == f_ing_formateada])
        
        if not df_ing.empty:
            df_ing = df_ing.dropna(axis=1, how='all').fillna('-')
            df_ing = df_ing.sort_values(by='Hora', ascending=False)
            st.dataframe(df_ing[['Hora', 'Producto', 'Cantidad_Entrante', 'Stock_Resultante', 'Precio_Fijado']], use_container_width=True, hide_index=True)
        else:
            st.info(f"No hubo ingresos de stock el {f_ing_formateada}")
