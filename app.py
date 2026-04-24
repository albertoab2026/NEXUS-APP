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

# --- 0. CONFIGURACIÓN ---
TABLA_STOCK = st.secrets["tablas"]["stock"]
TABLA_VENTAS = st.secrets["tablas"]["ventas"]
TABLA_MOVS = st.secrets["tablas"]["movs"]
TABLA_TENANTS = st.secrets["tablas"]["tenants"]
TABLA_CIERRES = st.secrets["tablas"]["cierres"]

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
except Exception as e:
    st.error("Error de sistema. Contacta a soporte.")
    print(f"ERROR AWS CONEXION: {e}")
    st.stop()

def registrar_cierre(total_cierre, usuario_turno, tipo_turno, usuario_cierre):
    f_c, h_c, uid_c = obtener_tiempo_peru()
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

def verificar_cierre_tardio():
    f_hoy, h_hoy, _ = obtener_tiempo_peru()
    ayer = (datetime.now(tz_peru) - timedelta(days=1)).strftime("%d/%m/%Y")

    res_v = tabla_ventas.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant))
    ventas_ayer = [v for v in res_v.get('Items', []) if v['Fecha'] == ayer]

    res_c = tabla_cierres.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant))
    cierres_ayer = [c for c in res_c.get('Items', []) if c['Fecha'] == ayer]

    if ventas_ayer and not cierres_ayer:
        total_pendiente = sum([Decimal(str(v['Total'])) for v in ventas_ayer])
        usuario_deudor = ventas_ayer[-1]['Usuario'] if ventas_ayer else "NADIE"
        registrar_cierre(total_pendiente, usuario_deudor, "CIERRE TARDÍO", "SISTEMA")
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

def obtener_limites_tenant():
    try:
        respuesta = tabla_tenants.get_item(Key={'TenantID': st.session_state.tenant})
        if 'Item' in respuesta:
            item = respuesta['Item']
            if item.get('Estado')!= 'ACTIVO':
                st.error("Tu plan está suspendido o vencido. Contacta a soporte para reactivar.")
                st.stop()

            max_prod = int(item['MaxProductos'])
            max_stock = int(item['MaxStock'])
            plan = item.get('Plan', 'BASICO')

            total_actual = contarProductosEnBD()
            df_temp = obtener_datos()
            stock_max_actual = int(df_temp['Stock'].max()) if not df_temp.empty else 0

            if total_actual > max_prod or stock_max_actual > max_stock:
                st.session_state.modo_lectura = True
                st.session_state.mensaje_lectura = f"⚠️ MODO LECTURA: Tienes {total_actual}/{max_prod} productos y stock máximo de {stock_max_actual}/{max_stock}. Solo puedes VENDER hasta regularizar tu plan {plan}."
            else:
                st.session_state.modo_lectura = False

            return max_prod, max_stock, plan
    except Exception as e:
        st.error("Error de sistema. Contacta a soporte.")
        print(f"ERROR PLAN: {e}")
        st.stop()
    return 1500, 500, 'BASICO'

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
# ===== LOGIN NUEVO CON NOMBRE EMPLEADO =====
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

if st.session_state.auth and 'verifico_cierre' not in st.session_state:
    with st.spinner('Verificando cierres pendientes...'):
        verificar_cierre_tardio()
    st.session_state.verifico_cierre = True

MAX_PRODUCTOS_TOTALES, MAX_STOCK_POR_PRODUCTO, PLAN_ACTUAL = obtener_limites_tenant()
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
with tabs[0]: # VENTA
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

with tabs[1]: # STOCK
    st.subheader("📦 Consulta de Almacén")
    col_filtro, col_excel = st.columns([3, 1])
    with col_filtro:
        filtro_stock = st.text_input("🔍 Escriba para filtrar tabla:", key="f_stock_input").upper()
    with col_excel:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_inv.to_excel(writer, index=False, sheet_name='Inventario')
        st.download_button(
            label="📥 Descargar Excel",
            data=output.getvalue(),
            file_name=f"Inventario_{st.session_state.tenant}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    df_mostrar = df_inv[df_inv['Producto'].str.contains(filtro_stock, na=False)]

    def estilo_filas(fila):
        if fila.Stock <= 0:
            return ['background-color: #721c24; color: white; font-weight: bold;'] * len(fila)
        elif fila.Stock < 5:
            return ['color: #ff4b4b; font-weight: bold;'] * len(fila)
        return [''] * len(fila)

    st.dataframe(
        df_mostrar.style.apply(estilo_filas, axis=1).format({"Precio": "{:.2f}", "Precio_Compra": "{:.2f}", "Stock": "{:d}"}),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Producto": st.column_config.TextColumn("Producto", width="medium"),
            "Precio_Compra": st.column_config.NumberColumn("Costo", format="S/ %.2f", width="small"),
            "Precio": st.column_config.NumberColumn("Venta", format="S/ %.2f", width="small"),
            "Stock": st.column_config.NumberColumn("Stock", width="small"),
        }
    )
