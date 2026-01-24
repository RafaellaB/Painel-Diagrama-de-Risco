import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime


def gerar_diagramas(df_analisado):
    st.header("Generated Risk Diagrams")
    
    # Dicionários de Tradução e Cores
    mapa_de_cores = {'Alto': '#D32F2F', 'Moderado Alto': '#FFA500', 'Moderado': '#FFC107', 'Baixo': '#4CAF50'}
    traducoes_risco = {'Baixo': 'Low', 'Moderado': 'Moderate', 'Moderado Alto': 'High-Moderate', 'Alto': 'High'}
    definicoes_risco_en = {'Low': 'Risk < 30', 'Moderate': '30 ≤ Risk < 50', 'High-Moderate': '50 ≤ Risk < 100', 'High': 'Risk ≥ 100'}
    
    for (data, estacao), grupo in df_analisado.groupby(['data', 'nomeEstacao']):
        if grupo.empty: continue
        
        st.subheader(f"Risk Diagram: {estacao} - {pd.to_datetime(data).strftime('%Y-%m-%d')}")
 
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
            # Tradução do status para o Hover
            status_en = traducoes_risco.get(ponto['Classificacao_Risco'], ponto['Classificacao_Risco'])
            
            fig.add_trace(go.Scatter(
                x=[ponto['VP']], y=[ponto['AM']], mode='markers', 
                marker=dict(color=cor_ponto, size=12, line=dict(width=1, color='black')), 
                hoverinfo='text', 
                # Hover labels em inglês
                hovertext=f"<b>Time:</b> {ponto['hora_ref']}<br><b>Risk:</b> {status_en}<br><b>RVI:</b> {ponto['VP']}<br><b>THI:</b> {ponto['AM']}",
                showlegend=False
            ))
        
        # Gerando a legenda com os nomes em Inglês
        for risco_pt, risco_en in traducoes_risco.items():
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode='markers', 
                marker=dict(color=mapa_de_cores[risco_pt], size=10, symbol='square'), 
                name=f"<b>{risco_en}</b>: {definicoes_risco_en[risco_en]}"
            ))
        
        fig.update_layout(
            xaxis_title='Rainfall Volume Index (RVI)', 
            yaxis_title='Tidal Height Index (THI)', 
            margin=dict(l=40, r=40, t=40, b=40), 
            showlegend=True, 
            legend_title_text='<b>Risk Levels</b>'
        )
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{data}_{estacao}")



st.set_page_config(layout="wide")
st.title("Flood Risk Diagrams")

#carregamento de dados
@st.cache_data(ttl=86400)
def carregar_dados():
    #URL para o arquivo "raw" no GitHub
    url = 'https://raw.githubusercontent.com/RafaellaB/Painel-Diagrama-de-Risco/main/resultado_risco_final.csv'
    
    #Lê o arquivo CSV diretamente da URL
    df = pd.read_csv(url) 
    
    #Converte a coluna 'data' para o tipo de objeto de data, sem o horário
    df['data'] = pd.to_datetime(df['data']).dt.date
    return df

try:
    df_analisado = carregar_dados()

   #barra lateral
    st.sidebar.header("Analysis Filters")
    
    data_inicio = st.sidebar.date_input("Select start date", value=df_analisado['data'].min(), min_value=df_analisado['data'].min(), max_value=df_analisado['data'].max())
    data_fim = st.sidebar.date_input("Select end date", value=df_analisado['data'].max(), min_value=df_analisado['data'].min(), max_value=df_analisado['data'].max())
    
    estacoes_disponiveis = df_analisado['nomeEstacao'].unique().tolist()
    estacoes_selecionadas = st.sidebar.multiselect('Select Stations', options=estacoes_disponiveis, default=estacoes_disponiveis)

    #botão explorar diagramas
    if st.sidebar.button("Explore Risk Diagrams", type="primary"):
        if data_inicio > data_fim:
            st.error("The start date cannot be later than the end date.")
        elif not estacoes_selecionadas:
            st.error("Please select at least one station.")
        else:
            # Filtra o DataFrame com base na seleção do usuário
            df_filtrado = df_analisado[
                (df_analisado['data'] >= data_inicio) & 
                (df_analisado['data'] <= data_fim) &
                (df_analisado['nomeEstacao'].isin(estacoes_selecionadas))
            ]
            
            st.header(f"Risk Analysis: {data_inicio.strftime('%Y-%m-%d')} to {data_fim.strftime('%Y-%m-%d')}")

            if df_filtrado.empty:
                st.info("No risk points were found for the selected period and stations.")
            else:
                st.success(f"Analysis complete! Displaying {len(df_filtrado.groupby(['data', 'nomeEstacao']))} diagrama(s).")
                
                with st.expander("View Detailed Risk Table"):
                    st.dataframe(df_filtrado)

                # Chama a função para gerar os diagramas com os dados já filtrados
                gerar_diagramas(df_filtrado)
    else:
        # mensagem inicial que aparece antes do usuário clicar no botão
        st.info("Select the filters in the sidebar and click 'Explore Risk Diagrams' to start the analysis.")

except Exception as e:
    st.error(f"An error occurred while loading or processing the data: {e}")