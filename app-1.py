"""
SCRAPER DE LEADS - APP (versão Termux / Places API)
-----------------------------------------------------
Interface web + motor Places API (sem Playwright, sem browser).

SETUP NO TERMUX:
    pkg update && pkg install python -y
    pip install streamlit requests pandas

RODAR:
    streamlit run app.py
    (abre em localhost:8501 - acessa pelo navegador do Android)

PRECISA:
    Uma API Key do Google Places (console.cloud.google.com -> ativar Places API)

DEPLOY GRÁTIS (pra cliente self-service):
    1. Sobe pro GitHub
    2. share.streamlit.io -> conecta o repo -> deploy
    3. Configura a API_KEY como "Secret" no Streamlit Cloud (nunca deixa hardcoded no código)

MODELO DE NEGÓCIO:
    - Free: 20 leads/dia, com teu branding
    - Pago: $15-30/mês por cliente, acesso ilimitado (SaaS recorrente)
"""

import streamlit as st
import pandas as pd
import requests
import time

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

st.set_page_config(page_title="Scraper de Leads", page_icon="🔍", layout="centered")


def buscar_lugares(query: str, api_key: str, max_results: int, progress_callback=None):
    resultados = []
    params = {"query": query, "key": api_key}

    while len(resultados) < max_results:
        resp = requests.get(TEXT_SEARCH_URL, params=params).json()

        if resp.get("status") not in ("OK", "ZERO_RESULTS"):
            st.error(f"Erro na API: {resp.get('status')} - {resp.get('error_message', '')}")
            break

        for lugar in resp.get("results", []):
            if len(resultados) >= max_results:
                break
            resultados.append({
                "place_id": lugar.get("place_id"),
                "Nome": lugar.get("name"),
                "Endereço": lugar.get("formatted_address"),
                "Avaliação": lugar.get("rating", ""),
                "Nº Avaliações": lugar.get("user_ratings_total", ""),
            })
            if progress_callback:
                progress_callback(len(resultados), max_results, "buscando")

        next_token = resp.get("next_page_token")
        if not next_token:
            break
        time.sleep(2)
        params = {"pagetoken": next_token, "key": api_key}

    return resultados


def enriquecer(resultados, api_key: str, progress_callback=None):
    total = len(resultados)
    for i, item in enumerate(resultados):
        params = {
            "place_id": item["place_id"],
            "fields": "formatted_phone_number,website",
            "key": api_key,
        }
        resp = requests.get(DETAILS_URL, params=params).json()
        detalhes = resp.get("result", {})
        item["Telefone"] = detalhes.get("formatted_phone_number", "")
        item["Site"] = detalhes.get("website", "")
        if progress_callback:
            progress_callback(i + 1, total, "enriquecendo")
    return resultados


# ---------- INTERFACE ----------

st.title("🔍 Scraper de Leads")
st.caption("Extraia contatos de negócios (Google Places) por nicho e região.")

with st.sidebar:
    st.subheader("Configuração")
    api_key = st.text_input("Google Places API Key", type="password", help="console.cloud.google.com -> Places API")
    st.caption("A chave não é salva — só usada durante essa sessão.")

col1, col2 = st.columns(2)
with col1:
    nicho = st.text_input("Nicho", placeholder="Ex: clínicas dentárias")
with col2:
    regiao = st.text_input("Cidade/Região", placeholder="Ex: Maputo")

max_leads = st.slider("Quantidade de leads", min_value=5, max_value=100, value=30, step=5)

if st.button("Buscar leads", type="primary", use_container_width=True):
    if not api_key:
        st.warning("Cola a tua API Key na barra lateral primeiro.")
    elif not nicho or not regiao:
        st.warning("Preenche o nicho e a região primeiro.")
    else:
        query = f"{nicho} em {regiao}"
        progress_bar = st.progress(0, text="Iniciando busca...")

        def update_progress(current, total, fase):
            label = "Buscando lugares" if fase == "buscando" else "Coletando telefone/site"
            progress_bar.progress(min(current / total, 1.0), text=f"{label}: {current}/{total}")

        with st.spinner("Trabalhando..."):
            resultados = buscar_lugares(query, api_key, max_leads, update_progress)
            if resultados:
                resultados = enriquecer(resultados, api_key, update_progress)

        if resultados:
            df = pd.DataFrame(resultados).drop(columns=["place_id"])
            st.success(f"{len(df)} leads encontrados!")
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Baixar CSV",
                data=csv,
                file_name=f"leads_{nicho.replace(' ', '_')}_{regiao.replace(' ', '_')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.error("Nenhum resultado encontrado. Tenta um nicho ou região diferente.")

st.divider()
st.caption("💼 Precisa de leads verificados ou volume maior? Entre em contato.")
