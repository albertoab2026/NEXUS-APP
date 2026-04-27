# -*- coding: utf-8 -*-
import streamlit as st
import boto3
import pandas as pd
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
import io
from fpdf import FPDF
import urllib.parse
import time
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

st.set_page_config(page_title="💎 Nexus - Sistema Empresarial", page_icon="💎", layout="wide")

# === CONFIG PLAN - CAMBIA AQUÍ ===
PLAN_ACTUAL = "PRO" # BASICO | PRO | PREMIUM
PRECIO_ACTUAL = 59
NUMERO_SOPORTE = "51964023239"
DESARROLLADOR = "⚙️ Desarrollado por Alberto"

MAX_PRODUCTOS = {"BASICO": 100, "PRO": 500, "PREMIUM": 2000}
MAX_STOCK_POR_PRODUCTO = 10000
MAX_PRODUCTOS_TOTALES = MAX_PRODUCTOS[PLAN_ACTUAL]

# === CONFIG UI ===
st.markdown("""
    <style>
        [data-testid="stButton"] button {height:60px;font-size:18px;font-weight:bold;border-radius:12px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);transition:all 0.2s ease;}
        [data-testid="stButton"] button:hover {transform:translateY(-2px);box-shadow:0 10px 15px -3px rgba(59,130,246,0.3);}
        button[kind="primary"] {background:linear-gradient(90deg,#3b82f6,#2563eb);color:white;}
        button[kind="secondary"] {background:linear-gradient(90deg,#f59e0b,#d97706);color:white;}
        [data-testid="stDataFrame"] {border-radius:12px;overflow:hidden;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);}
        [data-testid="stSidebar"] {background:linear-gradient(180deg,#3b82f6,#1e40af);}
        [data-testid="stSidebar"] * {color:white!important;}
    </style>
""", unsafe_allow_html=True)

# === FUNCIONES ===
def to_decimal(v):
    try:
        if isinstance(v, str) and v.strip() == '': return Decimal('0')
        return Decimal(str(v))
    except: return Decimal('0')

def obtener_tiempo_peru():
    tz_peru = ZoneInfo("America/Lima")
    ahora = datetime.now(tz_peru)
    return ahora.strftime('%d/%m/%Y'), ahora.strftime('%H:%M:%S'), ahora.strftime('%Y%m%d%H%M%S%f')

def tiene_whatsapp_habilitado():
    return PLAN_ACTUAL in ["PRO", "PREMIUM"]

# === DYNAMODB ===
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
tabla_stock = dynamodb.Table('nexus_stock')
tabla_ventas = dynamodb.Table('nexus_ventas')
tabla_movs = dynamodb.Table('nexus_movimientos')
tabla_cierres = dynamodb.Table('nexus_cierres')

def contarProductosEnBD():
    try:
        res = tabla_stock.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant), Select='COUNT')
        return res.get('Count', 0)
    except: return 0

def registrar_kardex(producto, cantidad, tipo, total, precio_compra, metodo):
    f, h, uid = obtener_tiempo_peru()
    mov = {'TenantID': st.session_state.tenant, 'MovimientoID': f"MOV-{uid}", 'Fecha': f, 'FechaISO': datetime.now(ZoneInfo("America/Lima")).strftime('%Y-%m-%d'), 'Hora': h, 'Producto': producto, 'Cantidad': int(cantidad), 'Tipo': tipo, 'Total': to_decimal(total), 'Precio_Compra': to_decimal(precio_compra), 'Metodo': metodo, 'Usuario': st.session_state.usuario}
    tabla_movs.put_item(Item=mov)

def registrar_cierre(total_ventas, usuario_turno, tipo_cierre, usuario_autoriza, fecha_cierre=None):
    f, h, uid = obtener_tiempo_peru()
    cierre = {'TenantID': st.session_state.tenant, 'CierreID': f"CIERRE-{uid}", 'Fecha': fecha_cierre if fecha_cierre else f, 'Hora': h, 'Total_Ventas': to_decimal(total_ventas), 'UsuarioTurno': usuario_turno, 'TipoCierre': tipo_cierre, 'UsuarioAutoriza': usuario_autoriza}
    tabla_cierres.put_item(Item=cierre)
# FIN PARTE 1/8
# === LOGIN MULTIUSUARIO ===
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.rol = None
    st.session_state.usuario = None
    st.session_state.tenant = None

if not st.session_state.autenticado:
    st.markdown(f"<h1 style='text-align:center;color:#3b82f6;font-size:4rem;'>💎 NEXUS</h1><h3 style='text-align:center;color:#6b7280;'>Sistema Empresarial - Plan {PLAN_ACTUAL}</h3>", unsafe_allow_html=True)
    with st.form("login"):
        st.subheader("🔐 Acceso Multiusuario")
        empresa = st.text_input("Empresa:", placeholder="Mi Negocio SAC").upper()
        usuario = st.text_input("Usuario:", placeholder="admin o vendedor1")
        password = st.text_input("Password:", type="password")
        if st.form_submit_button("🚀 ENTRAR", use_container_width=True):
            if empresa == "DENTAL" and usuario == "admin" and password == "admin123":
                st.session_state.autenticado = True
                st.session_state.rol = "DUEÑO"
                st.session_state.usuario = "admin"
                st.session_state.tenant = "DENTAL"
                st.rerun()
            elif empresa == "DENTAL" and usuario == "vendedor1" and password == "vend123":
                st.session_state.autenticado = True
                st.session_state.rol = "EMPLEADO"
                st.session_state.usuario = "vendedor1"
                st.session_state.tenant = "DENTAL"
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas")
    st.stop()

# === ESTADO ===
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'metodo_pago' not in st.session_state: st.session_state.metodo_pago = "💵 EFECTIVO"
if 'confirmar' not in st.session_state: st.session_state.confirmar = False
if 'boleta' not in st.session_state: st.session_state.boleta = None
# FIN PARTE 2/8
# === CARGA INVENTARIO ===
tz_peru = ZoneInfo("America/Lima")
res = tabla_stock.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant))
df_inv = pd.DataFrame(res.get('Items', []))
if not df_inv.empty:
    for col in ['Precio', 'Precio_Compra', 'Stock']:
        if col in df_inv.columns:
            df_inv[col] = pd.to_numeric(df_inv[col], errors='coerce').fillna(0)
    df_inv['Stock'] = df_inv['Stock'].astype(int)
    df_inv = df_inv.sort_values('Producto')

