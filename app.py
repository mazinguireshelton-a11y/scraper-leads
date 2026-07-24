"""
SCRAPER DE LEADS COM PROSPECÇÃO INTELIGENTE E IA DE ABORDAGEM
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

st.set_page_config(page_title="Plataforma de Oportunidades B2B", page_icon="🚀", layout="wide")

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

def gerar_mensagem_inteligente(nome_empresa, site, avaliacao, num_avaliacoes, nicho, regiao):
    """Cria uma abordagem cirúrgica baseada na real necessidade da instituição"""
    
    # Converte avaliação para float se possível
    try:
        nota = float(avaliacao) if avaliacao else 0.0
    except:
        nota = 0.0

    # Cenário 1: Empresa não tem site (Oportunidade de presença digital)
    if not site:
        return (f"Olá, equipa da {nome_empresa}. Analisei o mercado de {nicho} em {regiao} e notei que vocês são uma referência, "
                f"mas ainda não possuem um site profissional estruturado. Hoje, centenas de clientes procuram por {nicho} no Google "
                f"e acabam por ir para a concorrência por falta de um canal digital direto. Gostariam de conversar sobre como podemos mudar isso?")
    
    # Cenário 2: Tem site, mas tem poucas avaliações ou nota baixa (Oportunidade de reputação)
    elif nota > 0 and nota < 4.0:
        return (f"Olá, equipa da {nome_empresa}. Estava a ver os registos de {nicho} em {regiao} e reparei que o vosso negócio tem um potencial enorme, "
                f"mas a vossa nota de avaliações no Google ({nota} estrelas) pode estar a fazer-vos perder clientes valiosos. "
                f"Podemos ajudar a otimizar a vossa presença e reputação digital. Têm 5 minutos esta semana?")
    
    # Cenário 3: Empresa estruturada (Oportunidade de escala / tráfego avançado)
    else:
        return (f"Olá, equipa da {nome_empresa}! Acompanho o vosso trabalho como {nicho} em {regiao} e vejo que já têm uma base sólida e um site excelente. "
                f"O nosso foco é ajudar empresas consolidadas como a vossa a escalar ainda mais o volume de clientes através de estratégias digitais avançadas. "
                f"Faz sentido alinharmos uma breve conversa?")

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
            avaliacao = lugar.get("rating", "")
            num_avaliacoes = lugar.get("review_count", 0)
            
            status_site = "Tem Site" if site else "⚠️ Precisa de Site (Oportunidade)"
            link_wa = gerar_link_whatsapp(telefone)
            email_extraido = extrair_email_do_site(site)
            
            # Gera a mensagem inteligente baseada nos dados reais da empresa
            mensagem_personalizada = gerar_mensagem_inteligente(nome_empresa, site, avaliacao, num_avaliacoes, nicho, regiao)
            
            resultados_finais.append({
                "Nome": nome_empresa,
                "Telefone": telefone,
                "WhatsApp Link": link_wa,
                "E-mail (Extraído)": email_extraido,
                "Status do Site": status_site,
                "Site": site,
                "Avaliação": str(avaliacao),
                "Nº Avaliações": str(num_avaliacoes),
                "Mensagem Inteligente de Abordagem": mensagem_personalizada
            })
            
            if progress_callback:
                progress_callback(len(resultados_finais), max_results, "Analisando necessidades e e-mails")
                
        return resultados_finais
    except Exception as e:
        st.error(f"Erro técnico: {e}")
        return []

def criar_word(dados, nicho, regiao):
    doc = Document()
    doc.add_heading(f"Relatório de Prospecção: {nicho} em {regiao}", 0)
    doc.add_paragraph("Gerado automaticamente pela plataforma B2B.\n")
    
    for item in dados:
        doc.add_heading(item["Nome"], level=2)
        doc.add_paragraph(f"• Telefone: {item['Telefone']}")
        doc.add_paragraph(f"• E-mail: {item['E-mail (Extraído)'] or 'Não encontrado'}")
        doc.add_paragraph(f"• Status: {item['Status do Site']}")
        doc.add_paragraph(f"• Abordagem Personalizada:\n{item['Mensagem Inteligente de Abordagem']}")
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
    
    elementos.append(Paragraph(f"Relatório Inteligente: {limpar_para_pdf(nicho)} ({limpar_para_pdf(regiao)})", titulo_estilo))
    elementos.append(Spacer(1, 12))
    
    tabela_dados = [["Nome", "Telefone", "Status", "Abordagem Sugerida"]]
    for item in dados:
        tabela_dados.append([
            Paragraph(limpar_para_pdf(item["Nome"]), styles['Normal']),
            Paragraph(limpar_para_pdf(item["Telefone"]), styles['Normal']),
            Paragraph(limpar_para_pdf(item["Status do Site"]), styles['Normal']),
            Paragraph(limpar_para_pdf(item["Mensagem Inteligente de Abordagem"]), styles['Normal'])
        ])
        
    tabela = Table(tabela_dados, colWidths=[110, 80, 110, 200])
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

st.title("🚀 Plataforma Global de Prospecção B2B")
st.markdown("Gere relatórios inteligentes com diagnósticos reais e abordagens personalizadas para qualquer negócio no mundo.")

with st.sidebar:
    st.subheader("Configuração")
    api_key = st.text_input("RapidAPI Key", type="password")

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    nicho = st.text_input("Nicho", placeholder="Ex: clínicas, farmácias, advogados")
with col2:
    regiao = st.text_input("Cidade/Região", placeholder="Ex: Maputo, Lisboa, Luanda")
with col3:
    max_leads = st.number_input("Leads", min_value=5, max_value=50, value=10)

if st.button("Iniciar Análise de Mercado", type="primary", use_container_width=True):
    if not api_key or not nicho or not regiao:
        st.warning("Preenche a chave da API, nicho e região.")
    else:
        query = f"{nicho} em {regiao}"
        progress_bar = st.progress(0, text="Iniciando motores de inteligência...")

        def update_progress(current, total, fase):
            progress_bar.progress(min(current / total, 1.0), text=f"{fase}: {current}/{total}")

        with st.spinner("Analisando empresas e gerando estratégias de abordagem..."):
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
    st.success(f"{len(df)} oportunidades analisadas com sucesso!")
    st.dataframe(df, use_container_width=True)

    st.subheader("📥 Exportar Relatório Estratégico:")
    b1, b2, b3 = st.columns(3)
    
    with b1:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Baixar CSV", data=csv, file_name=f"prospeccao_{nicho_atual}_{regiao_atual}.csv", mime="text/csv", use_container_width=True)
        
    with b2:
        word_file = criar_word(resultados, nicho_atual, regiao_atual)
        st.download_button("⬇️ Baixar Word (.docx)", data=word_file, file_name=f"relatorio_estrategico_{nicho_atual}_{regiao_atual}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
        
    with b3:
        pdf_file = criar_pdf(resultados, nicho_atual, regiao_atual)
        st.download_button("⬇️ Baixar PDF (.pdf)", data=pdf_file, file_name=f"relatorio_estrategico_{nicho_atual}_{regiao_atual}.pdf", mime="application/pdf", use_container_width=True)
    
