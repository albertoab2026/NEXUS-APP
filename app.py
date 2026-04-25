import streamlit as st
import pandas as pd
import boto3
from datetime import datetime, timedelta
import pytz
from boto3.dynamodb.conditions import Attr, Key
from fpdf import FPDF
import time
import re
import urllib.parse
from decimal import Decimal, ROUND_HALF_UP
import io
import uuid

# --- 0. CONFIGURACIÓN ---
TABLA_STOCK = st.secrets["tablas"]["stock"]
TABLA_VENTAS = st.secrets["tablas"]["ventas"]
TABLA_MOVS = st.secrets["tablas"]["movs"]
TABLA_TENANTS = st.secrets["tablas"]["tenants"]
TABLA_CIERRES = st.secrets["tablas"]["cierres"]
TABLA_PAGOS = st.secrets["tablas"]["pagos"]

st.set_page_config(page_title="NEXUS BALLARTA SaaS", layout="wide", page_icon="🚀")
tz_peru = pytz.timezone('America/Lima')

def to_decimal(f):
    return Decimal(str(f)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def obtener_tiempo_peru():
    ahora = datetime.now(tz_peru)
    fecha = ahora.strftime("%d/%m/%Y")
    hora = ahora.strftime("%H:%M:%S")
    id_unico = ahora.strftime("%Y%m%d%H%M%S%f")
    return fecha, hora, id_unico

try:
    dynamodb = boto3.resource('dynamodb',
                              region_name=st.secrets["aws"]["aws_region"],
                              aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
                              aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"])
    tabla_stock = dynamodb.Table(TABLA_STOCK)
    tabla_ventas = dynamodb.Table(TABLA_VENTAS)
    tabla_movs = dynamodb.Table(TABLA_MOVS)
    tabla_tenants = dynamodb.Table(TABLA_TENANTS)
    tabla_cierres = dynamodb.Table(TABLA_CIERRES)
    tabla_pagos = dynamodb.Table(TABLA_PAGOS)
except Exception as e:
    st.error("Error de sistema. Contacta a soporte.")
    print(f"ERROR AWS CONEXION: {e}")
    st.stop()

# ========== SISTEMA COBROS NEXUS ==========
def verificar_suscripcion(tenant_id):
    try:
        tenant = tabla_tenants.get_item(Key={'TenantID': tenant_id}).get('Item', {})
        if tenant.get('EstadoPago') == 'SUSPENDIDO': 
            return False, "SUSPENDIDO"
        fecha_cobro_str = tenant.get('ProximoCobro', '01/01/2000')
        fecha_cobro = datetime.strptime(fecha_cobro_str, '%d/%m/%Y').date()
        hoy = datetime.now(tz_peru).date()
        if fecha_cobro < hoy - timedelta(days=5): 
            return False, f"VENCIDO - Fecha límite: {fecha_cobro_str}"
        return True, "ACTIVO"
    except Exception as e:
        print(f"ERROR VERIFICAR SUSCRIPCION: {e}")
        return True, "ERROR"

if st.session_state.get('auth') and st.session_state.get('tenant'):
    activo, motivo = verificar_suscripcion(st.session_state['tenant'])
    if not activo:
        st.error(f"⛔ ACCESO BLOQUEADO: {motivo}")
        st.error("Contacta a soporte para regularizar tu pago y reactivar tu acceso.")
        st.stop()
# ========== FIN SISTEMA COBROS ==========
# === PARCHE FINAL: REGISTRAR_CIERRE ACEPTA FECHA ===
def registrar_cierre(total_cierre, usuario_turno, tipo_turno, usuario_cierre, fecha_cierre=None):
    if fecha_cierre is None:
        f_c, h_c, uid_c = obtener_tiempo_peru()
    else:
        f_c = fecha_cierre
        _, h_c, uid_c = obtener_tiempo_peru()

    tabla_cierres.put_item(Item={
        'TenantID': st.session_state.tenant,
        'CierreID': f"C-{uid_c}",
        'Fecha': f_c,
        'Hora': h_c,
        'UsuarioTurno': usuario_turno,
        'UsuarioCierre': usuario_cierre,
        'Total': to_decimal(total_cierre),
        'Tipo': tipo_turno
    })
    st.session_state.caja_cerrada = True
    st.session_state.ultimo_cierre = {
        'id': f"C-{uid_c}",
        'hora': h_c,
        'usuario_turno': usuario_turno,
        'usuario_cierre': usuario_cierre
    }

# === PARCHE FINAL: AUTO-CIERRE SOLO AYER Y SOLO 1AM-6AM ===
def verificar_cierre_tardio():
    hora_actual = datetime.now(tz_peru).hour
    if hora_actual < 1 or hora_actual > 6:
        return None

    f_hoy, h_hoy, _ = obtener_tiempo_peru()
    ayer = (datetime.now(tz_peru) - timedelta(days=1)).strftime("%d/%m/%Y")

    res_v = tabla_ventas.query(
        KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant),
        FilterExpression=Attr('Fecha').eq(ayer)
    )
    ventas_ayer = res_v.get('Items', [])

    res_c = tabla_cierres.query(
        KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant),
        FilterExpression=Attr('Fecha').eq(ayer)
    )
    cierres_ayer = res_c.get('Items', [])

    if ventas_ayer and not cierres_ayer:
        total_pendiente = sum([Decimal(str(v['Total'])) for v in ventas_ayer])
        usuario_deudor = ventas_ayer[-1]['Usuario'] if ventas_ayer else "NADIE"
        registrar_cierre(total_pendiente, usuario_deudor, "CIERRE TARDÍO", "SISTEMA", fecha_cierre=ayer)
        st.warning(f"🚨 AUTO-CIERRE: Día {ayer} se cerró con S/{float(total_pendiente):.2f} porque nadie lo hizo.")
        return total_pendiente
    return None

