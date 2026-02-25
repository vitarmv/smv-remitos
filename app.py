import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from fpdf import FPDF
from datetime import datetime
import io

# 1. CONFIGURACIÓN DE PÁGINA Y DISEÑO
st.set_page_config(page_title="SMV | Sistema de Remitos", layout="wide", initial_sidebar_state="collapsed")

# CSS personalizado para darle un look corporativo neutro
st.markdown("""
    <style>
    .main { background-color: #F8F9FA; }
    h1 { color: #1E3A8A; font-family: 'Helvetica', sans-serif; }
    .stButton>button { background-color: #1E3A8A; color: white; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

# 2. CONEXIÓN A FIREBASE
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        # Lee los secretos configurados en Streamlit Cloud
        cred_dict = dict(st.secrets["firebase"])
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# 3. FUNCIONES DE BASE DE DATOS
def obtener_productos():
    productos_ref = db.collection("productos").stream()
    return {doc.id: doc.to_dict() for doc in productos_ref}

def guardar_producto(codigo, descripcion, precio):
    db.collection("productos").document(codigo).set({
        "descripcion": descripcion,
        "precio": float(precio)
    })

# 4. FUNCIÓN PARA GENERAR EL PDF
def generar_pdf(cliente, fecha, num_remito, df_items, subtotal, ajuste, total):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(30, 58, 138) # Azul oscuro
    pdf.cell(0, 10, 'DISTRIBUIDORA SMV', ln=True)
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, 'Venta exclusiva al gremio | Importación Directa', ln=True)
    pdf.cell(0, 5, 'Buenos Aires, CABA', ln=True)
    pdf.ln(10)
    
    # Datos del Documento y Cliente
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(100, 8, f'REMITO Nro: {num_remito}')
    pdf.cell(0, 8, f'Fecha: {fecha}', ln=True)
    
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, f'Cliente / Local: {cliente}', ln=True)
    pdf.ln(5)
    
    # Tabla de productos
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(90, 8, 'Descripción', border=1)
    pdf.cell(20, 8, 'Cant.', border=1, align='C')
    pdf.cell(40, 8, 'Precio Unit. (USD)', border=1, align='C')
    pdf.cell(40, 8, 'Subtotal (USD)', border=1, align='C')
    pdf.ln()
    
    pdf.set_font('Arial', '', 10)
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
    
    # Pie de página legal (.com)
    pdf.ln(20)
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, 'Remito interno de control de mercadería. Garantía oficial 6 meses.', align='C', ln=True)
    pdf.cell(0, 5, 'Los valores expresados son netos. Pagos en USD billete o USDT.', align='C')
    
    return pdf.output(dest='S').encode('latin-1')

# 5. INTERFAZ DE USUARIO (FRONTEND)
st.title("📦 Generador de Remitos SMV")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Datos del Cliente")
    cliente_nombre = st.text_input("Nombre del Cliente o Local")
    num_remito = st.text_input("Número de Remito", value="0001-00000001")

with col2:
    st.subheader("Catálogo Rápido (Guardar nuevo)")
    with st.expander("Añadir producto a la base de datos"):
        nuevo_codigo = st.text_input("Código (Ej: IPH17-256)")
        nueva_desc = st.text_input("Descripción del Producto")
        nuevo_precio = st.number_input("Precio Venta (USD)", min_value=0.0, step=10.0)
        if st.button("Guardar en Catálogo"):
            guardar_producto(nuevo_codigo, nueva_desc, nuevo_precio)
            st.success("Producto guardado exitosamente.")

st.divider()

# Cargar productos existentes para referencia
cat_productos = obtener_productos()
nombres_productos = [p['descripcion'] for p in cat_productos.values()]

st.subheader("Detalle de Mercadería")

# Estado de la tabla
if 'df_items' not in st.session_state:
    st.session_state.df_items = pd.DataFrame(
        [{"Descripción": "", "Cantidad": 1, "Precio Unitario": 0.0, "Subtotal": 0.0}] * 5
    )

# Editor de datos interactivo
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

# Cálculos dinámicos
df_editado["Subtotal"] = df_editado["Cantidad"] * df_editado["Precio Unitario"]
subtotal_calculado = df_editado["Subtotal"].sum()

st.divider()

col_tot1, col_tot2 = st.columns([3, 1])
with col_tot2:
    st.write(f"**Subtotal:** ${subtotal_calculado:.2f}")
    ajuste = st.number_input("Ajuste / Descuento (USD)", value=0.0, step=5.0, help="Usa valores negativos para descuentos (Ej: -15)")
    total_final = subtotal_calculado + ajuste
    st.markdown(f"### TOTAL: ${total_final:.2f}")

# Botón de Generación de PDF
if st.button("📄 Generar Remito PDF", type="primary"):
    if not cliente_nombre:
        st.error("Por favor, ingresa el nombre del cliente.")
    else:
        # Filtrar filas vacías
        df_limpio = df_editado[df_editado["Descripción"].str.strip() != ""]
        fecha_actual = datetime.now().strftime("%d/%m/%Y")
        
        pdf_bytes = generar_pdf(cliente_nombre, fecha_actual, num_remito, df_limpio, subtotal_calculado, ajuste, total_final)
        
        st.success("¡Remito generado con éxito!")
        st.download_button(
            label="⬇️ Descargar PDF",
            data=pdf_bytes,
            file_name=f"Remito_SMV_{cliente_nombre.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )
