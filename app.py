import streamlit as st
import groq
import fitz
import requests
import base64
import json
from datetime import datetime, timedelta
from supabase import create_client, Client

# --- DISEÑO VISUAL "PREMIUM WHITE" ---
st.set_page_config(page_title="Alberto AI - PRO Edition", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    /* Fondo principal blanco puro */
    .stApp { 
        background-color: #ffffff; 
        color: #1f1f1f; 
    }
    
    /* Barra lateral en gris ultra claro */
    [data-testid="stSidebar"] { 
        background-color: #f8f9fa; 
        border-right: 1px solid #eeeeee; 
    }
    
    /* Burbujas de chat con estilo limpio */
    .stChatMessage { 
        background-color: #ffffff; 
        border: 1px solid #f0f0f0; 
        border-radius: 15px; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        margin-bottom: 15px; 
    }
    
    /* Input de texto moderno */
    .stChatInput { 
        border-radius: 12px !important; 
        border: 1px solid #e0e0e0 !important; 
        background-color: #ffffff !important;
    }

    /* Títulos y fuentes */
    h1, h2, h3 { 
        color: #1a1a1a; 
        font-family: 'Inter', sans-serif;
        font-weight: 700;
    }

    /* Botones personalizados */
    .stButton>button { 
        border-radius: 10px; 
        border: 1px solid #eeeeee;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        border-color: #007aff;
        color: #007aff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXIÓN A LAS LLAVES MAESTRAS ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    cliente_groq = groq.Groq(api_key=st.secrets["GROQ_API_KEY"])
    HF_API_KEY = st.secrets["HUGGINGFACE_API_KEY"]
    SERPER_KEY = st.secrets.get("SERPER_API_KEY", None)
except Exception as e:
    st.error(f"⚠️ Error en Secrets: {e}")
    st.stop()

# --- FUNCIONES DE MEMORIA (SUPABASE) ---
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

# --- FUNCIONES DE IA Y BÚSQUEDA ---
def buscar_google(query):
    if not SERPER_KEY: return "Error: Sin llave de Serper."
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "gl": "es", "hl": "es"})
    headers = {'X-API-KEY': SERPER_KEY, 'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, data=payload)
    results = response.json()
    snippets = [f"- {item['title']}: {item['snippet']}" for item in results.get('organic', [])[:3]]
    return "\n".join(snippets)

def generar_imagen(prompt):
    URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    try:
        r = requests.post(URL, headers=headers, json={"inputs": prompt}, timeout=40)
        if r.status_code == 200:
            return base64.b64encode(r.content).decode()
    except: return None
    return None

def generar_titulo(mensaje):
    try:
        res = cliente_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Resume en 2 palabras este tema. Solo texto."},
                      {"role": "user", "content": mensaje}],
            max_tokens=10
        )
        return res.choices[0].message.content.strip().replace('"', '')
    except: return "Chat Nuevo"

# --- ACCESO ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    with st.sidebar:
        st.title("🆔 Acceso")
        nombre = st.text_input("Dime tu nombre...")
        if st.button("Entrar"):
            if nombre:
                st.session_state.autenticado = True
                st.session_state.usuario = nombre.lower().strip()
                st.rerun()
    st.markdown("<h1 style='text-align:center; margin-top:5rem;'>Alberto AI</h1>", unsafe_allow_html=True)
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.subheader(f"👋 {st.session_state.usuario.capitalize()}")
    
    if st.button("➕ Nuevo Chat", use_container_width=True):
        st.session_state.chat_activo = "Nueva Conversación"
        st.rerun()
    
    st.markdown("---")
    
    with st.expander("📄 Analizar PDF"):
        archivo_pdf = st.file_uploader("Sube un PDF", type=["pdf"], key=f"pdf_{st.session_state.get('chat_activo', 'default')}")
        if archivo_pdf:
            doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
            st.session_state[f"pdf_txt_{st.session_state.get('chat_activo', 'default')}"] = "".join([p.get_text() for p in doc])[:5000]
            st.success("✅ PDF analizado")

    st.markdown("---")
    st.caption("Historial de chats:")
    titulos = db_cargar_titulos(st.session_state.usuario)
    for t in titulos:
        col_t, col_del = st.columns([0.8, 0.2])
        with col_t:
            if st.button(t, key=f"btn_{t}", use_container_width=True, type="primary" if t == st.session_state.get('chat_activo') else "secondary"):
                st.session_state.chat_activo = t
                st.rerun()
        with col_del:
            if st.button("🗑️", key=f"del_{t}"):
                db_borrar_chat(st.session_state.usuario, t)
                if st.session_state.chat_activo == t: st.session_state.chat_activo = "Nueva Conversación"
                st.rerun()
    
    st.markdown("---")
    with st.expander("🖼️ Galería de Fotos"):
        for img in db_cargar_galeria(st.session_state.usuario):
            st.image(base64.b64decode(img), use_container_width=True)

# --- ÁREA DE CHAT ---
if "chat_activo" not in st.session_state:
    st.session_state.chat_activo = "Nueva Conversación"

st.title(f"💬 {st.session_state.chat_activo}")

mensajes = db_cargar_mensajes(st.session_state.usuario, st.session_state.chat_activo)

if not mensajes:
    # HORA EN ESPAÑA
    ahora = datetime.utcnow() + timedelta(hours=1)
    fecha_txt = ahora.strftime("%d/%m/%Y")
    hora_txt = ahora.strftime("%H:%M")

    system_prompt = (
        f"Eres 'Alberto AI PRO'. Usuario: {st.session_state.usuario}. "
        f"FECHA Y HORA ACTUAL EN ESPAÑA: {fecha_txt} a las {hora_txt}. "
        "Si piden imágenes, responde SOLO: [IMAGEN] prompt-en-inglés. "
        "Si piden info actual, responde SOLO: [BUSCAR] consulta. "
        "Responde siempre en español de forma directa y elegante."
    )
    mensajes = [{"role": "system", "content": system_prompt}]

# Mostrar mensajes
for m in mensajes:
    if m["role"] != "system":
        with st.chat_message(m["role"]):
            if m.get("tipo") == "img": st.image(base64.b64decode(m["content"]), use_container_width=True)
            else: st.markdown(m["content"])

# Input
if prompt := st.chat_input("Escribe aquí..."):
    if st.session_state.chat_activo == "Nueva Conversación":
        st.session_state.chat_activo = generar_titulo(prompt)
    
    mensajes.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    
    with st.chat_message("assistant"):
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
        
        elif "[BUSCAR]" in full_res:
            placeholder.info("🔍 Buscando...")
            q = full_res.split("[BUSCAR]")[1].strip()
            data = buscar_google(q)
            res_ia = cliente_groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": f"Resume esto para el usuario de forma elegante: {data}"}]
            )
            txt = res_ia.choices[0].message.content
            placeholder.markdown(txt)
            mensajes.append({"role": "assistant", "content": txt})
        
        else:
            placeholder.markdown(full_res)
            mensajes.append({"role": "assistant", "content": full_res})
        
        db_guardar_chat(st.session_state.usuario, st.session_state.chat_activo, mensajes)
        st.rerun()