with tabs[2]: # REPORTES
    st.subheader("📊 Reporte de Ventas e Inteligencia")

    fecha_input = st.date_input("Día a consultar:", datetime.now(tz_peru), key="fecha_rep")
    fecha_r = fecha_input.strftime("%d/%m/%Y")
    fecha_hace_7 = (fecha_input - timedelta(days=7)).strftime("%d/%m/%Y")

    res_v = tabla_ventas.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant))
    datos_ventas_bruto = res_v.get('Items', [])

    if datos_ventas_bruto:
        df_rep_total = pd.DataFrame(datos_ventas_bruto)
        df_rep = df_rep_total[df_rep_total['Fecha'] == fecha_r].copy()
        df_pasado = df_rep_total[df_rep_total['Fecha'] == fecha_hace_7]

        if not df_rep.empty:
            for columna in ['Total', 'Precio_Compra', 'Cantidad']:
                df_rep[columna] = df_rep[columna].apply(lambda x: Decimal(str(x)))

            df_rep['Inversion_F'] = df_rep['Precio_Compra'] * df_rep['Cantidad']
            total_venta_dia = df_rep['Total'].sum()
            num_tickets = df_rep['VentaID'].nunique()
            ticket_promedio = total_venta_dia / num_tickets if num_tickets > 0 else Decimal('0.00')

            if not df_pasado.empty:
                total_pasado = df_pasado['Total'].apply(lambda x: Decimal(str(x))).sum()
                delta_num = float(total_venta_dia - total_pasado)
            else:
                delta_num = None

            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("💰 VENTA TOTAL", f"S/ {float(total_venta_dia):.2f}", delta=delta_num)
            if delta_num is not None:
                st.caption("vs semana pasada")
            kpi2.metric("🎫 TICKET PROMEDIO", f"S/ {float(ticket_promedio):.2f}", delta=f"{num_tickets} Tickets hoy")

            if st.session_state.rol == "DUEÑO":
                ganancia_total_dia = total_venta_dia - df_rep['Inversion_F'].sum()
                kpi3.metric("📈 GANANCIA NETA", f"S/ {float(ganancia_total_dia):.2f}")
            else:
                kpi3.metric("👤 USUARIO", st.session_state.usuario)

            st.divider()

            def calcular_metodo(nombre_metodo):
                filtrado = df_rep[df_rep['Metodo'].str.contains(nombre_metodo, na=False)]
                return filtrado['Total'].sum() if not filtrado.empty else Decimal('0.00')

            ef_v = calcular_metodo("EFECTIVO")
            ya_v = calcular_metodo("YAPE")
            pl_v = calcular_metodo("PLIN")

            c1, c2, c3 = st.columns(3)
            c1.metric("💵 EFECTIVO", f"S/ {float(ef_v):.2f}")
            c2.metric("🟣 YAPE", f"S/ {float(ya_v):.2f}")
            c3.metric("🔵 PLIN", f"S/ {float(pl_v):.2f}")

            st.divider()
            f_hoy, _, _ = obtener_tiempo_peru()

            res_cierres_hoy = tabla_cierres.query(
                KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant)
            )
            cierres_hoy = [c for c in res_cierres_hoy.get('Items', []) if c['Fecha'] == f_hoy]

            venta_post_cierre = False
            usuario_turno_actual = st.session_state.usuario
            if cierres_hoy:
                ultimo_cierre_hora = max([c['Hora'] for c in cierres_hoy])
                hora_actual = datetime.now(tz_peru).hour
                ventas_post = df_rep[df_rep['Hora'] > ultimo_cierre_hora]
                # === PARCHE: POST-CIERRE SOLO DESPUÉS DE LAS 11PM ===
                if not ventas_post.empty and hora_actual >= 23: # 23 = 11pm
                    venta_post_cierre = True
                    total_post = ventas_post['Total'].sum()
                    st.error(f"🚨 POST-CIERRE: Hay S/{float(total_post):.2f} vendidos DESPUÉS del último cierre de hoy a las {ultimo_cierre_hora}.")
                    usuario_turno_actual = ventas_post['Usuario'].iloc[-1]

            if not cierres_hoy or venta_post_cierre:
                tipo_cierre = "CIERRE POST-CIERRE" if venta_post_cierre else "CIERRE TURNO"
                if st.button(f"🏁 GENERAR {tipo_cierre}", use_container_width=True, type="primary"):
                    registrar_cierre(
                        total_cierre=total_venta_dia,
                        usuario_turno=usuario_turno_actual,
                        tipo_turno=tipo_cierre,
                        usuario_cierre=st.session_state.usuario
                    )

                    # === PARCHE: WHATSAPP SOLO PRO Y PREMIUM ===
                    if PLAN_ACTUAL in ["PRO", "PREMIUM"]:
                        msg_wa = f"*CIERRE {tipo_cierre} - {st.session_state.tenant}*\n"
                        msg_wa += f"📅 Fecha: {fecha_r}\n"
                        msg_wa += f"👤 Caja de: {usuario_turno_actual}\n"
                        msg_wa += f"🔐 Cerrado por: {st.session_state.usuario}\n"
                        msg_wa += f"--------------------------\n"
                        msg_wa += f"💵 Efectivo: S/ {float(ef_v):.2f}\n"
                        msg_wa += f"🟣 Yape: S/ {float(ya_v):.2f}\n"
                        msg_wa += f"🔵 Plin: S/ {float(pl_v):.2f}\n"
                        msg_wa += f"--------------------------\n"
                        msg_wa += f"💰 *TOTAL: S/ {float(total_venta_dia):.2f}*"
                        if venta_post_cierre:
                            msg_wa += f"\n⚠️ *INCLUYE VENTAS POST-CIERRE*"
                        st.link_button("📲 Enviar Cierre por WhatsApp", f"https://wa.me/?text={urllib.parse.quote(msg_wa)}", use_container_width=True)
                    else:
                        st.warning("🔒 Enviar por WhatsApp solo disponible en planes PRO y PREMIUM. Actualiza tu plan.")
            else:
                ultimo = cierres_hoy[-1]
                st.success(f"✅ Día {f_hoy} cerrado a las {ultimo['Hora']}. Caja de: {ultimo['UsuarioTurno']}. Cerrado por: {ultimo['UsuarioCierre']}")

            if st.session_state.rol == "DUEÑO":
                st.divider()
                st.subheader("🔐 PANEL DUEÑO - CIERRE REMOTO")

                if not cierres_hoy:
                    res_v_all = tabla_ventas.query(KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant))
                    df_total = pd.DataFrame(res_v_all.get('Items', []))
                    if not df_total.empty:
                        df_total['Total'] = df_total['Total'].apply(lambda x: Decimal(str(x)))
                        df_hoy_v = df_total[df_total['Fecha'] == f_hoy]
                        total_hoy = df_hoy_v['Total'].sum() if not df_hoy_v.empty else Decimal('0.00')
                    else:
                        total_hoy = Decimal('0.00')

                    if total_hoy > 0:
                        st.error(f"🚨 OJO: Hoy {f_hoy} hay S/{float(total_hoy):.2f} vendido y NADIE CERRÓ CAJA.")
                        usuario_deudor = df_hoy_v['Usuario'].iloc[-1] if not df_hoy_v.empty else "EMPLEADO"
                        st.warning(f"Caja pendiente de: {usuario_deudor}")

                        if st.button("🏁 CERRAR DÍA AHORA DESDE CELULAR", type="primary", use_container_width=True):
                            registrar_cierre(
                                total_cierre=total_hoy,
                                usuario_turno=usuario_deudor,
                                tipo_turno="CIERRE REMOTO",
                                usuario_cierre=st.session_state.usuario
                            )
                            st.success(f"Día {f_hoy} cerrado remotamente. Queda fichado que {st.session_state.usuario} cerró la caja de {usuario_deudor}.")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                    else:
                        st.info("✅ No hay ventas hoy. Nada que cerrar.")
                else:
                    u_cierre = cierres_hoy[-1]
                    st.success(f"✅ Día {f_hoy} ya cerrado a las {u_cierre['Hora']} por {u_cierre['UsuarioCierre']}. Caja de: {u_cierre['UsuarioTurno']}")

            if st.session_state.rol == "DUEÑO":
                st.divider()
                st.subheader("🔝 Top 5 Productos")
                df_top = df_rep.groupby('Producto')['Cantidad'].sum().sort_values(ascending=False).head(5)
                st.bar_chart(df_top)

            cols_mostrar = ['Hora', 'Producto', 'Total', 'Metodo']
            if 'Usuario' in df_rep.columns:
                cols_mostrar.append('Usuario')

            st.dataframe(
                df_rep.sort_values("Hora", ascending=False)[cols_mostrar],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Hora": st.column_config.TextColumn("Hora", width="small"),
                    "Producto": st.column_config.TextColumn("Producto", width="medium"),
                    "Total": st.column_config.NumberColumn("Total", format="S/ %.2f", width="small"),
                    "Metodo": st.column_config.TextColumn("Método", width="small"),
                    "Usuario": st.column_config.TextColumn("Usuario", width="small"),
                }
            )
        else: st.info("No hay ventas en esta fecha.")
    else: st.info("Sin ventas registradas.")
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
    with tabs[3]: # HISTORIAL
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

    with tabs[4]: # CARGAR
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
            st.caption(f"Columnas: Producto, Precio_Compra, Precio, Stock | Límite: {MAX_PRODUCTOS_TOTALES} productos")
            archivo_subido = st.file_uploader("Subir archivo", type=['xlsx', 'csv'], key="bulk_upload")
            if archivo_subido:
                try:
                    df_bulk = pd.read_excel(archivo_subido) if archivo_subido.name.endswith('xlsx') else pd.read_csv(archivo_subido)
                    df_bulk.columns = [str(c).strip().title() for c in df_bulk.columns]
                    st.write("Vista previa:", df_bulk.head(3))

                    total_actual = contarProductosEnBD()
                    espacios_libres = MAX_PRODUCTOS_TOTALES - total_actual

                    if len(df_bulk) > espacios_libres:
                        st.error(f"❌ Tu archivo tiene {len(df_bulk)} productos pero solo te quedan {espacios_libres} espacios.\n\nLímite de tu plan: {MAX_PRODUCTOS_TOTALES} productos totales.")
                    elif df_bulk['Stock'].max() > MAX_STOCK_POR_PRODUCTO:
                        st.error(f"❌ Hay productos con stock mayor a {MAX_STOCK_POR_PRODUCTO}. Corrige tu Excel.")
                    else:
                        if st.button("⚡ PROCESAR CARGA", use_container_width=True):
                            barra_progreso = st.progress(0)
                            for i, fila in df_bulk.iterrows():
                                p_bulk = str(fila['Producto']).upper()
                                costo_val = to_decimal(pd.to_numeric(fila['Precio_Compra'], errors='coerce') or 0.0)
                                precio_val = to_decimal(pd.to_numeric(fila['Precio'], errors='coerce') or 0.0)
                                stock_val = int(pd.to_numeric(fila['Stock'], errors='coerce') or 0)
                                tabla_stock.put_item(Item={'TenantID': st.session_state.tenant, 'Producto': p_bulk, 'Precio_Compra': costo_val, 'Precio': precio_val, 'Stock': stock_val})
                                registrar_kardex(p_bulk, stock_val, "CARGA MASIVA")
                                barra_progreso.progress((i + 1) / len(df_bulk))
                            st.success(f"✅ Carga finalizada. Productos cargados: {len(df_bulk)}"); time.sleep(2); st.rerun()
                except Exception as e:
                    st.error("Error de sistema. Contacta a soporte.")
                    print(f"ERROR CARGA: {e}")

    with tabs[5]: # MANTENIMIENTO
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
    st.caption(f"{emoji_plan} **Plan {PLAN_ACTUAL}** | Límite: {len(df_inv)}/{MAX_PRODUCTOS_TOTALES} productos")

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
        st.rerun()        
