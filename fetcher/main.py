import json
import os
import time
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo

TZ_MADRID = ZoneInfo("Europe/Madrid")

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

AEMET_API_KEY = os.getenv("AEMET_API_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")
CLOUDFRONT_DISTRIBUTION_ID = os.getenv("CLOUDFRONT_DISTRIBUTION_ID")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "eu-west-1")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")

AEMET_BASE = "https://opendata.aemet.es/opendata/api"

COMUNIDADES = [
    {"codigo": "and", "nombre": "Andalucía",              "capital": "Sevilla",                "cod_municipio": "41091"},
    {"codigo": "ara", "nombre": "Aragón",                  "capital": "Zaragoza",               "cod_municipio": "50297"},
    {"codigo": "ast", "nombre": "Asturias",                "capital": "Oviedo",                 "cod_municipio": "33044"},
    {"codigo": "bal", "nombre": "Islas Baleares",          "capital": "Palma",                  "cod_municipio": "07040"},
    {"codigo": "ican","nombre": "Canarias",                "capital": "Las Palmas de G.C.",      "cod_municipio": "35016"},
    {"codigo": "cb",  "nombre": "Cantabria",               "capital": "Santander",              "cod_municipio": "39075"},
    {"codigo": "cle", "nombre": "Castilla y León",         "capital": "Valladolid",             "cod_municipio": "47186"},
    {"codigo": "clm", "nombre": "Castilla-La Mancha",      "capital": "Toledo",                 "cod_municipio": "45168"},
    {"codigo": "cat", "nombre": "Cataluña",                "capital": "Barcelona",              "cod_municipio": "08019"},
    {"codigo": "ext", "nombre": "Extremadura",             "capital": "Mérida",                 "cod_municipio": "06083"},
    {"codigo": "gal", "nombre": "Galicia",                 "capital": "Santiago de Compostela", "cod_municipio": "15078"},
    {"codigo": "mad", "nombre": "Comunidad de Madrid",     "capital": "Madrid",                 "cod_municipio": "28079"},
    {"codigo": "mur", "nombre": "Región de Murcia",        "capital": "Murcia",                 "cod_municipio": "30030"},
    {"codigo": "nav", "nombre": "Navarra",                 "capital": "Pamplona",               "cod_municipio": "31201"},
    {"codigo": "rio", "nombre": "La Rioja",                "capital": "Logroño",                "cod_municipio": "26089"},
    {"codigo": "pva", "nombre": "País Vasco",              "capital": "Vitoria-Gasteiz",        "cod_municipio": "01059"},
    {"codigo": "val", "nombre": "Comunitat Valenciana",    "capital": "Valencia",               "cod_municipio": "46250"},
]


def aemet_get(path: str, max_retries: int = 3):
    """
    Llama a AEMET en dos pasos:
    1. GET /opendata/api/{path} → JSON con campo 'datos' (URL)
    2. GET {datos_url} → datos reales en JSON
    Reintenta con backoff exponencial si recibe 429.
    """
    for intento in range(max_retries + 1):
        try:
            r = requests.get(f"{AEMET_BASE}{path}", params={"api_key": AEMET_API_KEY}, timeout=10)
            if r.status_code == 429:
                wait = 10 * (2 ** intento)
                print(f"  429 en {path}, intento {intento + 1}/{max_retries + 1}, esperando {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            datos_url = r.json().get("datos")
            if not datos_url:
                print(f"Sin URL de datos para: {path}")
                return None
            r2 = requests.get(datos_url, timeout=10)
            if r2.status_code == 429:
                wait = 10 * (2 ** intento)
                print(f"  429 en datos URL, intento {intento + 1}/{max_retries + 1}, esperando {wait}s...")
                time.sleep(wait)
                continue
            r2.raise_for_status()
            return r2.json()
        except requests.exceptions.HTTPError as e:
            print(f"Error HTTP AEMET {path}: {e}")
            return None
        except Exception as e:
            print(f"Error AEMET {path}: {e}")
            return None
    print(f"Agotados {max_retries + 1} intentos para {path}")
    return None


def obtener_prediccion_municipio(cod_municipio: str) -> list[dict] | None:
    """Datos numéricos del municipio para los próximos 5 días: temp max/min, prob lluvia, estado cielo."""
    data = aemet_get(f"/prediccion/especifica/municipio/diaria/{cod_municipio}")
    if not data:
        return None
    try:
        hoy = datetime.now(TZ_MADRID).date()
        todos_dias = data[0]["prediccion"]["dia"]
        inicio = next(
            (i for i, d in enumerate(todos_dias) if d.get("fecha", "")[:10] >= str(hoy)),
            0
        )
        dias_raw = todos_dias[inicio:inicio + 5]
        result = []
        for dia in dias_raw:
            print(f"    fecha datos: {dia.get('fecha')}")

            temp = dia.get("temperatura", {})
            temp_max = temp.get("maxima")
            temp_min = temp.get("minima")

            # Probabilidad de precipitación: cogemos el máximo del día
            prob_lluvia = 0
            for franja in dia.get("probPrecipitacion", []):
                try:
                    prob_lluvia = max(prob_lluvia, int(franja.get("value") or 0))
                except (ValueError, TypeError):
                    pass

            # Estado del cielo: preferimos franja diurna "12-24", si no la primera con descripción
            cielo = None
            for franja in dia.get("estadoCielo", []):
                desc = franja.get("descripcion", "").strip()
                if not desc:
                    continue
                if franja.get("periodo") == "12-24":
                    cielo = desc
                    break
                if cielo is None:
                    cielo = desc  # primera válida como fallback

            fecha_str = dia.get("fecha", "")[:10]
            try:
                dia_semana = date.fromisoformat(fecha_str).strftime("%A").lower()
            except ValueError:
                dia_semana = ""

            result.append({
                "fecha": fecha_str,
                "dia_semana": dia_semana,
                "temp_max": temp_max,
                "temp_min": temp_min,
                "prob_lluvia": prob_lluvia,
                "cielo": cielo or "Sin datos",
            })
        return result
    except Exception as e:
        print(f"Error parseando municipio {cod_municipio}: {e}")
        return None


def generar_resumen_bedrock(comunidades: list[dict], manana: bool = False) -> str:
    """Genera un resumen meteorológico global a partir de los datos numéricos de las 17 CC.AA."""
    bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

    lineas = "\n".join(
        f"- {c['nombre']} ({c['capital']}): "
        f"máx {c['temp_max']}°C, mín {c['temp_min']}°C, "
        f"prob. lluvia {c['prob_lluvia']}%, cielo: {c['cielo']}"
        for c in comunidades
        if c["temp_max"] is not None
    )

    _DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
    _MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
              'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    fecha = (datetime.now(TZ_MADRID) + (timedelta(days=1) if manana else timedelta())).date()
    fecha_str = f"{_DIAS[fecha.weekday()]} {fecha.day} de {_MESES[fecha.month - 1]}"
    referencia = f"mañana {fecha_str}" if manana else f"hoy {fecha_str}"
    prompt = (
        f"Eres un meteorólogo español. Estos son los datos meteorológicos de {referencia} "
        "para las capitales de cada comunidad autónoma de España:\n\n"
        f"{lineas}\n\n"
        f"Escribe un resumen general del tiempo en España en 3-4 frases en español. "
        f"Comienza la primera frase con '{referencia.capitalize()}' (incluyendo el día y la fecha). "
        "Sé conciso y destaca cualquier anomalía regional importante (por ejemplo, si llueve "
        "en una zona mientras el resto está despejado, o temperaturas extremas en alguna región). "
        "Responde ÚNICAMENTE con el resumen, sin título ni introducción."
    )

    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 300, "temperature": 0.4},
    }

    print(f"\n--- PROMPT BEDROCK ---\n{prompt}\n--- FIN PROMPT ---\n")

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["output"]["message"]["content"][0]["text"].strip()
    except Exception as e:
        print(f"Error Bedrock: {e}")
        return "No se pudo generar el resumen meteorológico."


