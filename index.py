import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
import requests
import plotly.express as px
from streamlit_folium import folium_static

# Diccionario de pesos predeterminado
default_weights = {
    'Índice de servicios brindados': 3,
    'Conexiones totales de agua': 3,
    'Conexiones totales de alcantarillado': 3,
    'Población': 3,
    '¿La OC cuenta con reconocimiento de la muni?': 1,
    '¿Recibió asistencia técnica en los últimos 3 años?': 1,
    'Ind cuota': 4,
    '¿Cobra cuota?': 1,
    'Porcentaje de usuarios no morosos': 2,
    '¿La cuota cubre costos de O&M?': 1,
    'Índice continuidad horas semana': 1,
    '¿Realiza cloración?': 1,
    '¿El sistema cuenta con equipo clorador?': 1,
    'Estado operativo del reservorio': 1,
    'Antigüedad promedio del sistema': 1,
    'Antigüedad máxima del sistema': 1,
    'Distancia a la EP': 3
}

sections = {
    "Índice de servicios brindados": ['Índice de servicios brindados'],
    "Tamaño": ['Conexiones totales de agua', 
                          'Conexiones totales de alcantarillado', 'Población'],
    "Formalidad": ['¿La OC cuenta con reconocimiento de la muni?'],
    "Asistencia técnica": ['¿La OC cuenta con reconocimiento de la muni?'],
    "Cuota": ['Ind cuota', '¿Cobra cuota?', 'Porcentaje de usuarios no morosos', 
                                  '¿La cuota cubre costos de O&M?'],
    "Calidad del servicio": ['Índice continuidad horas semana', '¿Realiza cloración?', 
                                  '¿El sistema cuenta con equipo clorador?'],
    "Estado del sistema": ['Estado operativo del reservorio','Antigüedad promedio del sistema', 'Antigüedad máxima del sistema'],
    "Distancia a la EP":['Distancia a la EP']
}

def load_data(file):
    df = pd.read_excel(file)
    ranking_cols = df.loc[:, 'Índice de servicios brindados':'Distancia a la EP'].columns
    df = df[['p016_nombredelprestador', 'LONGITUD', 'LATITUD'] + list(ranking_cols)]
    return df, ranking_cols

# def calculate_ranking(df, ranking_cols, weights):
#     df["Ranking"] = df[ranking_cols].mul(weights).sum(axis=1) / sum(weights.values())
#     return df.sort_values("Ranking", ascending=False)

def calculate_sectional_ranking(df, ranking_cols, weights, sections):
    df_result = df.copy()
    
    # Calcular el ranking general
    df_result["Ranking"] = df_result[ranking_cols].mul(weights).sum(axis=1) / sum(weights.values())
    
    # Calcular los rankings por sección
    for section, cols in sections.items():
        section_weights = {col: weights[col] for col in cols if col in weights}
        df_result[section] = df_result[cols].mul(section_weights).sum(axis=1) / sum(section_weights.values())
    
    return df_result.sort_values("Ranking", ascending=False)

def generate_radar_chart(df_top, sections):
    # Seleccionar solo columnas de interés
    radar_data = df_top.melt(id_vars=["p016_nombredelprestador"], 
                              value_vars=list(sections.keys()), 
                              var_name="Categoría", 
                              value_name="Valor")
    
    fig = px.line_polar(radar_data, r="Valor", theta="Categoría", 
                         line_close=True, 
                         color="p016_nombredelprestador",
                         template="plotly_white")
    fig.update_traces(fill='toself')
    return fig

def generate_formula(weights):
    def sanitize(text):
        return text.replace("%", "\%").replace("&", "\&").replace("_", "\_") \
                   .replace("#", "\#").replace("$", "\$").replace("{", "\{") \
                   .replace("}", "\}").replace("^", "\^{}").replace("¿", "") \
                   .replace("?", "").replace("¡", "").replace("!", "") \
                   .replace("á", "a").replace("é", "e").replace("í", "i") \
                   .replace("ó", "o").replace("ú", "u").replace("ñ", "n")

    terms = [f"{w} \\times \\text{{{sanitize(var)}}}" for var, w in weights.items()]
    denominator = sum(weights.values())

    # Definir número de términos por línea para una mejor alineación
    num_terms_per_line = 3
    lines = []
    for i in range(0, len(terms), num_terms_per_line):
        line = " + ".join(terms[i:i+num_terms_per_line])
        lines.append(line)

    # Usar "aligned" con ajuste a la izquierda (&) para mejorar alineación
    numerator = " \\\\\n        & ".join(lines)  

    formula = rf"""
    \begin{{equation*}}
    \text{{Ranking}} = 
    \frac{{
        \begin{{aligned}}
        & {numerator}
        \end{{aligned}}
    }}{{{denominator}}}
    \end{{equation*}}
    """
    return formula



