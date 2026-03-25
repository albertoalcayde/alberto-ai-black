import streamlit as st
import groq
import fitz
import requests
import base64
import io
from PIL import Image

# --- CONFIGURACIÓN DE ÉLITE (MODO CLARO) ---
st.set_page_config(page_title="Alberto AI - White Edition", page_icon="⚪", layout="wide")

# CSS para una interfaz tipo "SaaS Moderno / Light Mode"
st.markdown("""
    <style>
    /* Fondo general y color de texto */
    .stApp { background-color: #f7f7f8; color: #212121; }
    
    /* Barra lateral blanca con borde sutil */
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e5e5e5; padding-top: 2rem; }
    
    /* Burbujas de chat estilo moderno */
    .stChatMessage { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 15px; margin-bottom: 10px; color: #212121; }
    
    /* Input de texto */
    .stChatInputContainer { padding-bottom: 20px; background-color: transparent; }
    .stChatInput { border-radius: 10px !important; border: 1px solid #ddd !important; background-color: #ffffff !important; color: #212121 !important; }
    
    /* Títulos y botones */
    h1 { color: #1a1a1a; font-family: 'Inter', sans-serif; font-weight: 700; }
    .stButton>button { background-color: #1a1a1a; color: #ffffff; border-radius: 8px; border: none; font-weight: bold; width: 100%; transition: 0.3s; }
    .stButton>button:hover { background-color: #444444; color: #ffffff; }
    
    /* Uploader de PDF */
    [data-testid="stFileUploadDropzone"] { background: #f0f0f0; border: 1px dashed #ccc; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- LÓGICA DE APIS ---
try:
    cliente_groq = groq.Groq(api_key=st.secrets["GROQ_API_KEY"])
    HF_API_KEY = st.secrets["HUGGINGFACE_API_KEY"]
except:
    st.error("⚠️ Configura tus Keys en los Secrets de Streamlit Cloud.")
    st.stop()

def generar_imagen(prompt):
    URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    try:
        r = requests.post(URL, headers=headers, json={"inputs": prompt}, timeout=20)
        if r.status_code == 200:
            return base64.b64encode(r.content).decode()
    except: return None
    return None

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown('<h1 style="font-size: 25px;">⚪ Alberto AI PRO</h1>', unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("### 📄 Documentos")
    archivo_pdf = st.file_uploader("Sube un PDF", type=["pdf"], label_visibility="collapsed")
    
    if archivo_pdf:
        with st.spinner("Analizando..."):
            doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
            texto_pdf = "".join([p.get_text() for p in doc])
            if "contexto_pdf" not in st.session_state or st.session_state.contexto_pdf != archivo_pdf.name:
                st.session_state.contexto_pdf = archivo_pdf.name
                st.session_state.mensajes.append({"role": "system", "content": f"Contenido del PDF: {texto_pdf[:4000]}"})
        st.success(f"✅ {archivo_pdf.name} cargado")

    st.markdown("---")
    st.markdown("### ⚙️ Ecosistema")
    st.caption("🧠 Inteligencia: Llama 3.3")
    st.caption("🎨 Generador: FLUX.1")
    
    if st.button("Limpiar conversación"):
        st.session_state.mensajes = [st.session_state.mensajes[0]]
        st.rerun()

# --- CHAT PRINCIPAL ---
if "mensajes" not in st.session_state:
    st.session_state.mensajes = [{"role": "system", "content": "Eres Alberto AI White Edition. Eres profesional, amable y eficiente. Respondes en español. Si te piden una imagen, genera un prompt en inglés que empiece con [IMAGEN]."}]

# Mostrar historial
for m in st.session_state.mensajes:
    if m["role"] != "system":
        with st.chat_message(m["role"]):
            if "tipo" in m and m["tipo"] == "img":
                st.image(base64.b64decode(m["content"]), use_container_width=True)
            else:
                st.markdown(m["content"])

# Entrada de usuario
if prompt := st.chat_input("Escribe tu duda o pide una imagen..."):
    st.session_state.mensajes.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        
        stream = cliente_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[m for m in st.session_state.mensajes if "tipo" not in m],
            stream=True,
            temperature=0.4
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                full_res += chunk.choices[0].delta.content
                if not full_res.startswith("[IMAGEN]"):
                    placeholder.markdown(full_res + "▌")

        # Generador de imágenes
        if full_res.startswith("[IMAGEN]"):
            placeholder.info("🎨 Creando imagen...")
            prompt_img = full_res.replace("[IMAGEN]", "").strip()
            img_b64 = generar_imagen(prompt_img)
            if img_b64:
                placeholder.empty()
                st.image(base64.b64decode(img_b64), use_container_width=True)
                st.session_state.mensajes.append({"role": "assistant", "content": img_b64, "tipo": "img"})
            else:
                placeholder.error("Error al generar la imagen. Inténtalo de nuevo.")
        else:
            st.session_state.mensajes.append({"role": "assistant", "content": full_res})