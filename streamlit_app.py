import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime, time
import itertools

st.set_page_config(layout="wide")
st.title("Mapa Interactivo de Desplazamientos y Paradas de Vehículos")

st.write("""
Sube uno o varios archivos Excel exportados del sistema de vehículos.  
Filtra por vehículo, fechas o texto. Cada punto muestra los detalles asociados.
""")

def parse_fecha(dia):
    try:
        return dia.split(" ",1)[1] if " " in dia else dia
    except Exception:
        return ""

def concat_fecha_hora(row):
    fecha_str = str(row["Fecha"])
    hora = row["Hora de inicio"]
    if isinstance(hora, time):
        hora_str = hora.strftime('%H:%M:%S')
    else:
        hora_str = "00:00:00"
    try:
        return datetime.strptime(fecha_str + " " + hora_str, "%d/%m/%y %H:%M:%S")
    except Exception:
        return pd.NaT

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
        df_total.columns = [c.strip() for c in df_total.columns]
        
        # --- Normalizar fecha/hora ---
        df_total["Fecha"] = df_total["Día"].astype(str).apply(parse_fecha)
        df_total["fechahora"] = df_total.apply(concat_fecha_hora, axis=1)

        vehiculos = df_total['Activo'].dropna().unique()
        fechas_validas = df_total['fechahora'].dropna()
        
        slider_ok = False
        if len(fechas_validas) >= 2 and fechas_validas.dtype.kind == 'M':
            try:
                fecha_min_pd = pd.to_datetime(fechas_validas.min())
                fecha_max_pd = pd.to_datetime(fechas_validas.max())
                fecha_min = fecha_min_pd.to_pydatetime()
                fecha_max = fecha_max_pd.to_pydatetime()
                if pd.isnull(fecha_min) or pd.isnull(fecha_max):
                    raise ValueError("Extremos nulos")
                slider_ok = True
            except Exception as e:
                st.error(f"Error con las fechas para el slider: {e}")
                slider_ok = False
        
        if slider_ok:
            st.sidebar.header("Filtros")
            filtro_vehiculo = st.sidebar.multiselect('Vehículo', vehiculos, default=list(vehiculos))
            try:
                rango_fecha = st.sidebar.slider(
                    'Rango de fechas',
                    min_value=fecha_min, max_value=fecha_max,
                    value=(fecha_min, fecha_max),
                    format="YYYY-MM-DD HH:mm"
                )
            except Exception as e:
                st.error(f"Error en el slider de fechas: {e}")
                rango_fecha = (fecha_min, fecha_max)
            texto = st.sidebar.text_input('Búsqueda libre (dirección, vehículo...)', '')
        
            # Filtrado
            df_filtro = df_total[
                (df_total['Activo'].isin(filtro_vehiculo)) &
                (df_total['fechahora'] >= rango_fecha[0]) & (df_total['fechahora'] <= rango_fecha[1])
            ]
            if texto:
                df_filtro = df_filtro[df_filtro.apply(lambda row: texto.lower() in str(row).lower(), axis=1)]
        else:
            st.warning('No hay fechas válidas para filtrar. Comprueba que los Excels tienen datos y el formato es correcto.')
            df_filtro = pd.DataFrame()  # vacío

        # --- SLIDER ACUMULATIVO TEMPORAL ---
        df_filtro = df_filtro.sort_values("fechahora").reset_index(drop=True)
        total_puntos = len(df_filtro)
        if total_puntos > 0:
            st.sidebar.markdown("---")
            st.sidebar.markdown("### Reproducción temporal")
            idx_slider = st.sidebar.slider(
                "Mostrar puntos hasta el número:",
                min_value=1,
                max_value=total_puntos,
                value=total_puntos,
                step=1,
                help="Mueve el slider para ver la evolución temporal de los puntos en el mapa."
            )
            df_play = df_filtro.iloc[:idx_slider]
        else:
            df_play = df_filtro  # vacío

        # ---------- MARCADORES DE COLORES POR VEHÍCULO ----------
        st.subheader("Vista en Mapa")
        if not df_play.empty:
            # Asigna color único a cada vehículo filtrado
            colores_base = ["blue", "red", "green", "purple", "orange", "darkred", "lightred", "beige", "darkblue", "darkgreen"]
            vehiculos_unicos = list(df_play['Activo'].dropna().unique())
            colores = dict(zip(vehiculos_unicos, itertools.cycle(colores_base)))

            m = folium.Map(location=[
                df_play["Latitud de inicio"].astype(float).mean() / 1e6,
                df_play["Longitud de inicio"].astype(float).mean() / 1e6
            ], zoom_start=10)

            for _, row in df_play.iterrows():
                lat = row["Latitud de inicio"] / 1e6
                lon = row["Longitud de inicio"] / 1e6
                vehiculo = row['Activo']
                color_icono = colores.get(vehiculo, "blue")
                # Hora: extrae sólo la parte de la hora, nunca lanza error
                hora_inicio = "-"
                if pd.notnull(row['Hora de inicio']):
                    h = row['Hora de inicio']
                    if isinstance(h, time):
                        hora_inicio = h.strftime("%H:%M:%S")
                    else:
                        hora_inicio = str(h)
                popup = f"""
                <b>Vehículo:</b> {vehiculo}<br>
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
                    icon=folium.Icon(color=color_icono, icon="car", prefix="fa")
                ).add_to(m)
            st_folium(m, width=1200, height=750)
        else:
            st.warning('No hay datos para esos filtros.')

        # Descargar CSV filtrado
        st.markdown("### Descargar datos filtrados")
        csv = df_play.to_csv(index=False).encode('utf-8')
        st.download_button("Descargar CSV", data=csv, file_name='datos_filtrados.csv', mime='text/csv')
else:
    st.info("Sube al menos un archivo Excel para empezar.")
