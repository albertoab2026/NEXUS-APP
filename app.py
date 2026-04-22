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
import io # Necesario para el Excel

# --- 0. CONFIGURACIÓN ---
TABLA_STOCK = 'SaaS_Stock_Test'
TABLA_VENTAS = 'SaaS_Ventas_Test'
TABLA_MOVS = 'SaaS_Movimientos_Test'
TABLA_TENANTS = 'NEXUS_TENANTS' # ← NUEVA TABLA DE PLANES

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
    # Intento de conexión con secrets de Streamlit
    dynamodb = boto3.resource('dynamodb',
                              region_name=st.secrets["aws"]["aws_region"],
                              aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
                              aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"])
    tabla_stock = dynamodb.Table(TABLA_STOCK)
    tabla_ventas = dynamodb.Table(TABLA_VENTAS)
    tabla_movs = dynamodb.Table(TABLA_MOVS)
    tabla_tenants = dynamodb.Table(TABLA_TENANTS) # ← NUEVA
except Exception as e:
    st.error(f"Error conexión AWS: {e}")
    st.stop()

# === NUEVA FUNCIÓN: LEER LÍMITES DEL PLAN DESDE DYNAMODB ===
def obtener_limites_tenant():
    """Lee los límites de MaxProductos y MaxStock desde la tabla NEXUS_TENANTS"""
    try:
        respuesta = tabla_tenants.get_item(Key={'TenantID': st.session_state.tenant})
        if 'Item' in respuesta:
            item = respuesta['Item']
            # Si está suspendido o vencido, bloquea todo
            if item.get('Estado')!= 'ACTIVO':
                st.error("Tu plan está suspendido o vencido. Contacta a soporte para reactivar.")
                st.stop()
            return int(item['MaxProductos']), int(item['MaxStock'])
    except Exception as e:
        st.error(f"Error cargando tu plan: {e}")
        st.stop()
    return 0, 0 # Si falla, bloquea por seguridad

# === NUEVA FUNCIÓN: CONTAR PRODUCTOS EN DYNAMODB ===
def contarProductosEnBD():
    """Cuenta cuántos productos hay en total para el tenant actual. Usa Select=COUNT pa' que sea barato."""
    try:
        respuesta = tabla_stock.query(
            KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant),
            Select='COUNT'
        )
        return respuesta.get('Count', 0)
    except Exception as e:
        st.error(f"Error contando productos: {e}")
        return 9999 # Si falla, bloquea por seguridad

if 'auth' not in st.session_state:
    st.session_state.auth = False
if 'rol' not in st.session_state:
    st.session_state.rol = None
if 'tenant' not in st.session_state:
    st.session_state.tenant = None
if 'carrito' not in st.session_state:
    st.session_state.carrito = []
if 'boleta' not in st.session_state:
    st.session_state.boleta = None
if 'confirmar' not in st.session_state:
    st.session_state.confirmar = False

if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center; color: #3498db;'>🚀 NEXUS BALLARTA SaaS</h1>", unsafe_allow_html=True)
    nombres_negocios = [k for k in st.secrets["auth_multi"].keys() if not k.endswith("_emp")]
    local_seleccionado = st.selectbox("📍 Seleccione su Negocio:", nombres_negocios)
    clave_ingresada = st.text_input("🔑 Contraseña:", type="password")
    clave_ingresada = clave_ingresada.strip()[:30]

    col_dueño, col_empleado = st.columns(2)

    def intentar_login(tipo_usuario):
        if not re.match("^[A-Za-z0-9]*$", clave_ingresada):
            time.sleep(2)
            st.error("❌ No se permiten símbolos raros.")
            return

        if tipo_usuario == "DUEÑO":
            clave_correcta = st.secrets["auth_multi"][local_seleccionado]
        else:
            clave_correcta = st.secrets["auth_multi"].get(f"{local_seleccionado}_emp")

        if clave_ingresada == str(clave_correcta):
            st.session_state.auth = True
            st.session_state.tenant = local_seleccionado
            st.session_state.rol = tipo_usuario
            st.rerun()
        else:
            time.sleep(2)
            st.error(f"❌ Contraseña de {tipo_usuario} incorrecta")

    if col_dueño.button("🔓 DUEÑO", use_container_width=True):
        intentar_login("DUEÑO")
    if col_empleado.button("🧑‍💼 EMPLEADO", use_container_width=True):
        intentar_login("EMPLEADO")
    st.stop()

