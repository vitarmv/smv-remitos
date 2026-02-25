import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from fpdf import FPDF
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA Y DISEÑO
# ==========================================
st.set_page_config(page_title="SMV | Sistema de Gestión", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .main { background-color: #F8F9FA; }
    h1 { color: #1E3A8A; font-family: 'Helvetica', sans-serif; }
    .stButton>button { background-color: #1E3A8A; color: white; border-radius: 5px; }
    .stSelectbox label, .stTextInput label, .stNumberInput label { font-weight: bold; color: #1E3A8A; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CONEXIÓN A FIREBASE
# ==========================================
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        cred_dict = dict(st.secrets["firebase"])
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# ==========================================
# 3. FUNCIONES DE BASE DE DATOS
# ==========================================
def obtener_productos():
    productos_ref = db.collection("productos").stream()
    return {doc.id: doc.to_dict() for doc in productos_ref}

def guardar_producto(codigo, descripcion, costo):
    db.collection("productos").document(codigo).set({
        "descripcion": descripcion,
        "costo": float(costo)
    })

def obtener_clientes():
    clientes_ref = db.collection("clientes").stream()
    return {doc.id: doc.to_dict() for doc in clientes_ref}

def guardar_cliente(nombre, direccion, localidad, dni_cuit, email, celular):
    doc_id = dni_cuit if dni_cuit.strip() != "" else celular
    if doc_id.strip() == "": doc_id = nombre
    db.collection("clientes").document(doc_id).set({
        "nombre": nombre, "direccion": direccion, "localidad": localidad,
        "dni_cuit": dni_cuit, "email": email, "celular": celular
    })

def guardar_venta(cliente_nombre, num_remito, total_costo, total_venta, ganancia, items_vendidos):
    # Guardamos el registro contable de la venta
    db.collection("ventas").document(num_remito).set({
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cliente": cliente_nombre,
        "num_remito": num_remito,
        "costo_total": float(total_costo),
        "venta_total": float(total_venta),
        "ganancia_neta": float(ganancia),
        "detalle_items": items_vendidos
    })

def obtener_ventas():
    ventas_ref = db.collection("ventas").order_by("fecha", direction=firestore.Query.DESCENDING).stream()
    return [doc.to_dict() for doc in ventas_ref]

# ==========================================
# 4. FUNCIÓN PARA GENERAR EL PDF (Seguro, sin costos)
# ==========================================
def generar_pdf(datos_cliente, fecha, num_remito, df_items, subtotal, ajuste, total):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 10, 'DISTRIBUIDORA SMV', ln=True)
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, 'Venta exclusiva al gremio | Importacion Directa', ln=True)
    pdf.cell(0, 5, 'Buenos Aires, CABA', ln=True)
    pdf.ln(8)
    
    # Datos Documento y Cliente
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(100, 8, f'REMITO Nro: {num_remito}')
    pdf.cell(0, 8, f'Fecha: {fecha}', ln=True)
    pdf.ln(4)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 8, ' DATOS DEL CLIENTE', border=1, ln=True, fill=True)
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 8, f" Nombre/Local: {datos_cliente.get('nombre', '')}", border='L')
    pdf.cell(0, 8, f" DNI/CUIT: {datos_cliente.get('dni_cuit', '')}", border='R', ln=True)
    pdf.cell(100, 8, f" Direccion: {datos_cliente.get('direccion', '')}, {datos_cliente.get('localidad', '')}", border='L')
    pdf.cell(0, 8, f" Celular: {datos_cliente.get('celular', '')}", border='R', ln=True)
    pdf.cell(0, 8, f" Email: {datos_cliente.get('email', '')}", border='LBR', ln=True)
    pdf.ln(8)
    
    # Tabla de productos (SOLO VENTA, NADA DE COSTOS)
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(90, 8, 'Descripcion', border=1, fill=True)
    pdf.cell(20, 8, 'Cant.', border=1, align='C', fill=True)
    pdf.cell(40, 8, 'Precio Unit. (USD)', border=1, align='C', fill=True)
    pdf.cell(40, 8, 'Subtotal (USD)', border=1, align='C', fill=True)
    pdf.ln()
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(0, 0, 0)
    for _, row in df_items.iterrows():
        if str(row['Descripción']).strip() != "":
            pdf.cell(90, 8, str(row['Descripción'])[:45], border=1)
            pdf.cell(20, 8, str(row['Cantidad']), border=1, align='C')
            pdf.cell(40, 8, f"${row['Precio Venta']:.2f}", border=1, align='C')
            pdf.cell(40, 8, f"${row['Subtotal Venta']:.2f}", border=1, align='C')
            pdf.ln()
            
    # Totales
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(150, 8, 'Subtotal:', align='R')
    pdf.cell(40, 8, f'${subtotal:.2f}', ln=True, align='R')
    if ajuste != 0:
        texto_ajuste = 'Descuento:' if ajuste < 0 else 'Recargo:'
        pdf.cell(150, 8, texto_ajuste, align='R')
        pdf.cell(40, 8, f'${ajuste:.2f}', ln=True, align='R')
    pdf.set_font('Arial', 'B', 13)
    pdf.cell(150, 10, 'TOTAL A PAGAR (USD):', align='R')
    pdf.cell(40, 10, f'${total:.2f}', ln=True, align='R')
    
    # Pie de página legal
    pdf.ln(20)
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, 'Remito interno de control de mercaderia. Garantia oficial 6 meses.', align='C', ln=True)
    pdf.cell(0, 5, 'Los valores expresados son netos. Pagos en USD billete o USDT.', align='C')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 5. INTERFAZ DE USUARIO CON PESTAÑAS
