import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from fpdf import FPDF
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA Y DISEÑO
# ==========================================
st.set_page_config(page_title="SMV | Sistema de Remitos", layout="wide", initial_sidebar_state="collapsed")

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
# --- PRODUCTOS ---
def obtener_productos():
    productos_ref = db.collection("productos").stream()
    return {doc.id: doc.to_dict() for doc in productos_ref}

def guardar_producto(codigo, descripcion, precio):
    db.collection("productos").document(codigo).set({
        "descripcion": descripcion,
        "precio": float(precio)
    })

# --- CLIENTES ---
def obtener_clientes():
    clientes_ref = db.collection("clientes").stream()
    return {doc.id: doc.to_dict() for doc in clientes_ref}

def guardar_cliente(nombre, direccion, localidad, dni_cuit, email, celular):
    doc_id = dni_cuit if dni_cuit.strip() != "" else celular
    if doc_id.strip() == "":
        doc_id = nombre # Fallback por si no pone ni DNI ni Celular
        
    db.collection("clientes").document(doc_id).set({
        "nombre": nombre,
        "direccion": direccion,
        "localidad": localidad,
        "dni_cuit": dni_cuit,
        "email": email,
        "celular": celular
    })

# ==========================================
# 4. FUNCIÓN PARA GENERAR EL PDF
# ==========================================
def generar_pdf(datos_cliente, fecha, num_remito, df_items, subtotal, ajuste, total):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado Empresa
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 10, 'DISTRIBUIDORA SMV', ln=True)
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, 'Venta exclusiva al gremio | Importacion Directa', ln=True)
    pdf.cell(0, 5, 'Buenos Aires, CABA', ln=True)
    pdf.ln(8)
    
    # Datos del Documento
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(100, 8, f'REMITO Nro: {num_remito}')
    pdf.cell(0, 8, f'Fecha: {fecha}', ln=True)
    pdf.ln(4)
    
    # Datos del Cliente
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
    
    # Tabla de productos
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
            pdf.cell(40, 8, f"${row['Precio Unitario']:.2f}", border=1, align='C')
            pdf.cell(40, 8, f"${row['Subtotal']:.2f}", border=1, align='C')
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
# 5. INTERFAZ DE USUARIO (FRONTEND)
# ==========================================
st.title("📦 Sistema de Gestión SMV")

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
                    
            datos_actuales_cliente = {
                "nombre": n_nombre, "direccion": n_dir, "localidad": n_loc,
                "dni_cuit": n_dni, "email": n_email, "celular": n_cel
            }
    else:
        datos_actuales_cliente = mapa_clientes[cliente_seleccionado]
        st.info(f"📍 **Ubicación:** {datos_actuales_cliente.get('direccion', '')}, {datos_actuales_cliente.get('localidad', '')}\n\n📱 **Tel:** {datos_actuales_cliente.get('celular', '')} | ✉️ **Email:** {datos_actuales_cliente.get('email', '')}\n\n🆔 **DNI/CUIT:** {datos_actuales_cliente.get('dni_cuit', '')}")

    num_remito = st.text_input("Número de Remito", value="0001-00000001")

# --- PANEL DE PRODUCTOS ---
with col_producto:
    st.subheader("🛒 Catálogo Rápido")
    with st.expander("Añadir producto nuevo a la base de datos"):
        nuevo_codigo = st.text_input("Código Interno (Ej: S25-256)")
        nueva_desc = st.text_input("Descripción del Producto")
        nuevo_precio = st.number_input("Precio Venta (USD)", min_value=0.0, step=10.0)
        if st.button("Guardar en Catálogo"):
            if nuevo_codigo and nueva_desc:
                guardar_producto(nuevo_codigo, nueva_desc, nuevo_precio)
                st.success("Producto guardado exitosamente.")
            else:
                st.warning("Completa el código y la descripción.")

st.divider()

# --- TABLA DE FACTURACIÓN ---
st.subheader("🧾 Detalle de Mercadería")

if 'df_items' not in st.session_state:
    st.session_state.df_items = pd.DataFrame(
        [{"Descripción": "", "Cantidad": 1, "Precio Unitario": 0.0, "Subtotal": 0.0}] * 5
    )

df_editado = st.data_editor(
    st.session_state.df_items,
    column_config={
        "Descripción": st.column_config.TextColumn("Descripción del Producto"),
        "Cantidad": st.column_config.NumberColumn("Cant.", min_value=1, step=1),
        "Precio Unitario": st.column_config.NumberColumn("Precio U. (USD)", min_value=0.0, format="$%.2f"),
        "Subtotal": st.column_config.NumberColumn("Subtotal", disabled=True, format="$%.2f")
    },
    num_rows="dynamic",
    use_container_width=True
)

df_editado["Subtotal"] = df_editado["Cantidad"] * df_editado["Precio Unitario"]
subtotal_calculado = df_editado["Subtotal"].sum()

st.divider()

# --- TOTALES Y GENERACIÓN DE PDF ---
col_tot1, col_tot2 = st.columns([3, 1])
with col_tot2:
    st.write(f"**Subtotal:** ${subtotal_calculado:.2f}")
    ajuste = st.number_input("Ajuste / Descuento (USD)", value=0.0, step=5.0, help="Negativo para descuentos")
    total_final = subtotal_calculado + ajuste
    st.markdown(f"### TOTAL: ${total_final:.2f}")

if st.button("📄 Generar Remito PDF", type="primary", use_container_width=True):
    nombre_validacion = datos_actuales_cliente.get('nombre', '')
    if not nombre_validacion:
        st.error("⚠️ Por favor, ingresa o selecciona el nombre del cliente arriba.")
    else:
        df_limpio = df_editado[df_editado["Descripción"].str.strip() != ""]
        if df_limpio.empty:
            st.warning("⚠️ No has agregado ningún producto al remito.")
        else:
            fecha_actual = datetime.now().strftime("%d/%m/%Y")
            pdf_bytes = generar_pdf(datos_actuales_cliente, fecha_actual, num_remito, df_limpio, subtotal_calculado, ajuste, total_final)
            
            st.success("¡Remito generado con éxito!")
            st.download_button(
                label="⬇️ Descargar PDF",
                data=pdf_bytes,
                file_name=f"Remito_SMV_{nombre_validacion.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )
