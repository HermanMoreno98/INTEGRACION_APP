import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
import plotly.express as px
from streamlit_folium import folium_static
from folium.plugins import Fullscreen
import leafmap.foliumap as leafmap

# Diccionario de pesos predeterminado
default_weights = {
    'Índice de servicios brindados': 4,
    'Conexiones totales de agua': 6,
    'Conexiones totales de alcantarillado': 1,
    'Población': 6,
    '¿La OC cuenta con reconocimiento de la muni?': 1,
    '¿Recibió asistencia técnica en los últimos 3 años?': 1,
    'Ind cuota': 4,
    '¿Cobra cuota?': 1,
    'Porcentaje de usuarios no morosos': 1,
    '¿La cuota cubre costos de O&M?': 2,
    'Índice continuidad horas semana': 1,
    '¿Realiza cloración?': 1,
    '¿El sistema cuenta con equipo clorador?': 1,
    'Estado operativo del reservorio': 1,
    'Antigüedad promedio del sistema': 2,
    'Antigüedad máxima del sistema': 2,
    'Distancia a la EP': 9
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
    df = df[['Prestador', 'LONGITUD', 'LATITUD','EPS'] + list(ranking_cols)]
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
    radar_data = df_top.melt(id_vars=["Prestador"], 
                              value_vars=list(sections.keys()), 
                              var_name="Categoría", 
                              value_name="Valor")
    
    fig = px.line_polar(radar_data, r="Valor", theta="Categoría", 
                         line_close=True, 
                         color="Prestador",
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

@st.cache_data
def cargar_geojson_local(ruta, nombre):
    try:
        geojson_data = gpd.read_file(ruta)
        return geojson_data
    except Exception as e:
        st.error(f"❌ Error al cargar {nombre}: {e}")
        return gpd.GeoDataFrame()
    
# Configuración inicial de session_state
if "geojson_data" not in st.session_state:
    st.session_state["geojson_data"] = {
        "datass": cargar_geojson_local("./data/datass.geojson", "datass"),
        "departamento": cargar_geojson_local("./data/departamento.geojson", "departamento"),
        "casco_urbano": cargar_geojson_local("./data/Buffer_EPS_casco_urbano.geojson", "casco_urbano"),
        "casco_no_urbano": cargar_geojson_local("./data/Buffer_EPS_casco_no_urbano.geojson", "casco_no_urbano"),
        "censo": cargar_geojson_local("./data/censo.geojson", "censo")
    }


def main():

    st.set_page_config(page_title="Ranking de Prestadores", layout="wide")
    
    # Configuración inicial de session_state
    if "geojson_data" not in st.session_state:
        st.session_state["geojson_data"] = {}

    st.title("🏆 Ranking de Prestadores de Servicios")

    df, ranking_cols = load_data("./data/base_app_final.xlsx")
    # st.sidebar.success("✅ Archivo cargado correctamente")
    
    st.sidebar.header("🔍 Filtrar por EPS")
    eps_options = df["EPS"].unique().tolist()
    # selected_eps = st.sidebar.multiselect("Selecciona EPS", eps_options, default=eps_options)
    selected_eps = st.sidebar.selectbox("Selecciona EPS", eps_options)

    # Inicializar session_state si no existe
    if "weights" not in st.session_state:
            st.session_state.weights = {col: default_weights.get(col, 1) for col in ranking_cols}

        # Configuración de pesos en la barra lateral
    st.sidebar.header("⚖️ Ajustar Pesos")
    with st.sidebar.expander("🔧 Modificar pesos"):
        for col in ranking_cols:
                st.session_state.weights[col] = st.slider(f"{col}", 1, 10, st.session_state.weights[col], 1)

        # Recalcular ranking inmediatamente cuando cambian los pesos
        # df_ranked = calculate_ranking(df, ranking_cols, st.session_state.weights)
    df_ranked = calculate_sectional_ranking(df,ranking_cols,st.session_state.weights,sections)
    
    # df_filtered = df_ranked[df_ranked["EPS"].isin(selected_eps)]
    df_filtered = df_ranked[df_ranked["EPS"] == selected_eps]

        # Configuración de layout en 2 columnas
    col1, col2 = st.columns([4.5, 2])  # Columna izquierda (ranking) | Derecha (mapa)

    with col2:
            top_n = st.slider("🎯 Selecciona Top N", 1, len(df_filtered), 10)
            df_top = df_filtered.head(top_n)
            
            st.subheader("📢 Resumen de Top Seleccionado")
            st.write(df_top[["Ranking","Prestador"]])

    with col1:
            st.subheader("🗺️ Mapa")
            map_center = [df_filtered["LATITUD"].mean(), df_filtered["LONGITUD"].mean()]
            m = folium.Map(location=map_center, zoom_start=10)

            # Limite Departamental
            geojson_data = st.session_state["geojson_data"].get("departamento", {})
            if isinstance(geojson_data, gpd.GeoDataFrame) and not geojson_data.empty:
                # gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
                gdf = geojson_data
                folium.GeoJson(
                    geojson_data,
                    name="Limite departamental",
                    style_function=lambda feature: {
                        "color": "black",
                        "weight": 1,
                        "fillOpacity": 0
                    }
                ).add_to(m)
                # Nombres en el centro de cada polígono
                for _, row in gdf.iterrows():
                    centroide = row.geometry.centroid
                    nombre = row["nomdep"]
                    folium.Marker(
                        location=[centroide.y, centroide.x],
                        icon=folium.DivIcon(html=f"<div style='font-size: 10px; color: black;'>{nombre}</div>")
                    ).add_to(m)

            # Buffer EPS casco urbano
            geojson_data = st.session_state["geojson_data"].get("casco_urbano", {})
            if isinstance(geojson_data, gpd.GeoDataFrame) and not geojson_data.empty:
                folium.GeoJson(
                    geojson_data,
                    name="Buffer_EPS_casco_urbano",
                    style_function=lambda feature: {
                        "fillColor": "#A9A9A9",
                        "color": "black",
                        "weight": 1,
                        "fillOpacity": 0.4
                    }
                ).add_to(m)

            # Buffer EPS casco no urbano
            geojson_data = st.session_state["geojson_data"].get("casco_no_urbano", {})
            if isinstance(geojson_data, gpd.GeoDataFrame) and not geojson_data.empty:
                def buffer_style(feature):
                    layer_value = feature["properties"].get("layer", "")
                    color = "#FFFF00" if layer_value == "A 2.5 Km del Área con población servida de la EPS" else "#87CEEB"
                    return {
                        "fillColor": color,
                        "color": "black",
                        "weight": 1,
                        "fillOpacity": 0.4
                    }
                m.add_geojson(
                    geojson_data,
                    layer_name="Buffer EPS Lambayeque",
                    style_function=buffer_style
                ).add_to(m)

            # Datass
            geojson_data = st.session_state["geojson_data"].get("datass", {})
            layer_datass = folium.FeatureGroup(name=f"DATASS: {selected_eps}")
            if isinstance(geojson_data, gpd.GeoDataFrame) and not geojson_data.empty:
                # Verifica si el GeoDataFrame tiene geometrías de tipo Point
                points = geojson_data[geojson_data.geometry.type == "Point"]
                
                # Filtrar puntos según la selección de EPS
                puntos_filtrados = points[points["EPS1"] == selected_eps]
                
                for _, row in puntos_filtrados.iterrows():
                    lon, lat = row.geometry.x, row.geometry.y
                    
                    # Añadir un CircleMarker para cada punto filtrado
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=3,  # Tamaño del marcador
                        color="blue",
                        fill=True,
                        fill_color="blue",
                        fill_opacity=0.6,
                        popup=row.get("nomprest", "Sin nombre")  # Cambia "nombre" según tu GeoJSON
                    ).add_to(layer_datass)

            layer_datass.add_to(m)

            # Censo
            geojson_data = st.session_state["geojson_data"].get("censo", {})
            layer_censo = folium.FeatureGroup(name=f"CENSO: {selected_eps}")
            if isinstance(geojson_data, gpd.GeoDataFrame) and not geojson_data.empty:
                # Verifica si el GeoDataFrame tiene geometrías de tipo Point
                points = geojson_data[geojson_data.geometry.type == "Point"]
                
                # Filtrar puntos según la selección de EPS
                puntos_filtrados = points[points["EPS1"] == selected_eps]
                
                for _, row in puntos_filtrados.iterrows():
                    lon, lat = row.geometry.x, row.geometry.y
                    
                    # Añadir un CircleMarker para cada punto filtrado
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=3,  # Tamaño del marcador
                        color="orange",
                        fill=True,
                        fill_color="orange",
                        fill_opacity=0.6,
                        popup=row.get("NOMCCPP", "Sin nombre")  # Cambia "nombre" según tu GeoJSON
                    ).add_to(layer_censo)

            layer_censo.add_to(m)


            # Puntos con filtros
            layer_top_puntos = folium.FeatureGroup(name=f"SUNASS: {selected_eps}")
            for idx, row in enumerate(df_filtered.iterrows()):
                # Si el índice es menor que 10, color rojo; de lo contrario, verde
                color = "red" if idx <= top_n else "green"
                radius = 6 if idx <= top_n else 4
                
                folium.CircleMarker(
                    location=[row[1]["LATITUD"], row[1]["LONGITUD"]],
                    radius=radius,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7,
                    popup=row[1]["Prestador"]
                ).add_to(layer_top_puntos)

            layer_top_puntos.add_to(m)


            # Control de capas
            folium.LayerControl().add_to(m)
            
            # Agregar el botón de pantalla completa
            Fullscreen(position='topright', title='Expandir', title_cancel='Salir', force_separate_button=True).add_to(m)

            folium_static(m)


    with st.expander("📋 Ver tabla de ranking", expanded=False):
        st.dataframe(df_top)
        
    # 🔹 Agregando el gráfico de radar debajo del mapa
    st.subheader("📊 Comparación entre Prestadores")
    radar_fig = generate_radar_chart(df_top, sections)  # Función que genera el gráfico
    st.plotly_chart(radar_fig, use_container_width=True)


        # Mostrar la ecuación con los pesos actualizados dinámicamente
    st.subheader("🧮 Fórmula de Cálculo del Ranking")
    formula = generate_formula(st.session_state.weights)
    st.latex(formula)

if __name__ == "__main__":
    main()
