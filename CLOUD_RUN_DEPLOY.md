# Cloud Run Production Deployment

Production uses one stateless Google Cloud Run container, Neon Postgres with pgvector,
Cloudflare R2 for player-uploaded images, and Gemini for AI.

## 1. Create provider resources

1. Create a Neon project and copy its pooled PostgreSQL connection string.
2. Create a Gemini API key in Google AI Studio.
3. Create a Cloudflare R2 bucket, an R2 API token, and a public/custom asset domain.
4. Create or select a Google Cloud project with billing enabled.

## 2. Configure this terminal

Run from the repository root and replace every placeholder:

```powershell
$PROJECT_ID="your-gcp-project"
$REGION="us-central1"
$REPOSITORY="investigation-room"
$SERVICE="investigation-room"

$DATABASE_URL="postgresql://USER:PASSWORD@HOST/DB?sslmode=require"
$GEMINI_API_KEY="your-gemini-key"
$APP_SECRET="a-long-random-secret"
$ADMIN_ALIASES="YourAdminAlias"

$R2_ENDPOINT_URL="https://ACCOUNT_ID.r2.cloudflarestorage.com"
$R2_ACCESS_KEY_ID="your-r2-access-key"
$R2_SECRET_ACCESS_KEY="your-r2-secret"
$R2_BUCKET="investigation-room-assets"
$R2_PUBLIC_BASE_URL="https://assets.example.com"
```

Generate `$APP_SECRET` with:

```powershell
$APP_SECRET = .venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 3. Initialize Neon and import repository cases

```powershell
.venv\Scripts\python.exe -m backend.scripts.apply_migration `
  --database-url $DATABASE_URL

.venv\Scripts\python.exe -m backend.scripts.import_case_bundles `
  --database-url $DATABASE_URL
```

This imports the existing repository cases. Production accounts and player progress begin fresh.

## 4. Enable Google Cloud services

Install the Google Cloud CLI, authenticate, and run:

```powershell
gcloud auth login
gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

gcloud artifacts repositories create $REPOSITORY `
  --repository-format=docker `
  --location=$REGION
```

If the repository already exists, the final command can be skipped.

## 5. Build and deploy

```powershell
$IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/investigation-room:latest"

gcloud builds submit --tag $IMAGE .

gcloud run deploy $SERVICE `
  --image $IMAGE `
  --region $REGION `
  --platform managed `
  --allow-unauthenticated `
  --min-instances 0 `
  --max-instances 3 `
  --cpu 1 `
  --memory 512Mi `
  --set-env-vars "INVESTIGATION_AI_PROVIDER=gemini,INVESTIGATION_SECURE_COOKIES=true,INVESTIGATION_RATE_LIMITS_ENABLED=true,INVESTIGATION_SEED_CASES_ON_START=false,INVESTIGATION_BOOTSTRAP_ADMIN_ALIASES=$ADMIN_ALIASES,INVESTIGATION_DATABASE_URL=$DATABASE_URL,GEMINI_API_KEY=$GEMINI_API_KEY,INVESTIGATION_SECRET_KEY=$APP_SECRET,R2_ENDPOINT_URL=$R2_ENDPOINT_URL,R2_ACCESS_KEY_ID=$R2_ACCESS_KEY_ID,R2_SECRET_ACCESS_KEY=$R2_SECRET_ACCESS_KEY,R2_BUCKET=$R2_BUCKET,R2_PUBLIC_BASE_URL=$R2_PUBLIC_BASE_URL"
```

For a serious public launch, move sensitive values from `--set-env-vars` into Google Secret
Manager. The command above is the shortest first-deployment path.

## 6. Set the final Cloud Run URL as CORS origin

Get the service URL:

```powershell
$SERVICE_URL = gcloud run services describe $SERVICE --region $REGION --format="value(status.url)"
$SERVICE_URL
```

Then configure the same-origin URL:

```powershell
gcloud run services update $SERVICE `
  --region $REGION `
  --update-env-vars "INVESTIGATION_CORS_ORIGINS=$SERVICE_URL"
```

Open `$SERVICE_URL`. Register using an alias listed in `$ADMIN_ALIASES` to receive the admin role.

## Operations

- Liveness: `$SERVICE_URL/health/live`
- Readiness: `$SERVICE_URL/health/ready`
- Application logs: `gcloud run services logs read $SERVICE --region $REGION`
- Redeploy after changes: rerun the build and deploy commands in step 5.
- Configure billing/quota alerts in Google Cloud and Google AI Studio.

The Gemini free tier may use submitted content to improve Google products. Disclose this to case
authors.
