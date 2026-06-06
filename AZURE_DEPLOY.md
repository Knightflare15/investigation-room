# Azure Deployment Guide

This project can now be deployed to Azure as a single custom container.

## Recommended Azure architecture

Use this setup:

- `Azure App Service (Linux, custom container)` for the full app
- `Azure Container Registry (ACR)` for the image
- `Azure Database for PostgreSQL Flexible Server` for production data
- App Service persistent storage at `/home` for writable case drafts and uploaded assets

This is the best fit for the current codebase because:

- the frontend is now served by the backend container
- the app writes case drafts and uploaded assets to disk
- App Service gives you persistent storage under `/home`
- PostgreSQL is safer than SQLite for real multi-user deployment

## Important production note

The app supports local Ollama, but Azure deployment is easiest if you do **not** depend on local Ollama at first.

You have 3 choices:

1. Deploy now without Ollama and let the app use its built-in fallback logic.
2. Point `OLLAMA_BASE_URL` to an Ollama-compatible endpoint you host elsewhere.
3. Later, deploy Ollama separately on a VM or another container-based service.

For a first live deployment, option 1 is the safest.

## What changed in the repo for Azure

- Added a root [Dockerfile](/C:/Users/Aryan/Documents/RAG_Project/Dockerfile)
- Added [.dockerignore](/C:/Users/Aryan/Documents/RAG_Project/.dockerignore)
- Made the writable cases path configurable in [backend/app/config.py](/C:/Users/Aryan/Documents/RAG_Project/backend/app/config.py)
- Added first-start case seeding and frontend static serving in [backend/app/main.py](/C:/Users/Aryan/Documents/RAG_Project/backend/app/main.py)

## Environment variables for Azure App Service

Set these in App Service configuration:

```text
WEBSITES_PORT=8000
WEBSITES_ENABLE_APP_SERVICE_STORAGE=true

INVESTIGATION_DATABASE_URL=postgresql://<user>:<password>@<server>.postgres.database.azure.com:5432/investigation_room?sslmode=require
INVESTIGATION_CASES_PATH=/home/site/cases
INVESTIGATION_SEED_CASES_ON_START=true

INVESTIGATION_SECRET_KEY=<long-random-secret>
INVESTIGATION_ADMIN_ACCESS_CODE=<your-admin-code>
INVESTIGATION_ADMIN_ALIASES=Consultant,Admin
INVESTIGATION_CORS_ORIGINS=https://<your-app-name>.azurewebsites.net

OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_CHAT_MODEL=llama3.1:8b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

If you are not running Ollama in Azure yet, leave the `OLLAMA_*` values alone. The app will fall back when the endpoint is unavailable.

## One-time Azure CLI flow

Replace the placeholders before running anything.

### 1. Variables

```powershell
$RG="investigation-room-rg"
$LOC="centralindia"
$ACR="investigationroomacr123"
$PLAN="investigation-room-plan"
$APP="investigation-room-app-123"
$PG="investigation-room-pg-123"
$PG_ADMIN="iradmin"
$PG_PASSWORD="<strong-postgres-password>"
$ADMIN_CODE="<your-admin-code>"
$APP_SECRET="<long-random-secret>"
```

### 2. Create the resource group

```powershell
az group create --name $RG --location $LOC
```

### 3. Create Azure Container Registry

```powershell
az acr create --resource-group $RG --name $ACR --sku Basic --admin-enabled true
```

### 4. Build and push the image from this repo

Run this from the repository root:

```powershell
az acr build --registry $ACR --image investigation-room:latest .
```

### 5. Create PostgreSQL Flexible Server

```powershell
az postgres flexible-server create `
  --resource-group $RG `
  --name $PG `
  --location $LOC `
  --admin-user $PG_ADMIN `
  --admin-password $PG_PASSWORD `
  --sku-name Standard_B1ms `
  --tier Burstable `
  --storage-size 32 `
  --version 16 `
  --public-access 0.0.0.0
