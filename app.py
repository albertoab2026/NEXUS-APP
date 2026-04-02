import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuración y Estilo
st.set_page_config(page_title="Inventario Dental Pro", layout="wide")

st.markdown("""
    <h1 style='text-align: center; color: #00acc1;'>🦷 SISTEMA DENTAL - CONTROL DE VENTAS</h1>
    <p style='text-align: center; color: #666;'>Gestión Profesional Alberto Ballarta</p>
""", unsafe_allow_html=True)

# 2. Inicializar Memorias
if 'df_memoria' not in st.session_state:
    st.session_state.df_memoria = pd.DataFrame({
        "Producto": ["Resina Z350", "Guantes Nitrilo", "Adhesivo Dental", "Algodón en rollo"],
        "Stock_Actual": [10, 40, 5, 30],
        "Precio_Venta": [85.0, 25.0, 120.0, 10.0]
    })

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

if 'ventas_dia' not in st.session_state:
    st.session_state.ventas_dia = []

# 3. Mostrar Inventario
st.subheader("📋 Stock Disponible")
st.dataframe(st.session_state.df_memoria, use_container_width=True, hide_index=True)

st.divider()

# 4. Sección de Ventas (CON RESET DE CANTIDAD Y ERROR SIMPLIFICADO)
st.subheader("🛒 Armar Pedido")
col1, col2 = st.columns(2)

with col1:
    prod_sel = st.selectbox("Selecciona producto:", st.session_state.df_memoria["Producto"])

with col2:
    # Usamos una clave (key) para poder resetear este número después
    cant_sel = st.number_input("Cantidad:", min_value=1, value=1, key="input_cantidad")

if st.button("➕ Agregar al Carrito", type="primary"):
    idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == prod_sel].index[0]
    stock_disponible = st.session_state.df_memoria.at[idx, 'Stock_Actual']
    
    if cant_sel > stock_disponible:
        # MENSAJE DE ERROR MÁS FÁCIL Y DIRECTO
        st.error(f"⚠️ No hay stock suficiente. Solo quedan {stock_disponible} unidades de {prod_sel}.")
    else:
        precio = st.session_state.df_memoria.at[idx, 'Precio_Venta']
        st.session_state.carrito.append({
            "Producto": prod_sel, 
            "Cant": cant_sel, 
            "Subtotal": cant_sel * precio
        })
        st.success(f"✅ {prod_sel} añadido.")
        
        # EL TRUCO PARA QUE EL NÚMERO VUELVA A 1
        st.session_state.input_cantidad = 1 
        st.rerun()

# 5. Gestión del Carrito
if st.session_state.carrito:
    st.subheader("📝 Artículos en el Carrito")
    df_car = pd.DataFrame(st.session_state.carrito)
    st.table(df_car)
    
    total = df_car['Subtotal'].sum()
    st.write(f"### Total a Cobrar: S/ {total}")
    
    metodo = st.selectbox("Método de Pago:", ["Efectivo", "Yape", "Plin", "Transferencia"])
    
    if st.button("🚀 REGISTRAR VENTA FINAL"):
        for item in st.session_state.carrito:
            idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == item['Producto']].index[0]
            st.session_state.df_memoria.at[idx, 'Stock_Actual'] -= item['Cant']
        
        st.session_state.ventas_dia.append({"Total": total, "Metodo": metodo, "Fecha": datetime.now().strftime("%H:%M")})
        st.session_state.carrito = [] 
        st.balloons()
        st.rerun()

st.divider()

# 6. Recaudación y Firma
st.subheader("💰 Recaudación del Día")
if st.session_state.ventas_dia:
    df_ventas = pd.DataFrame(st.session_state.ventas_dia)
    total_dia = df_ventas['Total'].sum()
    st.metric("GANANCIA TOTAL", f"S/ {total_dia}")
    st.table(df_ventas)

st.markdown(f"""
    <div style='text-align: center; color: #00796b;'>
        <p>💪 Desarrollado con esfuerzo por</p>
        <h3>Alberto Ballarta</h3>
        <p>Soluciones Cloud para Negocios Locales | 2026</p>
    </div>
""", unsafe_allow_html=True)
