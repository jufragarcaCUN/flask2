from flask import Flask, render_template, request
import pandas as pd
import plotly.express as px
import plotly.utils
import json
import os
from dotenv import load_dotenv

def crear_app():
    """
    Crea y configura la instancia de la aplicación Flask.
    Esta función encapsula toda la lógica de la aplicación, incluyendo rutas y funciones auxiliares,
    para que pueda ser importada y ejecutada por servidores WSGI (como Gunicorn en Render.com).
    """
    app = Flask(__name__)

    # Define la ruta base del directorio donde se encuentra este script.
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # Construye la ruta completa al archivo Excel, asumiendo que está en la carpeta 'static'.
    EXCEL_PATH = os.path.join(BASE_DIR, "static", "df.xlsx")

    def cargar_datos_y_grafico(programa=None, modelo="Probabilidad_RANDOM FOREST", rango=(0, 100)):
        """
        Carga datos desde el archivo Excel especificado, los filtra según los parámetros,
        y genera un gráfico interactivo usando Plotly Express.

        Args:
            programa (str, optional): Nombre del programa para filtrar los datos.
                                      Si es None, no se filtra por programa. Por defecto es None.
            modelo (str, optional): Nombre de la columna que se utilizará como eje Y en el gráfico
                                    y para el filtrado por rango. Por defecto es "Probabilidad_RANDOM FOREST".
            rango (tuple, optional): Una tupla (min_valor, max_valor) para filtrar los datos
                                     en la columna 'modelo'. Por defecto es (0, 100).

        Returns:
            dict: Un diccionario que contiene:
                  - "graphJSON": La representación JSON del gráfico Plotly, lista para incrustar en HTML.
                  - "columnas": Una lista de los nombres de las columnas del DataFrame filtrado.
                  - "registros": El número de filas (registros) en el DataFrame filtrado.
                  - "df_filtrado": El DataFrame de Pandas resultante después de aplicar todos los filtros.
                                   (Nota: este objeto no es serializable directamente a JSON en Flask para HTML,
                                   pero se puede usar internamente si es necesario).
        """
        try:
            df = pd.read_excel(EXCEL_PATH)
        except FileNotFoundError:
            # En caso de que el archivo Excel no se encuentre, imprime un error y retorna datos vacíos.
            print(f"Error: El archivo Excel no se encontró en {EXCEL_PATH}")
            return {
                "graphJSON": None,
                "columnas": [],
                "registros": 0,
                "df_filtrado": pd.DataFrame()
            }
        except Exception as e:
            # Captura cualquier otro error al leer el Excel
            print(f"Error al leer el archivo Excel: {e}")
            return {
                "graphJSON": None,
                "columnas": [],
                "registros": 0,
                "df_filtrado": pd.DataFrame()
            }


        # Elimina filas donde "Edad", la columna del modelo o "DescRF_Programa" tengan valores nulos.
        df = df.dropna(subset=["Edad", modelo, "DescRF_Programa"])

        # Aplica el filtro por el nombre del programa si se ha especificado uno.
        if programa:
            df = df[df["DescRF_Programa"] == programa]

        # Aplica el filtro por el rango de valores para la columna del modelo.
        df = df[(df[modelo] >= rango[0]) & (df[modelo] <= rango[1])]

        # Si el DataFrame queda vacío después de aplicar los filtros, retorna un conjunto de datos vacío.
        if df.empty:
            return {
                "graphJSON": None,
                "columnas": [],
                "registros": 0,
                "df_filtrado": pd.DataFrame()
            }

        # Añade una columna "emoji" para usar como marcador visual en el gráfico.
        df["emoji"] = "✈️"

        # Crea el gráfico de dispersión utilizando Plotly Express.
        fig = px.scatter(
            df,
            x="Edad",
            y=modelo,
            text="emoji", # Muestra el emoji en lugar de los puntos por defecto.
            color="DescRF_Programa", # Colorea los puntos según el programa.
            title=f"Predicción ({modelo}) por Edad", # Título del gráfico.
            # custom_data permite que estos campos estén disponibles al pasar el ratón por encima del punto.
            custom_data=["DescRF_Nombre_Estudiante", "Edad", "DescRF_Programa", modelo]
        )

        # Actualiza las propiedades visuales de los puntos (trazas) en el gráfico.
        fig.update_traces(
            textposition='top center', # Posiciona el emoji por encima del punto.
            marker=dict(size=1, color='rgba(0,0,0,0)'), # Hace el marcador subyacente casi invisible.
            # Define la plantilla personalizada para la información que aparece al pasar el ratón.
            hovertemplate="<b>Estudiante:</b> %{customdata[0]}<br>" +
                          "<b>Edad:</b> %{customdata[1]}<br>" +
                          "<b>Programa:</b> %{customdata[2]}<br>" +
                          f"<b>{modelo}:</b> %{{customdata[3]}}%" +
                          "<extra></extra>" # Elimina la información adicional por defecto de Plotly.
        )

        # Configura el diseño general del gráfico, incluyendo títulos de ejes y leyenda.
        fig.update_layout(
            yaxis_title=f"{modelo} (%)", # Título del eje Y.
            xaxis_title="Edad", # Título del eje X.
            showlegend=True, # Muestra la leyenda para los colores del programa.
            hovermode="closest" # Mejora la experiencia de hover para seleccionar puntos.
        )

        # Retorna un diccionario con el gráfico en formato JSON y otros datos relevantes.
        return {
            "graphJSON": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder),
            "columnas": df.columns.tolist(),
            "registros": len(df),
            "df_filtrado": df
        }

    @app.route("/", methods=["GET", "POST"])
    def index():
        """
        Esta es la ruta principal de la aplicación. Maneja tanto las solicitudes GET
        (cuando la página se carga por primera vez) como las solicitudes POST
        (cuando el usuario envía el formulario de filtros).
        """
        try:
            # Intenta cargar el DataFrame original para obtener la lista de programas.
            df_original = pd.read_excel(EXCEL_PATH)
        except FileNotFoundError:
            # Si el archivo no se encuentra, devuelve un mensaje de error HTTP 500.
            return "Error: El archivo df.xlsx no se encontró. Asegúrate de que esté en la carpeta 'static'.", 500
        except Exception as e:
            # Captura otros errores al leer el Excel
            return f"Error al cargar el archivo Excel: {e}", 500

        # Obtiene una lista de programas únicos del DataFrame original y los ordena.
        programas = sorted(df_original["DescRF_Programa"].dropna().unique())

        # Define los valores por defecto para los filtros del formulario.
        programa_seleccionado = None
        modelo_seleccionado = "Probabilidad_RANDOM FOREST"
        prob_min_seleccionada = 0
        prob_max_seleccionada = 100

        # Si la solicitud es POST, significa que el usuario ha enviado el formulario.
        if request.method == "POST":
            # Obtiene los valores de los campos del formulario.
            programa_seleccionado = request.form.get("programa")
            modelo_seleccionado = request.form.get("modelo", "Probabilidad_RANDOM FOREST")
            try:
                # Intenta convertir los valores de probabilidad a números flotantes.
                prob_min_seleccionada = float(request.form.get("prob_min", 0))
                prob_max_seleccionada = float(request.form.get("prob_max", 100))
            except ValueError:
                # Si los valores no son numéricos válidos, se restablecen a los valores por defecto.
                print("Advertencia: Los valores de probabilidad min/max no son válidos. Usando valores por defecto.")
                prob_min_seleccionada = 0
                prob_max_seleccionada = 100

        # Llama a la función auxiliar para cargar los datos y generar el gráfico
        # con los filtros aplicados (ya sean por defecto o los del formulario).
        data = cargar_datos_y_grafico(
            programa_seleccionado,
            modelo_seleccionado,
            (prob_min_seleccionada, prob_max_seleccionada)
        )

        # Renderiza la plantilla HTML 'index.html', pasando todos los datos necesarios
        # para que la página web se muestre dinámicamente.
        return render_template(
            "index.html",
            programas=programas, # Lista de todos los programas para el desplegable.
            programa=programa_seleccionado, # El programa actualmente seleccionado.
            modelo=modelo_seleccionado, # El modelo actualmente seleccionado.
            prob_min=prob_min_seleccionada, # La probabilidad mínima seleccionada.
            prob_max=prob_max_seleccionada, # La probabilidad máxima seleccionada.
            graphJSON=data["graphJSON"], # El gráfico Plotly en formato JSON.
            columnas=data["columnas"], # Nombres de las columnas del DF filtrado.
            registros=data["registros"], # Número de registros del DF filtrado.
            # Convierte el DataFrame filtrado a un formato de lista de diccionarios,
            # lo cual es fácil de consumir en el HTML/JavaScript para tablas o listados.
            dataFiltrada=data["df_filtrado"].to_dict(orient='records')
        )

    # Al final de la función crear_app(), se debe retornar la instancia de la aplicación Flask.
    # Esta es la aplicación que Gunicorn (o el servidor WSGI) importará y ejecutará.
    return app

# Este bloque se ejecuta SOLAMENTE cuando el script se corre directamente (ej. 'python app.py').
# NO se ejecuta cuando la aplicación es importada por un servidor WSGI como Gunicorn.
# Es crucial que NO esté indentado dentro de ninguna función.
if __name__ == "__main__":
    # Llama a la función crear_app() para obtener la instancia de la aplicación Flask configurada.
    app_instance = crear_app()
    # Ejecuta la aplicación.
    # 'host='0.0.0.0'' hace que la aplicación sea accesible desde cualquier dirección IP,
    # lo cual es necesario en entornos de servidor.
    # 'debug=True' habilita el modo de depuración (útil durante el desarrollo para ver errores).
    app_instance.run(host='0.0.0.0', debug=True)