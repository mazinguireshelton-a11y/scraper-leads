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
        # Finge ser um navegador real para não ser bloqueado
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        # Timeout curto (3 segundos) para o app não ficar travado se o site estiver fora do ar
        resposta = requests.get(url, headers=headers, timeout=3)
        
        # Expressão regular para encontrar qualquer coisa com formato de e-mail
        emails_encontrados = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", resposta.text))
        
        # Filtra falsos positivos comuns (como extensões de imagens)
        emails_validos = [e for e in emails_encontrados if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
        
        return ", ".join(emails_validos[:2]) # Devolve no máximo 2 e-mails
    except:
        return ""

def gerar_link_whatsapp(telefone):
    if not telefone:
        return ""
    # Remove todos os espaços e traços, deixando só os números
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
            
            # Executa as novas funções de valor agregado
            link_wa = gerar_link_whatsapp(telefone)
            email_extraido = extrair_email_do_site(site)
            mensagem_fria = f"Olá, equipa da {nome_empresa}. Vi que são uma referência como {nicho} em {regiao}. Gostaria de apresentar uma proposta rápida."
            
            resultados_finais.append({
                "Nome": nome_empresa,
                "Telefone": telefone,
                "WhatsApp Link": link_wa,
                "E-mail (Extraído)": email_extraido,
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
st.markdown("Extraia contatos, **e-mails**, links de WhatsApp e crie mensagens de prospecção automaticamente.")

with st.sidebar:
    st.subheader("Configuração")
    api_key = st.text_input("RapidAPI Key", type="password")
    st.divider()
    st.caption("Filtros Avançados pós-busca:")
    mostrar_sem_site = st.checkbox("🔍 Mostrar apenas empresas SEM site")
    mostrar_mal_avaliados = st.checkbox("⭐ Mostrar empresas com avaliação menor que 4.0")

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

        with st.spinner("Buscando empresas e rastreando sites... (Isto pode demorar alguns segundos por causa da busca de e-mails)"):
            resultados = buscar_lugares_rapidapi(query, api_key, max_leads, nicho, regiao, update_progress)

        if resultados:
            df = pd.DataFrame(resultados)
            
            # Aplicação dos Filtros Inteligentes de Negócio
            if mostrar_sem_site:
                df = df[df["Site"] == ""]
            if mostrar_mal_avaliados:
                # Converte para float lidando com valores vazios
                df["Avaliação"] = pd.to_numeric(df["Avaliação"], errors='coerce')
                df = df[df["Avaliação"] < 4.0]

            st.success(f"{len(df)} oportunidades validadas e prontas para prospecção!")
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
            st.error("Nenhum resultado encontrado. Verifica o teu limite na API.")
        
