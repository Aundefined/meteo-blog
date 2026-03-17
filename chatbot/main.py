import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3
import faiss
import numpy as np
from dotenv import load_dotenv

load_dotenv()

TZ_MADRID = ZoneInfo("Europe/Madrid")

S3_BUCKET = os.getenv("S3_BUCKET")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "eu-west-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-micro-v1:0")
EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBED_DIMENSIONS = 256
TOP_K = 5
MAX_HISTORY = 20  # últimos 20 mensajes (10 turnos)

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


def load_conversation(session_id: str) -> list[dict]:
    s3 = boto3.client("s3")
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=f"conversations/{session_id}.json")
        return json.loads(obj["Body"].read())
    except s3.exceptions.NoSuchKey:
        return []
    except Exception:
        return []


def save_conversation(session_id: str, conversation: list[dict]) -> None:
    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"conversations/{session_id}.json",
        Body=json.dumps(conversation, ensure_ascii=False, indent=2),
        ContentType="application/json",
    )


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


def generate_answer(question: str, history: list[dict], chunks: list[dict], weather: dict, session_id: str = "") -> str:
    rag_context = "\n\n---\n\n".join(
        f"[{c['source']} — {c['section']}]\n{c['text']}"
        for c in chunks
    )
    weather_context = json.dumps(weather, ensure_ascii=False, indent=2)
    hoy = datetime.now(TZ_MADRID).strftime("%A %d de %B de %Y")

    system_prompt = (
        "Eres Nuwe, un asistente del proyecto meteo-blog, una aplicación meteorológica serverless desplegada en AWS.\n\n"
        "Puedes responder dos tipos de preguntas:\n"
        "- Sobre la arquitectura y el código del proyecto: usa el CONTEXTO TÉCNICO.\n"
        "- Sobre el tiempo meteorológico en España: usa los DATOS METEOROLÓGICOS.\n"
        "Usa únicamente la fuente relevante para cada pregunta. "
        "Si la respuesta no está en ninguna fuente, dilo claramente.\n\n"
        "Cuando respondas sobre el tiempo, ten en cuenta:\n"
        "- Los datos provienen de AEMET, la agencia meteorológica oficial de España. Son datos oficiales y completamente válidos.\n"
        "- Responde siempre con los datos exactos que tienes: temperaturas, probabilidad de lluvia, estado del cielo.\n"
        "- No añadas disclaimers ni recomendaciones de consultar otras fuentes. No son necesarios.\n"
        "- No expreses dudas sobre la validez de los datos.\n\n"
        f"Hoy es {hoy}.\n\n"
        f"CONTEXTO TÉCNICO:\n{rag_context}\n\n"
        f"DATOS METEOROLÓGICOS:\n{weather_context}"
    )

    # El contexto va como primer par user/assistant para que el historial pueda seguir
    messages = [
        {"role": "user", "content": [{"text": system_prompt}]},
        {"role": "assistant", "content": [{"text": "Entendido, estoy listo para responder."}]},
    ]

    # Historial reciente (últimos MAX_HISTORY mensajes)
    for msg in history[-MAX_HISTORY:]:
        messages.append({
            "role": msg["role"],
            "content": [{"text": msg["content"]}],
        })

    messages.append({"role": "user", "content": [{"text": question}]})

    if S3_BUCKET and session_id:
        try:
            boto3.client("s3").put_object(
                Bucket=S3_BUCKET,
                Key=f"debug/{session_id}.json",
                Body=json.dumps(messages, ensure_ascii=False, indent=2),
                ContentType="application/json",
            )
        except Exception as e:
            print(f"Error guardando debug: {e}")

    bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({
            "messages": messages,
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
        session_id = body.get("session_id", "").strip()

        if not question:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Falta el campo 'pregunta'"}),
            }
        if not session_id:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Falta el campo 'session_id'"}),
            }

        load_index()
        chunks = search(embed(question))
        weather = load_weather()
        history = load_conversation(session_id)

        answer = generate_answer(question, history, chunks, weather, session_id)

        history.append({"role": "user", "content": question, "timestamp": datetime.now(TZ_MADRID).isoformat()})
        history.append({"role": "assistant", "content": answer, "timestamp": datetime.now(TZ_MADRID).isoformat()})
        save_conversation(session_id, history)

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
    load_dotenv("../fetcher/.env")
    event = {"requestContext": {"http": {"method": "POST"}}, "body": json.dumps({"pregunta": "¿Cómo funciona la Lambda del fetcher?", "session_id": "test-session-local"})}
    result = lambda_handler(event, None)
    print(json.loads(result["body"])["respuesta"])
