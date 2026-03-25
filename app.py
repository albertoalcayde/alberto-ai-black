import streamlit as st
import groq
import fitz
import requests
import base64
import json
from datetime import datetime, timedelta
from supabase import create_client, Client

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Alberto AI - Light Edition", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

# --- CSS: ESTILO CHATGPT MODO CLARO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif !important;
        background-color: #FFFFFF !important;
        color: #0D0D0D !important;
    }

    /* --- BARRA LATERAL GRIS MUY CLARO --- */
    [data-testid="stSidebar"] {
        background-color: #F9F9F9 !important;
        border-right: 1px solid #ECECEC !important;
    }
    
    [data-testid="stSidebar"] * {
        color: #0D0D0D !important;
    }

    /* Botones de historial */
    [data-testid="stSidebar"] button[kind="secondary"] {
        background-color: transparent !important;
        border: none !important;
        border-radius: 8px !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 8px 12px !important;
        transition: background-color 0.2s;
        font-weight: 400 !important;
    }
    [data-testid="stSidebar"] button[kind="secondary"]:hover {
        background-color: #ECECEC !important;
    }
    
    /* Botón Chat Activo */
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #ECECEC !important; 
        border: none !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 8px 12px !important;
    }

    /* --- ÁREA CENTRAL BLANCA --- */
    .main .block-container {
        padding-top: 3rem !important;
        max-width: 800px !important; 
    }

    /* Mensajes limpios */
    .stChatMessage {
        background-color: transparent !important;
        border: none !important;
        padding: 1rem 0rem !important;
    }

    /* --- BARRA DE ESCRITURA --- */
    [data-testid="stChatInputContainer"] {
        background-color: #FFFFFF !important;
        padding-bottom: 2rem !important;
    }
    .stChatInput {
        background-color: #F4F4F4 !important;
        border-radius: 25px !important;
        border: 1px solid #E5E5E5 !important;
        padding-left: 1rem !important;
    }

    /* Pantalla inicio */
    .inicio-titulo {
        text-align: center;
        font-size: 2rem;
        font-weight: 600;
        margin-top: 15vh;
        margin-bottom: 2rem;
        color: #0D0D0D;
    }
    
    /* Ocultar header */
    header[data-testid="stHeader"] { display: none !important; }
    [data-testid="stFileUploader"] {
        border: 1px dashed #CCCCCC !important;
        border-radius: 8px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXIÓN ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    cliente_groq = groq.Groq(api_key=st.secrets["GROQ_API_KEY"])
    HF_API_KEY = st.secrets["HUGGINGFACE_API_KEY"]
    SERPER_KEY = st.secrets.get("SERPER_API_KEY", None)
except Exception as e:
    st.error(f"⚠️ Error de conexión. Revisa tus Secrets en Streamlit.")
    st.stop()

# --- MEMORIA DB ---
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

# --- IA Y HERRAMIENTAS ---
def buscar_google(query):
    if not SERPER_KEY: return "Error: Sin API."
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "gl": "es", "hl": "es"})
    headers = {'X-API-KEY': SERPER_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        results = response.json()
        snippets = [f"- {item['title']}: {item['snippet']}" for item in results.get('organic', [])[:3]]
        return "\n".join(snippets) if snippets else "No hay resultados."
    except: return "Error."

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
            messages=[{"role": "system", "content": "Resume en 2-3 palabras este tema. Solo texto."},
                      {"role": "user", "content": mensaje}],
            max_tokens=10
        )
        return res.choices[0].message.content.strip().replace('"', '')
    except: return "Chat"

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    with st.sidebar:
        st.subheader("Acceso")
        nombre = st.text_input("Nombre:")
        if st.button("Entrar", type="secondary"):
            if nombre:
                st.session_state.autenticado = True
                st.session_state.usuario = nombre.lower().strip()
                st.rerun()
    st.markdown("<div class='inicio-titulo'>Alberto AI</div>", unsafe_allow_html=True)
    st.stop()

# --- PREPARACIÓN DEL CHAT (Cerebro primero) ---
if "chat_activo" not in st.session_state:
    st.session_state.chat_activo = "Nueva Conversación"

mensajes = db_cargar_mensajes(st.session_state.usuario, st.session_state.chat_activo)

ahora = datetime.utcnow() + timedelta(hours=1)
if not mensajes:
    system_prompt = (
        f"Eres un asistente IA. Usuario: {st.session_state.usuario}. "
        f"Fecha/Hora: {ahora.strftime('%d/%m/%Y %H:%M')} (España). "
        "Si piden imágenes, usa SOLO: [IMAGEN] prompt-inglés. "
        "Si piden buscar, usa SOLO: [BUSCAR] consulta. "
        "Responde en español, claro y directo."
    )
    mensajes = [{"role": "system", "content": system_prompt}]

