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

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "scraper-leads-app/1.0"}

st.set_page_config(page_title="Scraper de Leads", page_icon="🔍", layout="centered")


def geocodificar_regiao(regiao: str):
    params = {"q": regiao, "format": "json", "limit": 1}
    resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS).json()
    if not resp:
        return None
    return float(resp[0]["lat"]), float(resp[0]["lon"])


def buscar_negocios(nicho: str, regiao: str, max_results: int, raio_metros: int = 15000, progress_callback=None):
    coords = geocodificar_regiao(regiao)
    if not coords:
        return []
    lat, lon = coords

    query = f"""
    [out:json][timeout:25];
    (
      node["name"~"{nicho}",i](around:{raio_metros},{lat},{lon});
      node["shop"~"{nicho}",i](around:{raio_metros},{lat},{lon});
      node["amenity"~"{nicho}",i](around:{raio_metros},{lat},{lon});
    );
    out body {max_results};
    """
    resp = requests.post(OVERPASS_URL, data={"data": query}, headers=HEADERS)
    if resp.status_code != 200:
        return []

    elementos = resp.json().get("elements", [])
    resultados = []
    for el in elementos[:max_results]:
        tags = el.get("tags", {})
        nome = tags.get("name")
        if not nome:
            continue
        resultados.append({
            "Nome": nome,
            "Endereço": ", ".join(filter(None, [
                tags.get("addr:street", ""),
                tags.get("addr:housenumber", ""),
                tags.get("addr:city", ""),
            ])) or "",
            "Telefone": tags.get("phone", tags.get("contact:phone", "")),
            "Site": tags.get("website", tags.get("contact:website", "")),
        })
        if progress_callback:
            progress_callback(len(resultados), max_results)
    return resultados


# ---------- INTERFACE ----------

st.title("🔍 Scraper de Leads")
st.caption("Extraia contatos de negócios (OpenStreetMap) por nicho e região — grátis, sem API key.")

col1, col2 = st.columns(2)
with col1:
    nicho = st.text_input("Nicho", placeholder="Ex: restaurante, farmacia, escola")
with col2:
    regiao = st.text_input("Cidade/Região", placeholder="Ex: Maputo")

max_leads = st.slider("Quantidade de leads", min_value=5, max_value=100, value=30, step=5)
st.caption("💡 Use termos genéricos (ex: 'clinica' em vez de 'clinica dentaria') para mais resultados.")

if st.button("Buscar leads", type="primary", use_container_width=True):
    if not nicho or not regiao:
        st.warning("Preenche o nicho e a região primeiro.")
    else:
        progress_bar = st.progress(0, text="Iniciando busca...")

        def update_progress(current, total):
            progress_bar.progress(min(current / total, 1.0), text=f"{current}/{total} encontrados")

        with st.spinner("Buscando no OpenStreetMap..."):
            resultados = buscar_negocios(nicho, regiao, max_leads, progress_callback=update_progress)

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
