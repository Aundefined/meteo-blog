# Meteo Blog — Previsión del Tiempo en España en Tiempo Real 🌦️

Proyecto MLOps en producción que combina datos meteorológicos en tiempo real de la Agencia Estatal de Meteorología (AEMET) con resúmenes generados por Inteligencia Artificial mediante AWS Bedrock. Incluye un chatbot RAG que responde preguntas sobre la arquitectura del propio proyecto. Completamente serverless, automatizado y desplegado en AWS.

**Demo en vivo:** https://dz2xr9ouy3oet.cloudfront.net

---

## Descripción general

Esta aplicación obtiene la previsión del tiempo para las 17 comunidades autónomas de España 5 veces al día (0h, 6h, 10h, 14h y 18h hora española), genera un resumen en lenguaje natural usando un Large Language Model, y sirve todo a través de un frontend estático alojado en AWS.

El proyecto demuestra un flujo MLOps completo: ingesta de datos desde una API externa, inferencia con IA, pipeline RAG, infraestructura como código, automatización CI/CD y despliegue cloud-native, todo sin gestionar ningún servidor.

---

## Arquitectura

```
EventBridge Scheduler (5x/día)
        │
        ▼
Lambda Fetcher [Docker/ECR]
        │
        ├── AEMET OpenData API ──► datos meteorológicos de las 17 CC.AA.
        │
        ├── AWS Bedrock (Amazon Nova Micro) ──► resumen generado por IA
        │
        └── S3 ──► escribe weather.json + invalidación caché CloudFront

CloudFront CDN
        │
        ├── /index.html  ◄── frontend estático (HTML + JS)
        ├── /app.js
        ├── /weather.json  ◄── datos actualizados por la Lambda
        └── /rag/*  ◄── índice FAISS + chunks (para el chatbot)

API Gateway HTTP API
        │
        ▼
Lambda Chatbot [Docker/ECR]
        │
        ├── S3 ──► carga índice FAISS + chunks del proyecto
        ├── AWS Bedrock (Titan Embed v2) ──► embedding de la pregunta
        └── AWS Bedrock (Amazon Nova Micro) ──► respuesta en lenguaje natural
```

**Decisión de diseño clave — fetcher:** no hay API Gateway ni servidor backend. La Lambda escribe un único archivo `weather.json` en S3 de forma programada, y el frontend lo lee directamente desde CloudFront. Esto elimina una capa completa de infraestructura, reduce el coste a casi cero y mejora la fiabilidad.

**Decisión de diseño clave — chatbot:** el índice RAG (FAISS + chunks del repo) se genera una vez con un script local y se almacena en S3. La Lambda del chatbot lo carga en memoria en el cold start y lo cachea entre invocaciones. Sin base de datos vectorial gestionada, sin costes adicionales.

---

## Stack tecnológico

