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

def obtener_siguiente_remito():
    try:
        ventas_ref = db.collection("ventas").order_by("num_remito", direction=firestore.Query.DESCENDING).limit(1).get()
        if ventas_ref:
            ultimo_remito = ventas_ref[0].to_dict().get("num_remito", "")
            if "-" in ultimo_remito:
                partes = ultimo_remito.split("-")
                siguiente_numero = int(partes[1]) + 1
                return f"0001-{siguiente_numero:08d}"
    except Exception:
        pass
    return "0001-00000100"

# ==========================================
# 4. FUNCIÓN PARA GENERAR EL PDF
# ==========================================
def generar_pdf(datos_cliente, fecha, num_remito, df_items, subtotal, ajuste, total):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 10, 'DISTRIBUIDORA SMV', ln=True)
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, 'Venta exclusiva al gremio | Importacion Directa', ln=True)
    pdf.cell(0, 5, 'Buenos Aires, CABA', ln=True)
    pdf.ln(8)
    
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
        pdf.cell(90, 8, str(row['Descripción'])[:45], border=1)
        pdf.cell(20, 8, str(row['Cantidad']), border=1, align='C')
        pdf.cell(40, 8, f"${row['Precio Venta']:.2f}", border=1, align='C')
        pdf.cell(40, 8, f"${row['Subtotal Venta']:.2f}", border=1, align='C')
        pdf.ln()
            
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
    
    pdf.ln(20)
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, 'Remito interno de control de mercaderia. Garantia oficial 6 meses.', align='C', ln=True)
    pdf.cell(0, 5, 'Los valores expresados son netos. Pagos en USD billete o USDT.', align='C')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 5. INTERFAZ DE USUARIO
# ==========================================
st.title("📦 Sistema de Gestión SMV")

tab1, tab2, tab3 = st.tabs(["🧾 Emitir Remito", "📊 Reportes", "📦 Catálogo de Proveedor"])

# --- PESTAÑA 3: CATÁLOGO ---
with tab3:
    st.header("📦 Listado de Productos del Proveedor")
    
    with st.expander("➕ Añadir nuevo producto al catálogo"):
        c_cod = st.text_input("Código (Ej: S25-256)", key="cat_cod")
        c_desc = st.text_input("Descripción del Producto", key="cat_desc")
        c_costo = st.number_input("Costo Proveedor (USD)", min_value=0.0, step=10.0, key="cat_costo")
        if st.button("Guardar Producto", type="primary"):
            if c_cod and c_desc:
                guardar_producto(c_cod, c_desc, c_costo)
                st.success("Producto guardado exitosamente.")
            else:
                st.warning("Completa el código y la descripción.")
                
    prods_db = obtener_productos()
    if prods_db:
        lista_prods = [{"Código": k, "Descripción": v.get("descripcion", ""), "Costo Proveedor (USD)": v.get("costo", 0.0)} for k, v in prods_db.items()]
        df_catalogo = pd.DataFrame(lista_prods)
        st.dataframe(df_catalogo, use_container_width=True)
        
        csv_cat = df_catalogo.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Catálogo en Excel", data=csv_cat, file_name="Catalogo_SMV.csv", mime="text/csv")
    else:
        st.info("El catálogo está vacío. Cargá productos para empezar.")

