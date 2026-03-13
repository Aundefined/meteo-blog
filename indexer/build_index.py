"""
build_index.py — Construye el índice RAG del proyecto meteo-blog.

Chunkea los ficheros del repo, genera embeddings con Bedrock Titan Embed v2,
construye un índice FAISS y lo sube a S3.

Uso:
    conda activate meteo-blog
    cd indexer
    python build_index.py
"""

import json
import os
import re
from pathlib import Path

import boto3
import faiss
import numpy as np
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "fetcher" / ".env")

S3_BUCKET = os.getenv("S3_BUCKET")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "eu-west-1")
EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBED_DIMENSIONS = 256

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Chunkers
# ---------------------------------------------------------------------------

def _first_line(text: str) -> str:
    return text.strip().split("\n")[0][:80]


def chunk_by_headers(text: str, filename: str) -> list[dict]:
    """Divide markdown por secciones (## Título)."""
    chunks = []
    sections = re.split(r"\n(?=## )", text)
    for section in sections:
        section = section.strip()
        if len(section) < 50:
            continue
        title = section.split("\n")[0].strip("# ").strip()
        chunks.append({"text": section, "source": filename, "section": title})
    return chunks


def chunk_by_functions(text: str, filename: str) -> list[dict]:
    """Divide Python por funciones/clases."""
    chunks = []
    parts = re.split(r"\n(?=(?:def |class )\w)", text)
    current = ""
    for part in parts:
        if len(current) + len(part) < 2000:
            current += part
        else:
            if current.strip():
                chunks.append({"text": current.strip(), "source": filename, "section": _first_line(current)})
            current = part
    if current.strip():
        chunks.append({"text": current.strip(), "source": filename, "section": _first_line(current)})
    return chunks


def chunk_terraform(text: str, filename: str) -> list[dict]:
    """Divide Terraform por bloques de primer nivel."""
    chunks = []
    parts = re.split(r"\n(?=(?:resource|variable|data|output|module|provider|locals|terraform)\s)", text)
    for part in parts:
        part = part.strip()
        if len(part) < 30:
            continue
        chunks.append({"text": part, "source": filename, "section": _first_line(part)})
    return chunks


def chunk_yaml(text: str, filename: str) -> list[dict]:
    """Divide el workflow de GitHub Actions por jobs."""
    # Separar por jobs (líneas con exactamente 2 espacios de indentación)
    parts = re.split(r"\n(?=  [a-zA-Z_-]+:)", text)
    if len(parts) <= 3:
        return [{"text": text.strip(), "source": filename, "section": filename}]
    chunks = []
    for part in parts:
        part = part.strip()
        if len(part) < 50:
            continue
        chunks.append({"text": part, "source": filename, "section": _first_line(part)})
    return chunks


def chunk_whole(text: str, filename: str) -> list[dict]:
    """Fichero pequeño: un solo chunk."""
    return [{"text": text.strip(), "source": filename, "section": filename}]


# ---------------------------------------------------------------------------
# Ficheros a indexar
# ---------------------------------------------------------------------------

FILES = [
    (REPO_ROOT / "README.md",                             chunk_by_headers),
    (REPO_ROOT / "fetcher" / "main.py",                   chunk_by_functions),
    (REPO_ROOT / "fetcher" / "Dockerfile",                chunk_whole),
    (REPO_ROOT / "fetcher" / "requirements.txt",          chunk_whole),
    (REPO_ROOT / "terraform" / "main.tf",                 chunk_terraform),
    (REPO_ROOT / "terraform" / "variables.tf",            chunk_terraform),
    (REPO_ROOT / "terraform" / "lambda.tf",               chunk_terraform),
    (REPO_ROOT / "terraform" / "s3.tf",                   chunk_terraform),
    (REPO_ROOT / "terraform" / "cloudfront.tf",           chunk_terraform),
    (REPO_ROOT / "terraform" / "eventbridge.tf",          chunk_terraform),
    (REPO_ROOT / "terraform" / "iam.tf",                  chunk_terraform),
    (REPO_ROOT / "terraform" / "outputs.tf",              chunk_terraform),
    (REPO_ROOT / "terraform" / "ecr.tf",                  chunk_terraform),
    (REPO_ROOT / ".github" / "workflows" / "deploy.yml",  chunk_yaml),
    (REPO_ROOT / "frontend" / "app.js",                   chunk_whole),
    (REPO_ROOT / "frontend" / "index.html",               chunk_whole),
]


# ---------------------------------------------------------------------------
# Embeddings con Bedrock Titan Embed Text v2
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str]) -> np.ndarray:
    bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    vectors = []
    for i, text in enumerate(texts):
        print(f"  Embedding {i + 1}/{len(texts)}...")
        body = json.dumps({
            "inputText": text[:8000],  # límite seguro
            "dimensions": EMBED_DIMENSIONS,
            "normalize": True,
        })
        response = bedrock.invoke_model(
            modelId=EMBED_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        vectors.append(result["embedding"])
    return np.array(vectors, dtype="float32")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build():
    print("=== Construyendo índice RAG ===\n")

    # 1. Chunking
    all_chunks = []
    for filepath, chunker in FILES:
        if not filepath.exists():
            print(f"  [SKIP] {filepath} no encontrado")
            continue
        text = filepath.read_text(encoding="utf-8")
        rel_path = str(filepath.relative_to(REPO_ROOT)).replace("\\", "/")
        chunks = chunker(text, rel_path)
        print(f"  {rel_path}: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    print(f"\nTotal chunks: {len(all_chunks)}")

    # 2. Embeddings
    print("\nGenerando embeddings con Titan Embed v2...")
    vectors = embed_texts([c["text"] for c in all_chunks])

    # 3. Índice FAISS (Inner Product con vectores normalizados = cosine similarity)
    print("\nConstruyendo índice FAISS...")
    index = faiss.IndexFlatIP(EMBED_DIMENSIONS)
    index.add(vectors)

    # 4. Guardar localmente
    faiss.write_index(index, "/tmp/index.faiss")
    with open("/tmp/chunks.json", "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
    print(f"Índice local: /tmp/index.faiss ({len(all_chunks)} vectores)")

    # 5. Subir a S3
    if not S3_BUCKET:
        print("\nS3_BUCKET no configurado. Ficheros guardados en /tmp/ únicamente.")
        return

    print(f"\nSubiendo a s3://{S3_BUCKET}/rag/ ...")
    s3 = boto3.client("s3")
    s3.upload_file("/tmp/index.faiss", S3_BUCKET, "rag/index.faiss")
    s3.upload_file("/tmp/chunks.json", S3_BUCKET, "rag/chunks.json")
    print("¡Índice subido correctamente!")
    print(f"  s3://{S3_BUCKET}/rag/index.faiss")
    print(f"  s3://{S3_BUCKET}/rag/chunks.json")


if __name__ == "__main__":
    build()
