# diagrama_meses_chuvosos_selecao_periodo.py

# ==============================================================================
# IMPORTS
# ==============================================================================
import streamlit as st
import pandas as pd
import numpy as np
from urllib.parse import quote
import plotly.graph_objects as go
import datetime
from calendar import monthrange
import pandas.api.types as ptypes

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    layout="wide",
    page_title="Diagramas de Risco para Alagamentos e Inundações"
)

# ==============================================================================
# FUNÇÕES DE CARREGAMENTO E PROCESSAMENTO
# ==============================================================================
@st.cache_data
def carregar_dados_brutos_por_mes(ano, mes):
    """Carrega dados de um único mês, com depurador para nomes de arquivo."""
    mapa_meses = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
        7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    nome_mes = mapa_meses.get(mes)
    df_chuva, df_mare = pd.DataFrame(), pd.DataFrame()

    try:
        arquivo_mare = f'mare_recife_{nome_mes.upper()}.csv'
        url_mare = f'https://raw.githubusercontent.com/RafaellaB/Dados-Pluviom-tricos-CEMADEN/main/{quote(arquivo_mare)}'
        df_mare = pd.read_csv(url_mare, sep=';', encoding='latin1')
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

    padroes_chuva = [
        f'{nome_mes.title()} {ano}_Cemaden_Dados Pluviométricos.csv',
        f'{nome_mes.lower()} {ano}_Cemaden_Dados Pluviométricos.csv',
        f'{nome_mes.upper()} {ano}_Cemaden_Dados Pluviométricos .csv',
        f'{nome_mes.upper()} {ano}_Cemaden_Dados Pluviométricos.csv'
    ]
    
    sucesso_chuva = False
    for nome_arquivo in padroes_chuva:
        try:
            url_chuva = f'https://raw.githubusercontent.com/RafaellaB/Dados-Pluviom-tricos-CEMADEN/main/{quote(nome_arquivo)}'
            df_chuva = pd.read_csv(url_chuva, sep=';', encoding='utf-8')
            df_chuva['datahora'] = pd.to_datetime(df_chuva['datahora'], errors='coerce')
            df_chuva.dropna(subset=['datahora'], inplace=True)
            if ptypes.is_string_dtype(df_chuva['valorMedida']):
                df_chuva['valorMedida'] = (df_chuva['valorMedida'].astype(str).str.replace(',', '.', regex=False).astype(float))
            sucesso_chuva = True
            break
        except Exception:
            continue

    if not sucesso_chuva:
        return pd.DataFrame(), df_mare

    return df_chuva, df_mare

@st.cache_data
def carregar_dados_por_periodo(data_inicio, data_fim):
    """Carrega e concatena dados de chuva e maré para o período selecionado."""
    df_chuva_total = pd.DataFrame()
    df_mare_total = pd.DataFrame()
    
    periodo = pd.date_range(start=data_inicio, end=data_fim, freq='MS')
    meses_a_processar = sorted(list(set(date.month for date in periodo)))
    
    sucesso = False
    for mes in meses_a_processar:
        ano = data_inicio.year
        df_chuva_mes, df_mare_mes = carregar_dados_brutos_por_mes(ano, mes)
        
        if not df_chuva_mes.empty and not df_mare_mes.empty:
            df_chuva_total = pd.concat([df_chuva_total, df_chuva_mes], ignore_index=True)
            df_mare_total = pd.concat([df_mare_total, df_mare_mes], ignore_index=True)
            sucesso = True
        else:
            st.warning(f"Dados não encontrados para o mês {mes}. Os dados desse mês serão ignorados na análise.")

    if not sucesso:
        st.error("Nenhum dado pôde ser carregado para o período selecionado. Verifique os arquivos no repositório.")
        return pd.DataFrame(), pd.DataFrame()
    
    df_chuva_total['datahora'] = pd.to_datetime(df_chuva_total['datahora'])
    df_chuva_total.drop_duplicates(subset=['datahora', 'nomeEstacao'], inplace=True)
    df_mare_total['datahora'] = pd.to_datetime(df_mare_total['data'] + ' ' + df_mare_total['hora'], format='%d/%m/%Y %H:%M', errors='coerce')
    df_mare_total.dropna(subset=['datahora'], inplace=True)
    df_mare_total.drop_duplicates(subset=['datahora'], inplace=True)
    
    return df_chuva_total, df_mare_total