# === HEADER ===
col1, col2, col3 = st.columns([2, 3, 1])
with col1:
    st.markdown(f"<h1 style='margin:0;color:#3b82f6;'>💎 NEXUS</h1><p style='margin:0;color:#6b7280;'>Plan {PLAN_ACTUAL} | {st.session_state.rol}</p>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div style='background:linear-gradient(135deg,#f3f4f6,#e5e7eb);padding:20px;border-radius:16px;text-align:center;'><p style='margin:0;font-size:12px;color:#6b7280;'>USUARIO ACTIVO</p><h2 style='margin:5px 0;color:#1f2937;'>{st.session_state.usuario}</h2></div>", unsafe_allow_html=True)
with col3:
    if st.button("🚪 SALIR", use_container_width=True, key="btn_salir"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# === TABS SEGÚN ROL ===
if st.session_state.rol == "DUEÑO":
    tabs = st.tabs(["🛒 VENTA", "📊 INVENTARIO", "💰 CAJA", "📋 HISTORIAL", "📥 CARGAR", "🛠️ MANTENIMIENTO"])
else:
    tabs = st.tabs(["🛒 VENTA", "📊 INVENTARIO", "💰 CAJA", "📋 HISTORIAL"])
# FIN PARTE 3/8
# === TAB VENTA ===
with tabs[0]:
    f_hoy, h_hoy, _ = obtener_tiempo_peru()
    res_cierre = tabla_cierres.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant), FilterExpression=Attr('Fecha').eq(f_hoy) & Attr('UsuarioTurno').eq(st.session_state.usuario))
    ya_cerro = len(res_cierre.get('Items', [])) > 0
    hora_cierre = max([c['Hora'] for c in res_cierre.get('Items', [])]) if ya_cerro else None

    if ya_cerro:
        st.warning(f"⚠️ YA CERRASTE CAJA HOY A LAS {hora_cierre}")
        st.info("Las ventas que hagas ahora son POST-CIERRE. Se sumarán al reporte de mañana.")
        if st.button("🔓 REABRIR CAJA - SOLO DUEÑO", use_container_width=True, key="btn_reabrir_caja") and st.session_state.rol == "DUEÑO":
            for c in res_cierre.get('Items', []):
                tabla_cierres.delete_item(Key={'TenantID': st.session_state.tenant, 'CierreID': c['CierreID']})
            st.success("✅ Caja reabierta"); time.sleep(1); st.rerun()

    if st.session_state.boleta:
        b = st.session_state.boleta
        st.success("✅ VENTA REALIZADA")
        st.markdown(f"""<div style="background:white;color:black;padding:20px;border:2px solid #3b82f6;max-width:350px;margin:auto;font-family:monospace;border-radius:16px;box-shadow:0 10px 15px -3px rgba(59,130,246,0.3);">
            <h3 style="text-align:center;margin:0;color:#3b82f6;">{st.session_state.tenant}</h3>
            <p style="text-align:center;margin:0;">{b['fecha']} {b['hora']}</p><hr style="border-color:#3b82f6;">
            {''.join([f'<div style="display:flex;justify-content:space-between;"><span>{i["Cantidad"]}x {i["Producto"]}</span><span>S/{float(i["Subtotal"]):.2f}</span></div>' for i in b['items']])}
            <hr style="border-color:#3b82f6;"><div style="display:flex;justify-content:space-between;"><span>MÉTODO:</span><span>{b['metodo']}</span></div>
            <div style="display:flex;justify-content:space-between;color:#ef4444;"><span>DESC:</span><span>- S/{float(b['rebaja']):.2f}</span></div>
            <div style="display:flex;justify-content:space-between;font-size:18px;color:#3b82f6;"><b>NETO:</b><b>S/{float(b['t_neto']):.2f}</b></div>""", unsafe_allow_html=True)

        pdf = FPDF(orientation='P', unit='mm', format=(80, 200))
        pdf.add_page()
        pdf.set_font('Courier', 'B', 12)
        pdf.cell(0, 5, st.session_state.tenant, 0, 1, 'C')
        pdf.set_font('Courier', '', 8)
        pdf.cell(0, 4, f"{b['fecha']} {b['hora']}", 0, 1, 'C')
        pdf.cell(0, 2, '-'*40, 0, 1, 'C')
        for i in b['items']:
            nombre = str(i['Producto'])[:15]
            pdf.cell(40, 4, f"{i['Cantidad']}x {nombre}", 0, 0)
            pdf.cell(0, 4, f"S/{float(i['Subtotal']):.2f}", 0, 1, 'R')
        pdf.cell(0, 2, '-'*40, 0, 1, 'C')
        metodo_pdf = str(b['metodo']).replace('🟣 ', '').replace('🔵 ', '').replace('💵 ', '')
        pdf.cell(40, 4, f"METODO:", 0, 0)
        pdf.cell(0, 4, metodo_pdf, 0, 1, 'R')
        pdf.cell(40, 4, f"DESC:", 0, 0)
        pdf.cell(0, 4, f"- S/{float(b['rebaja']):.2f}", 0, 1, 'R')
        pdf.set_font('Courier', 'B', 10)
        pdf.cell(40, 5, f"NETO:", 0, 0)
        pdf.cell(0, 5, f"S/{float(b['t_neto']):.2f}", 0, 1, 'R')
        pdf_output = pdf.output(dest='S').encode('latin-1')

        df_boleta = pd.DataFrame(b['items'])
        df_boleta['Fecha'] = b['fecha']
        df_boleta['Hora'] = b['hora']
        df_boleta['Metodo'] = b['metodo']
        df_boleta['Descuento'] = float(b['rebaja'])
        df_boleta['Total_Neto'] = float(b['t_neto'])
        buf_excel = io.BytesIO()
        with pd.ExcelWriter(buf_excel, engine='openpyxl') as w:
            df_boleta[['Fecha', 'Hora', 'Producto', 'Cantidad', 'Precio', 'Subtotal', 'Metodo', 'Descuento', 'Total_Neto']].to_excel(w, index=False, sheet_name='Ticket')

        col1, col2 = st.columns(2)
        col1.download_button("📄 PDF 80mm", pdf_output, f"Ticket_{b['fecha'].replace('/','')}.pdf", "application/pdf", use_container_width=True, key="btn_pdf_boleta")
        col2.download_button("📊 EXCEL", buf_excel.getvalue(), f"Ticket_{b['fecha'].replace('/','')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="btn_excel_boleta")

        if tiene_whatsapp_habilitado():
            texto = f"*TICKET - {st.session_state.tenant}*\n{b['fecha']} {b['hora']}\n---\n" + "\n".join([f"{i['Cantidad']}x {i['Producto']} - S/{float(i['Subtotal']):.2f}" for i in b['items']]) + f"\n---\n*TOTAL: S/{float(b['t_neto']):.2f}*\nMetodo: {b['metodo']}"
            st.link_button("📲 WhatsApp", f"https://wa.me/?text={urllib.parse.quote(texto)}", use_container_width=True)
        if st.button("⬅️ NUEVA VENTA", use_container_width=True, key="btn_nueva_venta"): st.session_state.boleta = None; st.rerun()
    else:
        tab_vender, tab_ingreso_emp = st.tabs(["🛒 VENDER", "📦 INGRESAR MERCADERÍA"])

        with tab_vender:
            st.subheader("🛍️ Nueva Venta")
            busq = st.text_input("🔍 Buscar:", key="bv", placeholder="Escribe nombre del producto...").upper()
            ops = []
            for _, f in df_inv.iterrows():
                if busq in str(f['Producto']):
                    est = f"STOCK: {f['Stock']}" if f['Stock'] > 0 else "🚫 AGOTADO"
                    ops.append(f"{f['Producto']} | S/ {f['Precio']:.2f} | {est}")
            col1, col2 = st.columns([3, 1])
            if ops:
                sel = col1.selectbox("Producto:", ops, key="sel_v", placeholder="Busca y selecciona producto")
                p_sel = sel.split(" | ")[0] if sel else None
            else:
                st.info("👆 Escribe arriba para buscar productos")
                sel = None
                p_sel = None
            cant = col2.number_input("Cant:", min_value=1, value=1, key="cant_v")
            if p_sel:
                dp = df_inv[df_inv['Producto'] == p_sel].iloc[0]
                en_carro = sum(i['Cantidad'] for i in st.session_state.carrito if i['Producto'] == p_sel)
                disp = dp.Stock - en_carro
                st.info(f"Disponible: {disp}")
                if st.button("➕ Añadir", use_container_width=True, key="btn_add_carrito"):
                    if cant <= disp:
                        st.session_state.carrito.append({'Producto': p_sel, 'Cantidad': int(cant), 'Precio': to_decimal(dp.Precio), 'Precio_Compra': to_decimal(dp.Precio_Compra), 'Subtotal': to_decimal(dp.Precio) * int(cant)})
                        st.rerun()
                    else: st.error("❌ Sin stock")
            if st.session_state.carrito:
                for idx, item in enumerate(st.session_state.carrito):
                    c1, c2 = st.columns([3,1])
                    c1.write(f"{item['Producto']} x{item['Cantidad']}")
                    c2.write(f"S/{float(item['Subtotal']):.2f}")
                if st.button("🗑️ VACIAR", key="btn_vaciar_carrito"): st.session_state.carrito = []; st.rerun()

                st.write("**Método de Pago:**")
                col_ef, col_yape, col_plin = st.columns(3)

                with col_ef:
                    st.markdown("<div style='text-align:center;font-size:40px;'>💵</div>", unsafe_allow_html=True)
                    if st.button("EFECTIVO", use_container_width=True, type="primary" if st.session_state.metodo_pago=="💵 EFECTIVO" else "secondary", key="btn_efectivo"):
                        st.session_state.metodo_pago = "💵 EFECTIVO"
                        st.rerun()

                with col_yape:
                    st.markdown("<div style='text-align:center;font-size:40px;'>🟣</div>", unsafe_allow_html=True)
                    if st.button("YAPE", use_container_width=True, type="primary" if st.session_state.metodo_pago=="🟣 YAPE" else "secondary", key="btn_yape"):
                        st.session_state.metodo_pago = "🟣 YAPE"
                        st.rerun()

                with col_plin:
                    st.markdown("<div style='text-align:center;font-size:40px;'>🔵</div>", unsafe_allow_html=True)
                    if st.button("PLIN", use_container_width=True, type="primary" if st.session_state.metodo_pago=="🔵 PLIN" else "secondary", key="btn_plin"):
                        st.session_state.metodo_pago = "🔵 PLIN"
                        st.rerun()

                metodo = st.session_state.metodo_pago
                st.markdown(f"<h3 style='text-align:center;color:#3b82f6;'>Seleccionado: {metodo}</h3>", unsafe_allow_html=True)

                rebaja = st.number_input("💸 Descuento:", min_value=0.0, value=0.0, key="num_rebaja")
                total = max(Decimal('0.00'), sum(i['Subtotal'] for i in st.session_state.carrito) - to_decimal(rebaja))
                st.markdown(f"<h1 style='text-align:center;color:#3b82f6;font-size:3rem;'>S/ {float(total):.2f}</h1>", unsafe_allow_html=True)
                if st.button("🚀 FINALIZAR", use_container_width=True, type="primary", key="btn_finalizar"): st.session_state.confirmar = True
                if st.session_state.confirmar:
                    if st.button(f"✅ CONFIRMAR S/ {float(total):.2f}", use_container_width=True, key="btn_confirmar_venta"):
                        f, h, uid = obtener_tiempo_peru()
                        for item in st.session_state.carrito:
                            tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': item['Producto']}, UpdateExpression="SET Stock = Stock - :s", ConditionExpression="Stock >= :s", ExpressionAttributeValues={':s': item['Cantidad']})
                            tabla_ventas.put_item(Item={'TenantID': st.session_state.tenant, 'VentaID': f"V-{uid}", 'Fecha': f, 'Hora': h, 'Producto': item['Producto'], 'Cantidad': int(item['Cantidad']), 'Total': item['Subtotal'], 'Precio_Compra': item['Precio_Compra'], 'Metodo': metodo, 'Rebaja': to_decimal(rebaja), 'Usuario': st.session_state.usuario})
                            registrar_kardex(item['Producto'], item['Cantidad'], "VENTA", item['Subtotal'], item['Precio_Compra'], metodo)
                        st.session_state.boleta = {'items': st.session_state.carrito, 't_neto': total, 'rebaja': to_decimal(rebaja), 'metodo': metodo, 'fecha': f, 'hora': h}
                        st.session_state.carrito = []; st.session_state.confirmar = False; st.rerun()

        with tab_ingreso_emp:
            st.subheader("📦 Registrar Ingreso de Mercadería")
            st.caption("Registra lo que llegó de tu proveedor - Empleados pueden usar esta pestaña")

            if not df_inv.empty:
                prod_ingreso = st.selectbox("Producto que llegó:", df_inv['Producto'].tolist(), key="sel_ingreso_emp")

                if prod_ingreso:
                    df_prod = df_inv[df_inv['Producto'] == prod_ingreso].iloc[0]
                    ultimo_pc = float(df_prod['Precio_Compra'])
                    st.info(f"Stock actual: {int(df_prod['Stock'])} unidades | Último costo: S/{ultimo_pc:.2f} | Venta: S/{df_prod['Precio']:.2f}")

                    st.markdown("**📦 DATOS DE LA COMPRA:**")
                    col1, col2 = st.columns(2)
                    unidad_medida = col1.selectbox("Unidad:", ["Unidades", "Docenas", "Cajas", "Paquetes", "Millares"], key="unidad_medida_emp")
                    cantidad = col2.number_input(f"Cantidad:", min_value=1, value=1, key="cant_lote_emp")

                    multiplicador = {"Unidades": 1, "Docenas": 12, "Cajas": 1, "Paquetes": 1, "Millares": 1000}[unidad_medida]

                    if unidad_medida in ["Cajas", "Paquetes"]:
                        unid_x_bulto = st.number_input(f"¿Cuántas unidades trae cada {unidad_medida[:-1]}?", min_value=1, value=50, key="unid_bulto_emp")
                        multiplicador = unid_x_bulto

                    cant_ingreso = cantidad * multiplicador
                    costo_sugerido = ultimo_pc * cant_ingreso

                    usar_ultimo = st.checkbox(f"✓ Usar último costo: S/{ultimo_pc:.2f} c/u → Total: S/{costo_sugerido:.2f}", value=False, key="check_ultimo_emp")

                    if usar_ultimo:
                        precio_total_lote = costo_sugerido
                        st.success(f"✅ Usando último precio: S/{precio_total_lote:.2f}")
                    else:
                        precio_total_lote = st.number_input(f"Costo total S/:", min_value=0.0, value=0.0, key="precio_lote_emp", help="Lo que pagaste por todo según tu factura")

                    nuevo_pc = precio_total_lote / cant_ingreso if cant_ingreso > 0 else 0

                    st.success(f"✅ Total: {cant_ingreso} unidades | Costo unitario: S/{nuevo_pc:.2f}")
                    stock_final = int(df_prod['Stock']) + cant_ingreso
                    st.metric("Stock nuevo", f"{stock_final} unidades")

                    if st.button("📥 REGISTRAR", use_container_width=True, type="primary", key="btn_ingreso_stock_emp"):
                        if stock_final > MAX_STOCK_POR_PRODUCTO:
                            st.error(f"❌ Stock máximo: {MAX_STOCK_POR_PRODUCTO}")
                        else:
                            stock_viejo = int(df_prod['Stock'])
                            pc_viejo = float(df_prod['Precio_Compra'])
                            pc_promedio = ((stock_viejo * pc_viejo) + (cant_ingreso * nuevo_pc)) / stock_final if stock_viejo > 0 else nuevo_pc

                            tabla_stock.update_item(
                                Key={'TenantID': st.session_state.tenant, 'Producto': prod_ingreso},
                                UpdateExpression="SET Stock = :s, Precio_Compra = :pc",
                                ExpressionAttributeValues={':s': stock_final, ':pc': to_decimal(pc_promedio)}
                            )
                            registrar_kardex(prod_ingreso, cant_ingreso, "INGRESO_STOCK", precio_total_lote, nuevo_pc, f"INGRESO_{st.session_state.usuario}")
                            st.success(f"✅ {st.session_state.usuario} ingresó {cant_ingreso} {prod_ingreso} | Nuevo costo: S/{pc_promedio:.2f}")
                            time.sleep(1)
                            st.rerun()
            else:
                st.warning("⚠️ No hay productos")
# FIN PARTE 4/8
# === TAB INVENTARIO - DUEÑO VE COSTO, EMPLEADO NO ===
with tabs[1]:
    st.subheader("📊 Inventario")
    col1, col2 = st.columns([3, 1])
    f_filtro = col1.date_input("📅 Ver stock en:", value=datetime.now(tz_peru).date(), key="date_inventario")
    if col2.button("🔄 ACTUALIZAR", use_container_width=True, key="btn_actualizar_inv"): st.cache_data.clear(); st.rerun()

    fecha_iso = f_filtro.strftime('%Y-%m-%d')
    res_movs = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').lte(fecha_iso))
    df_movs = pd.DataFrame(res_movs.get('Items', []))

    if not df_movs.empty:
        df_movs['Cantidad'] = pd.to_numeric(df_movs['Cantidad'], errors='coerce').fillna(0)
        df_movs['Total'] = pd.to_numeric(df_movs['Total'], errors='coerce').fillna(0)
        df_movs['Precio_Compra'] = pd.to_numeric(df_movs['Precio_Compra'], errors='coerce').fillna(0)

        stock_hist = {}
        costo_hist = {}

        for _, row in df_movs.iterrows():
            prod = row['Producto']
            if prod not in stock_hist:
                stock_hist[prod] = 0
                costo_hist[prod] = 0

            if row['Tipo'] in ['CARGA_INICIAL', 'CARGA_MASIVA', 'INGRESO_STOCK']:
                stock_hist[prod] += row['Cantidad']
                costo_hist[prod] = row['Precio_Compra']
            elif row['Tipo'] == 'VENTA':
                stock_hist[prod] -= row['Cantidad']
            elif row['Tipo'] == 'AJUSTE_MANUAL':
                stock_hist[prod] += row['Cantidad']
                if row['Precio_Compra'] > 0:
                    costo_hist[prod] = row['Precio_Compra']

        df_display = pd.DataFrame([{'Producto': p, 'Stock': int(s), 'Precio_Compra': costo_hist.get(p, 0)} for p, s in stock_hist.items()])
        df_display = pd.merge(df_display, df_inv[['Producto', 'Precio']], on='Producto', how='left')
        df_display['Precio'] = df_display['Precio'].fillna(0)

        if st.session_state.rol == "DUEÑO":
            df_display['Valor_Inv'] = df_display['Stock'] * df_display['Precio_Compra']
            df_tabla = df_display[['Producto', 'Stock', 'Precio_Compra', 'Precio', 'Valor_Inv']].copy()
            df_tabla.columns = ['PROD', 'STOCK', 'COSTO', 'VENTA', 'VALOR']
        else:
            df_tabla = df_display[['Producto', 'Stock', 'Precio']].copy()
            df_tabla.columns = ['PROD', 'STOCK', 'VENTA']
            st.info("💡 Solo el dueño ve costos y ganancias")

        st.dataframe(
            df_tabla,
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "PROD": st.column_config.TextColumn("PROD", width="medium"),
                "STOCK": st.column_config.NumberColumn("STOCK", width="small"),
                "COSTO": st.column_config.NumberColumn("COSTO", format="S/ %.2f", width="small"),
                "VENTA": st.column_config.NumberColumn("VENTA", format="S/ %.2f", width="small"),
                "VALOR": st.column_config.NumberColumn("VALOR", format="S/ %.2f", width="small")
            }
        )

        if st.session_state.rol == "DUEÑO":
            col1, col2, col3 = st.columns(3)
            col1.metric("📦 PRODUCTOS", len(df_display))
            col2.metric("📊 STOCK TOTAL", int(df_display['Stock'].sum()))
            col3.metric("💰 VALOR INVENTARIO", f"S/ {float(df_display['Valor_Inv'].sum()):.2f}")
        else:
            col1, col2 = st.columns(2)
            col1.metric("📦 PRODUCTOS", len(df_display))
            col2.metric("📊 STOCK TOTAL", int(df_display['Stock'].sum()))
    else:
        st.info(f"📭 No hay datos hasta el {f_filtro.strftime('%d/%m/%Y')}")