# === CANDADOS DINÁMICOS POR PLAN - SE CARGAN DESPUÉS DEL LOGIN ===
MAX_PRODUCTOS_TOTALES, MAX_STOCK_POR_PRODUCTO = obtener_limites_tenant()

def obtener_datos():
    respuesta = tabla_stock.query(
        KeyConditionExpression=Key('TenantID').eq(st.session_state.tenant)
    )
    items = respuesta.get('Items', [])
    df = pd.DataFrame(items)
    if df.empty:
        return pd.DataFrame(columns=['Producto', 'Precio_Compra', 'Precio', 'Stock'])
    df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0).astype(int)
    df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0.0)
    df['Precio_Compra'] = pd.to_numeric(df['Precio_Compra'], errors='coerce').fillna(0.0)
    return df[['Producto', 'Precio_Compra', 'Precio', 'Stock']].sort_values('Producto')

df_inv = obtener_datos()

lista_pestanas = ["🛒 VENTA", "📦 STOCK", "📊 REPORTES"]
if st.session_state.rol == "DUEÑO":
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

        texto_wa = f"*TICKET DE VENTA - {st.session_state.tenant}*\n"
        texto_wa += f"Fecha: {b['fecha']} {b['hora']}\n---\n"
        for i in b['items']:
            texto_wa += f"{i['Cantidad']}x {i['Producto']} - S/{float(i['Subtotal']):.2f}\n"
        texto_wa += f"---\n*TOTAL NETO: S/{float(b['t_neto']):.2f}*\nMetodo: {b['metodo']}\n"
        texto_wa += f"_*No válido como comprobante tributario*_"
        wa_url = f"https://wa.me/?text={urllib.parse.quote(texto_wa)}"
        st.link_button("📲 Enviar reporte por WhatsApp", wa_url, use_container_width=True)

        try:
            # CAMBIO: PDF AHORA EN 80MM PARA TIQUETERA
            pdf = FPDF(orientation='P', unit='mm', format=(80, 200))
            pdf.add_page()
            pdf.set_margins(3, 3, 3)
            pdf.set_auto_page_break(auto=True, margin=3)

            # Encabezado
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(74, 6, txt=str(st.session_state.tenant)[:30], ln=True, align='C')
            pdf.set_font("Arial", size=8)
            pdf.cell(74, 4, txt=f"{b['fecha']} {b['hora']}", ln=True, align='C')
            pdf.cell(74, 2, txt="-" * 42, ln=True, align='C')

            # Productos
            pdf.set_font("Arial", size=9)
            for i in b['items']:
                nombre_corto = i['Producto'][:20]
                pdf.cell(50, 5, txt=f"{i['Cantidad']}x {nombre_corto}")
                pdf.cell(24, 5, txt=f"S/{float(i['Subtotal']):.2f}", ln=True, align='R')

            pdf.cell(74, 2, txt="-" * 42, ln=True, align='C')

            # Totales
            pdf.set_font("Arial", size=8)
            metodo_limpio = b['metodo'].replace("💵 ", "").replace("🟣 ", "").replace("🔵 ", "")
            pdf.cell(50, 4, txt=f"Pago: {metodo_limpio}")
            pdf.cell(24, 4, txt=f"Desc: -S/{float(b['rebaja']):.2f}", ln=True, align='R')

            pdf.set_font("Arial", 'B', 10)
            pdf.cell(74, 6, txt=f"TOTAL: S/ {float(b['t_neto']):.2f}", ln=True, align='C')

            # Pie legal
            pdf.set_font("Arial", 'I', 7)
            pdf.cell(74, 4, txt="Documento de control interno", ln=True, align='C')
            pdf.cell(74, 3, txt="No valido como comprobante SUNAT", ln=True, align='C')

            pdf_bytes = pdf.output(dest='S').encode('latin-1', 'ignore')
            st.download_button(label="📥 Descargar Ticket PDF 80mm", data=pdf_bytes, file_name=f"Ticket_{b['fecha'].replace('/','-')}.pdf", mime="application/pdf", use_container_width=True)
        except Exception as e:
            st.error(f"Error PDF: {e}")

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
                        # --- MEJORA ANTI-NEGATIVOS: ConditionExpression ---
                        try:
                            # Intentamos restar el stock solo si es mayor o igual a la cantidad pedida
                            tabla_stock.update_item(
                                Key={'TenantID': st.session_state.tenant, 'Producto': item_v['Producto']},
                                UpdateExpression="SET Stock = Stock - :s",
                                ConditionExpression="Stock >= :s",
                                ExpressionAttributeValues={':s': item_v['Cantidad']}
                            )

                            # Si la actualización de stock fue exitosa, registramos la venta
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
                                'Usuario': st.session_state.rol
                            })
                        except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
                            # Si alguien vendió el producto en ese mismo instante y ya no hay stock:
                            st.error(f"❌ ¡CRÍTICO! El stock de '{item_v['Producto']}' cambió justo ahora y ya no hay suficiente. Venta cancelada.")
                            st.stop()

                    st.session_state.boleta = {'items': st.session_state.carrito, 't_neto': total_neto, 'rebaja': to_decimal(rebaja_v), 'metodo': metodo_p, 'fecha': f_v, 'hora': h_v}
                    st.session_state.carrito = []
                    st.session_state.confirmar = False
                    st.rerun()

