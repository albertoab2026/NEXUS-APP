import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

# 1. Configuración de Hora de Lima
zona_horaria = pytz.timezone('America/Lima')

st.set_page_config(page_title="Inventario Dental Pro - Alberto Ballarta", layout="wide")

# Estilo Adaptativo
st.markdown("""
    <style>
    .stDataFrame { border: 1px solid #464b5d; border-radius: 10px; }
    .footer-container {
        text-align: center; margin-top: 50px; padding: 20px;
        border-top: 2px solid #0056b3; background-color: rgba(128, 128, 128, 0.1);
        border-radius: 15px 15px 0 0;
    }
    .footer-name { font-size: 20px; font-weight: bold; color: #0056b3; }
    .strength-icon { font-size: 30px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦷 Sistema Dental - Control de Ventas")

# 2. Inicializar memorias
if 'df_memoria' not in st.session_state:
    st.session_state.df_memoria = pd.read_csv('inventario.csv')
    st.session_state.df_memoria['Stock_Actual'] = st.session_state.df_memoria['Stock_Inicial']

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

if 'historial_ventas' not in st.session_state:
    st.session_state.historial_ventas = []

if 'producto_anterior' not in st.session_state:
    st.session_state.producto_anterior = None

# 3. Mostrar Inventario
st.subheader("📋 Stock Disponible")
st.dataframe(st.session_state.df_memoria[['Producto', 'Stock_Actual', 'Precio_Venta']], use_container_width=True, hide_index=True)

st.divider()

# 4. SECCIÓN: ARMAR EL PEDIDO
st.subheader("🛒 Armar Pedido")
c1, c2 = st.columns(2)

with c1:
    prod_sel = st.selectbox("Selecciona producto:", st.session_state.df_memoria['Producto'])

if prod_sel != st.session_state.producto_anterior:
    st.session_state.cant_input = 1
    st.session_state.producto_anterior = prod_sel

with c2:
    cant_sel = st.number_input("Cantidad:", min_value=1, key="cant_input")

if st.button("➕ Agregar al Carrito", type="primary"):
    # REGLA DE ORO: No dejar agregar al carrito más de lo que hay en stock actual
    idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == prod_sel].index[0]
    stock_disponible = st.session_state.df_memoria.at[idx, 'Stock_Actual']
    
    if cant_sel <= stock_disponible:
        precio_v = st.session_state.df_memoria.at[idx, 'Precio_Venta']
        st.session_state.carrito.append({
            "Producto": prod_sel,
            "Cant": cant_sel,
            "Subtotal": cant_sel * precio_v
        })
        st.rerun()
    else:
        st.error(f"❌ No puedes agregar {cant_sel}. Solo quedan {stock_disponible} en stock.")

# --- GESTIÓN DEL CARRITO ---
if st.session_state.carrito:
    st.write("### 📝 Artículos en el Carrito:")
    df_carrito = pd.DataFrame(st.session_state.carrito)
    st.dataframe(df_carrito, use_container_width=True, hide_index=True)
    
    total_carrito = df_carrito['Subtotal'].sum()
    st.write(f"### **Total a Cobrar: S/ {total_carrito:,.2f}**")
    
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
    with col_btn1:
        metodo_pago = st.selectbox("Método de Pago:", ["Efectivo", "Yape", "Plin", "Transferencia"])
    with col_btn2:
        if st.button("↩️ Borrar último", use_container_width=True):
            if st.session_state.carrito:
                st.session_state.carrito.pop()
                st.rerun()
    with col_btn3:
        if st.button("🗑️ Vaciar todo", use_container_width=True):
            st.session_state.carrito = []
            st.rerun()

    if st.button("🚀 REGISTRAR VENTA FINAL", type="primary", use_container_width=True):
        # Doble verificación antes de descontar
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

# 5. CIERRE DE CAJA
if st.button("🔴 VER RECAUDACIÓN DEL DÍA", use_container_width=True):
    if st.session_state.historial_ventas:
        st.header("💰 Resumen de Caja")
        df_final = pd.DataFrame(st.session_state.historial_ventas)
        st.dataframe(df_final, use_container_width=True, hide_index=True)
        
        resumen_pago = df_final.groupby('Pago')['Total'].sum().reset_index()
        st.write("### Por tipo de pago:")
        st.dataframe(resumen_pago, use_container_width=True, hide_index=True)
        
        st.metric("TOTAL GENERAL", f"S/ {df_final['Total'].sum():,.2f}")
    else:
        st.warning("No hay ventas aún.")

# --- TU FIRMA FINAL 💪 ---
st.markdown(f"""
    <div class="footer-container">
        <div class="strength-icon">💪</div>
        <div style="color: #6c757d; font-size: 14px;">Desarrollado con esfuerzo por</div>
        <div class="footer-name">Alberto Ballarta</div>
        <div style="color: #6c757d; font-size: 13px; font-style: italic; margin-top: 5px;">
            Soluciones Cloud para Negocios Locales | 2026
        </div>
    </div>
    """, unsafe_allow_html=True)
