import streamlit as st
import groq
import fitz  # PyMuPDF
import requests
import base64
import io
from PIL import Image

# 1. Configuración de página (Estética SaaS Minimalista)
st.set_page_config(page_title="Alberto AI - Black Edition", page_icon="⬛", layout="centered", initial_sidebar_state="collapsed")

# 2. Inyección de CSS
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;} .block-container { padding-top: 2rem; padding-bottom: 2rem; } [data-testid="stFileUploadDropzone"] { padding: 1rem; border-radius: 5px; }</style>""", unsafe_allow_html=True)

st.title("⬛ Alberto AI")

# 3. Inicializar APIs
try:
    cliente_groq = groq.Groq(api_key=st.secrets["GROQ_API_KEY"])
    HF_API_KEY = st.secrets["HUGGINGFACE_API_KEY"]
except KeyError:
    st.error("Error: Faltan claves en secrets.toml.")
    st.stop()
except FileNotFoundError:
    st.error("Error: No se encuentra el archivo secrets.toml.")
    st.stop()

# Función interna para generar la imagen con el NUEVO ENRUTADOR de Hugging Face
def generar_imagen(prompt_imagen):
    # ¡Actualizado al nuevo servidor de Hugging Face!
    API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt_imagen})
        if response.status_code == 200:
            imagen = Image.open(io.BytesIO(response.content))
            buffered = io.BytesIO()
            imagen.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode(), None
        else:
            return None, f"Código {response.status_code}: {response.text}"
    except Exception as e:
        return None, str(e)

# 4. Memoria del Chat y Personalidad
if "mensajes" not in st.session_state:
    st.session_state.mensajes = [
        {"role": "system", "content": "Eres 'Alberto AI - Black Edition', un asistente de IA de élite. Respondes SIEMPRE en español de España de forma directa. IMPORTANTE: Si el usuario te pide generar, crear o dibujar una imagen, tu respuesta DEBE empezar obligatoriamente con la etiqueta [IMAGEN] seguida del prompt en inglés detallado para enviárselo al generador de imágenes. Ejemplo: [IMAGEN] A cyberpunk city at night with neon lights, photorealistic. No añadas más texto después del prompt."}
    ]

# 5. Motor de Ingesta de PDF
with st.expander("📄 Añadir documento PDF", expanded=False):
    archivo_pdf = st.file_uploader("", type=["pdf"], label_visibility="collapsed")
    if archivo_pdf is not None:
        if "pdf_actual" not in st.session_state or st.session_state.pdf_actual != archivo_pdf.name:
            doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
            texto_extraido = "".join([pagina.get_text() for pagina in doc])
            st.session_state.mensajes.append({"role": "system", "content": f"El usuario ha subido el documento '{archivo_pdf.name}'. Contenido: {texto_extraido}"})
            st.session_state.pdf_actual = archivo_pdf.name
            st.success("Documento memorizado.")

# 6. Mostrar historial de mensajes
for mensaje in st.session_state.mensajes:
    if mensaje["role"] == "user":
        with st.chat_message("user"): st.markdown(mensaje["content"])
    elif mensaje["role"] == "assistant":
        with st.chat_message("assistant"):
            if "[IMAGEN]" in mensaje.get("tipo", ""):
                st.image(base64.b64decode(mensaje["content"]))
            else:
                st.markdown(mensaje["content"])

# 7. Input del usuario y Respuesta
if prompt := st.chat_input("Escribe tu orden o pide una imagen..."):
    st.session_state.mensajes.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        respuesta_completa = ""
        stream = cliente_groq.chat.completions.create(model="llama-3.3-70b-versatile", messages=[m for m in st.session_state.mensajes if "tipo" not in m], stream=True, temperature=0.3)
        for chunk in stream:
            if chunk.choices[0].delta.content:
                respuesta_completa += chunk.choices[0].delta.content
                if not respuesta_completa.startswith("[IMAGEN]"):
                    placeholder.markdown(respuesta_completa + "▌")
        
        if respuesta_completa.startswith("[IMAGEN]"):
            placeholder.markdown("🎨 Conectando con el servidor FLUX...")
            prompt_traducido = respuesta_completa.replace("[IMAGEN]", "").strip()
            
            imagen_b64, error_msg = generar_imagen(prompt_traducido)
            
            if imagen_b64:
                placeholder.empty()
                st.image(base64.b64decode(imagen_b64))
                st.session_state.mensajes.append({"role": "assistant", "content": imagen_b64, "tipo": "[IMAGEN]"})
            else:
                placeholder.error(f"Fallo en motor de imagen. Detalle técnico: {error_msg}")
                st.session_state.mensajes.append({"role": "assistant", "content": f"No he podido generar la imagen. Error: {error_msg}"})
        else:
            placeholder.markdown(respuesta_completa)
            st.session_state.mensajes.append({"role": "assistant", "content": respuesta_completa})