def arredondar_e_padronizar_horarios(df_original, ano):
    if df_original.empty: return pd.DataFrame()
    df = df_original.copy()
    def construir_data_completa(data_str):
        data_str = str(data_str).strip()
        partes = data_str.split('/')
        if len(partes) > 2 and len(partes[-1]) == 4: return data_str
        else: return f"{data_str}/{ano}"
    df['data_corrigida'] = df['data'].apply(construir_data_completa)
    df['datahora'] = pd.to_datetime(df['data_corrigida'] + ' ' + df['hora'], format='%d/%m/%Y %H:%M', errors='coerce')
    df = df.dropna(subset=['datahora']).sort_values('datahora').reset_index(drop=True)
    if df.empty: return pd.DataFrame()
    primeiro_horario_exato = df.loc[0, 'datahora']
    primeiro_horario_arredondado = primeiro_horario_exato.round(freq='30min')
    dados_padronizados = [{'datahora': primeiro_horario_arredondado, 'altura': df.loc[0, 'altura']}]
    hora_atual = primeiro_horario_arredondado
    for i in range(1, len(df)):
        hora_atual += pd.Timedelta(hours=6)
        dados_padronizados.append({'datahora': hora_atual, 'altura': df.loc[i, 'altura']})
    return pd.DataFrame(dados_padronizados)

def calcular_alturas_manualmente_corrigido(df):
    if df.empty or len(df) < 2: return pd.DataFrame(columns=['datahora', 'altura'])
    resultados = []
    df = df.sort_values('datahora').reset_index(drop=True)
    for i in range(len(df) - 1):
        inicio, fim = df.loc[i, 'datahora'], df.loc[i + 1, 'datahora']
        L1, L2 = df.loc[i, 'altura'], df.loc[i + 1, 'altura']
        intervalo_horas = (fim - inicio).total_seconds() / 3600
        if intervalo_horas == 0: continue
        taxa = (L2 - L1) / intervalo_horas
        resultados.append({'datahora': inicio, 'altura': L1})
        horarios_intermediarios = pd.date_range(start=inicio, end=fim, freq='h')
        for horario in horarios_intermediarios:
            if horario in [inicio, fim]: continue
            horas_passadas = (horario - inicio).total_seconds() / 3600
            altura_calc = L1 + taxa * horas_passadas
            resultados.append({'datahora': horario, 'altura': round(altura_calc, 2)})
    resultados.append({'datahora': df.loc[len(df)-1, 'datahora'], 'altura': df.loc[len(df)-1, 'altura']})
    return pd.DataFrame(resultados).drop_duplicates('datahora').sort_values('datahora').reset_index(drop=True)

def processar_dados_chuva(df_chuva, datas_desejadas, estacoes_desejadas):
    df = df_chuva[df_chuva['nomeEstacao'].isin(estacoes_desejadas)].copy()
    df['data'] = df['datahora'].dt.date.astype(str)
    df = df[df['data'].isin(datas_desejadas)]
    if df.empty: return pd.DataFrame()
    df = df.set_index('datahora').sort_index()
    resultados_por_estacao = []
    for estacao, grupo in df.groupby('nomeEstacao'):
        chuva_10min = grupo['valorMedida'].rolling('10min').sum()
        chuva_2h = grupo['valorMedida'].rolling('2H').sum()
        temp_df = pd.DataFrame({'chuva_10min': chuva_10min, 'chuva_2h': chuva_2h})
        agregado_horario = temp_df.resample('h').last()
        agregado_horario['VP'] = (agregado_horario['chuva_10min'] / (10/60)) + agregado_horario['chuva_2h']
        agregado_horario['nomeEstacao'] = estacao
        resultados_por_estacao.append(agregado_horario)
    df_vp = pd.concat(resultados_por_estacao).reset_index()
    df_vp.dropna(subset=['VP'], inplace=True)
    df_vp['data'] = df_vp['datahora'].dt.strftime('%Y-%m-%d')
    df_vp['hora_ref'] = df_vp['datahora'].dt.strftime('%H:00:00')
    return df_vp[['data', 'hora_ref', 'nomeEstacao', 'VP']]