def contarProductosEnBD():
    try:
        respuesta = tabla_stock.query(
            KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant),
            Select='COUNT'
        )
        return respuesta.get('Count', 0)
    except Exception as e:
        st.error("Error de sistema. Contacta a soporte.")
        print(f"ERROR CONTEO: {e}")
        return 9999

@st.cache_data(ttl=60)
def obtener_datos():
    items = []
    last_key = None
    while len(items) < 2000:
        if last_key:
            respuesta = tabla_stock.query(
                KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant),
                Limit=500,
                ExclusiveStartKey=last_key
            )
        else:
            respuesta = tabla_stock.query(
                KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant),
                Limit=500
            )
        items.extend(respuesta.get('Items', []))
        last_key = respuesta.get('LastEvaluatedKey')
        if not last_key:
            break
    df = pd.DataFrame(items)
    if df.empty:
        return pd.DataFrame(columns=['Producto', 'Precio_Compra', 'Precio', 'Stock'])
    df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
    df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
    df['Precio_Compra'] = pd.to_numeric(df['Precio_Compra'], errors='coerce').fillna(0.0)
    return df[['Producto', 'Precio_Compra', 'Precio', 'Stock']].sort_values('Producto')
# === PARCHE: USA EstadoPago Y ProximoCobro ===
def obtener_limites_tenant():
    try:
        respuesta = tabla_tenants.get_item(Key={'TenantID': st.session_state.tenant})

        if 'Item' not in respuesta:
            st.error(f"🚨 Tenant '{st.session_state.tenant}' no existe en NEXUS_TENANTS. Revisa que el nombre en secrets coincida exacto.")
            st.stop()

        item = respuesta['Item']

        if item.get('EstadoPago') == 'SUSPENDIDO':
            st.error("⛔ Tu cuenta está SUSPENDIDA por falta de pago. Contacta a soporte para reactivar.")
            st.stop()

        fecha_cobro_str = item.get('ProximoCobro', '01/01/2000')
        fecha_cobro = datetime.strptime(fecha_cobro_str, '%d/%m/%Y').date()
        hoy = datetime.now(tz_peru).date()

        if fecha_cobro < hoy - timedelta(days=5):
            st.error(f"⛔ Tu suscripción VENCIO el {fecha_cobro_str}. Contacta a soporte para renovar.")
            st.stop()

        max_prod = int(item.get('MaxProductos', 0))
        max_stock = int(item.get('MaxStock', 0))
        plan = item.get('Plan', 'SIN_PLAN')
        precio = item.get('PrecioMensual', 0)

        if max_prod == 0 or max_stock == 0:
            st.error("🚨 Tu tenant no tiene MaxProductos o MaxStock configurado en DynamoDB.")
            st.stop()

        total_actual = contarProductosEnBD()
        df_temp = obtener_datos()
        stock_max_actual = int(df_temp['Stock'].max()) if not df_temp.empty else 0

        if total_actual > max_prod or stock_max_actual > max_stock:
            st.session_state.modo_lectura = True
            st.session_state.mensaje_lectura = f"⚠️ MODO LECTURA: Tienes {total_actual}/{max_prod} productos y stock máximo de {stock_max_actual}/{max_stock}. Solo puedes VENDER hasta regularizar tu plan {plan}."
        else:
            st.session_state.modo_lectura = False

        return max_prod, max_stock, plan, precio

    except Exception as e:
        st.error("Error de sistema leyendo tu plan. Contacta a soporte.")
        print(f"ERROR PLAN: {e}")
        st.stop()

if 'auth' not in st.session_state:
    st.session_state.auth = False
if 'rol' not in st.session_state:
    st.session_state.rol = None
if 'tenant' not in st.session_state:
    st.session_state.tenant = None
if 'usuario' not in st.session_state:
    st.session_state.usuario = None
