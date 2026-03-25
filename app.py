import streamlit as st
import groq
import fitz
import requests
import base64
import io
from PIL import Image

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="Alberto AI - Pro Hub", page_icon="🏢", layout="wide")

# Estética White Edition (Limpia y Moderna)
st.markdown("""
    <style>
    .stApp { background-color: #f7f7f8; color: #212121; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e5e5e5; }
    .stChatMessage { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 12px; }
    .stExpander { background-color: #ffffff; border: 1px solid #eee; border-radius: 10px; margin-bottom: 10px; }
    h1 { color: #1a1a1a; font-family: 'Inter', sans-serif; }
    .welcome-box { padding: 3rem; text-align: center; background: white; border-radius: 20px; border: 1px solid #eee; margin-top: 5rem; }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZACIÓN DE ESTADOS ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "imagenes_galeria" not in st.session_state:
    st.session_state.imagenes_galeria = [] # Aquí guardaremos las fotos

# --- PANTALLA DE ACCESO ---
def pantalla_acceso():
    with st.sidebar:
        st.title("🆔 Identificación")
        nombre = st.text_input("¿Quién eres?", placeholder="Tu nombre...")
        if st.button("Entrar al Hub"):
            if nombre.strip():
                st.session_state.autenticado = True
                st.session_state.usuario_actual = nombre.strip()
                st.rerun()
            else:
                st.warning("Introduce un nombre.")

if not st.session_state.autenticado:
    st.markdown("<div class='welcome-box'><h1>Alberto AI Premium</h1><p>Identifícate en el panel lateral para acceder a tus herramientas.</p></div>", unsafe_allow_html=True)
    pantalla_acceso()
    st.stop()

# --- LLAVES API ---
try:
    cliente_groq = groq.Groq(api_key=st.secrets["GROQ_API_KEY"])
    HF_API_KEY = st.secrets["HUGGINGFACE_API_KEY"]
except:
    st.error("Error: Revisa las Keys en los Secrets.")
    st.stop()

def generar_imagen(prompt):
    URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    try:
        r = requests.post(URL, headers=headers, json={"inputs": prompt}, timeout=20)
        return base64.b64encode(r.content).decode() if r.status_code == 200 else None
    except: return None

# --- BARRA LATERAL (HERRAMIENTAS DESPLEGABLES) ---
with st.sidebar:
    st.markdown(f"### ✨ Hola, **{st.session_state.usuario_actual}**")
    st.markdown("---")
    
    # 1. Desplegable para Subir Archivos
    with st.expander("📄 Subir Documento PDF"):
        archivo_pdf = st.file_uploader("", type=["pdf"], label_visibility="collapsed")
        if archivo_pdf:
            doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
            st.session_state.pdf_content = "".join([p.get_text() for p in doc])
            st.success(f"Analizado: {archivo_pdf.name}")

    # 2. Desplegable para Galería de Imágenes
    with st.expander("🎨 Mi Galería de Imágenes"):
        if not st.session_state.imagenes_galeria:
            st.caption("Aún no has generado imágenes.")
        else:
            for i, img_data in enumerate(reversed(st.session_state.imagenes_galeria)):
                st.image(base64.b64decode(img_data), caption=f"Imagen {len(st.session_state.imagenes_galeria)-i}", use_container_width=True)
                st.markdown("---")

    st.markdown("---")
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.session_state.mensajes = []
        st.session_state.imagenes_galeria = []
        st.rerun()

# --- CHAT PRINCIPAL ---
if "mensajes" not in st.session_state:
    st.session_state.mensajes = [{"role": "system", "content": f"Eres Alberto AI. Hablas con {st.session_state.usuario_actual}. Responde siempre en español. Si piden imagen, usa [IMAGEN] + prompt inglés."}]

# Mostrar historial
for m in st.session_state.mensajes:
    if m["role"] != "system":
        with st.chat_message(m["role"]):
            if "tipo" in m and m["tipo"] == "img":
                st.image(base64.b64decode(m["content"]), use_container_width=True)
            else:
                st.markdown(m["content"])

# Input de usuario
if prompt := st.chat_input(f"¿Qué necesitas hoy, {st.session_state.usuario_actual}?"):
    st.session_state.mensajes.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        
        ctx = [m for m in st.session_state.mensajes if "tipo" not in m]
        if "pdf_content" in st.session_state:
            ctx.insert(1, {"role": "system", "content": f"Contexto PDF: {st.session_state.pdf_content[:3000]}"})

        stream = cliente_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=ctx,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                full_res += chunk.choices[0].delta.content
                if not full_res.startswith("[IMAGEN]"):
                    placeholder.markdown(full_res + "▌")

        if full_res.startswith("[IMAGEN]"):
            placeholder.info("🎨 Generando arte...")
            img_b64 = generar_imagen(full_res.replace("[IMAGEN]", "").strip())
            if img_b64:
                placeholder.empty()
                st.image(base64.b64decode(img_b64), use_container_width=True)
                # GUARDAR EN HISTORIAL Y EN GALERÍA
                st.session_state.mensajes.append({"role": "assistant", "content": img_b64, "tipo": "img"})
                st.session_state.imagenes_galeria.append(img_b64)
                st.rerun() # Refrescamos para que aparezca en el desplegable lateral al momento
        else:
            st.session_state.mensajes.append({"role": "assistant", "content": full_res})