def processar_dados_mare(df_mare, ano):
    df_picos = arredondar_e_padronizar_horarios(df_mare, ano)
    df_interpolado = calcular_alturas_manualmente_corrigido(df_picos)
    if df_interpolado.empty: return pd.DataFrame()
    df_sincronizado = df_interpolado.set_index('datahora').resample('h').mean().reset_index()
    df_sincronizado.rename(columns={'altura': 'AM'}, inplace=True)
    df_sincronizado.dropna(subset=['AM'], inplace=True)
    df_sincronizado['data'] = df_sincronizado['datahora'].dt.strftime('%Y-%m-%d')
    df_sincronizado['hora_ref'] = df_sincronizado['datahora'].dt.strftime('%H:00:00')
    return df_sincronizado[['data', 'hora_ref', 'AM']]

def calcular_risco(df_final):
    if df_final.empty: return pd.DataFrame()
    df_final['VP'] = df_final['VP'].round(2)
    df_final['AM'] = df_final['AM'].round(2)
    df_final['Nivel_Risco_Valor'] = (df_final['VP'] * df_final['AM']).fillna(0).round(2)
    bins = [-np.inf, 30, 50, 100, np.inf]
    labels = ['Baixo', 'Moderado', 'Moderado Alto', 'Alto']
    df_final['Classificacao_Risco'] = pd.cut(df_final['Nivel_Risco_Valor'], bins=bins, labels=labels, right=False)
    return df_final

def executar_analise_refatorado(df_chuva, df_mare, datas_desejadas, estacoes_desejadas, ano):
    df_vp = processar_dados_chuva(df_chuva, datas_desejadas, estacoes_desejadas)
    if df_vp.empty: return pd.DataFrame()
    df_am = processar_dados_mare(df_mare, ano)
    if df_am.empty: return pd.DataFrame()
    df_final = pd.merge(df_vp, df_am, on=['data', 'hora_ref'], how='left')
    df_final.dropna(subset=['VP', 'AM'], inplace=True)
    if df_final.empty: return pd.DataFrame()
    df_com_risco = calcular_risco(df_final)
    return df_com_risco.sort_values(by=['data', 'nomeEstacao', 'hora_ref'], ignore_index=True)

def gerar_diagramas(df_analisado):
    mapa_de_cores = {'Alto': '#D32F2F', 'Moderado Alto': '#FFA500', 'Moderado': '#FFC107', 'Baixo': '#4CAF50'}
    definicoes_risco = {'Baixo': 'RA < 30', 'Moderado': '30 ≤ RA < 50', 'Moderado Alto': '50 ≤ RA < 100', 'Alto': 'RA ≥ 100'}
    for (data, estacao), grupo in df_analisado.groupby(['data', 'nomeEstacao']):
        if grupo.empty: continue
        st.subheader(f"Diagrama de Risco: {estacao} - {pd.to_datetime(data).strftime('%d/%m/%Y')}")
        fig = go.Figure()
        lim_x = max(110, grupo['VP'].max() * 1.2 if not grupo.empty else 110)
        lim_y = 5
        x_grid, y_grid = np.arange(0, lim_x, 1), np.linspace(0, lim_y, 100)
        z_grid = np.array([x * y for y in y_grid for x in x_grid]).reshape(len(y_grid), len(x_grid))
        colorscale = [[0, "#90EE90"], [30/100, "#FFD700"], [50/100, "#FFA500"], [1.0, "#D32F2F"]]
        fig.add_trace(go.Heatmap(x=x_grid, y=y_grid, z=z_grid, colorscale=colorscale, showscale=False, zmin=0, zmax=100, hoverinfo='none'))
        grupo = grupo.sort_values(by='hora_ref')
        fig.add_trace(go.Scatter(x=grupo['VP'], y=grupo['AM'], mode='lines', line=dict(color='black', width=1.5, dash='dash'), hoverinfo='none', showlegend=False))
        for _, ponto in grupo.iterrows():
            cor_ponto = mapa_de_cores.get(ponto['Classificacao_Risco'], 'black')
            fig.add_trace(go.Scatter(x=[ponto['VP']], y=[ponto['AM']], mode='markers', marker=dict(color=cor_ponto, size=12, line=dict(width=1, color='black')), hoverinfo='text', hovertext=f"<b>Hora:</b> {ponto['hora_ref']}<br><b>Risco:</b> {ponto['Classificacao_Risco']} ({ponto['Nivel_Risco_Valor']})<br><b>VP:</b> {ponto['VP']}<br><b>AM:</b> {ponto['AM']}", showlegend=False))
        
        for risco, definicao in definicoes_risco.items():
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color=mapa_de_cores[risco], size=10, symbol='square'), name=f"<b>{risco}</b>: {definicao}"))
        
        fig.update_layout(title=f'<b>{estacao}</b>', xaxis_title='Índice de Precipitação (mm)', yaxis_title='Índice de Altura da Maré (m)', margin=dict(l=40, r=40, t=40, b=40), showlegend=True, legend_title_text='<b>Níveis de Risco</b>')
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{data}_{estacao}")

