import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime
import requests
from io import StringIO

# 1. DICIONÁRIO DE TRADUÇÃO GLOBAL
# Configurado para alternar siglas técnicas conforme o idioma (RVI/THI vs VP/AM)
LANGUAGES = {
    'EN': {
        'page_title': "Flood Risk Diagrams - Recife",
        'sidebar_header': "Analysis Filters",
        'start_date': "Select start date",
        'end_date': "Select end date",
        'select_stations': "Select Stations",
        'btn_explore': "Explore Risk Diagrams",
        'error_date': "The start date cannot be later than the end date.",
        'error_station': "Please select at least one station.",
        'analysis_header': "Risk Analysis",
        'no_data': "No risk points were found for the selected period and stations.",
        'success': "Analysis complete! Displaying {} diagram(s).",
        'initial_info': "Select the filters in the sidebar and click 'Explore Risk Diagrams' to start the analysis.",
        'chart_header': "Generated Risk Diagrams",
        'diag_title': "Risk Diagram",
        'xaxis': 'Rainfall Volume Index (RVI)',
        'yaxis': 'Tidal Height Index (THI)',
        'legend_title': '<b>Risk Levels</b>',
        'hover_time': 'Time',
        'hover_risk': 'Risk',
        'label_rvi': 'RVI',
        'label_thi': 'THI',
        'riscos': {'Baixo': 'Low', 'Moderado': 'Moderate', 'Moderado Alto': 'High-Moderate', 'Alto': 'High'},
        'def_riscos': {'Low': 'Risk < 30', 'Moderate': '30 ≤ Risk < 50', 'High-Moderate': '50 ≤ Risk < 100', 'High': 'Risk ≥ 100'}
    },
    'PT': {
        'page_title': "Diagramas de Risco de Inundação - Recife",
        'sidebar_header': "Filtros de Análise",
        'start_date': "Data de início",
        'end_date': "Data de fim",
        'select_stations': "Selecionar Estações",
        'btn_explore': "Explorar Diagramas de Risco",
        'error_date': "A data de início não pode ser posterior à data de término.",
        'error_station': "Por favor, selecione pelo menos uma estação.",
        'analysis_header': "Análise de Risco",
        'no_data': "Nenhum ponto de risco encontrado para o período e estações selecionados.",
        'success': "Análise concluída! Exibindo {} diagrama(s).",
        'initial_info': "Selecione os filtros na barra lateral e clique em 'Explorar Diagramas de Risco' para começar.",
        'chart_header': "Diagramas de Risco Gerados",
        'diag_title': "Diagrama de Risco",
        'xaxis': 'Volume de Precipitação (VP)',
        'yaxis': 'Altura da Maré (AM)',
        'legend_title': '<b>Níveis de Risco</b>',
        'hover_time': 'Hora',
        'hover_risk': 'Risco',
        'label_rvi': 'VP',
        'label_thi': 'AM',
        'riscos': {'Baixo': 'Baixo', 'Moderado': 'Moderado', 'Moderado Alto': 'Moderado Alto', 'Alto': 'Alto'},
        'def_riscos': {'Baixo': 'Risco < 30', 'Moderado': '30 ≤ Risco < 50', 'Moderado Alto': '50 ≤ Risco < 100', 'Alto': 'Risco ≥ 100'}
    }
}

# 2. FUNÇÃO DE CARREGAMENTO COM CORREÇÃO DE NOMES (TORREÃO/DOIS IRMÃOS)
@st.cache_data(show_spinner=False, ttl=86400)
def carregar_dados():
    url = 'https://raw.githubusercontent.com/RafaellaB/Painel-Diagrama-de-Risco/main/resultado_risco_final.csv'
    try:
        response = requests.get(url)
        content = response.content.decode('utf-8-sig') 
        df = pd.read_csv(StringIO(content))
        
        # Limpeza de caracteres especiais para evitar duplicatas erradas
        if 'nomeEstacao' in df.columns:
            df['nomeEstacao'] = df['nomeEstacao'].str.replace('TorreÃ£o', 'Torreão').str.replace('Dois IrmÃ£os', 'Dois Irmãos')
            
        df['data'] = pd.to_datetime(df['data']).dt.date
        return df
    except Exception as e:
        st.error(f"Erro ao carregar CSV: {e}")
        return pd.DataFrame()

