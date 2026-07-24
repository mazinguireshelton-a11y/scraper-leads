"""
SCRAPER DE LEADS - APP (versão RapidAPI - Sem Cartão de Crédito)
-----------------------------------------------------
"""

import streamlit as st
import pandas as pd
import requests

# Novo URL da API "Local Business Data"
SEARCH_URL = "https://local-business-data.p.rapidapi.com/search"

st.set_page_config(page_title="Scraper de Leads (RapidAPI)", page_icon="🔍", layout="centered")

def buscar_lugares_rapidapi(query: str, api_key: str, max_results: int, progress_callback=None):
    # Configuração dos cabeçalhos exigidos pelo RapidAPI
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "local-business-data.p.rapidapi.com"
    }
    
    # Parâmetros da busca (query, limite de resultados e idioma)
    querystring = {
        "query": query, 
        "limit": str(max_results), 
        "language": "pt"
    }
    
    try:
        response = requests.get(SEARCH_URL, headers=headers, params=querystring)
        
        if response.status_code != 200:
            st.error(f"Erro na API: {response.status_code} - Verifica a tua API Key do RapidAPI.")
            return []
            
        dados = response.json()
        
        # A API devolve os resultados dentro de uma lista chamada 'data'
        resultados_api = dados.get("data", [])
        resultados_finais = []
        
        for i, lugar in enumerate(resultados_api):
            if len(resultados_finais) >= max_results:
                break
            
            # Extrair os dados (usando .get para evitar erros se o dado não existir)
            resultados_finais.append({
                "Nome": lugar.get("name", "N/A"),
                "Telefone": lugar.get("phone_number", ""),
                "Endereço": lugar.get("full_address", ""),
                "Site": lugar.get("website", ""),
                "Avaliação": lugar.get("rating", ""),
                "Nº Avaliações": lugar.get("review_count", "")
            })
            
            if progress_callback:
                progress_callback(len(resultados_finais), max_results, "buscando e coletando telefones")
                
        return resultados_finais
        
    except Exception as e:
        st.error(f"Ocorreu um erro técnico: {e}")
        return []

# ---------- INTERFACE ----------

st.title("🔍 Scraper de Leads (RapidAPI)")
st.caption("Extraia contatos e telefones de negócios (via RapidAPI).")

with st.sidebar:
    st.subheader("Configuração")
    api_key = st.text_input("RapidAPI Key", type="password", help="Cola aqui a tua chave (começa com c3d8...)")
    st.caption("A chave não é salva — só usada durante essa sessão.")

col1, col2 = st.columns(2)
with col1:
    nicho = st.text_input("Nicho", placeholder="Ex: advogados")
with col2:
    regiao = st.text_input("Cidade/Região", placeholder="Ex: Maputo")

max_leads = st.slider("Quantidade de leads", min_value=5, max_value=50, value=20, step=5)

if st.button("Buscar leads", type="primary", use_container_width=True):
    if not api_key:
        st.warning("Cola a tua API Key na barra lateral primeiro.")
    elif not nicho or not regiao:
        st.warning("Preenche o nicho e a região primeiro.")
    else:
        query = f"{nicho} em {regiao}"
        progress_bar = st.progress(0, text="Iniciando busca...")

        def update_progress(current, total, fase):
            progress_bar.progress(min(current / total, 1.0), text=f"{fase}: {current}/{total}")

        with st.spinner("Buscando empresas e telefones..."):
            resultados = buscar_lugares_rapidapi(query, api_key, max_leads, update_progress)

        if resultados:
            df = pd.DataFrame(resultados)
            st.success(f"{len(df)} leads encontrados!")
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Baixar CSV (Excel)",
                data=csv,
                file_name=f"leads_{nicho.replace(' ', '_')}_{regiao.replace(' ', '_')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.error("Nenhum resultado encontrado ou o limite gratuito da API acabou.")
        