if 'nombre_emp_temp' not in st.session_state:
    st.session_state.nombre_emp_temp = ""
if 'carrito' not in st.session_state:
    st.session_state.carrito = []
if 'boleta' not in st.session_state:
    st.session_state.boleta = None
if 'confirmar' not in st.session_state:
    st.session_state.confirmar = False
if 'modo_lectura' not in st.session_state:
    st.session_state.modo_lectura = False
if 'intentos_fallidos' not in st.session_state:
    st.session_state.intentos_fallidos = 0
if 'tiempo_bloqueo' not in st.session_state:
    st.session_state.tiempo_bloqueo = None
if 'caja_cerrada' not in st.session_state:
    st.session_state.caja_cerrada = False
if 'ultimo_cierre' not in st.session_state:
    st.session_state.ultimo_cierre = None
if 'ultima_verificacion_fecha' not in st.session_state:
    st.session_state.ultima_verificacion_fecha = None

if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center; color: #3498db;'>🚀 NEXUS BALLARTA SaaS</h1>", unsafe_allow_html=True)
    if st.session_state.tiempo_bloqueo:
        if datetime.now(tz_peru) < st.session_state.tiempo_bloqueo:
            tiempo_restante = (st.session_state.tiempo_bloqueo - datetime.now(tz_peru)).seconds
            st.error(f"❌ Demasiados intentos fallidos. Espera {tiempo_restante} segundos.")
            st.stop()
        else:
            st.session_state.intentos_fallidos = 0
            st.session_state.tiempo_bloqueo = None
    tenants_admin = [k for k in st.secrets if k not in ["tablas", "aws"] and not k.endswith("_emp")]
    tenant_seleccionado = st.selectbox("📍 Seleccione su Negocio:", [t.replace("_", " ") for t in tenants_admin])
    tenant_key = tenant_seleccionado.replace(" ", "_")
    clave_input = st.text_input("🔑 Contraseña:", type="password", key="login_pass").strip()[:30]
    col_dueño, col_empleado = st.columns(2)
    def intentar_login(tipo_usuario, nombre_emp=None):
        if not re.match("^[A-Za-z0-9]*$", clave_input):
            time.sleep(2)
            st.error("❌ No se permiten símbolos raros.")
            return
        if tipo_usuario == "DUEÑO":
            if tenant_key in st.secrets:
                clave_correcta = st.secrets[tenant_key]["clave"]
                usuario_correcto = "DUEÑO"
            else:
                st.error("Negocio no configurado en secrets.")
                return
        else:
            tenant_emp_key = f"{tenant_key}_emp"
            if tenant_emp_key in st.secrets:
                clave_correcta = st.secrets[tenant_emp_key]["clave"]
                usuario_correcto = nombre_emp
            else:
                st.error("Este negocio no tiene empleado configurado.")
                return
        if clave_input == str(clave_correcta):
            st.session_state.auth = True
            st.session_state.tenant = tenant_seleccionado
            st.session_state.rol = tipo_usuario
            st.session_state.usuario = usuario_correcto
            st.session_state.intentos_fallidos = 0
            st.rerun()
        else:
            st.session_state.intentos_fallidos += 1
            if st.session_state.intentos_fallidos >= 5:
                st.session_state.tiempo_bloqueo = datetime.now(tz_peru) + timedelta(minutes=5)
                st.error("❌ Demasiados intentos. Bloqueado por 5 minutos.")
                st.stop()
            time.sleep(2)
            st.error(f"❌ Contraseña de {tipo_usuario} incorrecta. Intentos: {st.session_state.intentos_fallidos}/5")
    if col_dueño.button("🔓 DUEÑO", use_container_width=True):
        intentar_login("DUEÑO")
    with col_empleado:
        nombre_emp = st.text_input(
            "👤 Tu nombre:",
            value=st.session_state.nombre_emp_temp,
            key="input_nombre_emp",
            placeholder="Ej: JUAN",
            max_chars=20
        ).upper().strip()
        if st.button("🧑‍💼 EMPLEADO", use_container_width=True):
            if not nombre_emp:
                st.warning("Pon tu nombre pa' entrar como empleado")
            elif not re.match("^[A-Z0-9 ]*$", nombre_emp):
                st.error("❌ Solo letras y números en el nombre.")
            else:
                st.session_state.nombre_emp_temp = nombre_emp
                intentar_login("EMPLEADO", nombre_emp)
    st.stop()

if st.session_state.auth:
    f_actual, _, _ = obtener_tiempo_peru()
    hora_actual_login = datetime.now(tz_peru).hour
    if st.session_state.get('ultima_verificacion_fecha')!= f_actual:
        st.session_state.verifico_cierre = False
        st.session_state.ultima_verificacion_fecha = f_actual
    if not st.session_state.get('verifico_cierre', False) and 1 <= hora_actual_login <= 6:
        with st.spinner('Verificando cierres pendientes...'):
            verificar_cierre_tardio()
        st.session_state.verifico_cierre = True

