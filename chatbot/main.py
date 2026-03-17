import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_MADRID = ZoneInfo("Europe/Madrid")

import boto3
import faiss
import numpy as np
from dotenv import load_dotenv

load_dotenv()

S3_BUCKET = os.getenv("S3_BUCKET")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "eu-west-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-micro-v1:0")
EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBED_DIMENSIONS = 256
TOP_K = 5

INDEX_PATH = "/tmp/index.faiss"
CHUNKS_PATH = "/tmp/chunks.json"

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
}

# Cache entre invocaciones de Lambda
_index = None
_chunks = None


def load_index():
    global _index, _chunks
    if _index is not None:
        return
    s3 = boto3.client("s3")
    s3.download_file(S3_BUCKET, "rag/index.faiss", INDEX_PATH)
    s3.download_file(S3_BUCKET, "rag/chunks.json", CHUNKS_PATH)
    _index = faiss.read_index(INDEX_PATH)
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        _chunks = json.load(f)
    print(f"Índice cargado: {_index.ntotal} vectores, {len(_chunks)} chunks")


def load_weather() -> dict:
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=S3_BUCKET, Key="weather.json")
    return json.loads(obj["Body"].read())


def classify_question(question: str) -> bool:
    """Devuelve True si la pregunta es sobre meteorología/tiempo, False si es técnica."""
    bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    prompt = (
        "¿Es esta pregunta sobre el tiempo meteorológico o la predicción del tiempo? "
        "Responde únicamente 'si' o 'no'.\n\n"
        f"Pregunta: {question}"
    )
    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 5, "temperature": 0},
        }),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    answer = result["output"]["message"]["content"][0]["text"].strip().lower()
    return answer.startswith("si") or answer.startswith("sí")


def embed(text: str) -> np.ndarray:
    bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    response = bedrock.invoke_model(
        modelId=EMBED_MODEL_ID,
        body=json.dumps({"inputText": text, "dimensions": EMBED_DIMENSIONS, "normalize": True}),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return np.array([result["embedding"]], dtype="float32")


def search(vector: np.ndarray) -> list[dict]:
    scores, indices = _index.search(vector, TOP_K)
    return [
        {**_chunks[idx], "score": float(score)}
        for score, idx in zip(scores[0], indices[0])
        if idx >= 0
    ]


def generate_answer(question: str, chunks: list[dict]) -> str:
    context = "\n\n---\n\n".join(
        f"[{c['source']} — {c['section']}]\n{c['text']}"
        for c in chunks
    )
    prompt = (
        "Eres Nuwe, un asistente técnico que explica cómo está construido el proyecto meteo-blog, "
        "una aplicación meteorológica serverless desplegada en AWS.\n\n"
        "Tu objetivo es explicar decisiones de diseño, arquitectura y funcionamiento interno: "
        "por qué se eligió cada tecnología, cómo interactúan los componentes, qué hace cada parte del código. "
        "NO des instrucciones de instalación, despliegue ni comandos para ejecutar el proyecto.\n\n"
        "Usa ÚNICAMENTE el siguiente contexto extraído del código y documentación "
        "del proyecto para responder. Si la respuesta no está en el contexto, dilo claramente.\n\n"
        f"CONTEXTO:\n{context}\n\n"
        f"PREGUNTA: {question}\n\n"
        "Responde en español de forma clara y concisa, orientado a explicar el diseño técnico."
    )
    bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 500, "temperature": 0.2},
        }),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"].strip()


def generate_weather_answer(question: str, weather: dict) -> str:
    context = json.dumps(weather, ensure_ascii=False, indent=2)
    hoy = datetime.now(TZ_MADRID).strftime("%A %d de %B de %Y")
    prompt = (
        "Eres Nuwe, un asistente meteorológico. Tienes los datos de predicción del tiempo "
        "para las próximas comunidades autónomas de España.\n\n"
        f"Hoy es {hoy}.\n\n"
        f"DATOS METEOROLÓGICOS:\n{context}\n\n"
        f"PREGUNTA: {question}\n\n"
        "Responde en español de forma clara y concisa usando únicamente los datos proporcionados."
    )
    bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 500, "temperature": 0.2},
        }),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"].strip()


def lambda_handler(event, context):
    # CORS preflight
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        body = json.loads(event.get("body") or "{}")
        question = body.get("pregunta", "").strip()
        if not question:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Falta el campo 'pregunta'"}),
            }

        es_meteo = classify_question(question)

        if es_meteo:
            weather = load_weather()
            answer = generate_weather_answer(question, weather)
        else:
            load_index()
            chunks = search(embed(question))
            answer = generate_answer(question, chunks)

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"respuesta": answer}, ensure_ascii=False),
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Error interno del servidor"}),
        }


if __name__ == "__main__":
    # Prueba local
    load_dotenv(f"../fetcher/.env")
    event = {"requestContext": {"http": {"method": "POST"}}, "body": json.dumps({"pregunta": "¿Cómo funciona la Lambda del fetcher?"})}
    result = lambda_handler(event, None)
    print(json.loads(result["body"])["respuesta"])
