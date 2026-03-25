import streamlit as st
import groq
import fitz
import requests
import base64
import json
from supabase import create_client, Client

# --- CONFIGURACIÓN DE ÉLITE ---
st.set_page_config(page_title="Alberto AI - Ultimate Cloud", page_icon="⚡", layout="wide")

# CSS Estética Premium
st.markdown("""
    <style>
    .stApp { background-color: #f7f7f8; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e5e5e5; }
    .stChatMessage { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 12px; margin-bottom: 15px; }
    .stChatInput { border-radius: 10px !important; border: 1px solid #ddd !important; }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXIÓN A BASES DE DATOS ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    cliente_groq = groq.Groq(api_key=st.secrets["GROQ_API_KEY"])
    HF_API_KEY = st.secrets["HUGGINGFACE_API_KEY"]
except Exception as e:
    st.error("⚠️ Error en las llaves API. Revisa los Secrets en Streamlit Cloud.")
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

def generar_imagen(prompt):
    URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    r = requests.post(URL, headers=headers, json={"inputs": prompt})
    return base64.b64encode(r.content).decode() if r.status_code == 200 else None

def generar_titulo(mensaje):
    try:
        res = cliente_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "Resume en 3 palabras el tema de este mensaje para un título."},
                      {"role": "user", "content": mensaje}],
            max_tokens=10
        )
        return res.choices[0].message.content.strip().replace('"', '')
    except:
        return "Nueva Conversación"

# --- SISTEMA DE ACCESO ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    with st.sidebar:
        st.title("🆔 Acceso")
        nombre = st.text_input("¿Cómo te llamas?")
        if st.button("Entrar"):
            if nombre:
                st.session_state.autenticado = True
                st.session_state.usuario = nombre.lower().strip()
                st.rerun()
    st.markdown("<h1 style='text-align:center;'>Alberto AI Cloud</h1><p style='text-align:center;'>Inicia sesión a la izquierda.</p>", unsafe_allow_html=True)
    st.stop()

# --- INTERFAZ ACTIVA ---
with st.sidebar:
    st.subheader(f"👋 {st.session_state.usuario.capitalize()}")
    
    if st.button("➕ Nuevo Chat", use_container_width=True):
        st.session_state.chat_activo = "Nueva Conversación"
        st.rerun()
    
    st.markdown("---")
    
    # 📄 SECCIÓN DE ARCHIVOS RECUPERADA
    with st.expander("📄 Subir y Analizar PDF"):
        archivo_pdf = st.file_uploader("Sube un documento", type=["pdf"])
        if archivo_pdf:
            doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
            texto_pdf = "".join([p.get_text() for p in doc])
            st.session_state[f"pdf_{st.session_state.get('chat_activo', 'Nueva') }"] = texto_pdf[:4000]
            st.success("✅ PDF analizado")

    st.markdown("---")
    st.caption("Tus conversaciones:")
    titulos_db = db_cargar_titulos(st.session_state.usuario)
    for t in titulos_db:
        if st.button(t, key=f"btn_{t}", use_container_width=True, type="primary" if t == st.session_state.get('chat_activo') else "secondary"):
            st.session_state.chat_activo = t
            st.rerun()
    
    with st.expander("🖼️ Galería"):
        for img in db_cargar_galeria(st.session_state.usuario):
            st.image(base64.b64decode(img))

# Gestionar chat activo
if "chat_activo" not in st.session_state:
    st.session_state.chat_activo = "Nueva Conversación"

mensajes = db_cargar_mensajes(st.session_state.usuario, st.session_state.chat_activo)
if not mensajes:
    mensajes = [{"role": "system", "content": "Eres Alberto AI. Responde en español. Si piden imagen, usa la etiqueta [IMAGEN] seguida del prompt en inglés."}]

st.title(f"💬 {st.session_state.chat_activo}")

# Mostrar historial
for m in mensajes:
    if m["role"] != "system":
        with st.chat_message(m["role"]):
            if m.get("tipo") == "img": st.image(base64.b64decode(m["content"]))
            else: st.markdown(m["content"])

# Entrada de usuario
if prompt := st.chat_input("Dime algo..."):
    # 1. Autotitular si es el primer mensaje real
    if st.session_state.chat_activo == "Nueva Conversación":
        st.session_state.chat_activo = generar_titulo(prompt)
    
    mensajes.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        
        # Inyectar PDF en el contexto si existe
        pdf_ctx = st.session_state.get(f"pdf_{st.session_state.chat_activo}", "")
        ctx_envio = [m for m in mensajes if m.get("tipo") != "img"]
        if pdf_ctx:
            ctx_envio.insert(1, {"role": "system", "content": f"Usa esta info del PDF: {pdf_ctx}"})

        try:
            stream = cliente_groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=ctx_envio,
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_res += chunk.choices[0].delta.content
                    placeholder.markdown(full_res + "▌")
            
            if "[IMAGEN]" in full_res:
                placeholder.info("🎨 Generando imagen...")
                img_b64 = generar_imagen(full_res.replace("[IMAGEN]", "").strip())
                if img_b64:
                    placeholder.empty()
                    st.image(base64.b64decode(img_b64))
                    mensajes.append({"role": "assistant", "content": img_b64, "tipo": "img"})
                    db_guardar_imagen(st.session_state.usuario, img_b64)
            else:
                mensajes.append({"role": "assistant", "content": full_res})
            
            # Guardar en Supabase
            db_guardar_chat(st.session_state.usuario, st.session_state.chat_activo, mensajes)
            st.rerun()
            
        except Exception as e:
            st.error("❌ Error de conexión. Revisa tu llave de Groq.")