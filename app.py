import streamlit as st
import groq
import fitz
import requests
import base64
import json
from datetime import datetime, timedelta
from supabase import create_client, Client

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Alberto AI - Modern Edition", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

# --- INYECCIÓN DE CSS MAESTRO (EL CLON VISUAL) ---
st.markdown("""
    <style>
    /* Importar fuente moderna bold */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif !important;
        background-color: #FFFFFF !important;
        color: #111827 !important;
    }

    /* --- 1. BARRA LATERAL OSCURA (ESTILO CHATGPT) --- */
    [data-testid="stSidebar"] {
        background-color: #171717 !important; /* Negro muy oscuro */
        border-right: 1px solid #262626 !important;
        padding-top: 1rem;
    }
    
    /* Textos en la barra lateral */
    [data-testid="stSidebar"] .stMarkdown, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] caption {
        color: #E5E7EB !important; /* Gris muy claro */
    }

    /* Botones Secundarios en Sidebar (Chats viejos) */
    [data-testid="stSidebar"] button[kind="secondary"] {
        background-color: transparent !important;
        border: 1px solid #404040 !important;
        color: #E5E7EB !important;
        border-radius: 8px !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding-left: 10px !important;
        transition: all 0.2s;
    }
    [data-testid="stSidebar"] button[kind="secondary"]:hover {
        background-color: #262626 !important;
        border-color: #525252 !important;
    }
    
    /* Botón Primario en Sidebar (Chat Activo) */
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #262626 !important; /* Gris oscuro para el activo */
        border: 1px solid #525252 !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
    }

    /* --- 2. ÁREA DE CHAT PRINCIPAL (BLANCO) --- */
    .main .block-container {
        padding-top: 2rem !important;
        max-width: 800px !important; /* Centrar chat */
    }

    /* Burbujas de chat estilo tarjetas limpias */
    .stChatMessage {
        background-color: #FFFFFF !important;
        border: none !important;
        border-radius: 0px !important;
        padding: 1rem 0rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* Separador sutil entre mensajes */
    .stChatMessage:not(:last-child) {
        border-bottom: 1px solid #F3F4F6 !important;
    }

    /* Avatar circular */
    [data-testid="stChatMessageAvatar"] {
        border-radius: 50% !important;
    }

    /* Ocultar el header superior por defecto */
    header[data-testid="stHeader"] {
        background-color: rgba(255, 255, 255, 0) !important;
        color: rgba(0,0,0,0) !important;
    }

    /* --- 3. BARRA DE ENTRADA (BOTTOM FIXED) --- */
    [data-testid="stChatInputContainer"] {
        background-color: #FFFFFF !important;
        padding-bottom: 1rem !important;
    }
    .stChatInput {
        background-color: #F4F4F4 !important; /* Gris muy claro */
        border-radius: 24px !important;
        border: 1px solid #E5E7EB !important;
        color: #111827 !important;
        padding-left: 1rem !important;
    }

    /* --- 4. DISEÑO DE TARJETAS DE BIENVENIDA (LA CLAVE) --- */
    .welcome-container {
        text-align: center;
        margin-top: 5rem;
        margin-bottom: 3rem;
    }
    
    .welcome-title {
        font-size: 40px;
        font-weight: 800;
        color: #111827;
        margin-bottom: 2rem;
        letter-spacing: -1px;
    }

    .card-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 1rem;
        max-width: 650px;
        margin: 0 auto;
    }

    .suggestion-card {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 16px;
        padding: 1rem;
        text-align: left;
        cursor: pointer;
        transition: all 0.2s;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .suggestion-card:hover {
        background-color: #F9FAFB;
        border-color: #D1D5DB;
        transform: translateY(-2px);
    }

    .card-icon {
        font-size: 1.2rem;
        margin-bottom: 0.5rem;
    }
    .card-title {
        font-weight: 700;
        font-size: 15px;
        color: #111827;
        margin-bottom: 0.2rem;
    }
    .card-desc {
        font-size: 13px;
        color: #6B7280;
    }
    
    /* Ocultar elementos molestos de Streamlit */
    [data-testid="stFileUploader"] {
        border: 1px dashed #404040 !important;
        border-radius: 8px !important;
        background-color: #171717 !important;
    }
    [data-testid="stFileUploader"] label {
        color: #E5E7EB !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXIÓN A LAS LLAVES MAESTRAS (SIN CAMBIOS) ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    cliente_groq = groq.Groq(api_key=st.secrets["GROQ_API_KEY"])
    HF_API_KEY = st.secrets["HUGGINGFACE_API_KEY"]
    SERPER_KEY = st.secrets.get("SERPER_API_KEY", None)
except Exception as e:
    st.error(f"⚠️ Error de configuración crítica. Revisa los Secrets.")
    st.stop()

# --- FUNCIONES DE MEMORIA (SIN CAMBIOS) ---
def db_guardar_chat(usuario, titulo, mensajes):
    data = {"usuario": usuario, "titulo_chat": titulo, "contenido": mensajes}
    supabase.table("historial_chats").upsert(data, on_conflict="usuario,titulo_chat").execute()

def db_borrar_chat(usuario, titulo):
    supabase.table("historial_chats").delete().eq("usuario", usuario).eq("titulo_chat", titulo).execute()

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

# --- FUNCIONES DE IA Y BÚSQUEDA (SIN CAMBIOS) ---
def buscar_google(query):
    if not SERPER_KEY: return "Error: Sin API de búsqueda."
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "gl": "es", "hl": "es"})
    headers = {'X-API-KEY': SERPER_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        results = response.json()
        snippets = [f"- {item['title']}: {item['snippet']}" for item in results.get('organic', [])[:3]]
        return "\n".join(snippets) if snippets else "No hay resultados."
    except: return "Error de búsqueda."

def generar_imagen(prompt):
    URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    try:
        r = requests.post(URL, headers=headers, json={"inputs": prompt}, timeout=40)
        if r.status_code == 200: return base64.b64encode(r.content).decode()
    except: return None
    return None

def generar_titulo(mensaje):
    try:
        res = cliente_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Resume en 2 palabras bold este tema. Solo texto."},
                      {"role": "user", "content": mensaje}],
            max_tokens=10
        )
        return res.choices[0].message.content.strip().replace('"', '')
    except: return "Chat Nuevo"

# --- ACCESO DE USUARIO ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    with st.sidebar:
        st.markdown("<h2 style='color:white; text-align:center;'>🆔 Acceso</h2>", unsafe_allow_html=True)
        nombre = st.text_input("Dime tu nombre...", key="login_name")
        if st.button("Entrar", type="secondary", use_container_width=True):
            if nombre:
                st.session_state.autenticado = True
                st.session_state.usuario = nombre.lower().strip()
                st.rerun()
    # Pantalla de carga central
    st.markdown(f"<div class='welcome-container'><div class='welcome-title'>Alberto AI PRO</div><p>Inicia sesión en la barra lateral.</p></div>", unsafe_allow_html=True)
    st.stop()

# --- BARRA LATERAL (CENTRO DE CONTROL) ---
with st.sidebar:
    # Avatar circular superior estilo la imagen
    col_av, col_txt = st.columns([0.2, 0.8])
    with col_av:
        st.markdown(f"<div style='background-color:#525252; color:white; border-radius:50%; width:35px; height:35px; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:18px;'>{st.session_state.usuario[0].upper()}</div>", unsafe_allow_html=True)
    with col_txt:
        st.subheader(f"{st.session_state.usuario.capitalize()}")
    
    if st.button("➕ Nuevo Chat", use_container_width=True, type="secondary"):
        st.session_state.chat_activo = "Nueva Conversación"
        st.rerun()
    
    st.markdown("---")
    
    # PDF y Galería ocultos en expanders para no manchar
    with st.expander("📄 Analizar PDF"):
        archivo_pdf = st.file_uploader("Sube PDF", type=["pdf"], key=f"pdf_{st.session_state.get('chat_activo', 'default')}")
        if archivo_pdf:
            doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
            st.session_state[f"pdf_txt_{st.session_state.get('chat_activo', 'default')}"] = "".join([p.get_text() for p in doc])[:5000]
            st.success("✅ Listo")

    with st.expander("🖼️ Galería"):
        for img in db_cargar_galeria(st.session_state.usuario):
            st.image(base64.b64decode(img), use_container_width=True)

    st.markdown("---")
    st.caption("Historial de chats:")
    titulos = db_cargar_titulos(st.session_state.usuario)
    for t in titulos:
        col_t, col_del = st.columns([0.85, 0.15])
        with col_t:
            if st.button(t, key=f"btn_{t}", use_container_width=True, type="primary" if t == st.session_state.get('chat_activo') else "secondary"):
                st.session_state.chat_activo = t
                st.rerun()
        with col_del:
            if st.button("🗑️", key=f"del_{t}", help="Borrar chat"):
                db_borrar_chat(st.session_state.usuario, t)
                if st.session_state.chat_activo == t: st.session_state.chat_activo = "Nueva Conversación"
                st.rerun()

# --- ÁREA DE CHAT ---
if "chat_activo" not in st.session_state:
    st.session_state.chat_activo = "Nueva Conversación"

mensajes = db_cargar_mensajes(st.session_state.usuario, st.session_state.chat_activo)

# Lógica del Sistema (Invisible)
ahora = datetime.utcnow() + timedelta(hours=1) # UTC+1 España
system_prompt = (
    f"Eres 'Alberto AI PRO'. Usuario: {st.session_state.usuario}. "
    f"Hoy es {ahora.strftime('%d/%m/%Y')} {ahora.strftime('%H:%M')} en España. "
    "Si piden imágenes, responde SOLO: [IMAGEN] prompt-en-inglés. "
    "Si piden buscar, responde SOLO: [BUSCAR] consulta. "
    "Responde siempre en español de forma directa y profesional."
)

if not mensajes:
    mensajes = [{"role": "system", "content": system_prompt}]

# --- PANTALLA DE INICIO CLON DE LA IMAGEN ---
if len(mensajes) <= 1:
    st.markdown(f"""
        <div class="welcome-container">
            <div class="welcome-title">{st.session_state.usuario.capitalize()}, what are you<br>making today?</div>
            
            <div class="card-grid">
                <div class="suggestion-card">
                    <div class="card-icon" style="color: #60A5FA;">✏️</div>
                    <div class="card-title">Create image</div>
                    <div class="card-desc">delighted pug in a tiny, colorful party hat</div>
                </div>
                <div class="suggestion-card">
                    <div class="card-icon" style="color: #34D399;">🚀</div>
                    <div class="card-title">Write code</div>
                    <div class="card-desc">to build a complete application</div>
                </div>
                <div class="suggestion-card">
                    <div class="card-icon" style="color: #FBBF24;">📅</div>
                    <div class="card-title">Plan</div>
                    <div class="card-desc">a trip to see the Northern Lights in Norway</div>
                </div>
                <div class="suggestion-card">
                    <div class="card-icon" style="color: #A78BFA;">💡</div>
                    <div class="card-title">Brainstorm</div>
                    <div class="card-desc">names for my new orange cat</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
else:
    # Mostrar historial de chat normal
    st.markdown(f"<h3 style='margin-top:0; border-bottom:1px solid #F3F4F6; padding-bottom:1rem;'>{st.session_state.chat_activo}</h3>", unsafe_allow_html=True)
    for m in mensajes:
        if m["role"] != "system":
            # Usar avatares estilo la imagen
            av_style = "🤖" if m["role"] == "assistant" else st.session_state.usuario[0].upper()
            with st.chat_message(m["role"], avatar=av_style):
                if m.get("tipo") == "img": st.image(base64.b64decode(m["content"]), use_container_width=True)
                else: st.markdown(m["content"])

# --- ENTRADA DE USUARIO ---
if prompt := st.chat_input("Dime algo, Alberto..."):
    # Autotitular si es el inicio
    if st.session_state.chat_activo == "Nueva Conversación":
        st.session_state.chat_activo = generar_titulo(prompt)
    
    mensajes.append({"role": "user", "content": prompt})
    
    # Rerun instantáneo para limpiar las tarjetas de bienvenida e iniciar el chat
    if len(mensajes) == 2:
        db_guardar_chat(st.session_state.usuario, st.session_state.chat_activo, mensajes)
        st.rerun()
    
    with st.chat_message("user", avatar=st.session_state.usuario[0].upper()): st.markdown(prompt)
    
    with st.chat_message("assistant", avatar="🤖"):
        placeholder = st.empty()
        full_res = ""
        
        ctx = [m for m in mensajes if m.get("tipo") != "img"]
        pdf_ctx = st.session_state.get(f"pdf_txt_{st.session_state.chat_activo}", "")
        if pdf_ctx: ctx.insert(1, {"role": "system", "content": f"Usa este PDF: {pdf_ctx}"})

        stream = cliente_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=ctx,
            stream=True,
            temperature=0.2
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                full_res += chunk.choices[0].delta.content
                if not any(x in full_res for x in ["[IMAGEN]", "[BUSCAR]"]):
                    placeholder.markdown(full_res + "▌")
        
        # PROCESAR ACCIONES
        if "[IMAGEN]" in full_res:
            placeholder.info("🎨 Generando arte...")
            prompt_img = full_res.split("[IMAGEN]")[1].strip()
            img_b64 = generar_imagen(prompt_img)
            if img_b64:
                placeholder.empty()
                st.image(base64.b64decode(img_b64), use_container_width=True)
                mensajes.append({"role": "assistant", "content": img_b64, "tipo": "img"})
                db_guardar_imagen(st.session_state.usuario, img_b64)
            else: placeholder.error("Error al generar imagen.")
        
        elif "[BUSCAR]" in full_res:
            placeholder.info("🔍 Buscando en internet...")
            q = full_res.split("[BUSCAR]")[1].strip()
            data = buscar_google(q)
            res_ia = cliente_groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": f"Resume esto para Alberto de forma profesional: {data}"}]
            )
            txt = res_ia.choices[0].message.content
            placeholder.markdown(txt)
            mensajes.append({"role": "assistant", "content": txt})
        
        else:
            placeholder.markdown(full_res)
            mensajes.append({"role": "assistant", "content": full_res})
        
        db_guardar_chat(st.session_state.usuario, st.session_state.chat_activo, mensajes)
        # st.rerun() # No necesario aquí y puede causar flickering