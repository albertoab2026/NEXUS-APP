import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. Configuración y Hora Perú
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

# 3. Mostrar Stock (Siempre Real)
st.subheader("📋 Control de Stock Actual")
df_vis = st.session_state.df_memoria.copy()
df_vis['Precio_Venta'] = df_vis['Precio_Venta'].map('S/ {:,.2f}'.format)
st.table(df_vis)

st.divider()

# 4. Armar Pedido (CON RESET DE CANTIDAD FORZADO)
st.subheader("🛒 Armar Pedido del Cliente")
c1, c2 = st.columns(2)

with c1:
    prod_sel = st.selectbox("Selecciona Producto:", st.session_state.df_memoria["Producto"])

with c2:
    # Usamos una clave dinámica para forzar que el número vuelva a 1
    if "contador_reset" not in st.session_state:
        st.session_state.contador_reset = 0
    
    cant_sel = st.number_input(
        "Cantidad:", 
        min_value=1, 
        value=1, 
        key=f"input_cant_{st.session_state.contador_reset}"
    )

if st.button("➕ Agregar al Carrito", type="primary"):
    idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == prod_sel].index[0]
    
    # Calculamos cuánto stock queda "libre" (Stock real menos lo que ya está en el carrito)
    ya_en_carrito = sum(item['Cant'] for item in st.session_state.carrito if item['Producto'] == prod_sel)
    stock_disponible_real = st.session_state.df_memoria.at[idx, 'Stock_Actual'] - ya_en_carrito
    
    if cant_sel > stock_disponible_real:
        st.error(f"❌ ¡ERROR! No puedes agregar {cant_sel}. En el estante quedan {st.session_state.df_memoria.at[idx, 'Stock_Actual']} y ya tienes {ya_en_carrito} en el carrito.")
    else:
        precio = st.session_state.df_memoria.at[idx, 'Precio_Venta']
        st.session_state.carrito.append({"Producto": prod_sel, "Cant": cant_sel, "Subtotal": cant_sel * precio})
        st.success(f"✅ {prod_sel} añadido.")
        # FORZAMOS EL RESET DE LA CANTIDAD A 1
        st.session_state.contador_reset += 1
        st.rerun()

# 5. Venta del Cliente
if st.session_state.carrito:
    st.divider()
    st.subheader("📝 VENTA ACTUAL DEL CLIENTE")
    df_car = pd.DataFrame(st.session_state.carrito)
    
    # Formato soles en tabla de cliente
    df_car_v = df_car.copy()
    df_car_v['Subtotal'] = df_car_v['Subtotal'].map('S/ {:,.2f}'.format)
    st.dataframe(df_car_v, use_container_width=True, hide_index=True)
    
    total_ped = df_car['Subtotal'].sum()
    st.info(f"### TOTAL A COBRAR: S/ {total_ped:,.2f}")
    
    metodo = st.selectbox("Pago:", ["Efectivo", "Yape", "Plin"])

    if st.button("🚀 REGISTRAR VENTA FINAL", type="primary", use_container_width=True):
        # Descontar stock de la memoria
        for item in st.session_state.carrito:
            idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == item['Producto']].index[0]
            st.session_state.df_memoria.at[idx, 'Stock_Actual'] -= item['Cant']
        
        # Guardar en histórico con Soles
        st.session_state.ventas_dia.append({
            "Venta N°": len(st.session_state.ventas_dia) + 1,
            "Hora": obtener_hora_peru(),
            "Total": total_ped,
            "Pago": metodo
        })
        st.session_state.carrito = []
        st.balloons()
        st.rerun()

    if st.button("🗑️ Vaciar Carrito"):
        st.session_state.carrito = []
        st.rerun()

# 6. Recaudación del Día
st.divider()
if st.button("💰 MOSTRAR RECAUDACIÓN TOTAL DEL DÍA", use_container_width=True):
    if st.session_state.ventas_dia:
        df_v = pd.DataFrame(st.session_state.ventas_dia)
        st.success(f"## TOTAL GANADO HOY: S/ {df_v['Total'].sum():,.2f}")
        
        df_v_v = df_v.copy()
        df_v_v['Total'] = df_v_v['Total'].map('S/ {:,.2f}'.format)
        st.dataframe(df_v_v, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay ventas registradas todavía.")

st.markdown("<p style='text-align: center; color: #666;'>💪 Desarrollado por Alberto Ballarta | Carabayllo - Cloud 2026</p>", unsafe_allow_html=True)
