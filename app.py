import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime

# ==============================================================================
# FUNÇÃO PARA GERAR OS DIAGRAMAS (Sem alterações)
# ==============================================================================
def gerar_diagramas(df_analisado):
    st.header("Diagramas de Risco Gerados")
    mapa_de_cores = {'Alto': '#D32F2F', 'Moderado Alto': '#FFA500', 'Moderado': '#FFC107', 'Baixo': '#4CAF50'}
    definicoes_risco = {'Baixo': 'Risco < 30', 'Moderado': '30 ≤ Risco < 50', 'Moderado Alto': '50 ≤ Risco < 100', 'Alto': 'Risco ≥ 100'}
    
    for (data, estacao), grupo in df_analisado.groupby(['data', 'nomeEstacao']):
        if grupo.empty: continue
        
        st.subheader(f"Diagrama de Risco: {estacao} - {pd.to_datetime(data).strftime('%d/%m/%Y')}")
        fig = go.Figure()

        lim_x = max(110, grupo['VP'].max() * 1.2 if not grupo.empty else 110)
        lim_y = max(5, grupo['AM'].max() * 1.2 if not grupo.empty else 5)
        
        x_grid = np.arange(0, lim_x, 1)
        y_grid = np.linspace(0, lim_y, 100)
        z_grid = np.array([x * y for y in y_grid for x in x_grid]).reshape(len(y_grid), len(x_grid))
        
        colorscale = [[0.0, "#4CAF50"], [0.3, "#FFC107"], [0.5, "#FFA500"], [1.0, "#D32F2F"]]
        
        fig.add_trace(go.Heatmap(x=x_grid, y=y_grid, z=z_grid, colorscale=colorscale, showscale=False, zmin=0, zmax=100, hoverinfo='none'))
        
        grupo = grupo.sort_values(by='hora_ref')
        fig.add_trace(go.Scatter(x=grupo['VP'], y=grupo['AM'], mode='lines', line=dict(color='black', width=1.5, dash='dash'), hoverinfo='none', showlegend=False))
        
        for _, ponto in grupo.iterrows():
            cor_ponto = mapa_de_cores.get(ponto['Classificacao_Risco'], 'black')
            fig.add_trace(go.Scatter(
                x=[ponto['VP']], y=[ponto['AM']], mode='markers', 
                marker=dict(color=cor_ponto, size=12, line=dict(width=1, color='black')), 
                hoverinfo='text', 
                hovertext=f"<b>Hora:</b> {ponto['hora_ref']}<br><b>Risco:</b> {ponto['Classificacao_Risco']} ({ponto['Nivel_Risco_Valor']})<br><b>VP:</b> {ponto['VP']}<br><b>AM:</b> {ponto['AM']}",
                showlegend=False
            ))
        
        for risco, definicao in definicoes_risco.items():
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color=mapa_de_cores[risco], size=10, symbol='square'), name=f"<b>{risco}</b>: {definicao}"))
        
        fig.update_layout(xaxis_title='Índice de Precipitação (VP)', yaxis_title='Altura da Maré (AM)', margin=dict(l=40, r=40, t=40, b=40), showlegend=True, legend_title_text='<b>Níveis de Risco</b>')
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{data}_{estacao}")


# ==============================================================================
# LÓGICA PRINCIPAL DA APLICAÇÃO STREAMLIT (COM BOTÃO)
# ==============================================================================
st.set_page_config(layout="wide")
st.title("Diagramas de Risco para Alagamentos")

# ==============================================================================
# FUNÇÃO DE CARREGAMENTO DE DADOS (MODIFICADA)
# ==============================================================================
@st.cache_data
def carregar_dados():
    # URL para o arquivo "raw" no GitHub
    url = 'https://raw.githubusercontent.com/RafaellaB/Painel-Diagrama-de-Risco/main/risco_final_calculado.csv'
    
    # Lê o arquivo CSV diretamente da URL
    df = pd.read_csv(url) 
    
    # Converte a coluna 'data' para o tipo de objeto de data, sem o horário
    df['data'] = pd.to_datetime(df['data']).dt.date
    return df

try:
    df_analisado = carregar_dados()

    # --- INTERFACE DA BARRA LATERAL ---
    st.sidebar.header("Filtros da Análise")
    
    data_inicio = st.sidebar.date_input("Selecione a data de início", value=df_analisado['data'].min(), min_value=df_analisado['data'].min(), max_value=df_analisado['data'].max())
    data_fim = st.sidebar.date_input("Selecione a data de fim", value=df_analisado['data'].max(), min_value=df_analisado['data'].min(), max_value=df_analisado['data'].max())
    
    estacoes_disponiveis = df_analisado['nomeEstacao'].unique().tolist()
    estacoes_selecionadas = st.sidebar.multiselect('Selecione as Estações', options=estacoes_disponiveis, default=estacoes_disponiveis)

    # --- BOTÃO PARA GERAR A ANÁLISE ---
    if st.sidebar.button("Gerar Diagramas", type="primary"):
        if data_inicio > data_fim:
            st.error("A data de início não pode ser posterior à data de fim.")
        elif not estacoes_selecionadas:
            st.error("Por favor, selecione pelo menos uma estação.")
        else:
            # Filtra o DataFrame com base na seleção do usuário
            df_filtrado = df_analisado[
                (df_analisado['data'] >= data_inicio) & 
                (df_analisado['data'] <= data_fim) &
                (df_analisado['nomeEstacao'].isin(estacoes_selecionadas))
            ]
            
            st.header(f"Análise de Risco para o período de {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")

            if df_filtrado.empty:
                st.info("Nenhum ponto de risco foi encontrado para o período e estações selecionados.")
            else:
                st.success(f"Análise concluída! Exibindo {len(df_filtrado.groupby(['data', 'nomeEstacao']))} diagrama(s).")
                
                with st.expander("Ver Tabela de Risco Detalhada"):
                    st.dataframe(df_filtrado)

                # Chama a função para gerar os diagramas com os dados já filtrados
                gerar_diagramas(df_filtrado)
    else:
        # Mensagem inicial que aparece antes do usuário clicar no botão
        st.info("Selecione os filtros na barra lateral e clique em 'Gerar Diagramas' para iniciar a análise.")

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar ou processar os dados: {e}")