MAX_PRODUCTOS_TOTALES, MAX_STOCK_POR_PRODUCTO, PLAN_ACTUAL, PRECIO_ACTUAL = obtener_limites_tenant()
df_inv = obtener_datos()

if st.session_state.get('modo_lectura', False):
    st.warning(st.session_state.mensaje_lectura)

lista_pestanas = ["🛒 VENTA", "📦 STOCK", "📊 REPORTES"]
if st.session_state.rol == "DUEÑO":
    if st.session_state.get('modo_lectura', False):
        st.error("🔒 CARGAR y MANTENIMIENTO bloqueados. Estás pasado de tu plan. Solo puedes VENDER.")
    else:
        lista_pestanas += ["📋 HISTORIAL", "📥 CARGAR", "🛠️ MANT."]
tabs = st.tabs(lista_pestanas)
with tabs[0]:
    df_critico = df_inv[df_inv['Stock'] < 5].copy()
    if not df_critico.empty:
        st.warning(f"⚠️ ¡Atención! {len(df_critico)} productos tienen stock crítico (menos de 5 unidades).")
    if st.session_state.boleta:
        st.snow()
        b = st.session_state.boleta
        st.success("✅ VENTA REALIZADA CON ÉXITO")
        st.markdown(f"""<div style="background-color:white;color:black;padding:20px;border:2px solid #333;max-width:350px;margin:auto;font-family:monospace;">
            <h3 style="text-align:center;margin:0;">{st.session_state.tenant}</h3>
            <p style="text-align:center;margin:0;">{b['fecha']} {b['hora']}</p><hr>
            {''.join([f'<div style="display:flex;justify-content:space-between;"><span>{i["Cantidad"]}x {i["Producto"]}</span><span>S/{float(i["Subtotal"]):.2f}</span></div>' for i in b['items']])}
            <hr>
            <div style="display:flex;justify-content:space-between;"><span>MÉTODO:</span><span>{b['metodo']}</span></div>
            <div style="display:flex;justify-content:space-between;color:red;font-size:12px;"><span>DESCUENTO:</span><span>- S/{float(b['rebaja']):.2f}</span></div>
            <div style="display:flex;justify-content:space-between;font-size:18px;"><b>NETO:</b><b>S/{float(b['t_neto']):.2f}</b></div>
            <p style="text-align:center;font-size:10px;margin-top:10px;">*Documento de control interno*</p></div>""", unsafe_allow_html=True)
        st.write("")
        if PLAN_ACTUAL in ["PRO", "PREMIUM"]:
            texto_wa = f"*TICKET DE VENTA - {st.session_state.tenant}*\n"
            texto_wa += f"Fecha: {b['fecha']} {b['hora']}\n---\n"
            for i in b['items']:
                texto_wa += f"{i['Cantidad']}x {i['Producto']} - S/{float(i['Subtotal']):.2f}\n"
            texto_wa += f"---\n*TOTAL NETO: S/{float(b['t_neto']):.2f}*\nMetodo: {b['metodo']}\n"
            texto_wa += f"_*No válido como comprobante tributario*_"
            wa_url = f"https://wa.me/?text={urllib.parse.quote(texto_wa)}"
            st.link_button("📲 Enviar reporte por WhatsApp", wa_url, use_container_width=True)
        else:
            st.info("🔒 Enviar por WhatsApp solo disponible en planes PRO y PREMIUM")
        try:
            pdf = FPDF(orientation='P', unit='mm', format=(80, 200))
            pdf.add_page()
            pdf.set_margins(3, 3, 3)
            pdf.set_auto_page_break(auto=True, margin=3)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(74, 6, txt=str(st.session_state.tenant)[:30], ln=True, align='C')
            pdf.set_font("Arial", size=8)
            pdf.cell(74, 4, txt=f"{b['fecha']} {b['hora']}", ln=True, align='C')
            pdf.cell(74, 2, txt="-" * 42, ln=True, align='C')
            pdf.set_font("Arial", size=9)
            for i in b['items']:
                nombre_corto = i['Producto'][:20]
                pdf.cell(50, 5, txt=f"{i['Cantidad']}x {nombre_corto}")
                pdf.cell(24, 5, txt=f"S/{float(i['Subtotal']):.2f}", ln=True, align='R')
            pdf.cell(74, 2, txt="-" * 42, ln=True, align='C')
            pdf.set_font("Arial", size=8)
            metodo_limpio = b['metodo'].replace("💵 ", "").replace("🟣 ", "").replace("🔵 ", "")
            pdf.cell(50, 4, txt=f"Pago: {metodo_limpio}")
            pdf.cell(24, 4, txt=f"Desc: -S/{float(b['rebaja']):.2f}", ln=True, align='R')
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(74, 6, txt=f"TOTAL: S/ {float(b['t_neto']):.2f}", ln=True, align='C')
            pdf.set_font("Arial", 'I', 7)
            pdf.cell(74, 4, txt="Documento de control interno", ln=True, align='C')
            pdf.cell(74, 3, txt="No valido como comprobante SUNAT", ln=True, align='C')
            pdf_bytes = pdf.output(dest='S').encode('latin-1', 'ignore')
            st.download_button(label="📥 Descargar Ticket PDF 80mm", data=pdf_bytes, file_name=f"Ticket_{b['fecha'].replace('/','-')}.pdf", mime="application/pdf", use_container_width=True)
        except Exception as e:
            st.error("Error de sistema. Contacta a soporte.")
            print(f"ERROR PDF: {e}")
        if st.button("⬅️ NUEVA VENTA", use_container_width=True):
            st.session_state.boleta = None
            st.rerun()
    else:
        st.subheader("🛍️ Nueva Venta")
        busqueda_v = st.text_input("🔍 Buscar por Nombre de Producto:", key="input_bv").upper()
        opciones_formateadas = []
        mapping_nombres = {}
        for _, fila in df_inv.iterrows():
            if busqueda_v in str(fila['Producto']):
                estado_stock = f"STOCK: {fila['Stock']}" if fila['Stock'] > 0 else "🚫 AGOTADO"
                etiqueta = f"{fila['Producto']} | S/ {fila['Precio']:.2f} | {estado_stock}"
                opciones_formateadas.append(etiqueta)
                mapping_nombres[etiqueta] = fila['Producto']
        col_sel, col_cant = st.columns([3, 1])
        seleccion_formateada = col_sel.selectbox("Seleccionar Producto:", opciones_formateadas, index=0 if opciones_formateadas else None, key="sel_v_smart")
        p_seleccionado = mapping_nombres.get(seleccion_formateada) if seleccion_formateada else None
        cantidad_v = col_cant.number_input("Cant:", min_value=1, value=1, key=f"cant_{p_seleccionado}")
        if p_seleccionado:
            datos_p = df_inv[df_inv['Producto'] == p_seleccionado].iloc[0]
            en_el_carro = sum(item['Cantidad'] for item in st.session_state.carrito if item['Producto'] == p_seleccionado)
            disponible_ahora = datos_p.Stock - en_el_carro
            if datos_p.Stock <= 0:
                st.error("⚠️ Este producto no tiene stock físico.")
            else:
                st.info(f"💡 Seleccionado: {p_seleccionado} | Disponible: {disponible_ahora}")
            if st.button("➕ Añadir al Carrito", use_container_width=True):
                if cantidad_v <= disponible_ahora:
                    p_v_dec = to_decimal(datos_p.Precio)
                    st.session_state.carrito.append({'Producto': p_seleccionado, 'Cantidad': int(cantidad_v), 'Precio': p_v_dec, 'Precio_Compra': to_decimal(datos_p.Precio_Compra), 'Subtotal': p_v_dec * int(cantidad_v)})
                    st.rerun()
                else:
                    st.error("❌ No puedes vender más de lo que hay en stock.")
        if st.session_state.carrito:
            st.table(pd.DataFrame(st.session_state.carrito)[['Producto', 'Cantidad', 'Subtotal']])
            if st.button("🗑️ VACIAR CARRITO"):
                st.session_state.carrito = []
                st.rerun()
            metodo_p = st.radio("Forma de Pago:", ["💵 EFECTIVO", "🟣 YAPE", "🔵 PLIN"], horizontal=True)
            rebaja_v = st.number_input("💸 Descuento S/:", min_value=0.0, value=0.0, key="rebaja_v")
            total_bruto = sum(item['Subtotal'] for item in st.session_state.carrito)
            total_neto = max(Decimal('0.00'), total_bruto - to_decimal(rebaja_v))
            st.markdown(f"<h1 style='text-align:center; color:#2ecc71;'>S/ {float(total_neto):.2f}</h1>", unsafe_allow_html=True)
            if st.button("🚀 FINALIZAR VENTA", use_container_width=True, type="primary"):
                st.session_state.confirmar = True
            if st.session_state.confirmar:
                if st.button(f"✅ CONFIRMAR COBRO DE S/ {float(total_neto):.2f}", use_container_width=True):
                    f_v, h_v, uid_v = obtener_tiempo_peru()
                    for item_v in st.session_state.carrito:
                        try:
                            tabla_stock.update_item(
                                Key={'TenantID': st.session_state.tenant, 'Producto': item_v['Producto']},
                                UpdateExpression="SET Stock = Stock - :s",
                                ConditionExpression="Stock >= :s",
                                ExpressionAttributeValues={':s': item_v['Cantidad']}
                            )
                            tabla_ventas.put_item(Item={
                                'TenantID': st.session_state.tenant,
                                'VentaID': f"V-{uid_v}",
                                'Fecha': f_v, 'Hora': h_v,
                                'Producto': item_v['Producto'],
                                'Cantidad': int(item_v['Cantidad']),
                                'Total': item_v['Subtotal'],
                                'Precio_Compra': item_v['Precio_Compra'],
                                'Metodo': metodo_p,
                                'Rebaja': to_decimal(rebaja_v),
                                'Usuario': st.session_state.usuario
                            })
                        except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
                            st.error(f"❌ ¡CRÍTICO! El stock de '{item_v['Producto']}' cambió justo ahora y ya no hay suficiente. Venta cancelada.")
                            st.stop()
                    st.session_state.boleta = {'items': st.session_state.carrito, 't_neto': total_neto, 'rebaja': to_decimal(rebaja_v), 'metodo': metodo_p, 'fecha': f_v, 'hora': h_v}
                    st.session_state.carrito = []
                    st.session_state.confirmar = False
                    st.rerun()

