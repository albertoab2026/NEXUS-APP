import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. Configuración y Hora Perú (UTC-5)
st.set_page_config(page_title="Inventario Dental Pro", layout="wide")
st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 SISTEMA DENTAL - ALBERTO BALLARTA</h1>", unsafe_allow_html=True)

def obtener_hora_peru():
    return (datetime.utcnow() - timedelta(hours=5)).strftime("%H:%M:%S")

# 2. Inicializar Datos
if 'df_memoria' not in st.session_state:
    st.session_state.df_memoria = pd.DataFrame({
        "Producto": ["Resina Z350", "Guantes Nitrilo", "Adhesivo Dental", "Algodón en rollo"],
        "Stock_Actual": [10, 40, 5, 30],
        "Precio_Venta": [85.0, 25.0, 120.0, 10.0]
    })
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'ventas_dia' not in st.session_state: st.session_state.ventas_dia = []

# 3. Mostrar Stock (Limpio y real)
st.subheader("📋 Control de Stock Actual")
df_mostrar = st.session_state.df_memoria.copy()
df_mostrar['Precio_Venta'] = df_mostrar['Precio_Venta'].map('S/ {:,.2f}'.format)
st.table(df_mostrar)

st.divider()

# 4. Armar Pedido del Cliente
st.subheader("🛒 Armar Pedido del Cliente")
c1, c2 = st.columns(2)
with c1:
    prod_sel = st.selectbox("Selecciona Producto:", st.session_state.df_memoria["Producto"])
with c2:
    if 'c_reset' not in st.session_state: st.session_state.c_reset = 1
    cant_sel = st.number_input("Cantidad:", min_value=1, value=st.session_state.c_reset, key="input_c")

if st.button("➕ Agregar al Carrito", type="primary"):
    idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == prod_sel].index[0]
    stock_real = st.session_state.df_memoria.at[idx, 'Stock_Actual']
    
    if cant_sel > stock_real:
        # MENSAJE CORREGIDO: Muestra el stock real que queda
        st.error(f"⚠️ ¡STOCK INSUFICIENTE! Solo puedes vender hasta {stock_real} unidades de {prod_sel}.")
    else:
        precio = st.session_state.df_memoria.at[idx, 'Precio_Venta']
        st.session_state.carrito.append({"Producto": prod_sel, "Cant": cant_sel, "Subtotal": cant_sel * precio})
        st.success(f"✅ {prod_sel} añadido.")
        st.session_state.c_reset = 1
        st.rerun()

# 5. Detalle de la Venta del Cliente
if st.session_state.carrito:
    st.divider()
    st.subheader("📝 VENTA ACTUAL")
    df_car = pd.DataFrame(st.session_state.carrito)
    st.dataframe(df_car, use_container_width=True)
    
    total_cliente = df_car['Subtotal'].sum()
    st.write(f"## Total a Cobrar: S/ {total_cliente:,.2f}")
    
    metodo = st.selectbox("Método de Pago:", ["Efectivo", "Yape", "Plin"])

    if st.button("🚀 FINALIZAR VENTA DEL CLIENTE", type="primary", use_container_width=True):
        # Descontar stock
        for item in st.session_state.carrito:
            idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == item['Producto']].index[0]
            st.session_state.df_memoria.at[idx, 'Stock_Actual'] -= item['Cant']
        
        # Registrar con hora exacta de Perú
        st.session_state.ventas_dia.append({
            "Venta N°": len(st.session_state.ventas_dia) + 1,
            "Hora": obtener_hora_peru(),
            "Total": total_cliente,
            "Pago": metodo
        })
        st.session_state.carrito = []
        st.balloons()
        st.rerun()

# 6. RECAUDACIÓN DEL DÍA (Botón Grande)
st.divider()
st.subheader("📊 Resumen General")
if st.button("🔎 MOSTRAR RECAUDACIÓN TOTAL DEL DÍA", use_container_width=True):
    if st.session_state.ventas_dia:
        df_v = pd.DataFrame(st.session_state.ventas_dia)
        st.success(f"### GANANCIA TOTAL: S/ {df_v['Total'].sum():,.2f}")
        st.dataframe(df_v, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no se han registrado ventas hoy.")

st.markdown("<p style='text-align: center; color: #666;'>💪 Desarrollado por Alberto Ballarta | Carabayllo Cloud 2026</p>", unsafe_allow_html=True)
