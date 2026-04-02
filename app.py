import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. Configuración y Hora Perú
st.set_page_config(page_title="Inventario Dental Pro", layout="wide")
st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 SISTEMA DENTAL - ALBERTO BALLARTA</h1>", unsafe_allow_html=True)

def obtener_hora_peru():
    return (datetime.utcnow() - timedelta(hours=5)).strftime("%H:%M:%S")

# 2. Inicializar Datos (Solo si no existen)
if 'df_memoria' not in st.session_state:
    st.session_state.df_memoria = pd.DataFrame({
        "Producto": ["Resina Z350", "Guantes Nitrilo", "Adhesivo Dental", "Algodón en rollo"],
        "Stock_Actual": [10, 40, 5, 30],
        "Precio_Venta": [85.0, 25.0, 120.0, 10.0]
    })
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'ventas_dia' not in st.session_state: st.session_state.ventas_dia = []

# 3. Mostrar Stock (TABLA FIJA)
st.subheader("📋 Control de Stock Actual")
df_mostrar = st.session_state.df_memoria.copy()
# Evitar que muestre negativos visualmente antes de corregir
df_mostrar['Stock_Actual'] = df_mostrar['Stock_Actual'].clip(lower=0)
df_mostrar['Precio_Venta'] = df_mostrar['Precio_Venta'].map('S/ {:,.2f}'.format)
st.table(df_mostrar)

st.divider()

# 4. Armar Pedido
st.subheader("🛒 Armar Pedido del Cliente")
c1, c2 = st.columns(2)
with c1:
    prod_sel = st.selectbox("Selecciona Producto:", st.session_state.df_memoria["Producto"])
with c2:
    if 'c_reset' not in st.session_state: st.session_state.c_reset = 1
    cant_sel = st.number_input("Cantidad:", min_value=1, value=st.session_state.c_reset, key="input_c")

if st.button("➕ Agregar al Carrito", type="primary"):
    idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == prod_sel].index[0]
    stock_dispo = st.session_state.df_memoria.at[idx, 'Stock_Actual']
    
    if cant_sel > stock_dispo:
        st.error(f"⚠️ ¡STOCK INSUFICIENTE! Solo quedan {stock_dispo} unidades.")
    else:
        precio = st.session_state.df_memoria.at[idx, 'Precio_Venta']
        st.session_state.carrito.append({"Producto": prod_sel, "Cant": cant_sel, "Subtotal": cant_sel * precio})
        st.success(f"✅ {prod_sel} añadido.")
        st.session_state.c_reset = 1
        st.rerun()

# 5. Botón: VENTA DEL CLIENTE (Detalle actual)
if st.session_state.carrito:
    st.divider()
    st.subheader("📝 VENTA DEL CLIENTE (Detalle)")
    df_car = pd.DataFrame(st.session_state.carrito)
    st.dataframe(df_car, use_container_width=True)
    
    total_cliente = df_car['Subtotal'].sum()
    st.write(f"### Total a Cobrar: S/ {total_cliente:,.2f}")
    
    metodo = st.selectbox("Método de Pago:", ["Efectivo", "Yape", "Plin"])

    if st.button("🚀 FINALIZAR VENTA DEL CLIENTE", type="primary"):
        # Restar stock de verdad
        for item in st.session_state.carrito:
            idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == item['Producto']].index[0]
            st.session_state.df_memoria.at[idx, 'Stock_Actual'] -= item['Cant']
        
        # Guardar en el histórico del día
        st.session_state.ventas_dia.append({
            "Venta N°": len(st.session_state.ventas_dia) + 1,
            "Hora": obtener_hora_peru(),
            "Total": total_cliente,
            "Pago": metodo
        })
        st.session_state.carrito = [] # Limpiar para el siguiente cliente
        st.balloons()
        st.rerun()

    if st.button("🗑️ Cancelar Pedido"):
        st.session_state.carrito = []
        st.rerun()

# 6. Botón: RECAUDACIÓN DEL DÍA (Oculto por defecto para orden)
st.divider()
with st.expander("📊 VER RECAUDACIÓN TOTAL DEL DÍA"):
    if st.session_state.ventas_dia:
        df_v = pd.DataFrame(st.session_state.ventas_dia)
        st.metric("GANANCIA TOTAL", f"S/ {df_v['Total'].sum():,.2f}")
        st.dataframe(df_v, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay ventas cerradas hoy.")

st.markdown(f"<p style='text-align: center; color: #666;'>💪 Alberto Ballarta | Cloud Solution 2026</p>", unsafe_allow_html=True)