# === TAB CAJA - AMBOS VEN PERO EMPLEADO SOLO SUS VENTAS ===
with tabs[2]:
    st.subheader("💰 Reporte de Caja")
    col1, col2 = st.columns([3, 1])
    f_caja = col1.date_input("📅 Fecha:", value=datetime.now(tz_peru).date(), key="date_caja")
    if col2.button("🔄 ACTUALIZAR", use_container_width=True, key="btn_actualizar_caja"): st.cache_data.clear(); st.rerun()

    fecha_iso_caja = f_caja.strftime('%Y-%m-%d')

    if st.session_state.rol == "EMPLEADO":
        res_c = tabla_movs.query(
            IndexName='TenantID-FechaISO-index',
            KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_iso_caja),
            FilterExpression=Attr('Tipo').eq('VENTA') & Attr('Usuario').eq(st.session_state.usuario)
        )
        st.info(f"📊 Mostrando solo TUS ventas - {st.session_state.usuario}")
    else:
        res_c = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_iso_caja), FilterExpression=Attr('Tipo').eq('VENTA'))

    df_c = pd.DataFrame(res_c.get('Items', []))

    if not df_c.empty:
        df_c['Total'] = pd.to_numeric(df_c['Total'], errors='coerce').fillna(0)
        df_c['Precio_Compra'] = pd.to_numeric(df_c['Precio_Compra'], errors='coerce').fillna(0)
        df_c['Cantidad'] = pd.to_numeric(df_c['Cantidad'], errors='coerce').fillna(0)
        df_c['Costo'] = df_c['Precio_Compra'] * df_c['Cantidad']
        df_c['Ganancia'] = df_c['Total'] - df_c['Costo']

        vt = df_c['Total'].sum()
        ct = df_c['Costo'].sum()
        gn = df_c['Ganancia'].sum()

        if st.session_state.rol == "DUEÑO":
            c1, c2, c3 = st.columns(3)
            c1.metric("💵 VENTAS", f"S/ {float(vt):.2f}")
            c2.metric("📉 COSTOS", f"S/ {float(ct):.2f}")
            c3.metric("📈 GANANCIA", f"S/ {float(gn):.2f}")

            por_metodo = df_c.groupby('Metodo')['Total'].sum().to_dict()
            st.write("**Por método de pago:**")
            cols_metodo = st.columns(len(por_metodo))
            for idx, (metodo, total) in enumerate(por_metodo.items()):
                cols_metodo[idx].metric(metodo, f"S/ {float(total):.2f}")
        else:
            c1, c2 = st.columns(2)
            c1.metric("💵 TUS VENTAS", f"S/ {float(vt):.2f}")
            c2.metric("📊 TICKETS", len(df_c))

        st.write("---")
        st.write("**Detalle de ventas:**")
        df_detalle = df_c[['Hora', 'Producto', 'Cantidad', 'Total', 'Metodo']].copy()
        df_detalle['Cantidad'] = df_detalle['Cantidad'].astype(int)
        st.dataframe(df_detalle, use_container_width=True, hide_index=True, height=300)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            df_c.to_excel(w, index=False, sheet_name='Ventas')
        st.download_button("📥 DESCARGAR EXCEL", buf.getvalue(), f"Caja_{f_caja.strftime('%Y%m%d')}.xlsx", use_container_width=True, key="btn_desc_caja")

        if tiene_whatsapp_habilitado():
            if st.session_state.rol == "DUEÑO":
                texto = f"*CAJA {f_caja.strftime('%d/%m/%Y')}*\nVentas: S/{float(vt):.2f}\nCostos: S/{float(ct):.2f}\n*Ganancia: S/{float(gn):.2f}*"
            else:
                texto = f"*MIS VENTAS {f_caja.strftime('%d/%m/%Y')} - {st.session_state.usuario}*\nVentas: S/{float(vt):.2f}\nTickets: {len(df_c)}"
            st.link_button("📲 COMPARTIR", f"https://wa.me/?text={urllib.parse.quote(texto)}", use_container_width=True)
        else:
            st.caption("💡 WhatsApp solo disponible en Plan PRO/PREMIUM")
    else:
        st.info(f"📭 No hay ventas el {f_caja.strftime('%d/%m/%Y')}")