def registrar_kardex(producto_k, cantidad_k, tipo_k):
    f_k, h_k, uid_k = obtener_tiempo_peru()
    tabla_movs.put_item(Item={
        'TenantID': st.session_state.tenant,
        'MovID': f"M-{uid_k}",
        'Fecha': f_k, 'Hora': h_k,
        'Producto': producto_k,
        'Cantidad': int(cantidad_k),
        'Tipo': tipo_k,
        'Usuario': st.session_state.usuario
    })
if st.session_state.rol == "DUEÑO" and not st.session_state.get('modo_lectura', False):
    with tabs[3]:
        st.subheader("📋 Historial de Movimientos")
        fecha_h = st.date_input("Fecha de movimientos:", datetime.now(tz_peru), key="fecha_hist").strftime("%d/%m/%Y")
        res_m = tabla_movs.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant))
        items_movs_bruto = res_m.get('Items', [])
        if items_movs_bruto:
            df_hist_total = pd.DataFrame(items_movs_bruto)
            df_historial = df_hist_total[df_hist_total['Fecha'] == fecha_h]
            if not df_historial.empty:
                cols_hist = ['Hora', 'Producto', 'Cantidad', 'Tipo']
                if 'Usuario' in df_historial.columns:
                    cols_hist.append('Usuario')
                st.dataframe(
                    df_historial.sort_values("Hora", ascending=False)[cols_hist],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Hora": st.column_config.TextColumn("Hora", width="small"),
                        "Producto": st.column_config.TextColumn("Producto", width="medium"),
                        "Cantidad": st.column_config.NumberColumn("Cant", width="small"),
                        "Tipo": st.column_config.TextColumn("Tipo", width="medium"),
                        "Usuario": st.column_config.TextColumn("Usuario", width="small"),
                    }
                )
            else: st.info("Sin movimientos registrados hoy.")
        else: st.info("Historial vacío.")

    with tabs[4]:
        col_individual, col_masiva = st.columns(2)
        with col_individual:
            st.subheader("📥 Registro Individual")
            st.info(f"📦 **Plan {PLAN_ACTUAL}**: {MAX_PRODUCTOS_TOTALES} productos | {MAX_STOCK_POR_PRODUCTO} stock máximo por producto")
            with st.form("formulario_carga"):
                p_nombre = st.text_input("NOMBRE DEL PRODUCTO").upper()
                p_stock = st.number_input("STOCK INICIAL", min_value=1)
                p_costo = st.number_input("PRECIO COSTO (COMPRA)", min_value=0.0)
                p_venta = st.number_input("PRECIO VENTA", min_value=0.0)
                if st.form_submit_button("🚀 GUARDAR PRODUCTO"):
                    if p_nombre:
                        if p_stock > MAX_STOCK_POR_PRODUCTO:
                            st.error(f"❌ Tu plan permite máximo {MAX_STOCK_POR_PRODUCTO} unidades por producto.")
                        elif not df_inv[df_inv['Producto'] == p_nombre].empty:
                            st.error(f"❌ El producto '{p_nombre}' ya existe. Usa MANTENIMIENTO para reponer.")
                        else:
                            total_actual = contarProductosEnBD()
                            if total_actual >= MAX_PRODUCTOS_TOTALES:
                                st.error(f"❌ Llegaste al límite de {MAX_PRODUCTOS_TOTALES} productos de tu plan.\n\nPara más capacidad, actualiza tu plan.")
                            else:
                                tabla_stock.put_item(Item={'TenantID': st.session_state.tenant, 'Producto': p_nombre, 'Stock': int(p_stock), 'Precio': to_decimal(p_venta), 'Precio_Compra': to_decimal(p_costo)})
                                registrar_kardex(p_nombre, p_stock, "ENTRADA (NUEVO)")
                                st.success(f"✅ ¡Guardado! Te quedan {MAX_PRODUCTOS_TOTALES - total_actual - 1} espacios."); time.sleep(2); st.rerun()

        with col_masiva:
            st.subheader("📂 Carga Masiva (Excel/CSV)")
            st.caption(f"Columnas: Producto, Precio_Compra, Precio, Stock | Máx: 500 por carga")
            archivo_subido = st.file_uploader("Subir archivo", type=['xlsx', 'csv'], key="bulk_upload")
            if archivo_subido:
                try:
                    df_bulk = pd.read_excel(archivo_subido) if archivo_subido.name.endswith('xlsx') else pd.read_csv(archivo_subido)
                    df_bulk.columns = [str(c).strip().title() for c in df_bulk.columns]
                    st.write("Vista previa:", df_bulk.head(3))
                    total_actual = contarProductosEnBD()
                    espacios_libres = MAX_PRODUCTOS_TOTALES - total_actual
                    if len(df_bulk) > 500:
                        st.error("❌ Por rendimiento, sube máximo 500 productos por vez. Divide tu Excel.")
                        st.stop()
                    if len(df_bulk) > espacios_libres:
                        st.error(f"❌ Tu archivo tiene {len(df_bulk)} productos pero solo te quedan {espacios_libres} espacios.")
                        st.stop()
                    if df_bulk['Stock'].max() > MAX_STOCK_POR_PRODUCTO:
                        st.error(f"❌ Hay productos con stock mayor a {MAX_STOCK_POR_PRODUCTO}. Corrige tu Excel.")
                        st.stop()
                    if st.button("⚡ PROCESAR CARGA", use_container_width=True):
                        barra_progreso = st.progress(0)
                        total_items = len(df_bulk)
                        errores = []
                        productos_ok = []
                        with tabla_stock.batch_writer() as batch:
                            for i, fila in df_bulk.iterrows():
                                try:
                                    p_bulk = str(fila['Producto']).upper().strip()
                                    if not p_bulk:
                                        raise ValueError("Producto sin nombre")
                                    costo_val = to_decimal(pd.to_numeric(fila['Precio_Compra'], errors='coerce') or 0.0)
                                    precio_val = to_decimal(pd.to_numeric(fila['Precio'], errors='coerce') or 0.0)
                                    stock_val = int(pd.to_numeric(fila['Stock'], errors='coerce') or 0)
                                    if stock_val <= 0:
                                        raise ValueError(f"Stock debe ser > 0 en {p_bulk}")
                                    batch.put_item(Item={
                                        'TenantID': st.session_state.tenant,
                                        'Producto': p_bulk,
                                        'Precio_Compra': costo_val,
                                        'Precio': precio_val,
                                        'Stock': stock_val
                                    })
                                    productos_ok.append({'Producto': p_bulk, 'Stock': stock_val})
                                except Exception as e_item:
                                    errores.append(f"Fila {i+2}: {fila.get('Producto', 'SIN_NOMBRE')} - {str(e_item)}")
                                barra_progreso.progress((i + 1) / total_items)
                        for item_ok in productos_ok:
                            registrar_kardex(item_ok['Producto'], item_ok['Stock'], "CARGA MASIVA")
                        items_ok = len(productos_ok)
                        if errores:
                            st.error(f"⚠️ Carga parcial: {items_ok}/{total_items} productos guardados")
                            with st.expander("Ver errores"):
                                for error in errores:
                                    st.write(f"❌ {error}")
                        else:
                            st.success(f"✅ Carga perfecta: {items_ok} productos guardados")
                        time.sleep(2)
                        st.rerun()
                except Exception as e:
                    st.error("Error de sistema. Contacta a soporte.")
                    print(f"ERROR CARGA: {e}")

    with tabs[5]:
        st.subheader("🛠️ Gestión de Almacén")
        opcion_m = st.radio("Acción:", ["➕ REPONER STOCK", "📝 MODIFICAR PRECIOS", "🗑️ ELIMINAR"], horizontal=True)
        buscar_m = st.text_input("🔍 Buscar para gestionar:", key="input_mantenimiento").upper()
        lista_m = [p for p in df_inv['Producto'].tolist() if buscar_m in str(p)]
        if lista_m:
            p_sel_m = st.selectbox("Confirmar Producto:", lista_m, key="sel_mant_final")
            idx_m = df_inv[df_inv['Producto'] == p_sel_m].index
            if opcion_m == "➕ REPONER STOCK":
                cantidad_ingreso = st.number_input("Ingreso:", min_value=1)
                if st.button("✅ ACTUALIZAR"):
                    nuevo_stock_m = int(df_inv.at[idx_m[0], 'Stock'] + cantidad_ingreso)
                    if nuevo_stock_m > MAX_STOCK_POR_PRODUCTO:
                        st.error(f"❌ Tu plan no permite superar {MAX_STOCK_POR_PRODUCTO} unidades por producto. Stock actual: {df_inv.at[idx_m[0], 'Stock']}")
                    else:
                        tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_sel_m}, UpdateExpression="SET Stock = :s", ExpressionAttributeValues={':s': nuevo_stock_m})
                        registrar_kardex(p_sel_m, cantidad_ingreso, f"REPOSICIÓN (+{cantidad_ingreso})")
                        st.success("✅ Actualizado"); time.sleep(2); st.rerun()
            elif opcion_m == "📝 MODIFICAR PRECIOS":
                nuevo_c = st.number_input("Nuevo Costo:", value=float(df_inv.at[idx_m[0], 'Precio_Compra']))
                nuevo_v = st.number_input("Nueva Venta:", value=float(df_inv.at[idx_m[0], 'Precio']))
                if st.button("💾 GUARDAR"):
                    tabla_stock.update_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_sel_m}, UpdateExpression="SET Precio_Compra = :pc, Precio = :pv", ExpressionAttributeValues={':pc': to_decimal(nuevo_c), ':pv': to_decimal(nuevo_v)})
                    registrar_kardex(p_sel_m, 0, f"CAMBIO PRECIOS")
                    st.success("✅ Guardado"); time.sleep(2); st.rerun()
            else:
                if st.button(f"🗑️ ELIMINAR {p_sel_m}"):
                    tabla_stock.delete_item(Key={'TenantID': st.session_state.tenant, 'Producto': p_sel_m})
                    registrar_kardex(p_sel_m, 0, "BORRADO"); st.warning("Eliminado"); time.sleep(2); st.rerun()