# 3. FUNÇÃO PARA GERAR OS DIAGRAMAS (PLOTLY)
def gerar_diagramas(df_analisado, t):
    st.header(t['chart_header'])
    mapa_de_cores = {'Alto': '#D32F2F', 'Moderado Alto': '#FFA500', 'Moderado': '#FFC107', 'Baixo': '#4CAF50'}
    
    for (data, estacao), grupo in df_analisado.groupby(['data', 'nomeEstacao']):
        if grupo.empty: continue
        
        st.subheader(f"{t['diag_title']}: {estacao} - {pd.to_datetime(data).strftime('%Y-%m-%d')}")
        fig = go.Figure()

        lim_x = max(110, grupo['VP'].max() * 1.2)
        lim_y = max(5, grupo['AM'].max() * 1.2)
        
        x_grid = np.arange(0, lim_x, 1)
        y_grid = np.linspace(0, lim_y, 100)
        z_grid = np.array([x * y for y in y_grid for x in x_grid]).reshape(len(y_grid), len(x_grid))
        
        fig.add_trace(go.Heatmap(
            x=x_grid, y=y_grid, z=z_grid, 
            colorscale=[[0.0, "#4CAF50"], [0.3, "#FFC107"], [0.5, "#FFA500"], [1.0, "#D32F2F"]], 
            showscale=False, zmin=0, zmax=100, hoverinfo='none'
        ))
        
        grupo = grupo.sort_values(by='hora_ref')
        fig.add_trace(go.Scatter(
            x=grupo['VP'], y=grupo['AM'], mode='lines', 
            line=dict(color='black', width=1.5, dash='dash'), 
            hoverinfo='none', showlegend=False
        ))
        
        for _, ponto in grupo.iterrows():
            cor_ponto = mapa_de_cores.get(ponto['Classificacao_Risco'], 'black')
            status_traduzido = t['riscos'].get(ponto['Classificacao_Risco'], ponto['Classificacao_Risco'])
            
            # Balão de informação (Hover) corrigido com siglas dinâmicas
            fig.add_trace(go.Scatter(
                x=[ponto['VP']], y=[ponto['AM']], mode='markers', 
                marker=dict(color=cor_ponto, size=12, line=dict(width=1, color='black')), 
                hoverinfo='text', 
                hovertext=(
                    f"<b>{t['hover_time']}:</b> {ponto['hora_ref']}<br>"
                    f"<b>{t['hover_risk']}:</b> {status_traduzido}<br>"
                    f"<b>{t['label_rvi']}:</b> {ponto['VP']}<br>"
                    f"<b>{t['label_thi']}:</b> {ponto['AM']}"
                ),
                showlegend=False
            ))
        
        for risco_pt, risco_traduzido in t['riscos'].items():
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode='markers', 
                marker=dict(color=mapa_de_cores[risco_pt], size=10, symbol='square'), 
                name=f"<b>{risco_traduzido}</b>: {t['def_riscos'][risco_traduzido]}"
            ))
        
        fig.update_layout(
            xaxis_title=t['xaxis'], 
            yaxis_title=t['yaxis'], 
            showlegend=True, 
            legend_title_text=t['legend_title'],
            margin=dict(l=40, r=40, t=40, b=40)
        )
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{data}_{estacao}")

# --- APP PRINCIPAL ---
def main():
    st.set_page_config(page_title="Risco Recife", layout="wide")

    lang_choice = st.sidebar.radio("Language / Idioma", ["EN", "PT"], horizontal=True)
    t = LANGUAGES[lang_choice]

    st.title(t['page_title'])

    try:
        df_analisado = carregar_dados()
        if df_analisado.empty:
            return

        # Restrição de calendário para os anos de interesse (2025 em diante)
        data_minima = df_analisado['data'].min()
        data_maxima = df_analisado['data'].max()

        st.sidebar.header(t['sidebar_header'])
        
        data_inicio = st.sidebar.date_input(t['start_date'], value=data_minima, min_value=data_minima, max_value=data_maxima)
        data_fim = st.sidebar.date_input(t['end_date'], value=data_maxima, min_value=data_minima, max_value=data_maxima)
        
        estacoes_disponiveis = sorted(df_analisado['nomeEstacao'].unique().tolist())
        estacoes_selecionadas = st.sidebar.multiselect(t['select_stations'], options=estacoes_disponiveis, default=estacoes_disponiveis)

        if st.sidebar.button(t['btn_explore'], type="primary"):
            if data_inicio > data_fim:
                st.error(t['error_date'])
            elif not estacoes_selecionadas:
                st.error(t['error_station'])
            else:
                df_filtrado = df_analisado[
                    (df_analisado['data'] >= data_inicio) & 
                    (df_analisado['data'] <= data_fim) &
                    (df_analisado['nomeEstacao'].isin(estacoes_selecionadas))
                ]
                
                st.header(f"{t['analysis_header']}: {data_inicio} to {data_fim}")

                if df_filtrado.empty:
                    st.info(t['no_data'])
                else:
                    num_diags = len(df_filtrado.groupby(['data', 'nomeEstacao']))
                    st.success(t['success'].format(num_diags))
                    gerar_diagramas(df_filtrado, t)
        else:
            st.info(t['initial_info'])

    except Exception as e:
        st.error(f"Erro inesperado: {e}")

if __name__ == "__main__":
    main()