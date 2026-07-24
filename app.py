"""
SCRAPER DE LEADS PREMIUM - APP (RapidAPI + Exportação PDF/Word corrigida)
-----------------------------------------------------
"""

import streamlit as st
import pandas as pd
import requests
import re
from io import BytesIO
from bs4 import BeautifulSoup

from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

SEARCH_URL = "https://local-business-data.p.rapidapi.com/search"

st.set_page_config(page_title="Scraper Premium de Leads", page_icon="🚀", layout="wide")

def limpar_para_pdf(texto):
    """Remove caracteres que possam quebrar a geração do PDF"""
    if not texto:
        return ""
    # Substitui caracteres especiais problemáticos por texto seguro
    texto_limpo = str(texto).replace("&", "e").replace("<", "").replace(">", "")
    return texto_limpo

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
            status_site = "Tem Site" if site else "Precisa de Site (Oportunidade)"
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
                "Avaliação": str(lugar.get("rating", "")),
                "Nº Avaliações": str(lugar.get("review_count", 0)),
                "Mensagem de Prospecção": mensagem_fria
            })
            
            if progress_callback:
                progress_callback(len(resultados_finais), max_results, "Extraindo dados e e-mails")
                
        return resultados_finais
    except Exception as e:
        st.error(f"Erro técnico: {e}")
        return []

def criar_word(dados, nicho, regiao):
    doc = Document()
    doc.add_heading(f"Relatório de Oportunidades: {nicho} em {regiao}", 0)
    doc.add_paragraph("Gerado automaticamente pelo Scraper de Leads B2B.\n")
    
    for item in dados:
        doc.add_heading(item["Nome"], level=2)
        doc.add_paragraph(f"• Telefone: {item['Telefone']}")
        doc.add_paragraph(f"• E-mail: {item['E-mail (Extraído)'] or 'Não encontrado'}")
        doc.add_paragraph(f"• Status do Site: {item['Status do Site']}")
        doc.add_paragraph(f"• Site: {item['Site'] or 'N/A'}")
        doc.add_paragraph(f"• Sugestão de Abordagem: {item['Mensagem de Prospecção']}")
        doc.add_paragraph("-" * 40)
        
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def criar_pdf(dados, nicho, regiao):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elementos = []
    
    styles = getSampleStyleSheet()
    titulo_estilo = ParagraphStyle('TituloCustom', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor("#1f77b4"))
    
    elementos.append(Paragraph(f"Relatório de Leads: {limpar_para_pdf(nicho)} ({limpar_para_pdf(regiao)})", titulo_estilo))
    elementos.append(Spacer(1, 12))
    
    tabela_dados = [["Nome", "Telefone", "E-mail", "Status do Site"]]
    for item in dados:
        tabela_dados.append([
            Paragraph(limpar_para_pdf(item["Nome"]), styles['Normal']),
            Paragraph(limpar_para_pdf(item["Telefone"]), styles['Normal']),
            Paragraph(limpar_para_pdf(item["E-mail (Extraído)"] or "N/A"), styles['Normal']),
            Paragraph(limpar_para_pdf(item["Status do Site"]), styles['Normal'])
        ])
        
    tabela = Table(tabela_dados, colWidths=[130, 90, 140, 140])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1f77b4")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f9f9f9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    
    elementos.append(tabela)
    doc.build(elementos)
    buffer.seek(0)
    return buffer

# ---------- INTERFACE ----------

st.title("🚀 Gerador de Oportunidades B2B")
st.markdown("Extraia contatos, **e-mails**, links de WhatsApp e exporte os seus relatórios em diferentes formatos.")

with st.sidebar:
    st.subheader("Configuração")
    api_key = st.text_input("RapidAPI Key", type="password")

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
            st.session_state['resultados_cache'] = resultados
            st.session_state['nicho_cache'] = nicho
            st.session_state['regiao_cache'] = regiao

if 'resultados_cache' in st.session_state:
    resultados = st.session_state['resultados_cache']
    nicho_atual = st.session_state['nicho_cache']
    regiao_atual = st.session_state['regiao_cache']
    
    df = pd.DataFrame(resultados)
    st.success(f"{len(df)} oportunidades carregadas com sucesso!")
    st.dataframe(df, use_container_width=True)

    st.subheader("📥 Escolha o formato para baixar o relatório:")
    b1, b2, b3 = st.columns(3)
    
    with b1:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Baixar CSV (Excel)", data=csv, file_name=f"leads_{nicho_atual}_{regiao_atual}.csv", mime="text/csv", use_container_width=True)
        
    with b2:
        word_file = criar_word(resultados, nicho_atual, regiao_atual)
        st.download_button("⬇️ Baixar Word (.docx)", data=word_file, file_name=f"relatorio_{nicho_atual}_{regiao_atual}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
        
    with b3:
        pdf_file = criar_pdf(resultados, nicho_atual, regiao_atual)
        st.download_button("⬇️ Baixar PDF (.pdf)", data=pdf_file, file_name=f"relatorio_{nicho_atual}_{regiao_atual}.pdf", mime="application/pdf", use_container_width=True)
        
