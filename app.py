import streamlit as st
import groq
import fitz
import requests
import base64
import io
import time
from PIL import Image

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Alberto AI - OS", page_icon="🖥️", layout="wide")

# Estética Premium White
st.markdown("""
    <style>
    .stApp { background-color: #f7f7f8; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e5e5e5; }
    .stChatMessage { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 12px; margin-bottom: 10px; }
    .chat-link { padding: 10px; border-radius: 8px; cursor: pointer; border: 1px solid #eee; margin-bottom: 5px; background: #fff; text-align: left; width: 100%; }
    .chat-link:hover { background: #f0f0f0; }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZACIÓN DE LA BASE DE DATOS LOCAL (SESSION STATE) ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# Aquí guardaremos TODOS los chats: { "ID_Chat": [mensajes] }
if "diccionario_chats" not in st.session_state:
    st.session_state.diccionario_chats = {"Chat 1": []}
if "chat_activo" not in st.session_state:
    st.session_state.chat_activo = "Chat 1"
if "imagenes_galeria" not in st.session_state:
    st.session_state.imagenes_galeria = []

# --- PANTALLA DE ACCESO ---
if not st.session_state.autenticado:
    with st.sidebar:
        st.title("🆔 Identificación")
        nombre = st.text_input("Tu nombre...")
        if st.button("Entrar"):
            if nombre.strip():
                st.session_state.autenticado = True
                st.session_state.usuario_actual = nombre.strip()
                st.rerun()
    st.markdown("<h1 style='text-align:center; margin-top:10rem;'>Alberto AI OS</h1><p style='text-align:center;'>Identifícate para gestionar tus chats.</p>", unsafe_allow_html=True)
    st.stop()

# --- LLAVES API ---
try:
    cliente_groq = groq.Groq(api_key=st.secrets["GROQ_API_KEY"])
    HF_API_KEY = st.secrets["HUGGINGFACE_API_KEY"]
except:
    st.error("Error en las llaves API.")
    st.stop()

def generar_imagen(prompt):
    URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    try:
        r = requests.post(URL, headers=headers, json={"inputs": prompt}, timeout=20)
        return base64.b64encode(r.content).decode() if r.status_code == 200 else None
    except: return None

# --- BARRA LATERAL (SISTEMA DE ARCHIVOS Y CHATS) ---
with st.sidebar:
    st.markdown(f"### ✨ **{st.session_state.usuario_actual}**")
    
    # BOTÓN NUEVA CONVERSACIÓN
    if st.button("➕ Nueva Conversación", use_container_width=True):
        nuevo_id = f"Chat {len(st.session_state.diccionario_chats) + 1}"
        st.session_state.diccionario_chats[nuevo_id] = []
        st.session_state.chat_activo = nuevo_id
        st.rerun()

    st.markdown("---")
    st.subheader("📜 Historial de Chats")
    # Listar chats existentes como botones
    for titulo_chat in st.session_state.diccionario_chats.keys():
        # Resaltar el chat activo
        if st.button(titulo_chat, key=f"btn_{titulo_chat}", use_container_width=True, type="secondary" if titulo_chat != st.session_state.chat_activo else "primary"):
            st.session_state.chat_activo = titulo_chat
            st.rerun()

    st.markdown("---")
    with st.expander("📄 Subir PDF (Para este chat)"):
        archivo_pdf = st.file_uploader("", type=["pdf"], label_visibility="collapsed")
        if archivo_pdf:
            doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
            st.session_state[f"pdf_{st.session_state.chat_activo}"] = "".join([p.get_text() for p in doc])
            st.success("PDF vinculado a este chat.")

    with st.expander("🎨 Galería"):
        for img in reversed(st.session_state.imagenes_galeria):
            st.image(base64.b64decode(img), use_container_width=True)

# --- CUERPO DEL CHAT ACTIVO ---
st.title(f"💬 {st.session_state.chat_activo}")

mensajes_actuales = st.session_state.diccionario_chats[st.session_state.chat_activo]

# Si el chat está vacío, ponemos el saludo inicial
if not mensajes_actuales:
    mensajes_actuales.append({"role": "system", "content": f"Eres Alberto AI. Hablas con {st.session_state.usuario_actual} en el {st.session_state.chat_activo}. Responde en español."})

# Mostrar mensajes del chat seleccionado
for m in mensajes_actuales:
    if m["role"] != "system":
        with st.chat_message(m["role"]):
            if "tipo" in m and m["tipo"] == "img":
                st.image(base64.b64decode(m["content"]), use_container_width=True)
            else:
                st.markdown(m["content"])

# Input de chat
if prompt := st.chat_input("Escribe aquí..."):
    mensajes_actuales.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        
        # Contexto filtrado
        ctx = [m for m in mensajes_actuales if "tipo" not in m]
        # Añadir PDF si este chat específico tiene uno
        pdf_key = f"pdf_{st.session_state.chat_activo}"
        if pdf_key in st.session_state:
            ctx.insert(1, {"role": "system", "content": f"Contexto PDF: {st.session_state[pdf_key][:3000]}"})

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
            placeholder.info("Generando imagen...")
            img_b64 = generar_imagen(full_res.replace("[IMAGEN]", "").strip())
            if img_b64:
                placeholder.empty()
                st.image(base64.b64decode(img_b64), use_container_width=True)
                mensajes_actuales.append({"role": "assistant", "content": img_b64, "tipo": "img"})
                st.session_state.imagenes_galeria.append(img_b64)
                st.rerun()
        else:
            mensajes_actuales.append({"role": "assistant", "content": full_res})