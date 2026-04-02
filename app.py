import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. Configuración y Hora Perú
st.set_page_config(page_title="Inventario Dental Pro", layout="wide")
st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 CONTROL DE VENTAS - SISTEMA ALBERTO</h1>", unsafe_allow_html=True)

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

# 3. Mostrar Stock (Solo lectura)
st.subheader("📋 Stock Disponible")
df_vis = st.session_state.df_memoria.copy()
df_vis['Precio_Venta'] = df_vis['Precio_Venta'].map('S/ {:,.2f}'.format)
st.dataframe(df_vis, use_container_width=True, hide_index=True)

st.divider()

# 4. Sección de Pedido
st.subheader("🛒 Armar Pedido del Cliente")
c1, c2 = st.columns(2)
with c1:
    prod_sel = st.selectbox("Producto:", st.session_state.df_memoria["Producto"])
with c2:
    if 'c_reset' not in st.session_state: st.session_state.c_reset = 1
    cant_sel = st.number_input("Cantidad:", min_value=1, value=st.session_state.c_reset, key="input_cant")

if st.button("➕ Agregar al Carrito", type="primary"):
    idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == prod_sel].index[0]
    stock_ahora = st.session_state.df_memoria.at[idx, 'Stock_Actual']
    
    if cant_sel > stock_ahora:
        st.error(f"❌ ¡ERROR! No puedes vender {cant_sel}. Solo quedan {stock_ahora} unidades.")
    else:
        precio = st.session_state.df_memoria.at[idx, 'Precio_Venta']
        st.session_state.carrito.append({"Producto": prod_sel, "Cant": cant_sel, "Subtotal": cant_sel * precio})
        st.success(f"✅ Agregado: {prod_sel}")
        st.session_state.c_reset = 1
        st.rerun()

# 5. Carrito y Botón de Venta Final
if st.session_state.carrito:
    st.divider()
    st.subheader("📝 Detalle de Venta Actual")
    df_car = pd.DataFrame(st.session_state.carrito)
    st.table(df_car.style.format({"Subtotal": "S/ {:.2f}"}))
    
    total_cobrar = df_car['Subtotal'].sum()
    st.write(f"## TOTAL A COBRAR: S/ {total_cobrar:,.2f}")

    metodo = st.radio("Forma de Pago:", ["Efectivo", "Yape", "Plin"], horizontal=True)

    # BOTÓN DE VENTA FINAL CON SEGURO ANTI-NEGATIVO
    if st.button("✅ REGISTRAR VENTA AL CLIENTE", type="primary", use_container_width=True):
        error_stock = False
        # Verificación de último segundo antes de descontar
        for item in st.session_state.carrito:
            idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == item['Producto']].index[0]
            if st.session_state.df_memoria.at[idx, 'Stock_Actual'] < item['Cant']:
                error_stock = True
                break
        
        if error_stock:
            st.error("❌ La venta falló: Uno de los productos ya no tiene stock suficiente.")
        else:
            for item in st.session_state.carrito:
                idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == item['Producto']].index[0]
                st.session_state.df_memoria.at[idx, 'Stock_Actual'] -= item['Cant']
            
            st.session_state.ventas_dia.append({
                "Venta N°": len(st.session_state.ventas_dia) + 1,
                "Hora": obtener_hora_peru(),
                "Total": total_cobrar,
                "Pago": metodo
            })
            st.session_state.carrito = []
            st.balloons()
            st.rerun()

    if st.button("🗑️ Cancelar Todo el Carrito"):
        st.session_state.carrito = []
        st.rerun()

# 6. Recaudación Enumerada
st.divider()
if st.session_state.ventas_dia:
    st.subheader(f"💰 Resumen de Ventas - {obtener_hora_peru()}")
    df_final = pd.DataFrame(st.session_state.ventas_dia)
    st.metric("GANANCIA TOTAL DEL DÍA", f"S/ {df_final['Total'].sum():,.2f}")
    st.dataframe(df_final, use_container_width=True, hide_index=True)

st.markdown("<p style='text-align: center; color: #00796b;'>💪 Desarrollado por Alberto Ballarta | Cloud 2026</p>", unsafe_allow_html=True)
