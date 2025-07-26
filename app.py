# app.py (Versão Final com Cálculo de Maré por Intervalo e Junção Corrigida)

import streamlit as st
import pandas as pd
import numpy as np
from urllib.parse import quote
import os
import plotly.graph_objects as go
import datetime

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    layout="wide",
    page_title="Diagramas de Risco para Alagamentos e Inundações")
    

# ==============================================================================
# FUNÇÕES DE PROCESSAMENTO
# ==============================================================================

@st.cache_data
def carregar_dados_brutos():
    """Carrega os dados de chuva e maré do GitHub."""
    print("Carregando dados brutos do GitHub (executado apenas uma vez)...")
    arquivo_chuva = 'Maio 2025_Cemaden_Dados Pluviométricos.csv'
    url_chuva = f'https://raw.githubusercontent.com/RafaellaB/Dados-Pluviom-tricos-CEMADEN/main/{quote(arquivo_chuva)}'
    df_chuva = pd.read_csv(url_chuva, sep=';', encoding='utf-8')
    df_chuva['datahora'] = pd.to_datetime(df_chuva['datahora'], errors='coerce')
    df_chuva.dropna(subset=['datahora'], inplace=True)
    df_chuva['valorMedida'] = df_chuva['valorMedida'].astype(str).str.replace(',', '.', regex=False).astype(float)
    
    arquivo_mare = 'mare_recife_MAIO.csv'
    url_mare = f'https://raw.githubusercontent.com/RafaellaB/Dados-Pluviom-tricos-CEMADEN/main/{quote(arquivo_mare)}'
    df_mare = pd.read_csv(url_mare, sep=';', encoding='latin1')
    
    return df_chuva, df_mare