### Aplicación
| Componente | Tecnología |
|---|---|
| Fuente de datos | [AEMET OpenData API](https://opendata.aemet.es/) |
| IA / LLM | AWS Bedrock — Amazon Nova Micro |
| Embeddings RAG | AWS Bedrock — Amazon Titan Embed Text v2 |
| Vector store | FAISS (IndexFlatIP, 256 dimensiones) |
| Backend | Python 3.12 |
| Frontend | HTML + Vanilla JS + Tailwind CSS |

### Infraestructura AWS
| Servicio | Propósito |
|---|---|
| AWS Lambda | Ejecución serverless del fetcher y del chatbot |
| Amazon ECR | Registro de imágenes Docker (una por Lambda) |
| AWS Bedrock | Inferencia LLM y embeddings gestionados |
| Amazon S3 | Frontend, datos meteorológicos e índice RAG |
| Amazon CloudFront | CDN con HTTPS, sirve toda la aplicación |
| Amazon API Gateway (HTTP API) | Endpoint público para el chatbot |
| Amazon EventBridge Scheduler | Dispara el fetcher 5 veces al día |
| AWS IAM | Roles de mínimo privilegio para cada componente |

### DevOps
| Herramienta | Propósito |
|---|---|
| Terraform | Infrastructure as Code — todos los recursos AWS definidos y versionados |
| GitHub Actions | Pipeline CI/CD — build, push y despliegue en cada push a `main` |
| Docker | Lambdas empaquetadas como imágenes de contenedor |
| AWS OIDC | Autenticación sin credenciales estáticas entre GitHub Actions y AWS |

---

## Cómo funciona

### Pipeline de datos (fetcher)

1. **EventBridge** dispara la Lambda según un cron (`cron(0 0,6,10,14,18 * * ? *)` — 5 veces al día en hora española)
2. La Lambda llama a la **API de AEMET OpenData** para cada una de las 17 comunidades autónomas:
   - `GET /prediccion/especifica/municipio/diaria/{municipio}` → temperatura máx/mín, probabilidad de lluvia y estado del cielo para la capital de cada comunidad
3. Los datos estructurados se formatean en un prompt y se envían a **AWS Bedrock** (Amazon Nova Micro) para generar un resumen nacional de 3-4 frases en español
4. La Lambda escribe el `weather.json` resultante en **S3** y crea una **invalidación de caché en CloudFront**

### Pipeline RAG (chatbot)

1. **Indexación** (offline, script local): los ficheros del repositorio (código, Terraform, README, CI/CD) se trocean en chunks semánticos, se generan embeddings con **Titan Embed Text v2** (256 dimensiones) y se construye un índice **FAISS** que se sube a S3
2. **Consulta** (en tiempo real): el usuario escribe una pregunta → la Lambda la embeds con Titan → busca los 5 chunks más relevantes en FAISS (similitud coseno) → construye un prompt con el contexto → llama a **Nova Micro** → devuelve la respuesta

### Frontend

Aplicación de una sola página sin frameworks. Al cargar, `app.js` hace un `fetch` a `/weather.json` desde CloudFront y renderiza:
- Un resumen nacional generado por IA en la parte superior
- Un mapa SVG de España coloreado por probabilidad de lluvia con emojis por comunidad
- Cards meteorológicas por comunidad autónoma
- Un chatbot para preguntar sobre la arquitectura del proyecto

### Infraestructura como código

Todos los recursos AWS están definidos en Terraform y versionados en el repositorio:
- `ecr.tf` — registros de contenedores con política de ciclo de vida
- `lambda.tf` — Lambda del fetcher
- `chatbot.tf` — Lambda del chatbot, ECR, API Gateway HTTP API
- `s3.tf` — bucket del frontend con acceso público bloqueado
- `cloudfront.tf` — distribución con Origin Access Control, TTL diferenciado para `weather.json` (5 min) frente a assets estáticos (1h)
- `eventbridge.tf` — scheduler con política de reintentos
- `iam.tf` — roles de mínimo privilegio para fetcher, chatbot, EventBridge y GitHub Actions

### Pipeline CI/CD

En cada push a `main`, GitHub Actions:
1. Se autentica en AWS mediante **OIDC** (sin credenciales AWS almacenadas)
2. Construye y sube las imágenes Docker del **fetcher** y del **chatbot** a ECR
3. Actualiza ambas funciones **Lambda**
4. Sincroniza los ficheros del **frontend** en S3 (excluyendo `weather.json` y `rag/*`)
5. Crea una **invalidación de CloudFront** para `index.html` y `app.js`

Los cambios de infraestructura (Terraform) se aplican manualmente tras revisar el `plan`.

---

## Conceptos MLOps demostrados

**Pipeline de inferencia programado** — La Lambda fetcher actúa como un pipeline batch: ingesta datos brutos, los preprocesa en un prompt estructurado, llama a un LLM y persiste el resultado. Patrón análogo a los pipelines de predicción batch en ML.

**Pipeline RAG** — Implementación completa del patrón Retrieval-Augmented Generation: indexación offline de documentos, búsqueda semántica por similitud coseno y generación con contexto recuperado. El corpus es el propio código del proyecto.

**Inferencia ML serverless** — AWS Bedrock para LLM y embeddings significa cero gestión de modelos: sin instancias GPU, sin model serving, sin escalado manual.

**Vector store minimalista** — FAISS almacenado en S3 y cargado en memoria en el cold start. Sin bases de datos vectoriales gestionadas (Pinecone, OpenSearch) para mantener el coste en $0.

**Infraestructura como código** — Todo el stack es reproducible desde código con `terraform apply`.

**Cargas de trabajo contenerizadas** — Ambas Lambdas corren como contenedores Docker, garantizando ejecución consistente entre local y producción.

**CI/CD sin credenciales** — GitHub Actions se autentica en AWS mediante federación OIDC. El rol IAM tiene permisos mínimos acotados por componente.

**Observabilidad** — Logs de ejecución de cada Lambda en CloudWatch con retención de 14 días.

---

## Estructura del proyecto

```
meteo-blog/
├── fetcher/
│   ├── main.py              # Lambda: fetch AEMET + inferencia Bedrock + escritura S3
│   ├── requirements.txt
│   └── Dockerfile
├── chatbot/
│   ├── main.py              # Lambda: RAG con FAISS + Titan Embed + Nova Micro
│   ├── requirements.txt
│   └── Dockerfile
├── indexer/
│   └── build_index.py       # Script local: chunkea repo → embeddings → FAISS → S3
├── frontend/
│   ├── index.html
│   └── app.js
├── terraform/
│   ├── main.tf              # Provider + backend S3
│   ├── variables.tf
│   ├── ecr.tf
│   ├── s3.tf
│   ├── cloudfront.tf
│   ├── lambda.tf
│   ├── chatbot.tf           # Lambda chatbot + API Gateway + ECR
│   ├── eventbridge.tf
│   ├── iam.tf
│   └── outputs.tf
└── .github/
    └── workflows/
        └── deploy.yml
```

---

## Desarrollo local

**Requisitos previos:** Python 3.12, Anaconda, Docker Desktop, AWS CLI, Terraform

```bash
# Crear y activar el entorno conda
conda create -n meteo-blog python=3.12
conda activate meteo-blog

# Instalar dependencias
conda install -c conda-forge faiss-cpu -y
pip install -r fetcher/requirements.txt
pip install -r indexer/requirements.txt

# Configurar variables de entorno
cp fetcher/.env.example fetcher/.env
# Editar .env con tu API key de AEMET, credenciales AWS y S3_BUCKET

# Ejecutar el fetcher en local (escribe weather.json en frontend/)
cd fetcher
python main.py

# Construir el índice RAG (solo necesario cuando cambia el repo)
cd indexer
python build_index.py

# Abrir frontend/index.html con Live Server en VS Code
```

**Obtener API key de AEMET:** Registro gratuito en [opendata.aemet.es](https://opendata.aemet.es/centrodedescargas/inicio)

---

## Despliegue

### Requisitos previos
- Cuenta AWS con permisos suficientes
- Terraform >= 1.10
- Docker Desktop

### Primer despliegue

```bash
# Crear bucket S3 para el estado de Terraform (una sola vez)
aws s3api create-bucket --bucket meteo-blog-tfstate-{ACCOUNT_ID}-euw1 \
  --region eu-west-1 --create-bucket-configuration LocationConstraint=eu-west-1

# Crear repositorios ECR y subir imágenes iniciales
aws ecr create-repository --repository-name meteo-blog-fetcher --region eu-west-1
aws ecr create-repository --repository-name meteo-blog-chatbot --region eu-west-1

aws ecr get-login-password --region eu-west-1 | \
  docker login --username AWS --password-stdin {ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com

docker build --platform linux/amd64 --provenance=false -t meteo-blog-fetcher:latest ./fetcher
docker tag meteo-blog-fetcher:latest {ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/meteo-blog-fetcher:latest
docker push {ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/meteo-blog-fetcher:latest

docker build --platform linux/amd64 --provenance=false -t meteo-blog-chatbot:latest ./chatbot
docker tag meteo-blog-chatbot:latest {ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/meteo-blog-chatbot:latest
docker push {ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/meteo-blog-chatbot:latest

# Desplegar infraestructura
cd terraform
terraform init
terraform apply

# Construir y subir el índice RAG
cd ../indexer
python build_index.py
```

### Secrets de GitHub Actions necesarios

| Secret | Descripción |
|---|---|
| `AWS_ROLE_ARN` | ARN del rol IAM para GitHub Actions (del output de Terraform) |
| `CLOUDFRONT_DISTRIBUTION_ID` | ID de la distribución CloudFront (del output de Terraform) |

Una vez configurados los secrets, cualquier push a `main` dispara el despliegue completo.

---

## Estimación de costes

Ejecutar este proyecto en AWS cuesta aproximadamente **$0.10/mes** en pay-as-you-go:

| Servicio | Coste |
|---|---|
| Lambda fetcher | $0.02/mes (150 invocaciones/mes × 35s × 256MB) |
| Lambda chatbot | ~$0.01/mes (uso esporádico) |
| Bedrock (Nova Micro) | ~$0.01/mes (150 llamadas fetcher + consultas chatbot) |
| Bedrock (Titan Embed) | ~$0.00/mes (indexación puntual, coste despreciable) |
| S3 | $0.00/mes (almacenamiento y peticiones mínimos) |
| CloudFront | $0.01/mes (0.1GB transferencia + solicitudes HTTPS) |
| API Gateway HTTP API | $0.00/mes (uso mínimo, dentro del nivel gratuito) |
| ECR | $0.05/mes (~1GB de imágenes) |
| EventBridge Scheduler | $0.00/mes (dentro del nivel gratuito) |

---

## Licencia

MIT
