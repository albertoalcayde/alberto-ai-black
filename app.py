import streamlit as st
import groq
import fitz
import requests
import base64
import io
from PIL import Image

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Alberto AI - Smart OS", page_icon="🧠", layout="wide")

# Estética Premium White
st.markdown("""
    <style>
    .stApp { background-color: #f7f7f8; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e5e5e5; }
    .stChatMessage { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 12px; margin-bottom: 10px; }
    /* Estilo para los botones de la barra lateral */
    .stButton>button { border-radius: 8px; font-weight: 500; }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZACIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "diccionario_chats" not in st.session_state:
    st.session_state.diccionario_chats = {"Nueva Conversación": []}
if "chat_activo" not in st.session_state:
    st.session_state.chat_activo = "Nueva Conversación"
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

# --- FUNCIONES MAESTRAS ---
def generar_imagen(prompt):
    URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    try:
        r = requests.post(URL, headers=headers, json={"inputs": prompt}, timeout=20)
        return base64.b64encode(r.content).decode() if r.status_code == 200 else None
    except: return None

def generar_titulo_automatico(primer_mensaje):
    """Pide a la IA un título corto basado en el primer mensaje"""
    try:
        response = cliente_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Eres un experto en resumir. Crea un título de MÁXIMO 3 PALABRAS para este chat basándote en el mensaje del usuario. No uses comillas ni puntos finales. Solo el título."},
                      {"role": "user", "content": primer_mensaje}],
            max_tokens=10,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except:
        return f"Chat {len(st.session_state.diccionario_chats)}"

# --- BARRA LATERAL (HISTORIAL INTELIGENTE) ---
with st.sidebar:
    st.markdown(f"### ✨ **{st.session_state.usuario_actual}**")
    
    if st.button("➕ Nuevo Chat", use_container_width=True):
        nuevo_id = "Nueva Conversación " + str(len(st.session_state.diccionario_chats))
        st.session_state.diccionario_chats[nuevo_id] = []
        st.session_state.chat_activo = nuevo_id
        st.rerun()

    st.markdown("---")
    st.subheader("📜 Tus Chats")
    
    for id_chat in list(st.session_state.diccionario_chats.keys()):
        # Resaltamos el chat que estamos usando
        tipo_boton = "primary" if id_chat == st.session_state.chat_activo else "secondary"
        if st.button(id_chat, key=f"btn_{id_chat}", use_container_width=True, type=tipo_boton):
            st.session_state.chat_activo = id_chat
            st.rerun()

    st.markdown("---")
    with st.expander("📄 Subir PDF"):
        archivo_pdf = st.file_uploader("", type=["pdf"], label_visibility="collapsed")
        if archivo_pdf:
            doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
            st.session_state[f"pdf_{st.session_state.chat_activo}"] = "".join([p.get_text() for p in doc])
            st.success("PDF vinculado.")

    with st.expander("🎨 Galería"):
        for img in reversed(st.session_state.imagenes_galeria):
            st.image(base64.b64decode(img), use_container_width=True)

# --- CUERPO DEL CHAT ---
st.title(f"💬 {st.session_state.chat_activo}")

mensajes_actuales = st.session_state.diccionario_chats[st.session_state.chat_activo]

if not mensajes_actuales:
    mensajes_actuales.append({"role": "system", "content": f"Eres Alberto AI. Usuario: {st.session_state.usuario_actual}. Responde en español."})

for m in mensajes_actuales:
    if m["role"] != "system":
        with st.chat_message(m["role"]):
            if "tipo" in m and m["tipo"] == "img":
                st.image(base64.b64decode(m["content"]), use_container_width=True)
            else:
                st.markdown(m["content"])

# --- LÓGICA DE RESPUESTA Y AUTOTITULADO ---
if prompt := st.chat_input("Escribe tu mensaje..."):
    # 1. Guardamos el mensaje del usuario
    mensajes_actuales.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    # 2. ¿Es el primer mensaje? Generamos título
    # (Contamos 2 porque el índice 0 es el mensaje de 'system')
    if len(mensajes_actuales) == 2 and "Nueva Conversación" in st.session_state.chat_activo:
        nuevo_titulo = generar_titulo_automatico(prompt)
        # Actualizamos el diccionario con la nueva clave
        st.session_state.diccionario_chats[nuevo_titulo] = st.session_state.diccionario_chats.pop(st.session_state.chat_activo)
        st.session_state.chat_activo = nuevo_titulo
        st.rerun()

    # 3. Respuesta de la IA
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        
        ctx = [m for m in mensajes_actuales if "tipo" not in m]
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