with st.sidebar:
    st.title(f"🏢 {st.session_state.tenant}")
    st.write(f"Usuario: **{st.session_state.usuario}**")
    emoji_plan = {"BASICO": "🔵", "PRO": "🟣", "PREMIUM": "🟡"}.get(PLAN_ACTUAL, "⚪")
    st.caption(f"{emoji_plan} **Plan {PLAN_ACTUAL}** | S/ {float(PRECIO_ACTUAL):.0f}/mes")
    st.caption(f"Límite: {len(df_inv)}/{MAX_PRODUCTOS_TOTALES} productos")

    # ========== PANEL ADMIN COBROS ==========
    if st.session_state.rol == "DUEÑO":
        st.sidebar.markdown("---")
        st.sidebar.subheader("💰 Gestión de Cobros")
        with st.sidebar.expander("Registrar Pago Cliente"):
            tenants_res = tabla_tenants.scan()
            tenants_list = [t['TenantID'] for t in tenants_res.get('Items', [])]
            tenant_sel = st.selectbox("Cliente", tenants_list, key="cobro_tenant")
            monto = st.number_input("Monto S/.", min_value=0.0, step=10.0, key="cobro_monto")
            meses = st.number_input("Meses pagados", min_value=1, max_value=12, value=1, key="cobro_meses")
            if st.button("💵 Registrar Pago", key="btn_cobro"):
                t_data = tabla_tenants.get_item(Key={'TenantID': tenant_sel}).get('Item', {})
                prox_cobro_str = t_data.get('ProximoCobro', datetime.now(tz_peru).strftime('%d/%m/%Y'))
                prox_cobro = datetime.strptime(prox_cobro_str, '%d/%m/%Y')
                if prox_cobro.date() < datetime.now(tz_peru).date():
                    prox_cobro = datetime.now(tz_peru)
                nueva_fecha = (prox_cobro + timedelta(days=30*meses)).strftime('%d/%m/%Y')
                tabla_tenants.update_item(
                    Key={'TenantID': tenant_sel},
                    UpdateExpression="SET ProximoCobro=:f, EstadoPago=:e",
                    ExpressionAttributeValues={':f': nueva_fecha, ':e': 'ACTIVO'}
                )
                tabla_pagos.put_item(Item={
                    'PagoID': str(uuid.uuid4()),
                    'TenantID': tenant_sel,
                    'FechaRegistro': datetime.now(tz_peru).isoformat(),
                    'Monto': to_decimal(monto),
                    'Meses': int(meses),
                    'UsuarioRegistro': st.session_state.usuario
                })
                st.success(f"Pago registrado. Próximo cobro: {nueva_fecha}")
                time.sleep(2)
                st.rerun()
    # ========== FIN PANEL ==========

    if st.button("🔴 CERRAR SESIÓN"):
        st.session_state.auth = False
        st.session_state.rol = None
        st.session_state.tenant = None
        st.session_state.usuario = None
        st.session_state.nombre_emp_temp = ""
        st.session_state.carrito = []
        st.session_state.boleta = None
        st.session_state.confirmar = False
        st.session_state.verifico_cierre = False
        st.session_state.ultima_verificacion_fecha = None
        st.rerun()