# ==============================================================================
# INTERFACE DO STREAMLIT - MODO COM SELEÇÃO DE PERÍODO
# ==============================================================================
st.title("Diagramas de Risco para Alagamentos e Inundações")
st.sidebar.header("Filtros da Análise")

# Definir o ano fixo de 2025 para a análise
ano_analise = 2025

# Seletores de data
primeiro_dia_ano = datetime.date(ano_analise, 1, 1)
ultimo_dia_ano = datetime.date(ano_analise, 8, 31)
data_inicio = st.sidebar.date_input("Selecione a data de início", value=primeiro_dia_ano, min_value=primeiro_dia_ano, max_value=ultimo_dia_ano)
data_fim = st.sidebar.date_input("Selecione a data de fim", value=ultimo_dia_ano, min_value=primeiro_dia_ano, max_value=ultimo_dia_ano)

# ATUALIZAÇÃO: Inclusão da nova estação "Dois Irmãos"
ESTACOES_DO_ESTUDO = ["Campina do Barreto", "Torreão", "RECIFE - APAC", "Imbiribeira", "Dois Irmãos"]
estacoes_selecionadas = st.sidebar.multiselect('Selecione as Estações', options=ESTACOES_DO_ESTUDO, default=ESTACOES_DO_ESTUDO)

if st.sidebar.button("Iniciar Análise", type="primary"):
    
    if data_inicio > data_fim:
        st.error("A data de início não pode ser posterior à data de fim.")
    elif not estacoes_selecionadas:
        st.error("Por favor, selecione pelo menos uma estação para iniciar a análise.")
    else:
        st.header(f"Análise de Risco para o período de {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")
        
        with st.spinner(f"Carregando dados de {data_inicio.year}..."):
            df_chuva_raw, df_mare_raw = carregar_dados_por_periodo(data_inicio, data_fim)
        
        if df_chuva_raw.empty or df_mare_raw.empty:
            st.warning("Nenhum dado pôde ser carregado para o período selecionado.")
        else:
            with st.spinner(f"Processando análise do período..."):
                datas_desejadas = pd.date_range(start=data_inicio, end=data_fim).strftime('%Y-%m-%d').tolist()
                dados_analisados = executar_analise_refatorado(
                    df_chuva_raw, df_mare_raw, datas_desejadas, estacoes_selecionadas, ano_analise
                )

            if dados_analisados.empty:
                st.info("Nenhum ponto de risco foi calculado para o período com os filtros selecionados.")
            else:
                st.success(f"Análise concluída! {len(dados_analisados)} pontos de dados gerados.")
                
                with st.expander("Ver Tabela de Risco Detalhada"):
                    st.dataframe(dados_analisados)

                gerar_diagramas(dados_analisados)

        st.divider()
        #st.balloons() #animação
        st.header("Análise Concluída!")