import streamlit as st
import groq
import fitz
import requests
import base64
import io
from PIL import Image

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Alberto AI - Pro Hub", page_icon="🏢", layout="wide")

# Estética Premium White (Limpia y Moderna)
st.markdown("""
    <style>
    .stApp { background-color: #f7f7f8; color: #212121; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e5e5e5; }
    .stChatMessage { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 12px; margin-bottom: 10px; }
    .stExpander { background-color: #ffffff; border: 1px solid #eee; border-radius: 10px; margin-bottom: 10px; }
    h1 { color: #1a1a1a; font-family: 'Inter', sans-serif; font-weight: 700; }
    .welcome-box { padding: 3rem; text-align: center; background: white; border-radius: 20px; border: 1px solid #eee; margin-top: 5rem; }
    /* Estilo para los botones de chat en la sidebar */
    .stButton>button { border-radius: 8px; font-weight: 500; text-align: left; transition: 0.3s; }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZACIÓN DE ESTADOS ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# Base de datos local de chats
if "diccionario_chats" not in st.session_state:
    st.session_state.diccionario_chats = {"Nueva Conversación": []}
if "chat_activo" not in st.session_state:
    st.session_state.chat_activo = "Nueva Conversación"
if "imagenes_galeria" not in st.session_state:
    st.session_state.imagenes_galeria = []

# --- PANTALLA DE ACCESO ---
def pantalla_acceso():
    with st.sidebar:
        st.title("🆔 Identificación")
        nombre = st.text_input("Tu nombre...", placeholder="Escribe tu nombre...")
        if st.button("Comenzar Sesión"):
            if nombre.strip():
                st.session_state.autenticado = True
                st.session_state.usuario_actual = nombre.strip()
                st.rerun()
            else:
                st.warning("Por favor, introduce un nombre.")

if not st.session_state.autenticado:
    st.markdown("<div class='welcome-box'><h1>Alberto AI Community</h1><p>Por favor, identifícate en el panel lateral para empezar.</p></div>", unsafe_allow_html=True)
    pantalla_acceso()
    st.stop()

# --- LLAVES API ---
try:
    cliente_groq = groq.Groq(api_key=st.secrets["GROQ_API_KEY"])
    HF_API_KEY = st.secrets["HUGGINGFACE_API_KEY"]
except KeyError:
    st.error("Error: Revisa las Keys en los Secrets de Streamlit Cloud.")
    st.stop()

# --- FUNCIONES MAESTRAS ---
def generar_imagen(prompt):
    # ¡URL Verificada! Usamos el nuevo enrutador de Hugging Face
    URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    try:
        r = requests.post(URL, headers=headers, json={"inputs": prompt}, timeout=20)
        if r.status_code == 200:
            return base64.b64encode(r.content).decode()
        else:
            return None # Si el servidor falla, devolvemos None
    except Exception as e:
        return None

def generar_titulo_automatico(primer_mensaje):
    """Llama a la IA para resumir el chat en 3 palabras"""
    try:
        response = cliente_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Crea un título de MÁXIMO 3 PALABRAS para este chat basándote en el mensaje del usuario. No uses comillas ni puntos. Solo el título."},
                      {"role": "user", "content": primer_mensaje}],
            max_tokens=10,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except:
        return f"Chat {len(st.session_state.diccionario_chats)}"

# --- BARRA LATERAL (HERRAMIENTAS Y CHATS) ---
with st.sidebar:
    st.markdown(f"### ✨ Sesión de: **{st.session_state.usuario_actual}**")
    
    if st.button("➕ Nuevo Chat", use_container_width=True):
        nuevo_id = f"Nueva Conversación {str(len(st.session_state.diccionario_chats))}"
        st.session_state.diccionario_chats[nuevo_id] = []
        st.session_state.chat_activo = nuevo_id
        st.rerun()

    st.markdown("---")
    st.subheader("📜 Tus Chats")
    
    # Listado de chats existentes
    for id_chat in list(st.session_state.diccionario_chats.keys()):
        tipo_boton = "primary" if id_chat == st.session_state.chat_activo else "secondary"
        if st.button(id_chat, key=f"btn_{id_chat}", use_container_width=True, type=tipo_boton):
            st.session_state.chat_activo = id_chat
            st.rerun()

    st.markdown("---")
    
    # Desplegable de Archivos
    with st.expander("📄 Subir PDF (Para este chat)"):
        archivo_pdf = st.file_uploader("", type=["pdf"], label_visibility="collapsed")
        if archivo_pdf:
            doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
            st.session_state[f"pdf_{st.session_state.chat_activo}"] = "".join([p.get_text() for p in doc])
            st.success(f"'{archivo_pdf.name}' vinculado.")

    # Desplegable de Galería
    with st.expander("🎨 Galería"):
        if not st.session_state.imagenes_galeria:
            st.caption("Aún no hay imágenes.")
        else:
            for img in reversed(st.session_state.imagenes_galeria):
                st.image(base64.b64decode(img), use_container_width=True)
                st.markdown("---")

    st.markdown("---")
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.diccionario_chats = {"Nueva Conversación": []}
        st.session_state.chat_activo = "Nueva Conversación"
        st.session_state.imagenes_galeria = []
        st.rerun()

# --- CUERPO DEL CHAT ---
st.title(f"💬 {st.session_state.chat_activo}")

# Recuperamos la conversación del chat activo
mensajes_actuales = st.session_state.diccionario_chats[st.session_state.chat_activo]

if not mensajes_actuales:
    # Definimos el prompt de sistema para este chat, indicándole que si le piden una imagen, use [IMAGEN] + prompt inglés.
    system_prompt = f"Eres 'Alberto AI PRO'. Usuario: {st.session_state.usuario_actual}. Tu misión es ser eficiente y directo. Si te piden una imagen, responde EXCLUSIVAMENTE con la etiqueta [IMAGEN] seguida del prompt en inglés detallado. NO añadas texto de cortesía antes o después. Ejemplo: [IMAGEN] a photo of a futuristic cat. Responde en español para el texto normal."
    mensajes_actuales.append({"role": "system", "content": system_prompt})

# Mostrar mensajes del chat seleccionado
for m in mensajes_actuales:
    if m["role"] != "system":
        with st.chat_message(m["role"]):
            if "tipo" in m and m["tipo"] == "img":
                st.image(base64.b64decode(m["content"]), use_container_width=True)
            else:
                st.markdown(m["content"])

# --- LÓGICA DE RESPUESTA Y AUTOTITULADO ---
if prompt := st.chat_input("Dime algo..."):
    # 1. Guardamos el mensaje del usuario
    mensajes_actuales.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    # 2. ¿Es el primer mensaje? Generamos título temático
    # (Contamos 2 porque el índice 0 es el mensaje de 'system')
    if len(mensajes_actuales) == 2 and "Nueva Conversación" in st.session_state.chat_activo:
        nuevo_titulo = generar_titulo_automatico(prompt)
        # Actualizamos el diccionario con la nueva clave temárica
        st.session_state.diccionario_chats[nuevo_titulo] = st.session_state.diccionario_chats.pop(st.session_state.chat_activo)
        st.session_state.chat_activo = nuevo_titulo
        # ¡IMPORTANTE! Refrescamos para que el título en la sidebar cambie al instante
        st.rerun()

    # 3. Respuesta de la IA
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        
        # Filtramos para enviar solo texto al cerebro Llama
        ctx = [m for m in mensajes_actuales if "tipo" not in m]
        # Añadir contexto PDF si este chat específico tiene uno vinculado
        pdf_key = f"pdf_{st.session_state.chat_activo}"
        if pdf_key in st.session_state:
            ctx.insert(1, {"role": "system", "content": f"Documento de apoyo actual: {st.session_state[pdf_key][:3000]}"})

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

        # Generador de arte
        if full_res.startswith("[IMAGEN]"):
            placeholder.info("🎨 Alberto AI está creando arte digital para ti...")
            img_b64 = generar_imagen(full_res.replace("[IMAGEN]", "").strip())
            if img_b64:
                placeholder.empty()
                st.image(base64.b64decode(img_b64), use_container_width=True)
                # Guardamos la imagen en el chat y en la galería
                mensajes_actuales.append({"role": "assistant", "content": img_b64, "tipo": "img"})
                st.session_state.imagenes_galeria.append(img_b64)
                st.rerun() # Refrescamos para guardar cambios en galería
            else:
                placeholder.error("Servidor FLUX saturado. Reintenta en 10 seg.")
        else:
            mensajes_actuales.append({"role": "assistant", "content": full_res})