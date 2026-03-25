import streamlit as st
import groq
import fitz
import requests
import base64
import json
from supabase import create_client, Client

# --- CONFIGURACIÓN DE INTERFAZ PREMIUM ---
st.set_page_config(page_title="Alberto AI - PRO Edition", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f7f7f8; color: #1f1f1f; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e5e5e5; }
    .stChatMessage { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 12px; margin-bottom: 15px; }
    .stChatInput { border-radius: 10px !important; border: 1px solid #ddd !important; }
    h1 { font-weight: 800; color: #1a1a1a; }
    .stButton>button { border-radius: 8px; font-weight: 500; }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXIÓN A LAS LLAVES MAESTRAS ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    cliente_groq = groq.Groq(api_key=st.secrets["GROQ_API_KEY"])
    HF_API_KEY = st.secrets["HUGGINGFACE_API_KEY"]
except Exception as e:
    st.error(f"⚠️ Error en Secrets: {e}")
    st.stop()

# --- FUNCIONES DE MEMORIA (SUPABASE) ---
def db_guardar_chat(usuario, titulo, mensajes):
    data = {"usuario": usuario, "titulo_chat": titulo, "contenido": mensajes}
    supabase.table("historial_chats").upsert(data, on_conflict="usuario,titulo_chat").execute()

def db_cargar_titulos(usuario):
    res = supabase.table("historial_chats").select("titulo_chat").eq("usuario", usuario).order("fecha", desc=True).execute()
    return [item['titulo_chat'] for item in res.data]

def db_cargar_mensajes(usuario, titulo):
    res = supabase.table("historial_chats").select("contenido").eq("usuario", usuario).eq("titulo_chat", titulo).execute()
    return res.data[0]['contenido'] if res.data else []

def db_guardar_imagen(usuario, img_b64):
    supabase.table("galeria_imagenes").insert({"usuario": usuario, "imagen_b64": img_b64}).execute()

def db_cargar_galeria(usuario):
    res = supabase.table("galeria_imagenes").select("imagen_b64").eq("usuario", usuario).order("fecha", desc=True).execute()
    return [item['imagen_b64'] for item in res.data]

# --- FUNCIONES DE IA ---
def generar_imagen(prompt):
    URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    try:
        # Aumentamos timeout por seguridad
        r = requests.post(URL, headers=headers, json={"inputs": prompt}, timeout=40)
        if r.status_code == 200:
            return base64.b64encode(r.content).decode()
    except:
        return None
    return None

def generar_titulo(mensaje):
    try:
        res = cliente_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Resume en 2 o 3 palabras este tema para un título. Solo el texto, sin comillas."},
                      {"role": "user", "content": mensaje}],
            max_tokens=10
        )
        return res.choices[0].message.content.strip()
    except:
        return "Conversación Nueva"

# --- SISTEMA DE LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    with st.sidebar:
        st.title("🆔 Acceso")
        nombre = st.text_input("Tu nombre...")
        if st.button("Entrar"):
            if nombre:
                st.session_state.autenticado = True
                st.session_state.usuario = nombre.lower().strip()
                st.rerun()
    st.markdown("<h1 style='text-align:center; margin-top:5rem;'>Alberto AI PRO</h1><p style='text-align:center;'>Introduce tu nombre a la izquierda.</p>", unsafe_allow_html=True)
    st.stop()

# --- BARRA LATERAL (CENTRO DE CONTROL) ---
with st.sidebar:
    st.subheader(f"👋 Hola, {st.session_state.usuario.capitalize()}")
    
    if st.button("➕ Nuevo Chat", use_container_width=True):
        st.session_state.chat_activo = "Nueva Conversación"
        # Limpiar PDF contexto si existe al crear nuevo chat
        keys_to_del = [k for k in st.session_state.keys() if k.startswith("pdf_")]
        for k in keys_to_del: del st.session_state[k]
        st.rerun()
    
    st.markdown("---")
    
    # 📄 SECCIÓN PDF
    with st.expander("📄 Analizar Documentos"):
        archivo_pdf = st.file_uploader("Sube un PDF", type=["pdf"], key=f"uploader_{st.session_state.get('chat_activo', 'default')}")
        if archivo_pdf:
            doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
            texto_completo = "".join([p.get_text() for p in doc])
            st.session_state[f"pdf_{st.session_state.get('chat_activo', 'default')}"] = texto_completo[:5000]
            st.success("✅ Documento cargado en este chat")

    st.markdown("---")
    st.caption("Tus chats guardados:")
    titulos_db = db_cargar_titulos(st.session_state.usuario)
    for t in titulos_db:
        tipo_boton = "primary" if t == st.session_state.get('chat_activo') else "secondary"
        if st.button(t, key=f"btn_{t}", use_container_width=True, type=tipo_boton):
            st.session_state.chat_activo = t
            st.rerun()
    
    st.markdown("---")
    with st.expander("🖼️ Galería de Arte Total"):
        imgs = db_cargar_galeria(st.session_state.usuario)
        if not imgs:
            st.caption("Aún no hay imágenes.")
        else:
            for img in imgs:
                st.image(base64.b64decode(img), use_container_width=True)

# --- CHAT PRINCIPAL ---
if "chat_activo" not in st.session_state:
    st.session_state.chat_activo = "Nueva Conversación"

st.title(f"💬 {st.session_state.chat_activo}")

# Carga de mensajes (Desde DB o Sistema)
mensajes = db_cargar_mensajes(st.session_state.usuario, st.session_state.chat_activo)

if not mensajes:
    # EL PROMPT BLINDADO "FEW-SHOT": Con ejemplos para forzar obediencia
    system_prompt = (
        f"Eres 'Alberto AI PRO'. Usuario activo: {st.session_state.usuario}. "
        "INSTRUCCIÓN CRÍTICA DE ALINEACIÓN: Eres un motor de generación de etiquetas [IMAGEN]. "
        "Si el usuario pide una imagen, dibujo, foto o visual, responde ÚNICAMENTE con la etiqueta [IMAGEN] "
        "seguida de un prompt descriptivo en inglés de alta calidad. NO des explicaciones de texto, "
        "NO digas que eres un modelo de lenguaje, NO digas 'aquí tienes el prompt'. "
        "OBEDECE SIEMPRE USANDO EL FORMATO. Sigue estos ejemplos:\n\n"
        "User: Hazme una foto de un perro azul astronauta.\n"
        "Assistant: [IMAGEN] a highly detailed photo of a blue labrador dog wearing a futuristic astronaut suit on the moon.\n\n"
        "User: Genera paisaje ciberpunk.\n"
        "Assistant: [IMAGEN] cyberpuk city landscape, neon lights, rainy weather, high resolution cinematographic shot.\n\n"
        "Comienza ahora. Responde normal en español para texto. Para imágenes, usa SOLO el formato."
    )
    mensajes = [{"role": "system", "content": system_prompt}]

# Mostrar chat
for m in mensajes:
    if m["role"] != "system":
        with st.chat_message(m["role"]):
            if m.get("tipo") == "img": 
                st.image(base64.b64decode(m["content"]), use_container_width=True)
            else: 
                st.markdown(m["content"])

# Lógica de envío
if prompt := st.chat_input("¿En qué puedo ayudarte hoy, Alberto?"):
    # Autotitular si es el inicio
    if st.session_state.chat_activo == "Nueva Conversación":
        st.session_state.chat_activo = generar_titulo(prompt)
    
    mensajes.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        
        # Preparar contexto (incluyendo PDF si existe en este chat)
        pdf_ctx = st.session_state.get(f"pdf_{st.session_state.chat_activo}", "")
        ctx_envio = [m for m in mensajes if m.get("tipo") != "img"]
        if pdf_ctx:
            ctx_envio.insert(1, {"role": "system", "content": f"Usa esta información extraída de un PDF si es relevante para la conversación (máx 5000 caracteres): {pdf_ctx}"})

        try:
            # Bajamos temperatura para más consistencia
            stream = cliente_groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=ctx_envio,
                stream=True,
                temperature=0.1 
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_res += chunk.choices[0].delta.content
                    if not full_res.startswith("[IMAGEN]"):
                        placeholder.markdown(full_res + "▌")
            
            # Procesar si es imagen o texto
            if "[IMAGEN]" in full_res:
                placeholder.info("🎨 Generando arte con FLUX schnell...")
                # Extraer prompt inglés ignorando texto previo feo si lo hubiera
                clean_prompt = full_res.split("[IMAGEN]")[1].strip()
                # Limpiar posibles restos de cortesía si el modelo desobedece parcialmente
                clean_prompt = clean_prompt.split(".")[0].split("\n")[0].strip()
                
                img_b64 = generar_imagen(clean_prompt)
                
                if img_b64:
                    placeholder.empty()
                    st.image(base64.b64decode(img_b64), use_container_width=True)
                    mensajes.append({"role": "assistant", "content": img_b64, "tipo": "img"})
                    db_guardar_imagen(st.session_state.usuario, img_b64)
                else:
                    placeholder.error("Hubo un problema al conectar con el servidor de arte FLUX.")
            else:
                placeholder.markdown(full_res)
                mensajes.append({"role": "assistant", "content": full_res})
            
            # GUARDAR EN SUPABASE
            db_guardar_chat(st.session_state.usuario, st.session_state.chat_activo, mensajes)
            st.rerun()

        except Exception as e:
            st.error(f"❌ Error de conexión crítica: {e}")