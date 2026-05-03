import streamlit as st
from datetime import date
import db

st.set_page_config(layout="wide", page_title="Cierre V.4")
tenant_id = "BALLARTA_DENTAL" # Esto viene del login, por ahora hardcodeado
hoy = date.today().isoformat()

st.title("💰 CIERRE FARMACIA V.4")
st.caption("Solo 3 botones. Sin Excel. Sin parches.")

if st.button("🔓 ABRIR CIERRE", use_container_width=True, type="primary"):
    if db.abrir_cierre(tenant_id, hoy):
        st.success("✅ Cierre abierto. Listo para ventas.")
    else:
        st.warning("⚠️ Ya hay un cierre abierto hoy")

if st.button("🔒 CERRAR CIERRE", use_container_width=True):
    efectivo = st.number_input("💵 Efectivo del día", min_value=0.0, step=1.0)
    yape = st.number_input("🟣 Yape del día", min_value=0.0, step=1.0)
    plin = st.number_input("🔵 Plin del día", min_value=0.0, step=1.0)
    total = efectivo + yape + plin
    st.metric("TOTAL DEL DÍA", f"S/ {total:.2f}")
    db.cerrar_cierre(tenant_id, hoy, efectivo, yape, plin)
    st.success("✅ Cierre cerrado. Total guardado.")

if st.button("📊 VER HISTORIAL", use_container_width=True):
    historial = db.obtener_historial(tenant_id)
    if historial:
        st.dataframe(historial, use_container_width=True)
    else:
        st.info("No hay cierres aún")
