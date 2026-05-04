import streamlit as st
from datetime import date
import db

st.set_page_config(layout="wide", page_title="NEXUS V.4")
tenant_id = "BALLARTA_DENTAL"
hoy = date.today().isoformat()

st.title("💰 NEXUS V.4")

st.write("DEBUG: AWS Keys cargadas:", "aws_access_key_id" in st.secrets["aws"])
col1, col2 = st.columns(2)

with col1:
    if st.button("🔒 ABRIR CIERRE", use_container_width=True):
        if db.abrir_cierre(tenant_id, hoy):
            st.success("✅ Cierre abierto. Listo para cerrar")
            st.rerun()
        else:
            st.warning("⚠️ Ya hay un cierre abierto hoy")

with col2:
    if st.button("🔒 CERRAR CIERRE", use_container_width=True):
        cierre = db.obtener_cierre(tenant_id, hoy)
        if not cierre or cierre.get('Estado') != 'ABIERTO':
            st.error("❌ No hay un cierre abierto hoy. Abre uno primero.")
        else:
            st.session_state.mostrar_cerrar = True

if st.session_state.get('mostrar_cerrar', False):
    with st.form("cerrar_cierre_form"):
        st.subheader("Cerrar Cierre del Día")
        efectivo = st.number_input("💵 Efectivo del día", min_value=0.0, step=0.01, format="%.2f")
        yape = st.number_input("💜 Yape del día", min_value=0.0, step=0.01, format="%.2f")
        plin = st.number_input("🔵 Plin del día", min_value=0.0, step=0.01, format="%.2f")
        total = efectivo + yape + plin
        st.metric("TOTAL DEL DÍA", f"S/ {total:.2f}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("✅ Confirmar cierre"):
                db.cerrar_cierre(tenant_id, hoy, efectivo, yape, plin)
                st.success("✅ Cierre cerrado. Total guardado.")
                st.session_state.mostrar_cerrar = False
                st.rerun()
        with col2:
            if st.form_submit_button("❌ Cancelar"):
                st.session_state.mostrar_cerrar = False
                st.rerun()
