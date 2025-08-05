import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from io import BytesIO
from datetime import datetime

st.set_page_config(layout="wide")
st.title("Mapa Interactivo de Desplazamientos y Paradas de Vehículos")

st.write("""
Sube uno o varios archivos Excel exportados del sistema de vehículos.  
Filtra por vehículo, fechas o texto. Cada punto muestra los detalles asociados.
""")

uploaded_files = st.file_uploader("Sube tus archivos Excel", accept_multiple_files=True, type=["xlsx", "xls"])

if uploaded_files:
    dfs = []
    for f in uploaded_files:
        try:
            df = pd.read_excel(f)
            dfs.append(df)
        except Exception as e:
            st.error(f"Error cargando {f.name}: {e}")

    if dfs:
        df_total = pd.concat(dfs, ignore_index=True)
        # Normalizar nombres de columnas por si acaso
        df_total.columns = [c.strip() for c in df_total.columns]
        
        # --- Normalizar fecha/hora ---
        def parse_fecha(dia):
            # Quita el día de la semana y deja solo la fecha
            try:
                return dia.split(" ",1)[1] if " " in dia else dia
            except Exception:
                return ""
        df_total["Fecha"] = df_total["Día"].astype(str).apply(parse_fecha)
        
        def concat_fecha_hora(row):
            f = str(row["Fecha"])
            h = str(row["Hora de inicio"])
            if "nan" in f.lower() or "nan" in h.lower():
                return None
            return f"{f} {h}"
        df_total["fechahora"] = df_total.apply(concat_fecha_hora, axis=1)
        df_total["fechahora"] = pd.to_datetime(df_total["fechahora"], format="%d/%m/%y %H:%M:%S", errors="coerce")

        vehiculos = df_total['Activo'].dropna().unique()
        fecha_min = df_total['fechahora'].min()
        fecha_max = df_total['fechahora'].max()

        st.sidebar.header("Filtros")
        filtro_vehiculo = st.sidebar.multiselect('Vehículo', vehiculos, default=list(vehiculos))
        rango_fecha = st.sidebar.slider(
            'Rango de fechas',
            min_value=fecha_min, max_value=fecha_max,
            value=(fecha_min, fecha_max),
            format="YYYY-MM-DD HH:mm"
        )
        texto = st.sidebar.text_input('Búsqueda libre (dirección, vehículo...)', '')

        # Filtrado
        df_filtro = df_total[
            (df_total['Activo'].isin(filtro_vehiculo)) &
            (df_total['fechahora'] >= rango_fecha[0]) & (df_total['fechahora'] <= rango_fecha[1])
        ]
        if texto:
            df_filtro = df_filtro[df_filtro.apply(lambda row: texto.lower() in str(row).lower(), axis=1)]

        # Construir mapa
        st.subheader("Vista en Mapa")
        if not df_filtro.empty:
            m = folium.Map(location=[
                df_filtro["Latitud de inicio"].astype(float).mean() / 1e6,
                df_filtro["Longitud de inicio"].astype(float).mean() / 1e6
            ], zoom_start=10)

            for _, row in df_filtro.iterrows():
                lat = row["Latitud de inicio"] / 1e6
                lon = row["Longitud de inicio"] / 1e6
                # Hora: extrae sólo la parte de la hora, nunca lanza error
                hora_inicio = "-"
                if pd.notnull(row['Hora de inicio']):
                    h = str(row['Hora de inicio'])
                    if " " in h:
                        hora_inicio = h.split(" ")[-1]
                    else:
                        hora_inicio = h
                popup = f"""
                <b>Vehículo:</b> {row['Activo']}<br>
                <b>Fecha:</b> {row['Fecha']}<br>
                <b>Hora inicio:</b> {hora_inicio}<br>
                <b>Dirección:</b> {row['Ubicación de inicio']}<br>
                <b>Km inicial:</b> {row['Iniciar cuentakilómetros [km]']}<br>
                <b>Km final:</b> {row['Finalizar cuentakilómetros [km]']}<br>
                <b>Distancia:</b> {row['Distancia [km]']} km
                """
                folium.Marker(
                    [lat, lon],
                    popup=popup,
                    icon=folium.Icon(color="blue", icon="car", prefix="fa")
                ).add_to(m)
            st_folium(m, width=1200, height=750)
        else:
            st.warning('No hay datos para esos filtros.')

        # Descargar CSV filtrado
        st.markdown("### Descargar datos filtrados")
        csv = df_filtro.to_csv(index=False).encode('utf-8')
        st.download_button("Descargar CSV", data=csv, file_name='datos_filtrados.csv', mime='text/csv')
else:
    st.info("Sube al menos un archivo Excel para empezar.")