# --- PREPARAR TEXTO PARA DESCARGAR CHAT ---
chat_str = f"--- Documento exportado de Alberto AI ---\nChat: {st.session_state.chat_activo}\nFecha: {ahora.strftime('%d/%m/%Y')}\n\n"
for m in mensajes:
    if m["role"] != "system":
        autor = "Tú" if m["role"] == "user" else "Alberto AI"
        contenido = "[IMAGEN GENERADA]" if m.get("tipo") == "img" else m["content"]
        chat_str += f"{autor}:\n{contenido}\n\n"

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"**{st.session_state.usuario.capitalize()}**")
    
    if st.button("📝 Nuevo chat", use_container_width=True, type="secondary"):
        st.session_state.chat_activo = "Nueva Conversación"
        st.rerun()
    
    st.markdown("---")
    st.caption("Herramientas")
    
    # BOTÓN DESCARGAR CHAT TEXTO
    if len(mensajes) > 1:
        st.download_button(
            label="📥 Descargar este chat (.txt)",
            data=chat_str,
            file_name=f"{st.session_state.chat_activo.replace(' ', '_')}.txt",
            mime="text/plain",
            use_container_width=True
        )

    with st.expander("📄 Subir PDF"):
        archivo_pdf = st.file_uploader("", type=["pdf"], key=f"pdf_{st.session_state.get('chat_activo', 'def')}")
        if archivo_pdf:
            doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
            st.session_state[f"pdf_{st.session_state.get('chat_activo', 'def')}"] = "".join([p.get_text() for p in doc])[:5000]
            st.success("PDF Cargado")

    with st.expander("🖼️ Tu Galería"):
        for idx, img in enumerate(db_cargar_galeria(st.session_state.usuario)):
            img_bytes = base64.b64decode(img)
            st.image(img_bytes, use_container_width=True)
            # BOTÓN DESCARGAR IMAGEN EN GALERÍA
            st.download_button("⬇️ Descargar", data=img_bytes, file_name=f"Arte_AlbertoAI_{idx}.png", mime="image/png", key=f"dl_gal_{idx}", use_container_width=True)

    st.markdown("---")
    st.caption("Tus chats")
    titulos = db_cargar_titulos(st.session_state.usuario)
    for t in titulos:
        col1, col2 = st.columns([0.85, 0.15])
        with col1:
            if st.button(t, key=f"btn_{t}", use_container_width=True, type="primary" if t == st.session_state.get('chat_activo') else "secondary"):
                st.session_state.chat_activo = t
                st.rerun()
        with col2:
            if st.button("×", key=f"del_{t}"):
                db_borrar_chat(st.session_state.usuario, t)
                if st.session_state.chat_activo == t: st.session_state.chat_activo = "Nueva Conversación"
                st.rerun()

# --- CHAT CENTRAL ---
bienvenida = st.empty()
if len(mensajes) <= 1:
    bienvenida.markdown("<div class='inicio-titulo'>¿Qué tienes en mente hoy?</div>", unsafe_allow_html=True)
else:
    for idx, m in enumerate(mensajes):
        if m["role"] != "system":
            icono = "🤖" if m["role"] == "assistant" else "👤"
            with st.chat_message(m["role"], avatar=icono):
                if m.get("tipo") == "img": 
                    img_bytes = base64.b64decode(m["content"])
                    st.image(img_bytes, use_container_width=True)
                    # BOTÓN DESCARGAR IMAGEN EN EL CHAT
                    st.download_button("⬇️ Descargar Imagen", data=img_bytes, file_name=f"Imagen_IA_{idx}.png", mime="image/png", key=f"dl_chat_{idx}")
                else: 
                    st.markdown(m["content"])

# --- INPUT Y LÓGICA DE RESPUESTA ---
if prompt := st.chat_input("Pregunta lo que quieras"):
    bienvenida.empty()
    
    if st.session_state.chat_activo == "Nueva Conversación":
        st.session_state.chat_activo = generar_titulo(prompt)
    
    mensajes.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"): 
        st.markdown(prompt)
    
    with st.chat_message("assistant", avatar="🤖"):
        placeholder = st.empty()
        full_res = ""
        
        ctx = [m for m in mensajes if m.get("tipo") != "img"]
        pdf_ctx = st.session_state.get(f"pdf_{st.session_state.chat_activo}", "")
        if pdf_ctx: ctx.insert(1, {"role": "system", "content": f"PDF context: {pdf_ctx}"})

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
        
        if "[IMAGEN]" in full_res:
            placeholder.info("Generando imagen...")
            prompt_img = full_res.split("[IMAGEN]")[1].strip()
            img_b64 = generar_imagen(prompt_img)
            if img_b64:
                placeholder.empty()
                st.image(base64.b64decode(img_b64), use_container_width=True)
                mensajes.append({"role": "assistant", "content": img_b64, "tipo": "img"})
                db_guardar_imagen(st.session_state.usuario, img_b64)
            else: placeholder.error("Error al generar imagen.")
        
        elif "[BUSCAR]" in full_res:
            placeholder.info("Buscando en Google...")
            q = full_res.split("[BUSCAR]")[1].strip()
            data = buscar_google(q)
            res_ia = cliente_groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": f"Resume: {data}"}]
            )
            txt = res_ia.choices[0].message.content
            placeholder.markdown(txt)
            mensajes.append({"role": "assistant", "content": txt})
        
        else:
            placeholder.markdown(full_res)
            mensajes.append({"role": "assistant", "content": full_res})
        
    db_guardar_chat(st.session_state.usuario, st.session_state.chat_activo, mensajes)
    st.rerun()