def guardar_en_s3(datos: dict) -> None:
    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key="weather.json",
        Body=json.dumps(datos, ensure_ascii=False, indent=2),
        ContentType="application/json",
        CacheControl="max-age=0, no-cache",
    )
    print("weather.json guardado en S3.")


def invalidar_cloudfront() -> None:
    if not CLOUDFRONT_DISTRIBUTION_ID:
        print("CLOUDFRONT_DISTRIBUTION_ID no configurado, saltando invalidación.")
        return
    cf = boto3.client("cloudfront", region_name=AWS_REGION)
    cf.create_invalidation(
        DistributionId=CLOUDFRONT_DISTRIBUTION_ID,
        InvalidationBatch={
            "Paths": {"Quantity": 1, "Items": ["/weather.json"]},
            "CallerReference": str(int(time.time())),
        },
    )
    print("Invalidación CloudFront creada.")


def ejecutar() -> dict:
    print(f"Iniciando fetch - {datetime.now(TZ_MADRID).isoformat()}")

    comunidades_resultado = []

    for ccaa in COMUNIDADES:
        print(f"Procesando {ccaa['nombre']}...")

        dias = obtener_prediccion_municipio(ccaa["cod_municipio"])

        comunidades_resultado.append({
            "nombre": ccaa["nombre"],
            "capital": ccaa["capital"],
            "dias": dias if dias else [],
        })

        time.sleep(4)  # Respetar rate limit de AEMET

    # A partir de las 18h Madrid generamos el resumen para mañana (índice 1)
    manana = datetime.now(TZ_MADRID).hour >= 18
    idx = 1 if manana else 0
    comunidades_dia = [
        {
            "nombre": c["nombre"],
            "capital": c["capital"],
            "temp_max": c["dias"][idx]["temp_max"] if len(c["dias"]) > idx else None,
            "temp_min": c["dias"][idx]["temp_min"] if len(c["dias"]) > idx else None,
            "prob_lluvia": c["dias"][idx]["prob_lluvia"] if len(c["dias"]) > idx else None,
            "cielo": c["dias"][idx]["cielo"] if len(c["dias"]) > idx else "Sin datos",
        }
        for c in comunidades_resultado
    ]

    print(f"Generando resumen con Bedrock ({'mañana' if manana else 'hoy'})...")
    resumen = generar_resumen_bedrock(comunidades_dia, manana=manana)

    datos = {
        "updated_at": datetime.now(TZ_MADRID).strftime("%Y-%m-%dT%H:%M:%S%z"),
        "summary": resumen,
        "comunidades": comunidades_resultado,
    }

    if S3_BUCKET:
        guardar_en_s3(datos)
        invalidar_cloudfront()
    else:
        output_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "weather.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        print(f"weather.json guardado en {output_path}")

    print("Fetch completado.")
    return datos


def lambda_handler(event, context):
    resultado = ejecutar()
    return {"statusCode": 200, "body": f"OK - {len(resultado['comunidades'])} comunidades procesadas"}


if __name__ == "__main__":
    ejecutar()