# FIN PARTE 5/8
# === TAB HISTORIAL - DUEÑO Y EMPLEADO ===
with tabs[3]:
    st.subheader("📋 Historial de Movimientos")
    col1, col2 = st.columns([3, 1])
    f_hist = col1.date_input("📅 Ver movimientos de:", value=datetime.now(tz_peru).date(), key="date_hist")
    if col2.button("🔄 ACTUALIZAR", use_container_width=True, key="btn_actualizar_hist"): st.cache_data.clear(); st.rerun()

    fecha_iso_hist = f_hist.strftime('%Y-%m-%d')
    res_h = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(fecha_iso_hist))
    df_h = pd.DataFrame(res_h.get('Items', []))

    if not df_h.empty:
        df_h['Cantidad'] = pd.to_numeric(df_h['Cantidad'], errors='coerce').fillna(0).astype(int)
        df_h['Total'] = pd.to_numeric(df_h['Total'], errors='coerce').fillna(0)
        df_h['Precio_Compra'] = pd.to_numeric(df_h['Precio_Compra'], errors='coerce').fillna(0)

        df_h = df_h.sort_values('Hora', ascending=False)

        if st.session_state.rol == "DUEÑO":
            st.info("💡 Como DUEÑO ves todos los movimientos con costos")
            cols_mostrar = ['Hora', 'Tipo', 'Producto', 'Cantidad', 'Total', 'Precio_Compra', 'Metodo', 'Usuario']
        else:
            st.info("💡 Como EMPLEADO solo ves tus ventas")
            df_h = df_h[df_h['Usuario'] == st.session_state.usuario]
            cols_mostrar = ['Hora', 'Tipo', 'Producto', 'Cantidad', 'Total', 'Metodo']

        st.dataframe(
            df_h[cols_mostrar],
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "Hora": st.column_config.TextColumn("HORA", width="small"),
                "Tipo": st.column_config.TextColumn("TIPO", width="medium"),
                "Producto": st.column_config.TextColumn("PROD", width="medium"),
                "Cantidad": st.column_config.NumberColumn("CANT", width="small"),
                "Total": st.column_config.NumberColumn("TOTAL", format="S/ %.2f", width="small"),
                "Precio_Compra": st.column_config.NumberColumn("COSTO", format="S/ %.2f", width="small"),
                "Metodo": st.column_config.TextColumn("MÉTODO", width="small"),
                "Usuario": st.column_config.TextColumn("USER", width="small")
            }
        )

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            df_h.to_excel(w, index=False, sheet_name='Movimientos')
        st.download_button("📥 DESCARGAR EXCEL", buf.getvalue(), f"Historial_{f_hist.strftime('%Y%m%d')}.xlsx", use_container_width=True, key="btn_desc_hist")
    else:
        st.info(f"📭 No hay movimientos el {f_hist.strftime('%d/%m/%Y')}")

    st.write("---")
    st.subheader("🔒 Cierre de Caja")
    f_cierre, h_cierre, _ = obtener_tiempo_peru()
    res_cierre_hoy = tabla_cierres.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant), FilterExpression=Attr('Fecha').eq(f_cierre) & Attr('UsuarioTurno').eq(st.session_state.usuario))

    if res_cierre_hoy.get('Items', []):
        st.success(f"✅ Ya cerraste caja hoy a las {res_cierre_hoy['Items'][0]['Hora']}")
        if st.button("📄 VER REPORTE DEL CIERRE", use_container_width=True, key="btn_ver_cierre"):
            cierre = res_cierre_hoy['Items'][0]
            st.json({
                "Fecha": cierre['Fecha'],
                "Hora": cierre['Hora'],
                "Total Ventas": float(cierre['Total_Ventas']),
                "Usuario": cierre['UsuarioTurno'],
                "Tipo": cierre['TipoCierre']
            })
    else:
        if st.session_state.rol == "DUEÑO":
            if st.button("🔒 CERRAR MI CAJA", use_container_width=True, type="primary", key="btn_cerrar_caja_dueno"):
                res_v = tabla_movs.query(IndexName='TenantID-FechaISO-index', KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant) & Key('FechaISO').eq(datetime.now(tz_peru).strftime('%Y-%m-%d')), FilterExpression=Attr('Tipo').eq('VENTA') & Attr('Usuario').eq(st.session_state.usuario))
                df_v = pd.DataFrame(res_v.get('Items', []))
                total_v = pd.to_numeric(df_v['Total'], errors='coerce').fillna(0).sum() if not df_v.empty else 0
                registrar_cierre(total_v, st.session_state.usuario, "PROPIO", st.session_state.usuario)
                st.success(f"✅ Caja cerrada. Total: S/ {float(total_v):.2f}"); time.sleep(1); st.rerun()
        else:
            st.warning("⚠️ Solo el DUEÑO puede cerrar caja")
            if st.button("📞 SOLICITAR CIERRE AL DUEÑO", use_container_width=True, key="btn_solicitar_cierre"):
                st.info(f"Contacta al dueño: wa.me/{NUMERO_SOPORTE}")