```

Create the application database:

```powershell
az postgres flexible-server db create `
  --resource-group $RG `
  --server-name $PG `
  --database-name investigation_room
```

### 6. Create the App Service plan

```powershell
az appservice plan create `
  --name $PLAN `
  --resource-group $RG `
  --is-linux `
  --sku B1
```

### 7. Create the web app

```powershell
az webapp create `
  --resource-group $RG `
  --plan $PLAN `
  --name $APP
```

### 8. Point the web app at the container image

First fetch the ACR credentials:

```powershell
$ACR_USER = az acr credential show --name $ACR --query username -o tsv
$ACR_PASS = az acr credential show --name $ACR --query "passwords[0].value" -o tsv
```

Then configure the container:

```powershell
az webapp config container set `
  --name $APP `
  --resource-group $RG `
  --docker-custom-image-name "$ACR.azurecr.io/investigation-room:latest" `
  --docker-registry-server-url "https://$ACR.azurecr.io" `
  --docker-registry-server-user $ACR_USER `
  --docker-registry-server-password $ACR_PASS `
  --enable-app-service-storage true
```

### 9. Set application settings

```powershell
az webapp config appsettings set `
  --resource-group $RG `
  --name $APP `
  --settings `
  WEBSITES_PORT=8000 `
  WEBSITES_ENABLE_APP_SERVICE_STORAGE=true `
  INVESTIGATION_DATABASE_URL="postgresql://$PG_ADMIN:$PG_PASSWORD@$PG.postgres.database.azure.com:5432/investigation_room?sslmode=require" `
  INVESTIGATION_CASES_PATH="/home/site/cases" `
  INVESTIGATION_SEED_CASES_ON_START=true `
  INVESTIGATION_SECRET_KEY="$APP_SECRET" `
  INVESTIGATION_ADMIN_ACCESS_CODE="$ADMIN_CODE" `
  INVESTIGATION_ADMIN_ALIASES="Consultant,Admin" `
  INVESTIGATION_CORS_ORIGINS="https://$APP.azurewebsites.net"
```

### 10. Open the app

```powershell
az webapp browse --resource-group $RG --name $APP
```

## How this deployment behaves

- The frontend is built into the container image.
- FastAPI serves the API and the frontend.
- The app writes new draft cases and uploaded assets into `/home/site/cases`.
- On the first boot, if `/home/site/cases` is empty, the app copies the bundled `cases/` content into that writable folder.
- Existing authored data remains in `/home/site/cases` across restarts.

## Fast first deployment vs stronger production deployment

### Fast first deployment

Use:

- App Service custom container
- PostgreSQL Flexible Server
- no Ollama in Azure yet

This is the best path if you want the app online quickly.

### Stronger production deployment later

Add:

- GitHub Actions for automatic image builds and deploys
- Azure Key Vault for secrets
- managed identity for ACR pulls instead of admin credentials
- a separate hosted model endpoint if you want live LLM behavior in production

## Troubleshooting

### Frontend loads but API calls fail

Check:

- `INVESTIGATION_CORS_ORIGINS`
- App Service logs
- whether the app settings were actually applied

### Cases disappear after restart

Check:

- `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`
- `INVESTIGATION_CASES_PATH=/home/site/cases`

### The app starts but there are no sample cases

Check:

- `INVESTIGATION_SEED_CASES_ON_START=true`
- `/home/site/cases` is writable

### Dialogue feels weaker in Azure

That is expected if Ollama is not reachable. The app will still work, but it will use fallback logic.

## Official references

- Azure App Service custom containers: [Microsoft Learn](https://learn.microsoft.com/en-us/azure/app-service/configure-custom-container)
- App Service custom container tutorial: [Microsoft Learn](https://learn.microsoft.com/en-us/azure/app-service/tutorial-custom-container)
- Azure Container Registry quick build: [Microsoft Learn](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-quickstart-task-cli)
- Azure Database for PostgreSQL Flexible Server quickstart: [Microsoft Learn](https://learn.microsoft.com/azure/postgresql/flexible-server/quickstart-create-server)
