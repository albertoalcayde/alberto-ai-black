import streamlit as st
import groq
import fitz
import requests
import base64
import io
from PIL import Image

# --- CONFIGURACIÓN DE ÉLITE ---
st.set_page_config(page_title="Alberto AI - Multi-User", page_icon="👥", layout="wide")

# Estética Premium "Light Mode"
st.markdown("""
    <style>
    .stApp { background-color: #f7f7f8; color: #212121; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e5e5e5; }
    .stChatMessage { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 12px; }
    .stChatInput { border-radius: 10px !important; border: 1px solid #ddd !important; }
    h1 { color: #1a1a1a; font-family: 'Inter', sans-serif; }
    .login-box { padding: 2rem; border-radius: 15px; background: white; border: 1px solid #ddd; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- SISTEMA DE USUARIOS (GESTIÓN DIRECTA) ---
# Aquí puedes añadir a tus amigos y familiares. 
# Formato: "usuario": "contraseña"
USUARIOS_AUTORIZADOS = {
    "alberto": "pro2024",
    "familia": "casa2024",
    "amigo1": "invitado123"
}

# --- CONTROL DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

def login():
    with st.sidebar:
        st.title("🔐 Acceso Privado")
        usuario = st.text_input("Usuario")
        clave = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            if usuario in USUARIOS_AUTORIZADOS and USUARIOS_AUTORIZADOS[usuario] == clave:
                st.session_state.autenticado = True
                st.session_state.usuario_actual = usuario
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

if not st.session_state.autenticado:
    st.markdown("<div class='login-box'><h1>Bienvenido a Alberto AI</h1><p>Introduce tus credenciales en la barra lateral para comenzar.</p></div>", unsafe_allow_html=True)
    login()
    st.stop()

# --- SI ESTÁ AUTENTICADO, CARGAMOS EL RESTO ---

# Lógica de APIs
try:
    cliente_groq = groq.Groq(api_key=st.secrets["GROQ_API_KEY"])
    HF_API_KEY = st.secrets["HUGGINGFACE_API_KEY"]
except:
    st.error("Error de configuración de llaves API.")
    st.stop()

def generar_imagen(prompt):
    URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    try:
        r = requests.post(URL, headers=headers, json={"inputs": prompt}, timeout=20)
        return base64.b64encode(r.content).decode() if r.status_code == 200 else None
    except: return None

# --- INTERFAZ DEL USUARIO LOGUEADO ---
with st.sidebar:
    st.markdown(f"### 👋 Hola, {st.session_state.usuario_actual.capitalize()}")
    st.markdown("---")
    st.markdown("### 📄 Tus Documentos")
    archivo_pdf = st.file_uploader("Sube un PDF", type=["pdf"], label_visibility="collapsed")
    
    if archivo_pdf:
        doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
        st.session_state.pdf_content = "".join([p.get_text() for p in doc])
        st.success(f"Analizado: {archivo_pdf.name}")

    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# Memoria del chat (Cada usuario tiene la suya en su sesión de navegador)
if "mensajes" not in st.session_state:
    st.session_state.mensajes = [{"role": "system", "content": f"Eres Alberto AI. Te diriges a {st.session_state.usuario_actual}. Eres profesional y respondes en español. Imágenes con [IMAGEN] + prompt inglés."}]

# Mostrar historial
for m in st.session_state.mensajes:
    if m["role"] != "system":
        with st.chat_message(m["role"]):
            if "tipo" in m and m["tipo"] == "img":
                st.image(base64.b64decode(m["content"]), use_container_width=True)
            else:
                st.markdown(m["content"])

# Entrada de chat
if prompt := st.chat_input(f"Dime algo, {st.session_state.usuario_actual.capitalize()}..."):
    st.session_state.mensajes.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        
        # Construir contexto incluyendo el PDF si existe
        messages_to_send = [m for m in st.session_state.mensajes if "tipo" not in m]
        if "pdf_content" in st.session_state:
            messages_to_send.insert(1, {"role": "system", "content": f"Contexto del PDF actual: {st.session_state.pdf_content[:3000]}"})

        stream = cliente_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages_to_send,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                full_res += chunk.choices[0].delta.content
                if not full_res.startswith("[IMAGEN]"):
                    placeholder.markdown(full_res + "▌")

        if full_res.startswith("[IMAGEN]"):
            placeholder.info("🎨 Alberto AI está creando tu imagen...")
            img_b64 = generar_imagen(full_res.replace("[IMAGEN]", "").strip())
            if img_b64:
                placeholder.empty()
                st.image(base64.b64decode(img_b64), use_container_width=True)
                st.session_state.mensajes.append({"role": "assistant", "content": img_b64, "tipo": "img"})
        else:
            st.session_state.mensajes.append({"role": "assistant", "content": full_res})