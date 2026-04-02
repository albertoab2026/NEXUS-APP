import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. Configuración y Hora Perú
st.set_page_config(page_title="Inventario Dental Pro", layout="wide")
st.markdown("<h1 style='text-align: center; color: #00acc1;'>🦷 SISTEMA DENTAL - ALBERTO BALLARTA</h1>", unsafe_allow_html=True)

def obtener_hora_peru():
    # Ajuste manual para el servidor de Streamlit (UTC-5)
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

# 3. Mostrar Stock (Fijo y ordenado)
st.subheader("📋 Control de Stock Actual")
df_vis = st.session_state.df_memoria.copy()
# Evitar negativos visuales en la tabla principal
df_vis['Stock_Actual'] = df_vis['Stock_Actual'].apply(lambda x: x if x > 0 else 0)
df_vis['Precio_Venta'] = df_vis['Precio_Venta'].map('S/ {:,.2f}'.format)
st.table(df_vis)

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
        st.error(f"❌ No puedes agregar esto. Solo quedan {stock_real} unidades en stock.")
    else:
        precio = st.session_state.df_memoria.at[idx, 'Precio_Venta']
        st.session_state.carrito.append({"Producto": prod_sel, "Cant": cant_sel, "Subtotal": cant_sel * precio})
        st.success(f"✅ {prod_sel} añadido al carrito.")
        st.session_state.c_reset = 1
        st.rerun()

# 5. Venta del Cliente (Sección Detalle)
if st.session_state.carrito:
    st.divider()
    st.subheader("📝 Detalle de Compra del Cliente")
    df_car = pd.DataFrame(st.session_state.carrito)
    # Formato soles en el carrito
    df_car_soles = df_car.copy()
    df_car_soles['Subtotal'] = df_car_soles['Subtotal'].map('S/ {:,.2f}'.format)
    st.dataframe(df_car_soles, use_container_width=True, hide_index=True)
    
    total_pedido = df_car['Subtotal'].sum()
    st.info(f"### TOTAL VENTA CLIENTE: S/ {total_pedido:,.2f}")
    
    metodo = st.selectbox("Método de Pago:", ["Efectivo", "Yape", "Plin"])

    if st.button("🚀 FINALIZAR VENTA DEL CLIENTE", type="primary", use_container_width=True):
        # VALIDACIÓN FINAL DE STOCK (Seguro anti-negativos)
        puedo_vender = True
        for item in st.session_state.carrito:
            idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == item['Producto']].index[0]
            if st.session_state.df_memoria.at[idx, 'Stock_Actual'] < item['Cant']:
                st.error(f"❌ Error crítico: El producto {item['Producto']} se agotó mientras armabas el pedido.")
                puedo_vender = False
                break
        
        if puedo_vender:
            # Descontar de verdad
            for item in st.session_state.carrito:
                idx = st.session_state.df_memoria[st.session_state.df_memoria['Producto'] == item['Producto']].index[0]
                st.session_state.df_memoria.at[idx, 'Stock_Actual'] -= item['Cant']
            
            # Guardar en histórico
            st.session_state.ventas_dia.append({
                "Venta N°": len(st.session_state.ventas_dia) + 1,
                "Hora": obtener_hora_peru(),
                "Total": total_pedido,
                "Pago": metodo
            })
            st.session_state.carrito = [] # Limpiar carrito para el siguiente cliente
            st.balloons()
            st.rerun()

    if st.button("🗑️ Borrar Pedido Actual"):
        st.session_state.carrito = []
        st.rerun()

# 6. Recaudación Total del Día (Botón Grande)
st.divider()
if st.button("💰 VER RECAUDACIÓN TOTAL DEL DÍA", use_container_width=True):
    if st.session_state.ventas_dia:
        df_v = pd.DataFrame(st.session_state.ventas_dia)
        total_ganancia = df_v['Total'].sum()
        st.success(f"## GANANCIA TOTAL DEL DÍA: S/ {total_ganancia:,.2f}")
        # Formatear la tabla de recaudación
        df_v_soles = df_v.copy()
        df_v_soles['Total'] = df_v_soles['Total'].map('S/ {:,.2f}'.format)
        st.dataframe(df_v_soles, use_container_width=True, hide_index=True)
    else:
        st.warning("Todavía no se han cerrado ventas el día de hoy.")

st.markdown("<p style='text-align: center; color: #666;'>💪 Desarrollado por Alberto Ballarta | Carabayllo Cloud 2026</p>", unsafe_allow_html=True)
