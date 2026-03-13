# Meteo Blog — Previsión del Tiempo en España en Tiempo Real 🌦️

Proyecto MLOps en producción que combina datos meteorológicos en tiempo real de la Agencia Estatal de Meteorología (AEMET) con resúmenes generados por Inteligencia Artificial mediante AWS Bedrock. Completamente serverless, automatizado y desplegado en AWS.

**Demo en vivo:** https://dz2xr9ouy3oet.cloudfront.net

---

## Descripción general

Esta aplicación obtiene la previsión del tiempo para las 17 comunidades autónomas de España 5 veces al día (0h, 6h, 10h, 14h y 18h hora española), genera un resumen en lenguaje natural usando un Large Language Model, y sirve todo a través de un frontend estático alojado en AWS.

El proyecto demuestra un flujo MLOps completo: ingesta de datos desde una API externa, inferencia con IA, infraestructura como código, automatización CI/CD y despliegue cloud-native, todo sin gestionar ningún servidor.

---

## Arquitectura

```
EventBridge Scheduler (cada 4h)
        │
        ▼
AWS Lambda [Docker/ECR]
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
        └── /weather.json  ◄── datos actualizados cada 4h por la Lambda
```

**Decisión de diseño clave:** no hay API Gateway ni servidor backend. La Lambda escribe un único archivo `weather.json` en S3 de forma programada, y el frontend lo lee directamente desde CloudFront. Esto elimina una capa completa de infraestructura, reduce el coste a casi cero y mejora la fiabilidad.

---

## Stack tecnológico

