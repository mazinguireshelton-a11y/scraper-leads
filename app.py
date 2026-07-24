"""
MOTOR DE BUSCA B2B UNIVERSAL COM INTELIGÊNCIA ARTIFICIAL (Grok)
-----------------------------------------------------
"""

import streamlit as st
import pandas as pd
import requests
import re
import os
from io import BytesIO
from bs4 import BeautifulSoup

# Tenta carregar o dotenv para testes locais no Termux (se falhar, ignora)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURAÇÃO DE CHAVES DE API (SEGURANÇA) ---
# O código tenta ler do Streamlit Secrets primeiro. Se não encontrar, tenta do .env local.
try:
    RAPIDAPI_KEY = st.secrets.get("RAPIDAPI_KEY", os.getenv("RAPIDAPI_KEY", ""))
    GROK_API_KEY = st.secrets.get("GROK_API_KEY", os.getenv("GROK_API_KEY", ""))
except Exception:
    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
    GROK_API_KEY = os.getenv("GROK_API_KEY", "")

SEARCH_URL = "https://local-business-data.p.rapidapi.com/search"
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

st.set_page_config(page_title="Motor B2B Universal", page_icon="🌍", layout="wide")

# --- FUNÇÕES DE LIMPEZA E EXTRAÇÃO ---
def limpar_para_pdf(texto):
    if not texto:
        return ""
    return str(texto).replace("&", "e").replace("<", "").replace(">", "")

def extrair_email_do_site(url):
    if not url or url == "N/A":
        return ""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resposta = requests.get(url, headers=headers, timeout=3)
        emails_encontrados = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", resposta.text))
        emails_validos = [e for e in emails_encontrados if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
        return ", ".join(emails_validos[:2])
    except:
        return ""

def gerar_link_whatsapp(telefone):
    if not telefone:
        return ""
    numero_limpo = re.sub(r'\D', '', telefone)
    if numero_limpo:
        return f"https://wa.me/{numero_limpo}"
    return ""

def calcular_score_oportunidade(site, avaliacao, num_avaliacoes, telefone):
    """Calcula um score básico e rápido para priorizar os melhores contatos"""
    score = 0
    # Regras universais de pontuação
    if not site: score += 30
    try:
        nota = float(avaliacao) if avaliacao else 0.0
        if 0 < nota < 4.0: score += 20
    except: pass
    if not telefone: score -= 10
    return score

# --- INTEGRAÇÃO COM A IA DO GROK ---
def analisar_com_grok(nome, nicho, site, avaliacao, objetivo, api_key):
    """Usa o Grok para gerar um diagnóstico e mensagem baseada no objetivo do utilizador"""
    if not api_key:
        return "Erro: Chave da API do Grok não configurada."
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    prompt_sistema = "És um estrategista de negócios especialista em prospecção B2B direto e persuasivo."
    prompt_utilizador = f"""
    O meu objetivo profissional é: '{objetivo}'.
    Analisa esta empresa de forma breve para me ajudar a abordá-los:
    - Nome: {nome} (Nicho: {nicho})
    - Tem Website: {'Sim' if site else 'Não'}
    - Avaliação no Google: {avaliacao}
    
    Fornece apenas duas coisas:
    1. DIAGNÓSTICO: (1 frase avaliando a empresa face ao meu objetivo)
    2. MENSAGEM: (1 mensagem de WhatsApp curta e profissional, pronta a enviar, oferecendo o meu serviço/proposta)
    """
    
    payload = {
        "model": "grok-beta",
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_utilizador}
        ],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(GROK_API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            dados = response.json()
            return dados['choices'][0]['message']['content'].strip()
        else:
            return f"Erro na IA ({response.status_code}): {response.text}"
    except Exception as e:
        return f"Erro de ligação à IA: {e}"

# --- MOTOR DE BUSCA RAPIDAPI ---
def buscar_lugares_rapidapi(query: str, api_key: str, max_results: int, nicho: str, regiao: str, progress_callback=None):
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "local-business-data.p.rapidapi.com"
    }
    querystring = {"query": query, "limit": str(max_results), "language": "pt"}
    
    try:
        response = requests.get(SEARCH_URL, headers=headers, params=querystring)
        if response.status_code != 200:
            st.error("Erro na RapidAPI. Verifica a tua chave.")
            return []
            
        resultados_api = response.json().get("data", [])
        resultados_finais = []
        
        for i, lugar in enumerate(resultados_api):
            if len(resultados_finais) >= max_results: break
            
            nome_empresa = lugar.get("name", "N/A")
            telefone = lugar.get("phone_number", "")
            site = lugar.get("website", "")
            avaliacao = lugar.get("rating", "")
            num_avaliacoes = lugar.get("review_count", 0)
            
            score = calcular_score_oportunidade(site, avaliacao, num_avaliacoes, telefone)
            link_wa = gerar_link_whatsapp(telefone)
            email_extraido = extrair_email_do_site(site)
            
            resultados_finais.append({
                "Score": score,
                "Nome": nome_empresa,
                "Telefone": telefone,
                "WhatsApp": link_wa,
                "E-mail": email_extraido,
                "Site": site,
                "Avaliação": str(avaliacao),
                "Nº Avaliações": str(num_avaliacoes)
            })
            if progress_callback:
                progress_callback(len(resultados_finais), max_results, "A extrair dados e e-mails...")
                
        # Ordena a lista do melhor lead (maior score) para o pior
        return sorted(resultados_finais, key=lambda x: x["Score"], reverse=True)
    except Exception as e:
        st.error(f"Erro técnico: {e}")
        return []