with tabs[1]: # STOCK
    st.subheader("📦 Consulta de Almacén")

    # --- MEJORA: BOTÓN EXCEL AL LADO DEL FILTRO ---
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
    st.dataframe(df_mostrar.style.apply(estilo_filas, axis=1).format({"Precio": "{:.2f}", "Precio_Compra": "{:.2f}", "Stock": "{:d}"}), use_container_width=True, hide_index=True)

# --- REPORTES CORREGIDO ---
with tabs[2]:
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
                delta_valor = f"S/ {float(total_venta_dia - total_pasado):.2f} vs semana pasada"
            else:
                delta_valor = "Iniciando historial..."

            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("💰 VENTA TOTAL", f"S/ {float(total_venta_dia):.2f}", delta=delta_valor)
            kpi2.metric("🎫 TICKET PROMEDIO", f"S/ {float(ticket_promedio):.2f}", delta=f"{num_tickets} Tickets hoy")

            if st.session_state.rol == "DUEÑO":
                ganancia_total_dia = total_venta_dia - df_rep['Inversion_F'].sum()
                kpi3.metric("📈 GANANCIA NETA", f"S/ {float(ganancia_total_dia):.2f}")
            else:
                kpi3.metric("👤 USUARIO", st.session_state.rol)

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
            tipo_cierre = "TOTAL" if st.session_state.rol == "DUEÑO" else "DE MI TURNO"
            if st.button(f"🏁 GENERAR CIERRE {tipo_cierre}", use_container_width=True, type="primary"):
                msg_wa = f"*CIERRE {tipo_cierre} - {st.session_state.tenant}*\n"
                msg_wa += f"📅 Fecha: {fecha_r}\n👤 Por: {st.session_state.rol}\n"
                msg_wa += f"--------------------------\n"
                msg_wa += f"💵 Efectivo: S/ {float(ef_v):.2f}\n"
                msg_wa += f"🟣 Yape: S/ {float(ya_v):.2f}\n"
                msg_wa += f"🔵 Plin: S/ {float(pl_v):.2f}\n"
                msg_wa += f"--------------------------\n"
                msg_wa += f"💰 *TOTAL CAJA: S/ {float(total_venta_dia):.2f}*"
                st.link_button("📲 Enviar Cierre por WhatsApp", f"https://wa.me/?text={urllib.parse.quote(msg_wa)}", use_container_width=True)

            if st.session_state.rol == "DUEÑO":
                st.divider()
                st.subheader("🔝 Top 5 Productos")
                df_top = df_rep.groupby('Producto')['Cantidad'].sum().sort_values(ascending=False).head(5)
                st.bar_chart(df_top)

            cols_mostrar = ['Hora', 'Producto', 'Total', 'Metodo']
            if 'Usuario' in df_rep.columns:
                cols_mostrar.append('Usuario')

            st.dataframe(df_rep.sort_values("Hora", ascending=False)[cols_mostrar], use_container_width=True, hide_index=True)
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
        'Usuario': st.session_state.rol
    })