### Aplicación
| Componente | Tecnología |
|---|---|
| Fuente de datos | [AEMET OpenData API](https://opendata.aemet.es/) |
| IA / LLM | AWS Bedrock — Amazon Nova Micro |
| Backend | Python 3.12 |
| Frontend | HTML + Vanilla JS + Tailwind CSS |

### Infraestructura AWS
| Servicio | Propósito |
|---|---|
| AWS Lambda | Ejecución serverless del fetcher |
| Amazon ECR | Registro de imágenes Docker |
| AWS Bedrock | Inferencia LLM gestionada (Amazon Nova Micro) |
| Amazon S3 | Aloja los ficheros del frontend y los datos meteorológicos |
| Amazon CloudFront | CDN con HTTPS, sirve toda la aplicación |
| Amazon EventBridge Scheduler | Dispara la Lambda 5 veces al día (0h, 6h, 10h, 14h, 18h hora España) |
| AWS IAM | Roles de mínimo privilegio para Lambda, Scheduler y CI/CD |

### DevOps
| Herramienta | Propósito |
|---|---|
| Terraform | Infrastructure as Code — todos los recursos AWS definidos y versionados |
| GitHub Actions | Pipeline CI/CD — build, push y despliegue en cada push a `main` |
| Docker | Lambda empaquetada como imagen de contenedor para builds reproducibles |
| AWS OIDC | Autenticación sin credenciales estáticas entre GitHub Actions y AWS |

---

## Cómo funciona

### Pipeline de datos

1. **EventBridge** dispara la Lambda según un cron (`cron(0 0,6,10,14,18 * * ? *)` — 5 veces al día en hora española: 0h, 6h, 10h, 14h y 18h)
2. La Lambda llama a la **API de AEMET OpenData** para cada una de las 17 comunidades autónomas:
   - `GET /prediccion/especifica/municipio/diaria/{municipio}` → temperatura máx/mín, probabilidad de lluvia y estado del cielo para la capital de cada comunidad
3. Los datos estructurados (17 comunidades) se formatean en un prompt y se envían a **AWS Bedrock** (modelo Amazon Nova Micro) para generar un resumen nacional de 3-4 frases en español, destacando anomalías regionales
4. La Lambda escribe el `weather.json` resultante en **S3** y crea una **invalidación de caché en CloudFront** para que los usuarios siempre reciban datos frescos

### Frontend

Aplicación de una sola página sin frameworks. Al cargar, `app.js` hace un `fetch` a `/weather.json` desde CloudFront y renderiza:
- Un resumen nacional generado por IA en la parte superior
- Una card meteorológica por comunidad autónoma con temperatura, probabilidad de lluvia y estado del cielo con emoji

### Infraestructura como código

Todos los recursos AWS están definidos en Terraform y versionados en el repositorio:
- `ecr.tf` — registro de contenedores con política de ciclo de vida (conserva las últimas 10 imágenes)
- `lambda.tf` — configuración de la función, variables de entorno, grupo de logs en CloudWatch
- `s3.tf` — bucket del frontend con acceso público bloqueado
- `cloudfront.tf` — distribución con Origin Access Control, TTL diferenciado para `weather.json` (5 min) frente a assets estáticos (1h)
- `eventbridge.tf` — scheduler con política de reintentos
- `iam.tf` — rol de ejecución de Lambda, rol de EventBridge, rol OIDC para GitHub Actions (todos con mínimo privilegio)

### Pipeline CI/CD

En cada push a `main`, GitHub Actions:
1. Se autentica en AWS mediante **OIDC** (sin credenciales AWS almacenadas — buena práctica de seguridad)
2. Construye la imagen Docker con `--platform linux/amd64 --provenance=false` (requerido para compatibilidad con Lambda)
3. Sube la imagen a **ECR** etiquetada con el SHA del commit
4. Actualiza la función **Lambda** para usar la nueva imagen
5. Sincroniza los ficheros del **frontend** en S3 (excluyendo `weather.json`, gestionado por la Lambda)
6. Crea una **invalidación de CloudFront** para `index.html` y `app.js`

Los cambios de infraestructura (Terraform) se aplican manualmente tras revisar el `plan` — una decisión deliberada para evitar modificaciones accidentales en producción.

---

## Conceptos MLOps demostrados

**Pipeline de inferencia programado** — La Lambda actúa como un pipeline de inferencia: ingesta datos brutos, los preprocesa en un prompt estructurado, llama a un LLM para la inferencia y persiste el resultado. Este patrón es directamente análogo a los pipelines de predicción batch en ML.

**Inferencia ML serverless** — Usar AWS Bedrock para la inferencia LLM significa cero gestión de modelos: sin instancias GPU, sin infraestructura de model serving, sin preocupaciones de escalado. El modelo se invoca por petición vía API.

**Infraestructura como código** — Cada recurso cloud es reproducible desde código. Todo el stack puede destruirse y recrearse con `terraform apply`.

**Cargas de trabajo contenerizadas** — El fetcher corre como contenedor Docker en Lambda, garantizando ejecución consistente entre desarrollo local y producción (misma versión de Python, mismas dependencias).

**CI/CD sin credenciales** — GitHub Actions se autentica en AWS mediante federación OIDC en lugar de credenciales estáticas. El rol IAM tiene permisos acotados: únicamente las acciones necesarias (push a ECR, actualizar Lambda, sync S3, invalidar CloudFront).

**Observabilidad** — Los logs de ejecución de Lambda se envían a CloudWatch Logs con una retención de 14 días.

---

## Estructura del proyecto

```
meteo-blog/
├── fetcher/
│   ├── main.py              # Lambda handler: fetch AEMET + inferencia Bedrock + escritura S3
│   ├── requirements.txt
│   └── Dockerfile
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
pip install -r fetcher/requirements.txt

# Configurar variables de entorno
cp fetcher/.env.example fetcher/.env
# Editar .env con tu API key de AEMET y credenciales AWS

# Ejecutar el fetcher en local (escribe weather.json en frontend/)
cd fetcher
python main.py

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

# Build y push de la imagen Docker inicial (necesario antes del primer terraform apply)
aws ecr get-login-password --region eu-west-1 | \
  docker login --username AWS --password-stdin {ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com

docker build --platform linux/amd64 --provenance=false -t meteo-blog-fetcher:latest ./fetcher
docker tag meteo-blog-fetcher:latest {ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/meteo-blog-fetcher:latest
docker push {ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/meteo-blog-fetcher:latest

# Desplegar infraestructura
cd terraform
terraform init
terraform apply
```

### Secrets de GitHub Actions necesarios

| Secret | Descripción |
|---|---|
| `AWS_ROLE_ARN` | ARN del rol IAM para GitHub Actions (del output de Terraform) |
| `CLOUDFRONT_DISTRIBUTION_ID` | ID de la distribución CloudFront (del output de Terraform) |

Una vez configurados los secrets, cualquier push a `main` dispara el despliegue completo.

---

## Estimación de costes

Ejecutar este proyecto en AWS cuesta aproximadamente **$0.09/mes** en pay-as-you-go (verificado con AWS Pricing Calculator):

| Servicio | Coste |
|---|---|
| Lambda | $0.02/mes (150 invocaciones/mes × 35s × 256MB) |
| Bedrock (Nova Micro) | ~$0.01/mes (150 llamadas × ~1K tokens input + ~150 tokens output, $0.00004/1K input, $0.00016/1K output) |
| S3 | $0.00/mes (almacenamiento y peticiones mínimos) |
| CloudFront | $0.01/mes (0.1GB transferencia + 1000 solicitudes HTTPS) |
| ECR | $0.05/mes (0.5GB de imagen) |
| EventBridge Scheduler | $0.00/mes (150 invocaciones/mes, dentro del nivel gratuito de 14M) |

---

## Licencia

MIT
