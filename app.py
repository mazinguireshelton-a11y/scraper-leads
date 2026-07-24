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
    GMAIL_ENDERECO = st.secrets.get("GMAIL_ENDERECO", os.getenv("GMAIL_ENDERECO", ""))
    GMAIL_APP_PASSWORD = st.secrets.get("GMAIL_APP_PASSWORD", os.getenv("GMAIL_APP_PASSWORD", ""))
except Exception:
    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    GMAIL_ENDERECO = os.getenv("GMAIL_ENDERECO", "")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

SEARCH_URL = "https://local-business-data.p.rapidapi.com/search"
# URL CORRETO DO OPENROUTER
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# --- CONTROLE DE ACESSO POR CLIENTE ---
# Configura os clientes em .streamlit/secrets.toml (local) ou em
# "Settings > Secrets" no Streamlit Cloud, neste formato:
#
# [clientes]
# chave123 = { nome = "Cliente A", limite_diario = 20 }
# chave456 = { nome = "Cliente B", limite_diario = 50 }
#
import json
from datetime import date

ARQUIVO_USO = "uso_diario.json"

def carregar_clientes():
    try:
        return dict(st.secrets.get("clientes", {}))
    except Exception:
        return {}

def carregar_uso():
    if os.path.exists(ARQUIVO_USO):
        try:
            with open(ARQUIVO_USO, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_uso(dados):
    try:
        with open(ARQUIVO_USO, "w") as f:
            json.dump(dados, f)
    except Exception:
        pass  # não trava o app se não conseguir gravar (ex: filesystem read-only)

def verificar_e_registrar_uso(chave):
    """Retorna (permitido: bool, mensagem: str)."""
    uso = carregar_uso()
    hoje = str(date.today())
    registro = uso.get(chave, {"data": hoje, "contagem": 0})

    if registro["data"] != hoje:
        registro = {"data": hoje, "contagem": 0}

    clientes = carregar_clientes()
    limite = clientes.get(chave, {}).get("limite_diario", 10)

    if registro["contagem"] >= limite:
        return False, f"Limite diário de {limite} buscas atingido. Volta amanhã ou fala com o suporte."

    registro["contagem"] += 1
    uso[chave] = registro
    salvar_uso(uso)
    restantes = limite - registro["contagem"]
    return True, f"{restantes} buscas restantes hoje."

def tela_login():
    st.title("🔐 Acesso Restrito")
    st.caption("Este é um serviço pago. Insere a tua chave de acesso.")
    chave_input = st.text_input("Chave de acesso", type="password")
    if st.button("Entrar", type="primary"):
        clientes = carregar_clientes()
        if chave_input in clientes:
            st.session_state["autenticado"] = True
            st.session_state["chave_cliente"] = chave_input
            st.session_state["nome_cliente"] = clientes[chave_input].get("nome", "Cliente")
            st.rerun()
        else:
            st.error("Chave inválida. Confirma com quem te vendeu o acesso.")
    st.stop()

if "autenticado" not in st.session_state:
    tela_login()

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

def gerar_link_whatsapp(telefone, mensagem=""):
    if not telefone: return ""
    num = re.sub(r'\D', '', str(telefone))
    if not num: return ""
    if mensagem:
        from urllib.parse import quote
        return f"https://wa.me/{num}?text={quote(mensagem)}"
    return f"https://wa.me/{num}"

def extrair_mensagem_da_analise(analise_ia):
    """Puxa só a parte 'MENSAGEM' da resposta da IA, sem o rótulo nem o rodapé do modelo."""
    if not analise_ia:
        return ""
    match = re.search(r"MENSAGEM:?\s*(.+?)(?:\n\n_\(modelo|\Z)", analise_ia, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else analise_ia.split("_(modelo")[0].strip()

def enviar_email_gmail(remetente, senha_app, destinatario, assunto, corpo):
    """Envia e-mail via Gmail SMTP usando uma Senha de App (não a senha normal da conta)."""
    import smtplib
    from email.mime.text import MIMEText

    if not remetente or not senha_app:
        return False, "Configura o Gmail (endereço + Senha de App) na barra lateral primeiro."
    if not destinatario:
        return False, "Este lead não tem e-mail encontrado."

    msg = MIMEText(corpo)
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as servidor:
            servidor.login(remetente, senha_app)
            servidor.sendmail(remetente, [destinatario], msg.as_string())
        return True, "E-mail enviado!"
    except smtplib.SMTPAuthenticationError:
        return False, "Falha na autenticação — confirma que é uma Senha de App (16 caracteres), não a senha normal."
    except Exception as e:
        return False, f"Erro ao enviar: {e}"

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
                texto = dados['choices'][0]['message']['content'].strip()
                modelo_real = dados.get('model', modelo)  # o OpenRouter informa qual modelo respondeu de fato
                return f"{texto}\n\n_(modelo: {modelo_real})_"
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
col_titulo, col_user = st.columns([4, 1])
with col_titulo:
    st.title("🚀 Plataforma de Prospeção Inteligente")
with col_user:
    st.caption(f"👤 {st.session_state.get('nome_cliente', '')}")
    if st.button("Sair"):
        st.session_state.clear()
        st.rerun()

st.markdown("Encontra oportunidades de negócio e utiliza IA para gerar propostas comerciais adaptadas ao teu objetivo.")

if not RAPIDAPI_KEY or not OPENROUTER_API_KEY:
    with st.sidebar:
        st.warning("⚠️ Chaves API necessárias")
        RAPIDAPI_KEY = st.text_input("RapidAPI Key", value=RAPIDAPI_KEY, type="password")
        OPENROUTER_API_KEY = st.text_input("OpenRouter API Key", value=OPENROUTER_API_KEY, type="password")
        st.markdown("[Criar conta OpenRouter Grátis](https://openrouter.ai/)")

with st.sidebar:
    st.divider()
    st.subheader("📧 Envio por Gmail")
    GMAIL_ENDERECO = st.text_input("Teu Gmail", value=GMAIL_ENDERECO, placeholder="tuemail@gmail.com")
    GMAIL_APP_PASSWORD = st.text_input("Senha de App do Gmail", value=GMAIL_APP_PASSWORD, type="password",
                                        help="Não é a senha normal! Gera em: myaccount.google.com → Segurança → Senhas de app (precisa de verificação em 2 etapas ativada)")
    st.caption("As credenciais não são salvas — só usadas durante essa sessão.")

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
        permitido, msg_uso = verificar_e_registrar_uso(st.session_state["chave_cliente"])
        if not permitido:
            st.error(msg_uso)
        else:
            st.info(f"✅ {msg_uso}")
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

    # --- AÇÕES POR EMPRESA: enviar e-mail direto ou abrir WhatsApp com a mensagem da IA pronta ---
    leads_com_analise = [l for l in st.session_state['leads'] if l.get("Análise IA")]
    if leads_com_analise:
        st.divider()
        st.subheader("📤 Enviar Propostas")
        st.caption("E-mail é enviado direto pelo app. WhatsApp abre com a mensagem já preenchida — só falta tocar em Enviar (isso evita bloqueio da tua conta por envio automático em massa).")

        for idx, empresa in enumerate(st.session_state['leads']):
            if not empresa.get("Análise IA"):
                continue
            mensagem = extrair_mensagem_da_analise(empresa["Análise IA"])
            with st.expander(f"{empresa['Nome']} (Score: {empresa['Score']})"):
                st.markdown(empresa["Análise IA"])
                st.text_area("Mensagem que será usada", value=mensagem, key=f"msg_{idx}", height=80)

                colA, colB = st.columns(2)

                # E-mail
                email_destino = empresa.get("E-mail", "")
                with colA:
                    if email_destino:
                        if st.button(f"📧 Enviar E-mail", key=f"email_{idx}", use_container_width=True):
                            ok, texto_status = enviar_email_gmail(
                                GMAIL_ENDERECO, GMAIL_APP_PASSWORD, email_destino,
                                assunto=f"Proposta para {empresa['Nome']}",
                                corpo=st.session_state.get(f"msg_{idx}", mensagem)
                            )
                            st.success(texto_status) if ok else st.error(texto_status)
                    else:
                        st.caption("Sem e-mail encontrado")

                # WhatsApp
                with colB:
                    link_wa = gerar_link_whatsapp(empresa.get("Telefone", ""), st.session_state.get(f"msg_{idx}", mensagem))
                    if link_wa:
                        st.link_button("💬 Abrir WhatsApp", link_wa, use_container_width=True)
                    else:
                        st.caption("Sem telefone válido")

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
                    