def executar_analise(df_chuva, df_mare, datas_desejadas, estacoes_desejadas):
    """
    Executa o pipeline de análise com o cálculo de AM dinâmico
    para cada intervalo de maré.
    """
    #PROCESSAMENTO DA CHUVA ---
    print("--- Etapa 1: Processando dados de CHUVA ---")
    df_filtrado_chuva = df_chuva[df_chuva['nomeEstacao'].isin(estacoes_desejadas)].copy()
    df_filtrado_chuva['data'] = df_filtrado_chuva['datahora'].dt.date.astype(str)
    df_filtrado_chuva = df_filtrado_chuva[df_filtrado_chuva['data'].isin(datas_desejadas)]

    if df_filtrado_chuva.empty:
        return pd.DataFrame()

    horas_do_dia = range(24)
    horas_do_dia_str = [f"{h:02d}:00:00" for h in horas_do_dia]
    
    resultados_2h = []
    df_filtrado_chuva.loc[:, 'hora_numerica'] = df_filtrado_chuva['datahora'].dt.hour
    for hora in horas_do_dia:
        df_janela = df_filtrado_chuva[(df_filtrado_chuva['hora_numerica'] >= hora - 1) & (df_filtrado_chuva['hora_numerica'] < hora + 1)].copy()
        df_janela['janela'] = f"{hora:02d}:00:00"
        agrupado = df_janela.groupby(['nomeEstacao', 'data', 'janela'])['valorMedida'].sum().reset_index()
        resultados_2h.append(agrupado)
    df_v2horas = pd.concat(resultados_2h).rename(columns={'valorMedida': 'chuva_2h', 'janela': 'hora_ref'})

    resultados_15min = []
    for data_str in datas_desejadas:
        for hora_str in horas_do_dia_str:
            alvo = pd.to_datetime(f'{data_str} {hora_str}')
            inicio_intervalo = alvo - pd.Timedelta(minutes=10)
            df_intervalo = df_filtrado_chuva[(df_filtrado_chuva['datahora'] >= inicio_intervalo) & (df_filtrado_chuva['datahora'] < alvo)]
            soma = df_intervalo.groupby('nomeEstacao')['valorMedida'].sum().reset_index()
            soma['data'] = data_str
            soma['hora_alvo'] = hora_str
            resultados_15min.append(soma)
    df_v10min = pd.concat(resultados_15min).rename(columns={'valorMedida': 'chuva_10min', 'hora_alvo': 'hora_ref'})
    
    df_vp = pd.merge(df_v10min, df_v2horas, on=['data', 'hora_ref', 'nomeEstacao'], how='outer')
    df_vp[['chuva_10min', 'chuva_2h']] = df_vp[['chuva_10min', 'chuva_2h']].fillna(0)
    df_vp['VP'] = (df_vp['chuva_10min'] / (10/60)) + df_vp['chuva_2h']
    df_vp['datahora'] = pd.to_datetime(df_vp['data'] + ' ' + df_vp['hora_ref'])
    print("Dados de chuva processados.")

    # PROCESSAMENTO DA MARÉ POR INTERVALO 
    print("\n--- Etapa 2: Processando dados da MARÉ por intervalo ---")
    df_mare['data_str'] = pd.to_datetime(df_mare['data'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df_mare['datahora'] = pd.to_datetime(df_mare['data_str'] + ' ' + df_mare['hora'])
    dados_filtrados_mare = df_mare[df_mare['data_str'].isin(datas_desejadas)].copy()
    dados_filtrados_mare.sort_values(by='datahora', inplace=True)
    
    intervalos_am = []
    for data, grupo_dia in dados_filtrados_mare.groupby('data_str'):
        for i in range(len(grupo_dia) - 1):
            ponto_atual = grupo_dia.iloc[i]
            ponto_seguinte = grupo_dia.iloc[i+1]
            I1 = ponto_atual['altura']
            I2 = ponto_seguinte['altura']
            AM_intervalo = round(((I1 - I2) / 6) + I1, 2)
            intervalos_am.append({
                'datahora_inicio': ponto_atual['datahora'],
                'datahora_fim': ponto_seguinte['datahora'],
                'data': data,
                'AM': AM_intervalo
            })
    df_am_intervalos = pd.DataFrame(intervalos_am)
    print("Dados de maré por intervalo calculados.")

    
    print("\n--- Etapa 3: Unindo dados de chuva e maré (Método Explícito) ---")
    df_vp['AM'] = np.nan # Cria a coluna de AM vazia no DataFrame de chuva
    
    # Para cada intervalo de maré calculado, seleciona as linhas de chuva que caem dentro desse intervalo
    for _, intervalo in df_am_intervalos.iterrows():
        inicio = intervalo['datahora_inicio']
        fim = intervalo['datahora_fim']
        # Seleciona todas as linhas de chuva que caem dentro deste intervalo de tempo
        indices = df_vp[(df_vp['datahora'] >= inicio) & (df_vp['datahora'] < fim)].index
        # Atribui o valor de AM do intervalo a todas essas linhas de chuva
        df_vp.loc[indices, 'AM'] = intervalo['AM']
    
    df_final = df_vp.copy()
    print("Junção de dados concluída.")

    # --- ANÁLISE DE RISCO ---
    df_final.dropna(subset=['AM'], inplace=True) 
    df_final['VP'] = df_final['VP'].round(2)
    df_final['AM'] = df_final['AM'].round(2)
    df_final['Nivel_Risco_Valor'] = (df_final['VP'] * df_final['AM']).fillna(0).round(2)
    bins = [-np.inf, 30, 50, 100, np.inf]
    labels = ['Baixo', 'Moderado', 'Moderado Alto', 'Alto']
    df_final['Classificacao_Risco'] = pd.cut(df_final['Nivel_Risco_Valor'], bins=bins, labels=labels, right=False)
    
    return df_final.sort_values(by=['data', 'nomeEstacao', 'hora_ref'], ignore_index=True)

def gerar_diagramas(df_analisado):
    """
    Gera os diagramas interativos com uma legenda nativa customizada e
    chaves únicas para garantir a estabilidade no Streamlit.
    """
    # Dicionário que mapeia a classificação para uma cor
    mapa_de_cores = {'Alto': '#D32F2F', 'Moderado Alto': '#FFA500', 'Moderado': '#FFC107', 'Baixo': '#4CAF50'}
    
    # Dicionário com o texto para cada nível de risco na legenda
    definicoes_risco = {
        'Baixo': 'RA < 30',
        'Moderado': '30 ≤ RA < 50',
        'Moderado Alto': '50 ≤ RA < 100',
        'Alto': 'RA ≥ 100'
    }

    # Loop para criar um gráfico para cada dia e estação
    for (data, estacao), grupo in df_analisado.groupby(['data', 'nomeEstacao']):
        if grupo.empty: continue
        
        st.subheader(f"Diagrama de Risco: {estacao} - {pd.to_datetime(data).strftime('%d/%m/%Y')}")
        fig = go.Figure()

        # Configuração do gráfico (fundo, limites, etc.)
        lim_x = max(110, grupo['VP'].max() * 1.2) if not grupo.empty else 110
        lim_y = 5
        x_grid, y_grid = np.arange(0, lim_x, 1), np.linspace(0, lim_y, 100)
        z_grid = np.array([x * y for y in y_grid for x in x_grid]).reshape(len(y_grid), len(x_grid))
        colorscale = [[0, "#90EE90"], [30/100, "#FFD700"], [50/100, "#FFA500"], [1.0, "#D32F2F"]]
        fig.add_trace(go.Heatmap(x=x_grid, y=y_grid, z=z_grid, colorscale=colorscale, showscale=False, zmin=0, zmax=100))
        
        
        # Adicionado o parâmetro 'hoverinfo='none'' para desativar a caixa de texto do fundo.
        fig.add_trace(go.Heatmap(
            x=x_grid, 
            y=y_grid, 
            z=z_grid, 
            colorscale=colorscale, 
            showscale=False, 
            zmin=0, 
            zmax=100,
            hoverinfo='none' 
        ))
        
        
        # Plota a linha da trajetória
        grupo = grupo.sort_values(by='hora_ref')
        fig.add_trace(go.Scatter(x=grupo['VP'], y=grupo['AM'], mode='lines', line=dict(color='black', width=1.5, dash='dash'), hoverinfo='none', showlegend=False))
        
        # Plota os pontos de risco individuais
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
            fig.add_trace(go.Scatter(
                x=[None], y=[None], # Não plota nenhum ponto no gráfico
                mode='markers',
                marker=dict(color=mapa_de_cores[risco], size=10, symbol='square'),
                name=f"<b>{risco}</b>: {definicao}" # Este texto aparecerá na legenda
            ))
        

        # Atualiza o layout final do gráfico
        fig.update_layout(
            title=f'<b>{estacao}</b>',
            xaxis_title='Índice de Precipitação (mm)',
            yaxis_title='índice de Altura da Maré (m)',
            margin=dict(l=40, r=40, t=40, b=40),
            showlegend=True, # Liga a legenda para que os itens apareçam
            legend_title_text='<b>Níveis de Risco</b>'
        )
        
        
        # Chave única para cada gráfico combinando a data e a estação
        chave_unica = f"chart_{data}_{estacao}"
        st.plotly_chart(fig, use_container_width=True, key=chave_unica)
        

# ==============================================================================
# INTERFACE DO STREAMLIT
# ==============================================================================

st.title("Diagramas de Risco para Alagamentos e Inundações")

DATAS_FIXAS = pd.date_range(start='2025-05-14', end='2025-05-21').strftime('%Y-%m-%d').tolist()
#st.info(f"Período fixo de 14/05/2025 a 21/05/2025.")

df_chuva_raw, df_mare_raw = carregar_dados_brutos()

st.sidebar.header("Filtros da Análise")
ESTACOES_DO_ESTUDO = ["Campina do Barreto", "Torreão", "RECIFE - APAC", "Imbiribeira"]
estacoes_selecionadas = st.sidebar.multiselect(
    'Selecione as Estações',
    options=ESTACOES_DO_ESTUDO,
    default=ESTACOES_DO_ESTUDO
)

if not estacoes_selecionadas:
    st.warning("Por favor, selecione pelo menos uma estação na barra lateral.")
else:
    if st.button("Iniciar Análise"):
        with st.spinner(f"Analisando o período de {DATAS_FIXAS[0]} a {DATAS_FIXAS[-1]} para {len(estacoes_selecionadas)} estações..."):
            dados_analisados = executar_analise(df_chuva_raw, df_mare_raw, DATAS_FIXAS, estacoes_selecionadas)

            if dados_analisados.empty:
                st.info("Nenhum dado encontrado para os filtros selecionados.")
            else:
                st.success("Análise concluída!")
                
                st.header("Relatório de Pontos por Zona de Risco")
                for zona in ['Alto', 'Moderado Alto', 'Moderado', 'Baixo']:
                    pontos_na_zona = dados_analisados[dados_analisados['Classificacao_Risco'] == zona]
                    with st.expander(f"Pontos na Zona de Risco '{zona}': {len(pontos_na_zona)} ponto(s)"):
                        if not pontos_na_zona.empty:
                            st.dataframe(pontos_na_zona[['data', 'hora_ref', 'nomeEstacao', 'Nivel_Risco_Valor', 'VP', 'AM']])
 

                gerar_diagramas(dados_analisados)