# ==========================================
st.title("📦 Sistema de Gestión SMV")

# CREAMOS LAS PESTAÑAS
tab1, tab2 = st.tabs(["🧾 Emitir Remito", "📊 Reporte de Ganancias"])

with tab1:
    col_cliente, col_producto = st.columns(2)

    # --- PANEL DE CLIENTES ---
    cat_clientes = obtener_clientes()
    opciones_clientes = ["➕ Agregar Cliente Nuevo"]
    mapa_clientes = {}
    for doc_id, data in cat_clientes.items():
        nombre_mostrar = f"{data.get('nombre', '')} - {data.get('localidad', '')}"
        opciones_clientes.append(nombre_mostrar)
        mapa_clientes[nombre_mostrar] = data

    with col_cliente:
        st.subheader("👤 Datos del Cliente")
        cliente_seleccionado = st.selectbox("Buscar Cliente", opciones_clientes)
        datos_actuales_cliente = {}
        
        if cliente_seleccionado == "➕ Agregar Cliente Nuevo":
            with st.container(border=True):
                n_nombre = st.text_input("Nombre y Apellido / Local")
                col_a, col_b = st.columns(2)
                with col_a:
                    n_dni = st.text_input("DNI o CUIT")
                    n_cel = st.text_input("Celular / WhatsApp")
                with col_b:
                    n_loc = st.text_input("Localidad")
                    n_dir = st.text_input("Dirección")
                n_email = st.text_input("Email")
                if st.button("💾 Guardar Cliente", type="primary", use_container_width=True):
                    if n_nombre and n_cel:
                        guardar_cliente(n_nombre, n_dir, n_loc, n_dni, n_email, n_cel)
                        st.success("¡Cliente guardado! Actualiza la página (F5).")
                    else:
                        st.warning("El Nombre y el Celular son obligatorios.")
                datos_actuales_cliente = {"nombre": n_nombre, "direccion": n_dir, "localidad": n_loc, "dni_cuit": n_dni, "email": n_email, "celular": n_cel}
        else:
            datos_actuales_cliente = mapa_clientes[cliente_seleccionado]
            st.info(f"📍 {datos_actuales_cliente.get('direccion', '')}, {datos_actuales_cliente.get('localidad', '')}\n📱 Tel: {datos_actuales_cliente.get('celular', '')}")

        num_remito = st.text_input("Número de Remito", value=f"0001-{datetime.now().strftime('%y%m%d%H')}")

    # --- PANEL DE PRODUCTOS ---
    with col_producto:
        st.subheader("🛒 Catálogo Rápido")
        with st.expander("Añadir producto nuevo a la base de datos"):
            nuevo_codigo = st.text_input("Código Interno (Ej: S25-256)")
            nueva_desc = st.text_input("Descripción del Producto")
            nuevo_costo = st.number_input("Costo Proveedor (USD)", min_value=0.0, step=10.0, help="El precio al que vos lo comprás")
            if st.button("Guardar en Catálogo"):
                if nuevo_codigo and nueva_desc:
                    guardar_producto(nuevo_codigo, nueva_desc, nuevo_costo)
                    st.success("Producto guardado exitosamente.")
                else:
                    st.warning("Completa el código y la descripción.")

    st.divider()

    # --- TABLA DE FACTURACIÓN CON COSTOS ---
    st.subheader("🧾 Detalle de Mercadería")

    if 'df_items' not in st.session_state:
        st.session_state.df_items = pd.DataFrame(
            [{"Descripción": "", "Cantidad": 1, "Costo Unit.": 0.0, "Precio Venta": 0.0, "Subtotal Venta": 0.0}] * 5
        )

    df_editado = st.data_editor(
        st.session_state.df_items,
        column_config={
            "Descripción": st.column_config.TextColumn("Descripción del Producto", width="large"),
            "Cantidad": st.column_config.NumberColumn("Cant.", min_value=1, step=1),
            "Costo Unit.": st.column_config.NumberColumn("Costo Prov. (USD) 🔒", min_value=0.0, format="$%.2f", help="Solo para tu control interno"),
            "Precio Venta": st.column_config.NumberColumn("Precio Venta (USD)", min_value=0.0, format="$%.2f"),
            "Subtotal Venta": st.column_config.NumberColumn("Subtotal", disabled=True, format="$%.2f")
        },
        num_rows="dynamic",
        use_container_width=True
    )

    # Cálculos dinámicos internos
    df_editado["Subtotal Venta"] = df_editado["Cantidad"] * df_editado["Precio Venta"]
    df_editado["Costo Total Fila"] = df_editado["Cantidad"] * df_editado["Costo Unit."]
    
    subtotal_venta_calculado = df_editado["Subtotal Venta"].sum()
    costo_total_operacion = df_editado["Costo Total Fila"].sum()

    st.divider()

    # --- TOTALES Y GENERACIÓN DE PDF ---
    col_tot1, col_tot2 = st.columns([3, 1])
    with col_tot2:
        st.write(f"**Subtotal Venta:** ${subtotal_venta_calculado:.2f}")
        ajuste = st.number_input("Ajuste / Descuento (USD)", value=0.0, step=5.0)
        total_final = subtotal_venta_calculado + ajuste
        ganancia_operacion = total_final - costo_total_operacion
        
        st.markdown(f"### TOTAL A COBRAR: ${total_final:.2f}")

    if st.button("📄 Generar Remito PDF y Registrar Venta", type="primary", use_container_width=True):
        nombre_validacion = datos_actuales_cliente.get('nombre', '')
        if not nombre_validacion:
            st.error("⚠️ Selecciona el nombre del cliente arriba.")
        else:
            df_limpio = df_editado[df_editado["Descripción"].str.strip() != ""]
            if df_limpio.empty:
                st.warning("⚠️ No has agregado ningún producto al remito.")
            else:
                fecha_actual = datetime.now().strftime("%d/%m/%Y")
                
                # 1. Registrar en Base de Datos (Firebase)
                items_lista = df_limpio.to_dict('records')
                guardar_venta(nombre_validacion, num_remito, costo_total_operacion, total_final, ganancia_operacion, items_lista)
                
                # 2. Generar el PDF
                pdf_bytes = generar_pdf(datos_actuales_cliente, fecha_actual, num_remito, df_limpio, subtotal_venta_calculado, ajuste, total_final)
                
                st.success(f"¡Venta registrada! Ganancia estimada: ${ganancia_operacion:.2f} USD")
                st.download_button(
                    label="⬇️ Descargar PDF para el Cliente",
                    data=pdf_bytes,
                    file_name=f"Remito_SMV_{nombre_validacion.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )

# --- PESTAÑA 2: REPORTES ---
with tab2:
    st.header("📊 Inteligencia de Negocios")
    st.write("Historial de operaciones y cálculo de ganancias netas.")
    
    if st.button("🔄 Actualizar Datos"):
        st.rerun()
        
    ventas_historicas = obtener_ventas()
    
    if ventas_historicas:
        df_ventas = pd.DataFrame(ventas_historicas)
        
        # Metricas Clave
        m1, m2, m3 = st.columns(3)
        m1.metric("Ingresos Totales (Cobrado)", f"${df_ventas['venta_total'].sum():.2f}")
        m2.metric("Costo de Mercadería (Pagado)", f"${df_ventas['costo_total'].sum():.2f}")
        m3.metric("Ganancia Neta (Bolsillo)", f"${df_ventas['ganancia_neta'].sum():.2f}")
        
        st.divider()
        st.subheader("Historial Detallado")
        
        # Ocultar la columna de items detallados para la vista de tabla para que sea más limpia
        df_mostrar = df_ventas[['fecha', 'num_remito', 'cliente', 'costo_total', 'venta_total', 'ganancia_neta']]
        st.dataframe(df_mostrar, use_container_width=True)
        
        # Exportar a Excel (CSV)
        csv_export = df_mostrar.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Reporte Completo en Excel (CSV)",
            data=csv_export,
            file_name=f"Reporte_Ganancias_SMV_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("Todavía no hay ventas registradas. Generá tu primer remito para ver las estadísticas acá.")
