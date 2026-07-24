"""
SCRAPER DE LEADS PREMIUM - APP (RapidAPI + Web Scraping)
-----------------------------------------------------
"""

import streamlit as st
import pandas as pd
import requests
import re
from bs4 import BeautifulSoup

SEARCH_URL = "https://local-business-data.p.rapidapi.com/search"

st.set_page_config(page_title="Scraper Premium de Leads", page_icon="🚀", layout="wide")

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

def buscar_lugares_rapidapi(query: str, api_key: str, max_results: int, nicho: str, regiao: str, progress_callback=None):
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "local-business-data.p.rapidapi.com"
    }
    querystring = {"query": query, "limit": str(max_results), "language": "pt"}
    
    try:
        response = requests.get(SEARCH_URL, headers=headers, params=querystring)
        if response.status_code != 200:
            st.error("Erro na API. Verifica a tua chave.")
            return []
            
        resultados_api = response.json().get("data", [])
        resultados_finais = []
        
        for i, lugar in enumerate(resultados_api):
            if len(resultados_finais) >= max_results:
                break
            
            nome_empresa = lugar.get("name", "N/A")
            telefone = lugar.get("phone_number", "")
            site = lugar.get("website", "")
            
            # Identifica se tem site ou se é uma oportunidade sem site
            status_site = "Tem Site" if site else "⚠️ Precisa de Site (Oportunidade)"
            
            link_wa = gerar_link_whatsapp(telefone)
            email_extraido = extrair_email_do_site(site)
            mensagem_fria = f"Olá, equipa da {nome_empresa}. Vi que são uma referência como {nicho} em {regiao}. Gostaria de apresentar uma proposta rápida."
            
            resultados_finais.append({
                "Nome": nome_empresa,
                "Telefone": telefone,
                "WhatsApp Link": link_wa,
                "E-mail (Extraído)": email_extraido,
                "Status do Site": status_site,
                "Site": site,
                "Avaliação": lugar.get("rating", ""),
                "Nº Avaliações": lugar.get("review_count", 0),
                "Mensagem de Prospecção": mensagem_fria
            })
            
            if progress_callback:
                progress_callback(len(resultados_finais), max_results, "Extraindo dados e e-mails")
                
        return resultados_finais
    except Exception as e:
        st.error(f"Erro técnico: {e}")
        return []

# ---------- INTERFACE ----------

st.title("🚀 Gerador de Oportunidades B2B")
st.markdown("Extraia contatos, **e-mails**, links de WhatsApp e identifique quem precisa de serviços digitais.")

with st.sidebar:
    st.subheader("Configuração")
    api_key = st.text_input("RapidAPI Key", type="password")
    st.divider()
    st.caption("Dica: Podes ordenar ou pesquisar diretamente na tabela de resultados gerada.")

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    nicho = st.text_input("Nicho", placeholder="Ex: advogados")
with col2:
    regiao = st.text_input("Cidade/Região", placeholder="Ex: Maputo")
with col3:
    max_leads = st.number_input("Leads", min_value=5, max_value=50, value=10)

if st.button("Iniciar Varredura Completa", type="primary", use_container_width=True):
    if not api_key or not nicho or not regiao:
        st.warning("Preenche a chave da API, nicho e região.")
    else:
        query = f"{nicho} em {regiao}"
        progress_bar = st.progress(0, text="Iniciando motores...")

        def update_progress(current, total, fase):
            progress_bar.progress(min(current / total, 1.0), text=f"{fase}: {current}/{total}")

        with st.spinner("Buscando empresas e rastreando sites..."):
            resultados = buscar_lugares_rapidapi(query, api_key, max_leads, nicho, regiao, update_progress)

        if resultados:
            df = pd.DataFrame(resultados)

            st.success(f"{len(df)} oportunidades carregadas com sucesso!")
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Baixar Base de Dados (CSV)",
                data=csv,
                file_name=f"oportunidades_{nicho}_{regiao}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.error("Nenhum resultado encontrado. Tenta uma cidade específica.")
        
