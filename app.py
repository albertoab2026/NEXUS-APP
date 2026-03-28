import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

# Configuración de Hora de Lima
zona_horaria = pytz.timezone('America/Lima')

st.set_page_config(page_title="Inventario Dental Pro", layout="wide")
st.title("🦷 Sistema Dental - Control de Ventas")

# 1. Inicializar memorias
if 'df_memoria' not in st.session_state:
    st.session_state.df_memoria = pd.read_csv('inventario.csv')
    st.session_state.df_memoria['Stock_Actual'] = st.session_state.df_memoria['Stock_Inicial']

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

if 'historial_ventas' not in st.session_state:
    st.session_state.historial_ventas = []

# --- NUEVA LÓGICA DE RESETEO SIN AVISOS AMARILLOS ---
if 'producto_anterior' not in st.session_state:
    st.session_state.producto_anterior = None

# 2. Mostrar Inventario
st.subheader("📋 Stock en Tienda")
st.table(st.session_state.df_memoria[['Producto', 'Stock_Actual', 'Precio_Venta']])

st.divider()

# 3. SECCIÓN: ARMAR EL PEDIDO
st.subheader("🛒 Armar Pedido del Cliente")
c1, c2 = st.columns(2)

with c1:
    prod_sel = st.selectbox("Selecciona producto:", st.session_state.df_memoria['Producto'])

# Si el producto cambió, reseteamos la cantidad en la memoria
if prod_sel != st.session_state.producto_anterior:
    st.session_state.cant_input = 1
    st.session_state.producto_anterior = prod_sel

with c2:
    cant_sel = st.number_input("Cantidad:", min_value=1, key="cant_input")

if st.button("➕ Agregar al Carrito"):
    idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == prod_sel].index[0]
    precio_v = st.session_state.df_memoria.at[idx, 'Precio_Venta']
    
    st.session_state.carrito.append({
        "Producto": prod_sel,
        "Cant": cant_sel,
        "Subtotal": cant_sel * precio_v
    })
    st.toast(f"Agregado: {prod_sel}")
    st.rerun() # Para que se limpie la pantalla tras agregar

# --- GESTIÓN DEL CARRITO ---
if st.session_state.carrito:
    st.write("### 📝 Detalle del Pedido Actual:")
    df_carrito = pd.DataFrame(st.session_state.carrito)
    st.table(df_carrito)
    
    total_carrito = df_carrito['Subtotal'].sum()
    st.write(f"### **Total a Cobrar: S/ {total_carrito:,.2f}**")
    
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        metodo_pago = st.selectbox("Método de Pago:", ["Efectivo", "Yape", "Plin", "Transferencia"])
    with col_btn2:
        if st.button("↩️ Borrar último"):
            if st.session_state.carrito:
                st.session_state.carrito.pop()
                st.rerun()
    with col_btn3:
        if st.button("🗑️ Vaciar todo"):
            st.session_state.carrito = []
            st.rerun()

    if st.button("🚀 CONFIRMAR Y REGISTRAR VENTA FINAL"):
        for item in st.session_state.carrito:
            idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == item['Producto']].index[0]
            st.session_state.df_memoria.at[idx, 'Stock_Actual'] -= item['Cant']
            
            st.session_state.historial_ventas.append({
                "Hora": datetime.now(zona_horaria).strftime("%H:%M:%S"),
                "Producto": item['Producto'],
                "Cant": item['Cant'],
                "Total": item['Subtotal'],
                "Pago": metodo_pago
            })
        
        st.session_state.carrito = []
        st.success("¡Venta registrada con éxito!")
        st.balloons()
        st.rerun()

st.divider()

# 4. CIERRE DE CAJA
if st.button("🔴 VER RECAUDACIÓN DEL DÍA"):
    if st.session_state.historial_ventas:
        st.header("💰 Resumen de Caja Final")
        df_final = pd.DataFrame(st.session_state.historial_ventas)
        st.table(df_final)
        
        st.write("### Resumen por Pago:")
        resumen_pago = df_final.groupby('Pago')['Total'].sum()
        st.table(resumen_pago)
        
        st.metric("TOTAL GENERAL", f"S/ {df_final['Total'].sum():,.2f}")
    else:
        st.warning("No hay ventas en el historial.")