# --- PESTAÑA 1: REMITOS ---
with tab1:
    cat_clientes = obtener_clientes()
    opciones_clientes = ["➕ Agregar Cliente Nuevo"]
    mapa_clientes = {}
    for doc_id, data in cat_clientes.items():
        nombre_mostrar = f"{data.get('nombre', '')} - {data.get('localidad', '')}"
        opciones_clientes.append(nombre_mostrar)
        mapa_clientes[nombre_mostrar] = data

    st.subheader("👤 Cliente y Remito")
    col_c1, col_c2 = st.columns([2, 1])
    with col_c1:
        cliente_seleccionado = st.selectbox("Buscar Cliente", opciones_clientes, label_visibility="collapsed")
    with col_c2:
        num_remito_sugerido = obtener_siguiente_remito()
        num_remito = st.text_input("Número de Remito", value=num_remito_sugerido)
        
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
            if st.button("💾 Guardar Cliente", type="primary"):
                if n_nombre and n_cel:
                    guardar_cliente(n_nombre, n_dir, n_loc, n_dni, n_email, n_cel)
                    st.success("¡Cliente guardado! Actualiza la página (F5).")
            datos_actuales_cliente = {"nombre": n_nombre, "direccion": n_dir, "localidad": n_loc, "dni_cuit": n_dni, "email": n_email, "celular": n_cel}
    else:
        datos_actuales_cliente = mapa_clientes[cliente_seleccionado]

    st.divider()
    
    # -- CARRITO DE COMPRAS --
    st.subheader("🛒 Agregar Productos al Remito")
    
    mapa_prods = {v['descripcion']: v for k, v in prods_db.items()} if prods_db else {}
    opciones_prods = ["-- Seleccione un producto --"] + list(mapa_prods.keys())
    
    col_sel1, col_sel2, col_sel3 = st.columns([2, 1, 1])
    with col_sel1:
        prod_seleccionado = st.selectbox("Buscar en Catálogo", opciones_prods)
    
    costo_sugerido = 0.0
    if prod_seleccionado != "-- Seleccione un producto --":
        costo_sugerido = float(mapa_prods[prod_seleccionado].get("costo", 0.0))
        
    with col_sel2:
        cant_ingresar = st.number_input("Cantidad", min_value=1, step=1, value=1)
    with col_sel3:
        precio_venta_ingresar = st.number_input("Precio Venta (USD)", min_value=0.0, value=costo_sugerido)
        
    if st.button("➕ Añadir a la lista"):
        if prod_seleccionado != "-- Seleccione un producto --":
            if 'df_items' not in st.session_state:
                st.session_state.df_items = []
            
            # Se agrega con el tilde de "Quitar" en False por defecto
            st.session_state.df_items.append({
                "Quitar": False,
                "Descripción": prod_seleccionado,
                "Cantidad": cant_ingresar,
                "Costo Unit.": costo_sugerido,
                "Precio Venta": precio_venta_ingresar,
                "Subtotal Venta": cant_ingresar * precio_venta_ingresar
            })
            st.rerun()
        else:
            st.warning("Por favor selecciona un producto de la lista.")

    # -- TABLA DE RESULTADOS --
    st.subheader("🧾 Detalle de Mercadería a Facturar")
    if 'df_items' not in st.session_state:
        st.session_state.df_items = []
        
    df_actual = pd.DataFrame(st.session_state.df_items)
    
    if not df_actual.empty:
        # num_rows="fixed" evita que se cree un renglón vacío al final
        df_editado = st.data_editor(
            df_actual,
            column_config={
                "Quitar": st.column_config.CheckboxColumn("🗑️ Quitar", default=False),
                "Descripción": st.column_config.TextColumn("Descripción", width="large", disabled=True),
                "Cantidad": st.column_config.NumberColumn("Cant.", min_value=1),
                "Costo Unit.": st.column_config.NumberColumn("Costo Prov. (USD) 🔒", format="$%.2f", disabled=True),
                "Precio Venta": st.column_config.NumberColumn("Precio Venta (USD)", format="$%.2f"),
                "Subtotal Venta": st.column_config.NumberColumn("Subtotal", format="$%.2f", disabled=True)
            },
            num_rows="fixed", 
            use_container_width=True
        )
        
        # Procesar si el usuario tildó la opción de Quitar en alguna fila
        if df_editado["Quitar"].any():
            # Filtramos dejando solo los que NO están tildados para quitar
            df_restante = df_editado[df_editado["Quitar"] == False].copy()
            # Guardamos el estado limpio y recargamos
            st.session_state.df_items = df_restante.to_dict('records')
            st.rerun()
        
        # Recálculo normal si no se eliminó nada
        df_editado["Subtotal Venta"] = df_editado["Cantidad"] * df_editado["Precio Venta"]
        df_editado["Costo Total Fila"] = df_editado["Cantidad"] * df_editado["Costo Unit."]
        
        # Guardar en memoria omitiendo la columna temporal de costo total
        st.session_state.df_items = df_editado.drop(columns=["Costo Total Fila"], errors='ignore').to_dict('records')
        
        subtotal_venta = df_editado["Subtotal Venta"].sum()
        costo_total = df_editado["Costo Total Fila"].sum()
    else:
        st.info("La lista está vacía. Usa el buscador de arriba para agregar productos.")
        subtotal_venta = 0.0
        costo_total = 0.0

    st.divider()

    col_tot1, col_tot2 = st.columns([3, 1])
    with col_tot2:
        st.write(f"**Subtotal Venta:** ${subtotal_venta:.2f}")
        ajuste = st.number_input("Ajuste / Descuento (USD)", value=0.0, step=5.0)
        total_final = subtotal_venta + ajuste
        ganancia_operacion = total_final - costo_total
        
        st.markdown(f"### TOTAL A COBRAR: ${total_final:.2f}")

    if st.button("📄 Generar Remito PDF y Registrar Venta", type="primary", use_container_width=True):
        if not datos_actuales_cliente.get('nombre', ''):
            st.error("⚠️ Falta el cliente.")
        elif df_actual.empty:
            st.warning("⚠️ No has agregado productos.")
        else:
            fecha_actual = datetime.now().strftime("%d/%m/%Y")
            guardar_venta(datos_actuales_cliente['nombre'], num_remito, costo_total, total_final, ganancia_operacion, st.session_state.df_items)
            
            # Pasamos df_editado al PDF (la función PDF ignora la columna 'Quitar' automáticamente)
            pdf_bytes = generar_pdf(datos_actuales_cliente, fecha_actual, num_remito, df_editado, subtotal_venta, ajuste, total_final)
            
            st.success(f"¡Registrado! Ganancia: ${ganancia_operacion:.2f} USD")
            st.download_button("⬇️ Descargar PDF", data=pdf_bytes, file_name=f"Remito_{num_remito}.pdf", mime="application/pdf")
            
            if st.button("Limpiar para nueva venta"):
                st.session_state.df_items = []
                st.rerun()

# --- PESTAÑA 2: REPORTES ---
with tab2:
    st.header("📊 Inteligencia de Negocios")
    ventas_historicas = obtener_ventas()
    
    if ventas_historicas:
        df_ventas = pd.DataFrame(ventas_historicas)
        m1, m2, m3 = st.columns(3)
        m1.metric("Ingresos Totales", f"${df_ventas['venta_total'].sum():.2f}")
        m2.metric("Costo de Mercadería", f"${df_ventas['costo_total'].sum():.2f}")
        m3.metric("Ganancia Neta", f"${df_ventas['ganancia_neta'].sum():.2f}")
        
        st.dataframe(df_ventas[['fecha', 'num_remito', 'cliente', 'costo_total', 'venta_total', 'ganancia_neta']], use_container_width=True)