# FIN PARTE 6/8
# === TAB CARGAR - SOLO DUEÑO ===
if st.session_state.rol == "DUEÑO" and len(tabs) > 4:
    with tabs[4]:
        st.subheader("📥 Cargar Productos")
        actual = contarProductosEnBD()
        st.info(f"Productos: {actual}/{MAX_PRODUCTOS_TOTALES} | Stock máx/producto: {MAX_STOCK_POR_PRODUCTO}")

        tab_nuevo, tab_ingreso = st.tabs(["➕ PRODUCTO NUEVO", "📦 INGRESO DE STOCK"])

        with tab_nuevo:
            with st.expander("📝 AGREGAR PRODUCTO INDIVIDUAL", expanded=True):
                col1, col2 = st.columns(2)
                prod = col1.text_input("Producto:", max_chars=30, key="prod_cargar").upper().strip()
                pc = col1.number_input("Precio Compra:", min_value=0.0, value=0.0, key="pc_cargar")
                p = col2.number_input("Precio Venta:", min_value=0.01, value=1.0, key="p_cargar")
                s = col2.number_input("Stock Inicial:", min_value=0, value=0, key="s_cargar")

                if st.button("➕ AGREGAR PRODUCTO", use_container_width=True, key="btn_agregar_prod"):
                    if prod and p > 0:
                        if actual >= MAX_PRODUCTOS_TOTALES:
                            st.error(f"❌ Límite de {MAX_PRODUCTOS_TOTALES} productos alcanzado")
                        elif s > MAX_STOCK_POR_PRODUCTO:
                            st.error(f"❌ Stock máximo por producto: {MAX_STOCK_POR_PRODUCTO}")
                        else:
                            try:
                                tabla_stock.put_item(Item={
                                    'TenantID': st.session_state.tenant, 'Producto': prod,
                                    'Precio_Compra': to_decimal(pc), 'Precio': to_decimal(p), 'Stock': int(s)
                                }, ConditionExpression='attribute_not_exists(Producto)')
                                registrar_kardex(prod, s, "CARGA_INICIAL", s * p, pc, "INVENTARIO")
                                st.success(f"✅ {prod} agregado"); time.sleep(1); st.rerun()
                            except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
                                st.error("❌ Producto ya existe. Usa la pestaña 'INGRESO DE STOCK'")
                    else:
                        st.error("❌ Completa todos los campos")

        with tab_ingreso:
            st.markdown("### 📦 INGRESO DE MERCADERÍA - DUEÑO")
            st.caption("Ingresa como compras: por cajas, docenas, millares, etc")

            if not df_inv.empty:
                prod_ingreso = st.selectbox("Selecciona producto:", df_inv['Producto'].tolist(), key="sel_ingreso")

                if prod_ingreso:
                    df_prod = df_inv[df_inv['Producto'] == prod_ingreso].iloc[0]
                    ultimo_pc = float(df_prod['Precio_Compra'])
                    st.info(f"Stock actual: {int(df_prod['Stock'])} unidades | Último costo: S/{ultimo_pc:.2f} | Venta: S/{df_prod['Precio']:.2f}")

                    st.markdown("**📦 DATOS DE LA COMPRA:**")
                    col1, col2 = st.columns(2)

                    unidad_medida = col1.selectbox("Unidad:", ["Unidades", "Docenas", "Cajas", "Millares", "Paquetes"], key="unidad_medida")
                    cantidad = col2.number_input(f"Cantidad de {unidad_medida}:", min_value=1, value=1, key="cant_lote")

                    multiplicador = {"Unidades": 1, "Docenas": 12, "Cajas": 1, "Millares": 1000, "Paquetes": 1}[unidad_medida]

                    if unidad_medida in ["Cajas", "Paquetes"]:
                        unid_x_bulto = st.number_input(f"¿Cuántas unidades trae cada {unidad_medida[:-1]}?", min_value=1, value=50, key="unid_bulto")
                        multiplicador = unid_x_bulto

                    cant_ingreso = cantidad * multiplicador
                    costo_sugerido = ultimo_pc * cant_ingreso

                    usar_ultimo = st.checkbox(f"✓ Usar último costo: S/{ultimo_pc:.2f} c/u → Total sugerido: S/{costo_sugerido:.2f}", value=False, key="check_ultimo")

                    if usar_ultimo:
                        precio_total_lote = costo_sugerido
                        st.success(f"✅ Usando último precio registrado: S/{precio_total_lote:.2f}")
                    else:
                        precio_total_lote = st.number_input(f"Costo total del lote S/:", min_value=0.0, value=0.0, key="precio_lote", help="Lo que pagaste por todo el lote según factura")

                    nuevo_pc = precio_total_lote / cant_ingreso if cant_ingreso > 0 else 0

                    st.success(f"✅ Ingresan: {cant_ingreso} unidades | Costo x unidad: S/{nuevo_pc:.2f}")

                    stock_final = int(df_prod['Stock']) + cant_ingreso
                    st.metric("Stock después del ingreso", f"{stock_final} unidades")

                    if st.button("📥 REGISTRAR INGRESO", use_container_width=True, type="primary", key="btn_ingreso_stock"):
                        if stock_final > MAX_STOCK_POR_PRODUCTO:
                            st.error(f"❌ Stock máximo: {MAX_STOCK_POR_PRODUCTO}. Te pasas por {stock_final - MAX_STOCK_POR_PRODUCTO}")
                        else:
                            stock_viejo = int(df_prod['Stock'])
                            pc_viejo = float(df_prod['Precio_Compra'])

                            if stock_viejo > 0:
                                pc_promedio = ((stock_viejo * pc_viejo) + (cant_ingreso * nuevo_pc)) / stock_final
                            else:
                                pc_promedio = nuevo_pc

                            tabla_stock.update_item(
                                Key={'TenantID': st.session_state.tenant, 'Producto': prod_ingreso},
                                UpdateExpression="SET Stock = :s, Precio_Compra = :pc",
                                ExpressionAttributeValues={':s': stock_final, ':pc': to_decimal(pc_promedio)}
                            )
                            registrar_kardex(prod_ingreso, cant_ingreso, "INGRESO_STOCK", precio_total_lote, nuevo_pc, "COMPRA")
                            st.success(f"✅ Ingreso: {cant_ingreso} {prod_ingreso} | Nuevo costo promedio: S/{pc_promedio:.2f}")
                            time.sleep(1)
                            st.rerun()
            else:
                st.warning("⚠️ No hay productos cargados. Primero agrega productos en la pestaña 'PRODUCTO NUEVO'")

        st.write("---")
        st.subheader("📊 CARGA MASIVA EXCEL")
        st.caption("Formato: Producto | Precio_Compra | Precio | Stock")

        archivo = st.file_uploader("Sube tu Excel", type=['xlsx', 'xls'], key="upload_excel")
        if archivo:
            try:
                df_upload = pd.read_excel(archivo)
                df_upload.columns = [c.strip() for c in df_upload.columns]

                columnas_req = ['Producto', 'Precio_Compra', 'Precio', 'Stock']
                if not all(col in df_upload.columns for col in columnas_req):
                    st.error(f"❌ El Excel debe tener columnas: {', '.join(columnas_req)}")
                else:
                    df_upload['Producto'] = df_upload['Producto'].astype(str).str.upper().str.strip()
                    df_upload['Precio_Compra'] = pd.to_numeric(df_upload['Precio_Compra'], errors='coerce').fillna(0)
                    df_upload['Precio'] = pd.to_numeric(df_upload['Precio'], errors='coerce').fillna(0)
                    df_upload['Stock'] = pd.to_numeric(df_upload['Stock'], errors='coerce').fillna(0).astype(int)

                    df_upload = df_upload[df_upload['Producto']!= '']
                    df_upload = df_upload[df_upload['Precio'] > 0]
                    df_upload = df_upload[df_upload['Stock'] <= MAX_STOCK_POR_PRODUCTO]

                    if len(df_upload) + actual > MAX_PRODUCTOS_TOTALES:
                        st.error(f"❌ Excede límite. Máximo {MAX_PRODUCTOS_TOTALES - actual} productos más")
                    else:
                        st.write("**Vista previa:**")
                        st.dataframe(df_upload, use_container_width=True, hide_index=True, height=300)

                        if st.button("🚀 CARGAR TODO", use_container_width=True, key="btn_cargar_excel"):
                            progreso = st.progress(0)
                            for idx, row in df_upload.iterrows():
                                tabla_stock.put_item(Item={
                                    'TenantID': st.session_state.tenant,
                                    'Producto': row['Producto'],
                                    'Precio_Compra': to_decimal(row['Precio_Compra']),
                                    'Precio': to_decimal(row['Precio']),
                                    'Stock': int(row['Stock'])
                                })
                                registrar_kardex(row['Producto'], row['Stock'], "CARGA_MASIVA", row['Stock'] * row['Precio'], row['Precio_Compra'], "EXCEL")
                                progreso.progress((idx + 1) / len(df_upload))
                            st.success(f"✅ {len(df_upload)} productos cargados"); time.sleep(1); st.rerun()
            except Exception as e:
                st.error(f"❌ Error al leer Excel: {e}")
