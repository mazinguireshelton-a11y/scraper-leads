"""
MOTOR DE BUSCA B2B UNIVERSAL COM IA (OpenRouter)
-----------------------------------------------------
"""

import streamlit as st
import pandas as pd
import requests
import re
import os
from io import BytesIO
from bs4 import BeautifulSoup

# Tenta carregar o dotenv para testes locais
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURAÇÃO DE CHAVES DE API ---
try:
    RAPIDAPI_KEY = st.secrets.get("RAPIDAPI_KEY", os.getenv("RAPIDAPI_KEY", ""))
    OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", os.getenv("OPENROUTER_API_KEY", ""))
except Exception:
    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

SEARCH_URL = "https://local-business-data.p.rapidapi.com/search"
# URL CORRETO DO OPENROUTER
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# --- CONFIGURAÇÃO DA PÁGINA E ESTILO VISUAL (CSS) ---
st.set_page_config(page_title="Prospeção B2B com IA", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #f8f9fa;}
    h1 {color: #1e3a8a; font-family: 'Helvetica Neue', sans-serif;}
    .stButton>button {
        background-color: #2563eb; color: white; border-radius: 8px; font-weight: bold; transition: 0.3s;
    }
    .stButton>button:hover {background-color: #1d4ed8; border-color: #1d4ed8;}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE LIMPEZA E EXTRAÇÃO ---
def limpar_para_pdf(texto):
    if not texto:
        return "N/A"
    return str(texto).replace("&", "e").replace("<", "").replace(">", "")

def extrair_email_do_site(url):
    if not url or url == "N/A":
        return ""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resposta = requests.get(url, headers=headers, timeout=3)
        emails = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", resposta.text))
        validos = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
        return ", ".join(validos[:2])
    except:
        return ""

def gerar_link_whatsapp(telefone):
    if not telefone: return ""
    num = re.sub(r'\D', '', str(telefone))
    return f"https://wa.me/{num}" if num else ""

def calcular_score_oportunidade(site, avaliacao, num_avaliacoes, telefone):
    score = 0
    if not site: score += 30
    try:
        nota = float(avaliacao) if avaliacao else 0.0
        if 0 < nota < 4.0: score += 20
    except: pass
    if not telefone: score -= 10
    return score

# --- INTEGRAÇÃO COM A IA DO OPENROUTER ---
# Modelos em ordem de tentativa. O auto-router 'openrouter/free' escolhe
# sozinho um modelo grátis disponível — evita quebrar quando um ID específico
# é descontinuado (o catálogo de modelos grátis muda com frequência).
MODELOS_FALLBACK = [
    "openrouter/free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
]

def analisar_com_ia(nome, nicho, site, avaliacao, objetivo, api_key):
    if not api_key:
        return "Erro: Chave API OpenRouter em falta."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://streamlit.io",
        "X-Title": "Motor B2B Universal"
    }

    prompt = f"""
    O meu objetivo é: '{objetivo}'.
    Analisa esta empresa: Nome: {nome} (Nicho: {nicho}). Website: {'Sim' if site else 'Não'}. Avaliação: {avaliacao}.
    Retorna APENAS:
    1. DIAGNÓSTICO: (1 frase avaliando a empresa)
    2. MENSAGEM: (1 mensagem de WhatsApp curta e persuasiva para abordagem)
    """

    erro_final = ""
    for modelo in MODELOS_FALLBACK:
        payload = {
            "model": modelo,
            "messages": [
                {"role": "system", "content": "És um estratega de negócios B2B. Responde sempre em Português."},
                {"role": "user", "content": prompt}
            ]
        }
        try:
            response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                dados = response.json()
                return dados['choices'][0]['message']['content'].strip()
            else:
                erro_final = f"Erro IA ({response.status_code}): {response.text[:150]}"
                continue  # tenta o próximo modelo da lista
        except Exception as e:
            erro_final = f"Erro ligação IA: {e}"
            continue

    return erro_final or "Erro: nenhum modelo grátis disponível no momento."

# --- MOTOR DE BUSCA RAPIDAPI ---
def buscar_lugares(query, api_key, limit, nicho, regiao, progress=None):
    headers = {"x-rapidapi-key": api_key, "x-rapidapi-host": "local-business-data.p.rapidapi.com"}
    params = {"query": query, "limit": str(limit), "language": "pt"}
    
    try:
        res = requests.get(SEARCH_URL, headers=headers, params=params)
        if res.status_code != 200: return []
            
        dados = res.json().get("data", [])
        resultados = []
        
        for i, lugar in enumerate(dados):
            if len(resultados) >= limit: break
            
            nome = lugar.get("name", "N/A")
            tel = lugar.get("phone_number", "")
            site = lugar.get("website", "")
            aval = lugar.get("rating", "")
            
            score = calcular_score_oportunidade(site, aval, lugar.get("review_count", 0), tel)
            
            resultados.append({
                "Score": score,
                "Nome": nome,
                "Telefone": tel,
                "WhatsApp": gerar_link_whatsapp(tel),
                "E-mail": extrair_email_do_site(site),
                "Site": site,
                "Avaliação": str(aval)
            })
            if progress: progress(len(resultados), limit, "A extrair dados...")
                
        return sorted(resultados, key=lambda x: x["Score"], reverse=True)
    except Exception:
        return []

# --- EXPORTAÇÃO: WORD E PDF ---
def criar_word(dados, nicho, regiao):
    doc = Document()
    doc.add_heading(f"Relatório de Prospeção: {nicho} em {regiao}", 0)
    for item in dados:
        doc.add_heading(item["Nome"], level=2)
        doc.add_paragraph(f"• Contato: {item['Telefone']} | Email: {item['E-mail']}")
        doc.add_paragraph(f"• Score Comercial: {item['Score']}")
        doc.add_paragraph(f"• Análise IA:\n{item.get('Análise IA', 'Não analisado.')}")
        doc.add_paragraph("-" * 30)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def criar_pdf(dados, nicho, regiao):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elementos = []
    
    elementos.append(Paragraph(f"Relatório Estratégico: {nicho} em {regiao}", styles['Title']))
    elementos.append(Spacer(1, 15))
    
    for item in dados:
        nome = limpar_para_pdf(item['Nome'])
        elementos.append(Paragraph(f"<b>{nome}</b> (Score: {item['Score']})", styles['Heading2']))
        elementos.append(Paragraph(f"<b>Telefone:</b> {limpar_para_pdf(item['Telefone'])}", styles['Normal']))
        elementos.append(Paragraph(f"<b>E-mail:</b> {limpar_para_pdf(item['E-mail'])}", styles['Normal']))
        analise = limpar_para_pdf(item.get('Análise IA', 'Não gerado.'))
        elementos.append(Paragraph(f"<b>Análise IA:</b> {analise}", styles['Normal']))
        elementos.append(Spacer(1, 10))
        
    doc.build(elementos)
    buffer.seek(0)
    return buffer

# ---------- INTERFACE PRINCIPAL ----------
st.title("🚀 Plataforma de Prospeção Inteligente")
st.markdown("Encontra oportunidades de negócio e utiliza IA para gerar propostas comerciais adaptadas ao teu objetivo.")

if not RAPIDAPI_KEY or not OPENROUTER_API_KEY:
    with st.sidebar:
        st.warning("⚠️ Chaves API necessárias")
        RAPIDAPI_KEY = st.text_input("RapidAPI Key", value=RAPIDAPI_KEY, type="password")
        OPENROUTER_API_KEY = st.text_input("OpenRouter API Key", value=OPENROUTER_API_KEY, type="password")
        st.markdown("[Criar conta OpenRouter Grátis](https://openrouter.ai/)")

st.divider()

col1, col2, col3 = st.columns([2, 2, 1])
nicho = col1.text_input("🏢 Nicho / Setor", placeholder="Ex: Clínicas, Restaurantes")
regiao = col2.text_input("📍 Região", placeholder="Ex: Maputo, Lisboa")
max_leads = col3.number_input("📊 Qtd.", min_value=5, max_value=50, value=10)

objetivo = st.text_input("🎯 Objetivo Comercial", placeholder="Ex: Quero vender serviços de marketing digital")

if st.button("🔍 Iniciar Varredura do Mercado", type="primary", use_container_width=True):
    if not RAPIDAPI_KEY or not nicho or not regiao:
        st.error("Preenche os campos e as chaves API.")
    else:
        bar = st.progress(0, "A preparar...")
        with st.spinner("A rastrear empresas..."):
            resultados = buscar_lugares(f"{nicho} em {regiao}", RAPIDAPI_KEY, max_leads, nicho, regiao, 
                                      lambda c, t, msg: bar.progress(min(c/t, 1.0), msg))
            if resultados:
                st.session_state.update({'leads': resultados, 'n': nicho, 'r': regiao, 'obj': objetivo})
        bar.empty()

if 'leads' in st.session_state:
    df = pd.DataFrame(st.session_state['leads'])
    st.success(f"✅ {len(df)} oportunidades validadas e ordenadas por potencial (Score).")
    st.dataframe(df, use_container_width=True)
    
    st.markdown("### 🧠 Modo Premium: Abordagem IA (Gratuita)")
    qtd = st.slider("Analisar quantas empresas?", 1, len(df), min(3, len(df)))
    
    if st.button("✨ Gerar Estratégias com IA", type="primary"):
        with st.spinner("A IA está a redigir as mensagens..."):
            for i in range(qtd):
                empresa = st.session_state['leads'][i]
                resp = analisar_com_ia(empresa["Nome"], st.session_state['n'], empresa["Site"], 
                                     empresa["Avaliação"], st.session_state['obj'], OPENROUTER_API_KEY)
                st.session_state['leads'][i]["Análise IA"] = resp
            st.rerun()
            
    st.divider()
    st.subheader("📥 Exportar Relatórios")
    df_final = pd.DataFrame(st.session_state['leads'])
    
    b1, b2, b3 = st.columns(3)
    b1.download_button("📊 Excel (CSV)", data=df_final.to_csv(index=False).encode("utf-8"), 
                       file_name="leads.csv", mime="text/csv", use_container_width=True)
    b2.download_button("📝 Documento Word", data=criar_word(st.session_state['leads'], st.session_state['n'], st.session_state['r']), 
                       file_name="leads.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
    b3.download_button("📕 Relatório PDF", data=criar_pdf(st.session_state['leads'], st.session_state['n'], st.session_state['r']), 
                       file_name="leads.pdf", mime="application/pdf", use_container_width=True)
