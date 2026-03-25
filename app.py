import streamlit as st
import groq
import fitz
import requests
import base64
import io
from PIL import Image

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="Alberto AI - Community", page_icon="🤝", layout="wide")

# Estética White Edition mejorada
st.markdown("""
    <style>
    .stApp { background-color: #f7f7f8; color: #212121; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e5e5e5; }
    .stChatMessage { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 12px; }
    h1 { color: #1a1a1a; font-family: 'Inter', sans-serif; }
    .welcome-box { padding: 3rem; text-align: center; background: white; border-radius: 20px; border: 1px solid #eee; margin-top: 5rem; }
    </style>
    """, unsafe_allow_html=True)

# --- SISTEMA DE IDENTIFICACIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

def pantalla_acceso():
    with st.sidebar:
        st.title("🆔 Identificación")
        nombre = st.text_input("¿Cómo te llamas?", placeholder="Escribe tu nombre...")
        if st.button("Comenzar Sesión"):
            if nombre.strip():
                st.session_state.autenticado = True
                st.session_state.usuario_actual = nombre.strip()
                st.rerun()
            else:
                st.warning("Por favor, introduce un nombre.")

if not st.session_state.autenticado:
    st.markdown("<div class='welcome-box'><h1>Bienvenido a la IA de Alberto</h1><p>Por favor, identifícate en la barra lateral para empezar a chatear.</p></div>", unsafe_allow_html=True)
    pantalla_acceso()
    st.stop()

# --- CONFIGURACIÓN DE APIS ---
try:
    cliente_groq = groq.Groq(api_key=st.secrets["GROQ_API_KEY"])
    HF_API_KEY = st.secrets["HUGGINGFACE_API_KEY"]
except:
    st.error("Error en las llaves API de los Secrets.")
    st.stop()

def generar_imagen(prompt):
    URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    try:
        r = requests.post(URL, headers=headers, json={"inputs": prompt}, timeout=20)
        return base64.b64encode(r.content).decode() if r.status_code == 200 else None
    except: return None

# --- INTERFAZ DE USUARIO ACTIVA ---
with st.sidebar:
    st.markdown(f"### ✨ Sesión de: **{st.session_state.usuario_actual}**")
    st.markdown("---")
    st.markdown("### 📂 Analizar PDF")
    archivo_pdf = st.file_uploader("", type=["pdf"], label_visibility="collapsed")
    
    if archivo_pdf:
        doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
        st.session_state.pdf_content = "".join([p.get_text() for p in doc])
        st.success(f"Archivo '{archivo_pdf.name}' listo.")

    if st.button("Cambiar de Usuario"):
        st.session_state.autenticado = False
        st.session_state.mensajes = [] # Limpiamos chat al salir
        st.rerun()

# Memoria del chat individual
if "mensajes" not in st.session_state:
    st.session_state.mensajes = [{"role": "system", "content": f"Eres Alberto AI. Estás hablando con {st.session_state.usuario_actual}. Eres amable, brillante y respondes en español. Si piden imagen, usa [IMAGEN] + prompt en inglés."}]

# Mostrar historial
for m in st.session_state.mensajes:
    if m["role"] != "system":
        with st.chat_message(m["role"]):
            if "tipo" in m and m["tipo"] == "img":
                st.image(base64.b64decode(m["content"]), use_container_width=True)
            else:
                st.markdown(m["content"])

# Chat
if prompt := st.chat_input(f"¿En qué puedo ayudarte, {st.session_state.usuario_actual}?"):
    st.session_state.mensajes.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        
        ctx = [m for m in st.session_state.mensajes if "tipo" not in m]
        if "pdf_content" in st.session_state:
            ctx.insert(1, {"role": "system", "content": f"Documento actual: {st.session_state.pdf_content[:3000]}"})

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
            placeholder.info("🎨 Generando arte para ti...")
            img_b64 = generar_imagen(full_res.replace("[IMAGEN]", "").strip())
            if img_b64:
                placeholder.empty()
                st.image(base64.b64decode(img_b64), use_container_width=True)
                st.session_state.mensajes.append({"role": "assistant", "content": img_b64, "tipo": "img"})
        else:
            st.session_state.mensajes.append({"role": "assistant", "content": full_res})