# FIN PARTE 7/8
# === TAB MANTENIMIENTO - SOLO DUEÑO ===
if st.session_state.rol == "DUEÑO" and len(tabs) > 5:
    with tabs[5]:
        st.subheader("🛠️ Mantenimiento de Productos")

        tab_editar, tab_ajuste = st.tabs(["✏️ EDITAR PRODUCTO", "🔧 AJUSTE DE STOCK"])

        with tab_editar:
            st.markdown("### ✏️ Editar Precios y Datos")
            if not df_inv.empty:
                prod_edit = st.selectbox("Selecciona producto:", df_inv['Producto'].tolist(), key="sel_edit")

                if prod_edit:
                    df_prod = df_inv[df_inv['Producto'] == prod_edit].iloc[0]

                    col1, col2 = st.columns(2)
                    nuevo_nombre = col1.text_input("Nombre:", value=prod_edit, key="nombre_edit").upper().strip()
                    nuevo_pc = col1.number_input("Precio Compra:", min_value=0.0, value=float(df_prod['Precio_Compra']), key="pc_edit")
                    nuevo_p = col2.number_input("Precio Venta:", min_value=0.01, value=float(df_prod['Precio']), key="p_edit")

                    ganancia = nuevo_p - nuevo_pc
                    margen = (ganancia / nuevo_p * 100) if nuevo_p > 0 else 0

                    col1.metric("Ganancia x unidad", f"S/ {ganancia:.2f}")
                    col2.metric("Margen", f"{margen:.1f}%")

                    if st.button("💾 GUARDAR CAMBIOS", use_container_width=True, type="primary", key="btn_guardar_edit"):
                        if nuevo_nombre!= prod_edit:
                            tabla_stock.delete_item(Key={'TenantID': st.session_state.tenant, 'Producto': prod_edit})
                            tabla_stock.put_item(Item={
                                'TenantID': st.session_state.tenant,
                                'Producto': nuevo_nombre,
                                'Precio_Compra': to_decimal(nuevo_pc),
                                'Precio': to_decimal(nuevo_p),
                                'Stock': int(df_prod['Stock'])
                            })
                            st.success(f"✅ Producto renombrado a {nuevo_nombre}")
                        else:
                            tabla_stock.update_item(
                                Key={'TenantID': st.session_state.tenant, 'Producto': prod_edit},
                                UpdateExpression="SET Precio_Compra = :pc, Precio = :p",
                                ExpressionAttributeValues={':pc': to_decimal(nuevo_pc), ':p': to_decimal(nuevo_p)}
                            )
                            st.success(f"✅ {prod_edit} actualizado")
                        time.sleep(1)
                        st.rerun()

        with tab_ajuste:
            st.markdown("### 🔧 Ajuste Manual de Stock")
            st.warning("⚠️ Usar solo para mermas, robos o correcciones. Queda registrado en Kardex.")

            if not df_inv.empty:
                prod_ajuste = st.selectbox("Producto:", df_inv['Producto'].tolist(), key="sel_ajuste")

                if prod_ajuste:
                    df_prod = df_inv[df_inv['Producto'] == prod_ajuste].iloc[0]
                    stock_actual = int(df_prod['Stock'])

                    st.info(f"Stock actual: {stock_actual} unidades")

                    col1, col2 = st.columns(2)
                    tipo_ajuste = col1.selectbox("Tipo:", ["➕ SUMAR", "➖ RESTAR"], key="tipo_ajuste")
                    cantidad_ajuste = col2.number_input("Cantidad:", min_value=1, value=1, key="cant_ajuste")

                    motivo = st.text_input("Motivo:", placeholder="Ej: Merma, Robo, Inventario físico", key="motivo_ajuste")

                    if tipo_ajuste == "➕ SUMAR":
                        stock_nuevo = stock_actual + cantidad_ajuste
                        st.success(f"Stock nuevo: {stock_nuevo} unidades")
                    else:
                        stock_nuevo = stock_actual - cantidad_ajuste
                        if stock_nuevo < 0:
                            st.error(f"❌ No puedes restar más del stock actual")
                        else:
                            st.success(f"Stock nuevo: {stock_nuevo} unidades")

                    if st.button("💾 REGISTRAR AJUSTE", use_container_width=True, type="primary", key="btn_ajuste"):
                        if not motivo:
                            st.error("❌ Debes poner un motivo")
                        elif tipo_ajuste == "➖ RESTAR" and stock_nuevo < 0:
                            st.error("❌ Stock no puede quedar negativo")
                        else:
                            cant_final = cantidad_ajuste if tipo_ajuste == "➕ SUMAR" else -cantidad_ajuste
                            tabla_stock.update_item(
                                Key={'TenantID': st.session_state.tenant, 'Producto': prod_ajuste},
                                UpdateExpression="SET Stock = :s",
                                ExpressionAttributeValues={':s': stock_nuevo}
                            )
                            registrar_kardex(prod_ajuste, cant_final, "AJUSTE_MANUAL", 0, 0, motivo)
                            st.success(f"✅ Ajuste registrado: {cant_final:+d} {prod_ajuste}")
                            time.sleep(1)
                            st.rerun()

# === FOOTER ===
st.markdown("---")
st.markdown(f"<div style='text-align:center;color:#6b7280;padding:20px;'><p style='margin:0;font-size:14px;'>{DESARROLLADOR}</p><p style='margin:5px 0;font-size:12px;'>Plan {PLAN_ACTUAL} | S/ {PRECIO_ACTUAL}/mes | Soporte: {NUMERO_SOPORTE}</p></div>", unsafe_allow_html=True)
# FIN PARTE 8/8