# --- EXPORTAÇÃO ---
def criar_word(dados, nicho, regiao):
    doc = Document()
    doc.add_heading(f"Relatório Universal: {nicho} em {regiao}", 0)
    for item in dados:
        doc.add_heading(item["Nome"], level=2)
        doc.add_paragraph(f"• Telefone: {item['Telefone']}")
        doc.add_paragraph(f"• E-mail: {item['E-mail']}")
        doc.add_paragraph(f"• Score Comercial: {item['Score']}")
        doc.add_paragraph(f"• Análise Inteligente:\n{item.get('Análise Grok IA', 'Não analisado pela IA')}")
        doc.add_paragraph("-" * 40)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# ---------- INTERFACE PRINCIPAL ----------
st.title("🌍 Motor de Busca B2B e IA Estratégica")
st.markdown("Encontra negócios, extrai contatos e usa a IA do Grok para criar abordagens perfeitas para **qualquer objetivo**.")

# Mostra aviso se as chaves não estiverem no ambiente
if not RAPIDAPI_KEY or not GROK_API_KEY:
    st.sidebar.warning("⚠️ Chaves API não encontradas no sistema (.env ou Secrets).")
    RAPIDAPI_KEY = st.sidebar.text_input("RapidAPI Key", value=RAPIDAPI_KEY, type="password")
    GROK_API_KEY = st.sidebar.text_input("Grok API Key", value=GROK_API_KEY, type="password")

st.divider()

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    nicho = st.text_input("Nicho / Setor", placeholder="Ex: Restaurantes, Clínicas, Lojas")
with col2:
    regiao = st.text_input("Cidade / Região", placeholder="Ex: Maputo, Lisboa")
with col3:
    max_leads = st.number_input("Qtd. Resultados", min_value=5, max_value=50, value=10)

objetivo_busca = st.text_input("🎯 Qual é o teu objetivo com estes contatos?", 
                               placeholder="Ex: Quero vender serviços de gestão de tráfego pago / Quero propor parceria de fornecimento de embalagens / Quero criar websites.")

if st.button("🔍 Iniciar Pesquisa Rápida", type="primary", use_container_width=True):
    if not RAPIDAPI_KEY or not nicho or not regiao or not objetivo_busca:
        st.warning("Preenche as chaves de API, nicho, região e o teu objetivo.")
    else:
        query = f"{nicho} em {regiao}"
        progress_bar = st.progress(0, text="A buscar negócios...")
        def update_progress(current, total, fase):
            progress_bar.progress(min(current / total, 1.0), text=f"{fase}: {current}/{total}")

        with st.spinner("A rastrear empresas na RapidAPI..."):
            resultados = buscar_lugares_rapidapi(query, RAPIDAPI_KEY, max_leads, nicho, regiao, update_progress)

        if resultados:
            st.session_state['resultados_cache'] = resultados
            st.session_state['nicho_cache'] = nicho
            st.session_state['regiao_cache'] = regiao
            st.session_state['objetivo_cache'] = objetivo_busca

# Se já houver resultados em cache
if 'resultados_cache' in st.session_state:
    df = pd.DataFrame(st.session_state['resultados_cache'])
    st.success(f"{len(df)} oportunidades encontradas! Ordenadas por relevância comercial (Score).")
    st.dataframe(df, use_container_width=True)
    
    st.markdown("### 🧠 Modo Premium: Análise com IA (Grok)")
    st.caption("Gera um diagnóstico e uma mensagem de abordagem para os melhores resultados da tabela.")
    
    qtd_analisar = st.slider("Quantas empresas queres que a IA analise agora?", 1, len(df), min(3, len(df)))
    
    if st.button("Gerar Estratégias com Grok IA", type="secondary"):
        with st.spinner("O Grok está a analisar os dados e a criar abordagens..."):
            for i in range(qtd_analisar):
                empresa = st.session_state['resultados_cache'][i]
                resposta_ia = analisar_com_grok(
                    nome=empresa["Nome"], 
                    nicho=st.session_state['nicho_cache'],
                    site=empresa["Site"], 
                    avaliacao=empresa["Avaliação"], 
                    objetivo=st.session_state['objetivo_cache'],
                    api_key=GROK_API_KEY
                )
                st.session_state['resultados_cache'][i]["Análise Grok IA"] = resposta_ia
            
            st.success("Análise concluída!")
            st.rerun() # Atualiza a página para mostrar os novos dados na tabela
            
    # Exportação
    st.divider()
    st.subheader("📥 Exportar Relatório")
    df_atualizado = pd.DataFrame(st.session_state['resultados_cache'])
    
    b1, b2 = st.columns(2)
    with b1:
        csv = df_atualizado.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Baixar Excel (CSV)", data=csv, file_name=f"leads_{st.session_state['nicho_cache']}.csv", mime="text/csv", use_container_width=True)
    with b2:
        word_file = criar_word(st.session_state['resultados_cache'], st.session_state['nicho_cache'], st.session_state['regiao_cache'])
        st.download_button("⬇️ Baixar Word", data=word_file, file_name=f"relatorio_{st.session_state['nicho_cache']}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