if st.session_state.rol == "DUEÑO":
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
                st.dataframe(df_historial.sort_values("Hora", ascending=False)[cols_hist], use_container_width=True, hide_index=True)
            else: st.info("Sin movimientos registrados hoy.")
        else: st.info("Historial vacío.")

    with tabs[4]: # CARGAR - AQUÍ ESTÁN LOS CANDADOS DINÁMICOS
        col_individual, col_masiva = st.columns(2)
        with col_individual:
            st.subheader("📥 Registro Individual")
            st.caption(f"Límite de tu plan: {MAX_PRODUCTOS_TOTALES} productos | {MAX_STOCK_POR_PRODUCTO} stock máximo")
            with st.form("formulario_carga"):
                p_nombre = st.text_input("NOMBRE DEL PRODUCTO").upper()
                p_stock = st.number_input("STOCK INICIAL", min_value=1, max_value=MAX_STOCK_POR_PRODUCTO)
                p_costo = st.number_input("PRECIO COSTO (COMPRA)", min_value=0.0)
                p_venta = st.number_input("PRECIO VENTA", min_value=0.0)
                if st.form_submit_button("🚀 GUARDAR PRODUCTO"):
                    if p_nombre:
                        # CANDADO 1: STOCK MÁXIMO DEL PLAN
                        if p_stock > MAX_STOCK_POR_PRODUCTO:
                            st.error(f"❌ Tu plan permite máximo {MAX_STOCK_POR_PRODUCTO} unidades por producto.")
                        # CANDADO 2: VERIFICAR SI YA EXISTE
                        elif not df_inv[df_inv['Producto'] == p_nombre].empty:
                            st.error(f"❌ El producto '{p_nombre}' ya existe. Usa MANTENIMIENTO para reponer.")
                        else:
                            # CANDADO 3: MÁXIMO PRODUCTOS DEL PLAN
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

                    # VALIDAR CANDADOS ANTES DE PROCESAR
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
                except Exception as e: st.error(f"Error archivo: {e}")

    with tabs[5]: # MANTENIMIENTO
        st.subheader("🛠️ Gestión de Almacén")
        opcion_m = st.radio("Acción:", ["➕ REPONER STOCK", "📝 MODIFICAR PRECIOS", "🗑️ ELIMINAR"], horizontal=True)
        buscar_m = st.text_input("🔍 Buscar para gestionar:", key="input_mantenimiento").upper()
        lista_m = [p for p in df_inv['Producto'].tolist() if buscar_m in str(p)]
        if lista_m:
            p_sel_m = st.selectbox("Confirmar Producto:", lista_m, key="sel_mant_final")
            idx_m = df_inv[df_inv['Producto'] == p_sel_m].index
            if opcion_m == "➕ REPONER STOCK":
                cantidad_ingreso = st.number_input("Ingreso:", min_value=1, max_value=MAX_STOCK_POR_PRODUCTO)
                if st.button("✅ ACTUALIZAR"):
                    nuevo_stock_m = int(df_inv.at[idx_m[0], 'Stock'] + cantidad_ingreso)
                    # CANDADO: No pasar el límite del plan ni sumando
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
    st.write(f"Usuario: **{st.session_state.rol}**")
    st.caption(f"Plan activo | Límite: {len(df_inv)}/{MAX_PRODUCTOS_TOTALES} productos")
    if st.button("🔴 CERRAR SESIÓN"):
        st.session_state.auth = False
        st.rerun()
