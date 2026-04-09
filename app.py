import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import pytz
import time
import io

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Gestión Dental Tío - PRO", layout="wide")

def obtener_tiempo_peru():
    tz_peru = pytz.timezone('America/Lima')
    ahora = datetime.now(tz_peru)
    return ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S")

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
    # Tabla para el rastro de cambios de stock
    tabla_auditoria = dynamodb.Table('EntradasInventario') 
except Exception as e:
    st.error(f"Error AWS: {e}")
    st.stop()

# ESTADOS DE SESIÓN
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'confirmar' not in st.session_state: st.session_state.confirmar = False

# CARGAR STOCK
try:
    items = tabla_stock.scan().get('Items', [])
    df_stock = pd.DataFrame(items) if items else pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])
except:
    df_stock = pd.DataFrame(columns=['Producto', 'Stock', 'Precio'])

st.title("🦷 Sistema Dental: Control Total")

# --- SECCIÓN A: INVENTARIO ---
with st.expander("📦 Ver Stock Disponible"):
    if not df_stock.empty:
        df_stock['Stock'] = pd.to_numeric(df_stock['Stock'])
        st.dataframe(df_stock[['Producto', 'Stock', 'Precio']], use_container_width=True, hide_index=True)

st.divider()

# --- SECCIÓN B: CARRITO Y BLOQUEO DE STOCK ---
st.subheader("🛒 Punto de Venta")
if not df_stock.empty:
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        prod_sel = st.selectbox("Elegir Producto:", df_stock['Producto'].tolist())
    with c2:
        cant_sel = st.number_input("Cantidad:", min_value=1, value=1)
    with c3:
        st.write("##")
        if st.button("➕ Añadir"):
            stock_disp = int(df_stock.loc[df_stock['Producto'] == prod_sel, 'Stock'].values[0])
            if cant_sel <= stock_disp:
                precio = float(df_stock.loc[df_stock['Producto'] == prod_sel, 'Precio'].values[0])
                st.session_state.carrito.append({
                    'Producto': prod_sel, 'Cantidad': cant_sel,
                    'Precio': precio, 'Subtotal': round(precio * cant_sel, 2)
                })
                st.session_state.confirmar = False
            else:
                st.error(f"❌ Solo hay {stock_disp} en stock.")

if st.session_state.carrito:
    df_car = pd.DataFrame(st.session_state.carrito)
    st.table(df_car)
    total_car = df_car['Subtotal'].sum()
    st.markdown(f"### **TOTAL: S/ {total_car:.2f}**")
    v_metodo = st.radio("Método de Pago:", ["Yape", "Plin", "Efectivo"], horizontal=True)
    
    cv1, cv2 = st.columns(2)
    with cv1:
        if st.button("🚀 PROCESAR VENTA", use_container_width=True, type="primary"):
            st.session_state.confirmar = True
    with cv2:
        if st.button("🗑️ VACÍAR", use_container_width=True):
            st.session_state.carrito = []
            st.rerun()

    if st.session_state.confirmar:
        st.warning("⚠️ ¿Confirmar transacción?")
        if st.button("✅ SÍ, FINALIZAR"):
            try:
                fecha, hora = obtener_tiempo_peru()
                for item in st.session_state.carrito:
                    # Descontar
                    res = tabla_stock.get_item(Key={'Producto': item['Producto']})
                    nuevo_s = int(res['Item']['Stock']) - item['Cantidad']
                    tabla_stock.update_item(Key={'Producto': item['Producto']}, UpdateExpression="set Stock = :s", ExpressionAttributeValues={':s': nuevo_s})
                    
                    # Venta
                    id_v = f"V-{fecha.replace('/','')}-{hora.replace(':','')}-{item['Producto'][:3]}"
                    tabla_ventas.put_item(Item={
                        'ID_Venta': id_v, 'Fecha': fecha, 'Hora': hora,
                        'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']),
                        'Total': str(item['Subtotal']), 'Metodo': v_metodo
                    })
                st.balloons(); st.session_state.carrito = []; st.session_state.confirmar = False
                st.success("Venta Guardada"); time.sleep(1); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

st.write("##")
st.divider()

# --- SECCIÓN C: ADMIN CON REPORTE DETALLADO ---
with st.expander("🔐 PANEL DE ADMINISTRACIÓN"):
    password = st.text_input("Clave:", type="password")
    if password == admin_pass:
        fecha_hoy, _ = obtener_tiempo_peru()
        
        # 1. GANANCIAS EN TIEMPO REAL
        st.subheader(f"📊 Reporte de Hoy: {fecha_hoy}")
        ventas_raw = tabla_ventas.scan().get('Items', [])
        df_hoy = pd.DataFrame([v for v in ventas_raw if v['Fecha'] == fecha_hoy])
        
        if not df_hoy.empty:
            df_hoy['Total'] = pd.to_numeric(df_hoy['Total'])
            st.metric("GANANCIA TOTAL", f"S/ {df_hoy['Total'].sum():.2f}")
            # AQUÍ SE VE EL DETALLE QUE PEDISTE
            st.write("#### Detalle de lo vendido hoy:")
            st.dataframe(df_hoy[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']], use_container_width=True, hide_index=True)
        else: st.info("No hay ventas aún.")

        st.divider()

        # 2. GESTIÓN DE MERCADERÍA CON HISTORIAL
        st.subheader("📥 Registro de Stock (Llegada de productos)")
        with st.form("abastecimiento"):
            f_p = st.selectbox("Elegir Producto:", df_stock['Producto'].tolist()) if not df_stock.empty else st.text_input("Nombre")
            f_cant_llegada = st.number_input("Cantidad que está entrando:", min_value=1)
            f_precio_nuevo = st.number_input("Precio de Venta actual:", min_value=0.0)
            
            if st.form_submit_button("💾 REGISTRAR LLEGADA"):
                # Obtener stock actual antes de sumar
                res = tabla_stock.get_item(Key={'Producto': f_p})
                stock_previo = int(res['Item']['Stock']) if 'Item' in res else 0
                stock_final = stock_previo + f_cant_llegada
                
                # 1. Actualizar Stock
                tabla_stock.put_item(Item={'Producto': f_p, 'Stock': int(stock_final), 'Precio': str(f_precio_nuevo)})
                
                # 2. Guardar en Auditoría (El rastro que pediste)
                fecha, hora = obtener_tiempo_peru()
                tabla_auditoria.put_item(Item={
                    'ID_Ingreso': f"IN-{fecha.replace('/','')}-{hora.replace(':','')}",
                    'Fecha': fecha,
                    'Hora': hora,
                    'Producto': f_p,
                    'Cantidad_Entrante': int(f_cant_llegada),
                    'Stock_Resultante': int(stock_final),
                    'Precio_Fijado': str(f_precio_nuevo)
                })
                st.success(f"Stock de {f_p} actualizado. Ahora hay {stock_final} unidades."); time.sleep(1); st.rerun()

        # Mostrar historial de cambios de stock
        if st.checkbox("Ver historial de cambios en el inventario"):
            ingresos = tabla_auditoria.scan().get('Items', [])
            if ingresos:
                st.write("#### Rastro de llegada de mercadería:")
                st.dataframe(pd.DataFrame(ingresos).sort_values('Hora', ascending=False), use_container_width=True)
