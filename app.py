from flask import Flask, render_template, request, send_file
import pandas as pd
import plotly.express as px
import plotly.utils
import json
import os
import io  # Para manejar archivos en memoria
from dotenv import load_dotenv

def crear_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXCEL_PATH = os.path.join(BASE_DIR, "static", "df.xlsx")

    def cargar_datos_y_grafico(programa=None, modelo="Probabilidad_RANDOM FOREST", rango=(0, 100)):
        try:
            df = pd.read_excel(EXCEL_PATH)
        except FileNotFoundError:
            print(f"Error: El archivo Excel no se encontró en {EXCEL_PATH}")
            return {
                "graphJSON": None,
                "columnas": [],
                "registros": 0,
                "df_filtrado": pd.DataFrame()
            }
        except Exception as e:
            print(f"Error al leer el archivo Excel: {e}")
            return {
                "graphJSON": None,
                "columnas": [],
                "registros": 0,
                "df_filtrado": pd.DataFrame()
            }

        df = df.dropna(subset=["Edad", modelo, "DescRF_Programa"])

        if programa and programa != "Todos":
            df = df[df["DescRF_Programa"] == programa]

        df = df[(df[modelo] >= rango[0]) & (df[modelo] <= rango[1])]

        if df.empty:
            return {
                "graphJSON": None,
                "columnas": [],
                "registros": 0,
                "df_filtrado": pd.DataFrame()
            }

        df["emoji"] = "✈️"

        fig = px.scatter(
            df,
            x="Edad",
            y=modelo,
            text="emoji",
            color="DescRF_Programa",
            title=f"Predicción ({modelo}) por Edad",
            custom_data=["DescRF_Nombre_Estudiante", "Edad", "DescRF_Programa", modelo]
        )

        fig.update_traces(
            textposition='top center',
            marker=dict(size=1, color='rgba(0,0,0,0)'),
            hovertemplate="<b>Estudiante:</b> %{customdata[0]}<br>" +
                          "<b>Edad:</b> %{customdata[1]}<br>" +
                          "<b>Programa:</b> %{customdata[2]}<br>" +
                          f"<b>{modelo}:</b> %{{customdata[3]}}%" +
                          "<extra></extra>"
        )

        fig.update_layout(
            yaxis_title=f"{modelo} (%)",
            xaxis_title="Edad",
            showlegend=True,
            hovermode="closest"
        )

        return {
            "graphJSON": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder),
            "columnas": df.columns.tolist(),
            "registros": len(df),
            "df_filtrado": df
        }

    @app.route("/", methods=["GET", "POST"])
    def index():
        try:
            df_original = pd.read_excel(EXCEL_PATH)
        except FileNotFoundError:
            return "Error: El archivo df.xlsx no se encontró. Asegúrate de que esté en la carpeta 'static'.", 500
        except Exception as e:
            return f"Error al cargar el archivo Excel: {e}", 500

        programas = sorted(df_original["DescRF_Programa"].dropna().unique())
        programas.insert(0, "Todos")

        programa_seleccionado = "Todos"
        modelo_seleccionado = "Probabilidad_RANDOM FOREST"
        prob_min_seleccionada = 0
        prob_max_seleccionada = 100

        if request.method == "POST":
            programa_seleccionado = request.form.get("programa")
            modelo_seleccionado = request.form.get("modelo", "Probabilidad_RANDOM FOREST")
            try:
                prob_min_seleccionada = float(request.form.get("prob_min", 0))
                prob_max_seleccionada = float(request.form.get("prob_max", 100))
            except ValueError:
                print("Advertencia: Los valores de probabilidad no son válidos. Usando por defecto.")
                prob_min_seleccionada = 0
                prob_max_seleccionada = 100

        data = cargar_datos_y_grafico(
            programa_seleccionado,
            modelo_seleccionado,
            (prob_min_seleccionada, prob_max_seleccionada)
        )

        return render_template(
            "index.html",
            programas=programas,
            programa=programa_seleccionado,
            modelo=modelo_seleccionado,
            prob_min=prob_min_seleccionada,
            prob_max=prob_max_seleccionada,
            graphJSON=data["graphJSON"],
            columnas=data["columnas"],
            registros=data["registros"],
            dataFiltrada=data["df_filtrado"].to_dict(orient='records')
        )

    @app.route("/descargar_excel", methods=["POST"])
    def descargar_excel():
        programa = request.form.get("programa")
        modelo = request.form.get("modelo", "Probabilidad_RANDOM FOREST")
        try:
            prob_min = float(request.form.get("prob_min", 0))
            prob_max = float(request.form.get("prob_max", 100))
        except ValueError:
            prob_min = 0
            prob_max = 100

        data = cargar_datos_y_grafico(programa, modelo, (prob_min, prob_max))
        df_filtrado = data["df_filtrado"]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_filtrado.to_excel(writer, index=False, sheet_name="Filtrado")
        output.seek(0)

        return send_file(
            output,
            download_name="df_filtrado.xlsx",
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    return app

if __name__ == "__main__":
    load_dotenv()
    app_instance = crear_app()
    app_instance.run(host='0.0.0.0', debug=True)
