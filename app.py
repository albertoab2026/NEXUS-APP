import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

zona_horaria = pytz.timezone('America/Lima')

st.set_page_config(page_title="Inventario Dental Pro", layout="wide")
st.title("🦷 Sistema Dental - Demo")

# 1. Inicializar memorias (Inventario, Carrito e Historial)
if 'df_memoria' not in st.session_state:
    st.session_state.df_memoria = pd.read_csv('inventario.csv')
    st.session_state.df_memoria['Stock_Actual'] = st.session_state.df_memoria['Stock_Inicial']

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

if 'historial_ventas' not in st.session_state:
    st.session_state.historial_ventas = []

# 2. Mostrar Inventario
st.subheader("📋 Stock Disponible")
st.table(st.session_state.df_memoria[['Producto', 'Stock_Actual', 'Precio_Venta']])

st.divider()

# 3. SECCIÓN: ARMAR EL PEDIDO (Carrito)
st.subheader("🛒 Armar Pedido")
c1, c2 = st.columns(2)
with c1:
    prod_sel = st.selectbox("Selecciona producto:", st.session_state.df_memoria['Producto'])
with c2:
    cant_sel = st.number_input("Cantidad:", min_value=1, value=1)

if st.button("➕ Agregar al Carrito"):
    idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == prod_sel].index[0]
    precio_v = st.session_state.df_memoria.at[idx, 'Precio_Venta']
    
    # Agregar a la lista temporal
    st.session_state.carrito.append({
        "Producto": prod_sel,
        "Cant": cant_sel,
        "Subtotal": cant_sel * precio_v
    })
    st.toast(f"{prod_sel} agregado")

# --- MOSTRAR CARRITO ACTUAL ---
if st.session_state.carrito:
    st.write("### 📝 Artículos en el carrito:")
    df_carrito = pd.DataFrame(st.session_state.carrito)
    st.table(df_carrito)
    
    total_carrito = df_carrito['Subtotal'].sum()
    st.write(f"**Total a pagar: S/ {total_carrito:,.2f}**")
    
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        metodo_pago = st.radio("Método de Pago:", ["Efectivo", "Yape", "Plin", "Transferencia"])
    
    with col_v2:
        if st.button("🗑️ Vaciar Carrito"):
            st.session_state.carrito = []
            st.rerun()

    if st.button("🚀 REGISTRAR VENTA FINAL"):
        # Al confirmar, restamos del stock de verdad y guardamos en el historial
        for item in st.session_state.carrito:
            idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == item['Producto']].index[0]
            st.session_state.df_memoria.at[idx, 'Stock_Actual'] -= item['Cant']
            
            # Guardar en historial con método de pago y hora
            st.session_state.historial_ventas.append({
                "Hora": datetime.now(zona_horaria).strftime("%H:%M:%S"),
                "Producto": item['Producto'],
                "Cant": item['Cant'],
                "Total": item['Subtotal'],
                "Pago": metodo_pago
            })
        
        st.session_state.carrito = [] # Limpiar carrito tras venta
        st.success("¡Venta registrada con éxito!")
        st.balloons()
        st.rerun()

st.divider()

# 4. CIERRE DE CAJA
if st.button("🔴 VER CIERRE DE CAJA"):
    if st.session_state.historial_ventas:
        st.header("💰 Resumen de Caja")
        df_final = pd.DataFrame(st.session_state.historial_ventas)
        st.table(df_final)
        st.metric("TOTAL RECAUDADO", f"S/ {df_final['Total'].sum():,.2f}")
    else:
        st.warning("No hay ventas registradas aún.")