def main():
    st.set_page_config(page_title="Ranking de Prestadores", layout="wide")

    st.title("🏆 Ranking de Prestadores de Servicios")

    # Cargar datos desde Excel
    uploaded_file = st.sidebar.file_uploader("📂 Sube un archivo Excel", type=["xlsx", "xls"])
    if uploaded_file:
        df, ranking_cols = load_data(uploaded_file)
        st.sidebar.success("✅ Archivo cargado correctamente")

        # Inicializar session_state si no existe
        if "weights" not in st.session_state:
            st.session_state.weights = {col: default_weights.get(col, 1) for col in ranking_cols}

        # Configuración de pesos en la barra lateral
        st.sidebar.header("⚖️ Ajustar Pesos")
        with st.sidebar.expander("🔧 Modificar pesos"):
            for col in ranking_cols:
                st.session_state.weights[col] = st.slider(f"{col}", 1, 5, st.session_state.weights[col], 1)

        # Recalcular ranking inmediatamente cuando cambian los pesos
        # df_ranked = calculate_ranking(df, ranking_cols, st.session_state.weights)
        df_ranked = calculate_sectional_ranking(df,ranking_cols,st.session_state.weights,sections)

        # Configuración de layout en 2 columnas
        col1, col2 = st.columns([3, 3])  # Columna izquierda (ranking) | Derecha (mapa)

        with col1:
            top_n = st.slider("🎯 Selecciona Top N", 1, len(df), 10)
            df_top = df_ranked.head(top_n)

            with st.expander("📋 Ver tabla de ranking", expanded=True):
                st.dataframe(df_top)
            
            
            st.subheader("📢 Resumen de Top Seleccionado")
            st.write(df_top[["p016_nombredelprestador", "Ranking"]])

        with col2:
            st.subheader("🗺️ Mapa de Ubicaciones")
            map_center = [df_top["LATITUD"].mean(), df_top["LONGITUD"].mean()]
            m = folium.Map(location=map_center, zoom_start=10)

            # URL del primer GeoJSON (UP)
            up_url = "https://raw.githubusercontent.com/HermanMoreno98/DATA_DASH/refs/heads/main/up_lambayeque.geojson"
            try:
                response = requests.get(up_url)
                if response.status_code == 200:
                    geojson_data = response.json()
                    gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
                    folium.GeoJson(
                        geojson_data,
                        name="Unidades de proceso Lambayeque",
                        style_function=lambda feature: {
                            "color": "black",
                            "weight": 1,
                            "fillOpacity": 0
                        }
                    ).add_to(m)
                    # Agregar nombres en el centro de cada polígono
                    for _, row in gdf.iterrows():
                        centroide = row.geometry.centroid  # Obtener el centroide
                        nombre = row["codup"]  # Ajusta esto al nombre de la UP en tu GeoJSON

                        folium.Marker(
                            location=[centroide.y, centroide.x],
                            icon=folium.DivIcon(html=f"<div style='font-size: 10px; color: black;'>{nombre}</div>")
                        ).add_to(m)
                else:
                    st.error(f"⚠️ No se pudo cargar Sectores Lambayeque (Error {response.status_code})")
            except Exception as e:
                st.error(f"❌ Error al cargar Sectores Lambayeque: {e}")

            
            # URL del primer GeoJSON (Sectores)
            sector_url = "https://raw.githubusercontent.com/HermanMoreno98/DATA_DASH/refs/heads/main/sector_lambayeque.geojson"
            try:
                response = requests.get(sector_url)
                if response.status_code == 200:
                    geojson_data = response.json()
                    folium.GeoJson(
                        geojson_data,
                        name="Sectores Lambayeque",
                        style_function=lambda feature: {
                            "fillColor": "#A9A9A9",
                            "color": "black",
                            "weight": 1,
                            "fillOpacity": 0.4
                        }
                    ).add_to(m)
                else:
                    st.error(f"⚠️ No se pudo cargar Sectores Lambayeque (Error {response.status_code})")
            except Exception as e:
                st.error(f"❌ Error al cargar Sectores Lambayeque: {e}")

            # URL del segundo GeoJSON (Buffer EPS)
            buffer_url = "https://raw.githubusercontent.com/HermanMoreno98/DATA_DASH/refs/heads/main/buffer_eps_lambayeque.geojson"
            try:
                response = requests.get(buffer_url)
                if response.status_code == 200:
                    geojson_data = response.json()

                    def buffer_style(feature):
                        layer_value = feature["properties"].get("layer", "")
                        color = "#FFFF00" if layer_value == "A 2.5 Km del Área con población servida de la EPS" else "#87CEEB"
                        return {
                            "fillColor": color,
                            "color": "black",
                            "weight": 1,
                            "fillOpacity": 0.4
                        }

                    folium.GeoJson(
                        geojson_data,
                        name="Buffer EPS Lambayeque",
                        style_function=buffer_style
                    ).add_to(m)
                else:
                    st.error(f"⚠️ No se pudo cargar Buffer EPS Lambayeque (Error {response.status_code})")
            except Exception as e:
                st.error(f"❌ Error al cargar Buffer EPS Lambayeque: {e}")

            # Puntos
            for _, row in df_top.iterrows():
                color = "red" if row["Ranking"] > 0.6 else "green"
                
                folium.CircleMarker(
                    location=[row["LATITUD"], row["LONGITUD"]],
                    radius=6,  # Tamaño del círculo
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7,
                    popup=row["p016_nombredelprestador"]
                ).add_to(m)


            # Agregar control de capas
            folium.LayerControl().add_to(m)           
            
            folium_static(m)


            # 🔹 Agregando el gráfico de radar debajo del mapa
            st.subheader("📊 Comparación de Prestadores (Radar)")
            radar_fig = generate_radar_chart(df_top, sections)  # Función que genera el gráfico
            st.plotly_chart(radar_fig, use_container_width=True)


        # Mostrar la ecuación con los pesos actualizados dinámicamente
        st.subheader("🧮 Fórmula de Cálculo del Ranking")
        formula = generate_formula(st.session_state.weights)
        st.latex(formula)

if __name__ == "__main__":
    main()
