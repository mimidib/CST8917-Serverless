# Lab 2 — Smart Image Analyzer (Durable Functions: Fan-Out/Fan-In + Chaining)

**Course:** CST8917 — Cloud DevOps / Serverless
**Student:** Mimi Dib
**Date:** June 2026
**Demo video:** [Lab 2 Demo Video](https://youtu.be/gxVCF5Vmxfs)

---

## Overview

This lab builds a serverless **image-analysis pipeline** using **Azure Durable Functions**
(Python v2 model). When an image is uploaded to Blob Storage, an orchestrator runs four
analyses **in parallel** (fan-out/fan-in), then **chains** two more steps to build and
store a unified report. A separate HTTP endpoint lets you retrieve stored results.

The orchestration uses a **hybrid pattern**:

1. **Fan-Out / Fan-In** — run `analyze_colors`, `analyze_objects`, `analyze_text`, and
   `analyze_metadata` at the same time, then wait for all of them.
2. **Function Chaining** — `generate_report` → `store_results`, run sequentially after
   the parallel work completes.

```
                                  ┌──────────────────┐
  Image uploaded                  │   FAN-OUT (||)   │
  to "images"  ──► blob_trigger ─►│ analyze_colors   │
  container        (client)       │ analyze_objects  │─┐
                                  │ analyze_text     │ │  FAN-IN
                                  │ analyze_metadata │ │ (task_all)
                                  └──────────────────┘ │
                                                       ▼
                                  generate_report ──► store_results ──► Table Storage
                                       (chain)            (chain)     "ImageAnalysisResults"

  GET /api/results[/{id}] ──► get_results ──► reads from Table Storage
```

---

## Prerequisites

- **Python 3.11 or 3.12** installed
- **VS Code** with the **Azure Functions** extension
- **Azure Functions Core Tools** (provides the `func` CLI)
- **Azurite** storage emulator (VS Code extension or CLI) — for local Blob/Table/Durable state
- **Azure Storage Explorer** (standalone app or VS Code Azure extension) — to create the
  `images` container and upload test images
- An **Azure subscription** (for the deployment section)
- *Optional:* the **REST Client** VS Code extension — to run `test-function.http`
- *WSL/Linux only:* the `libsecret-1-0` package (required by Azure Storage Explorer / AzCopy)

---

## Functions

| # | Function | Type | Role |
|---|----------|------|------|
| 1 | `blob_trigger` | Client | Detects image upload, starts the orchestrator |
| 2 | `image_analyzer_orchestrator` | Orchestrator | Coordinates the workflow: fan-out, fan-in, then chain |
| 3 | `analyze_colors` | Activity | Extracts dominant colors from the image (Pillow) |
| 4 | `analyze_objects` | Activity | Detects objects/content in the image (mock) |
| 5 | `analyze_text` | Activity | Performs OCR — extracts text from the image (mock) |
| 6 | `analyze_metadata` | Activity | Extracts real image metadata (dimensions, format, size) |
| 7 | `generate_report` | Activity | Combines all four analyses into a unified report |
| 8 | `store_results` | Activity | Saves the report to Azure Table Storage |
| 9 | `get_results` | HTTP | Retrieves stored analysis results from Table Storage |

All functions live in [`ImageAnalyzerLab/function_app.py`](ImageAnalyzerLab/function_app.py).

---

## Project structure

```
Lab2/
├── README.md                     # this file
├── test-function.http            # REST Client tests for the HTTP endpoint
└── ImageAnalyzerLab/
    ├── function_app.py           # all 9 functions
    ├── requirements.txt          # Python dependencies
    ├── host.json                 # Functions host config
    ├── local.settings.example.json # An example of what your local.settings.json should look like
    └── local.settings.json       # (gitignored — created locally)
```

### Dependencies (`requirements.txt`)

| Package | Purpose |
|---------|---------|
| `azure-functions` | Azure Functions SDK |
| `azure-functions-durable` | Durable Functions extension (orchestrator/activities/client) |
| `azure-data-tables` | Azure Table Storage SDK for storing/reading results |
| `Pillow` | Python Imaging Library — reads image metadata and colors |

---

## Run locally

> All commands are run from the `ImageAnalyzerLab/` folder.

### 1. Create the virtual environment and install dependencies

```bash
# Create + activate a venv
python -m venv .venv
# source .venv/bin/activate        # Linux/macOS
source .venv/Scripts/activate      # Windows (Git Bash)

# Install dependencies into THIS venv
python -m pip install -r requirements.txt
```

### 2. Create `local.settings.json`

Copy `local.settings.example.json` to `local.settings.json` and adjust the values:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "ImageStorageConnection": "UseDevelopmentStorage=true"
  },
  "Host": {
    "CORS": "*"
  }
}
```

| Setting | Purpose |
|---------|---------|
| `AzureWebJobsStorage` | Durable Functions state storage |
| `ImageStorageConnection` | Connection used by the Blob trigger **and** Table Storage |
| `CORS` | Allows cross-origin requests to the function endpoints |

> Both connection strings point to **Azurite** for local development. When you deploy to
> Azure, these point to your real storage account.

### 3. Start Azurite

Durable Functions and Table Storage both require Azurite locally.

- Press `F1` → **Azurite: Start**, and confirm the status bar shows it running.
- CLI alternative:
  ```bash
  azurite --silent --location .azurite --debug .azurite/debug.log
  ```

### 4. Create the `images` container

The Blob trigger watches a container literally named **`images`** — it must exist before
you upload.

- **VS Code Azure extension:** Azure icon → Workspace → Attached Storage Accounts →
  Local Emulator → Blob Containers → right-click → **Create Blob Container** → name it `images`.
- **Azure Storage Explorer (app):** Local & Attached → Storage Accounts →
  (Emulator - Default Ports) → Blob Containers → **Create Blob Container** → `images`.
- **curl:**
  ```bash
  curl -X PUT "http://127.0.0.1:10000/devstoreaccount1/images?restype=container" \
    -H "x-ms-version: 2020-10-02"
  ```

### 5. Start the Function App

```bash
func start
```

### 6. Trigger the pipeline

Upload an image (`.jpg`/`.png`) into the **`images`** container (via Storage Explorer or
the VS Code Azure extension). The console will show the orchestration start, the four
parallel activities, and the report being stored.

---

## Test the HTTP endpoint

Use [`test-function.http`](test-function.http) with the VS Code **REST Client** extension,
or `curl`. The endpoint reads from Table Storage:

| Request | Description |
|---------|-------------|
| `GET /api/results` | Get all results (default limit 10) |
| `GET /api/results?limit=2` | Get results with a custom limit |
| `GET /api/results/{id}` | Get a specific result by ID |
| `GET /api/results/does-not-exist-id` | Returns `404` for an unknown ID |

Example:

```bash
curl http://localhost:7071/api/results
```

---

## Deploy to Azure

> The **table** `ImageAnalysisResults` is created automatically by the code
> (`create_table_if_not_exists`). You only need to provision the **Function App** and
> **storage account**, create the **`images`** container, and set the app setting.

### 1. Create the Function App in Azure

Press `F1` → **Azure Functions: Create Function App in Azure...(Advanced)** and answer:

| Prompt | Selection |
|--------|-----------|
| Select subscription | Your Azure subscription |
| Enter a globally unique name | e.g. `-image-analymimizer` |
| Select a runtime stack | `Python 3.12` |
| Select an OS | `Linux` |
| Select a resource group | Create new, e.g. `rg-serverless-lab2` |
| Select a location | A region near you, e.g. `Canada Central` |
| Select a hosting plan | `Consumption` |
| Select a storage account | Create new, e.g. `stimageanalyzer` |
| Select an Application Insights resource | `Skip for now` |

> **Use the Consumption plan, not Flex Consumption** — the classic Consumption plan is what
> the lab targets, and the blob trigger fires reliably on it. See the
> [Notes / observations](#notes--observations) section.

### 2. Configure the application setting

In the Azure Portal → your **Function App** → **Settings → Environment variables**
(or **Configuration → Application settings**) → **+ Add**:

| Name | Value |
|------|-------|
| `ImageStorageConnection` | The storage account's connection string (Storage Account → **Access keys** → **Connection string**) |

### 3. Create the `images` container in Azure

Azure Portal → your **Storage Account** → **Data Storage → Containers** → **+ Container** →
name it `images` → **Create**.

### 4. Deploy

Press `F1` → **Azure Functions: Deploy to Function App** → select your function app →
confirm the deployment.

### 5. Test in Azure

1. Upload an image to the `images` container (Storage Account → Containers → `images` → **Upload**).
2. Wait a few seconds for the orchestration to complete.
3. Browse to `https://<your-function-app-name>.azurewebsites.net/api/results` to see the results.

---

## Cleanup

- **Local:** stop the host, stop Azurite, and delete the local `.azurite/` folder.
- **Azure:** delete the resource group to remove all resources:
  ```bash
  az group delete --name rg-serverless-lab2 --yes --no-wait
  ```

---

## Notes / observations

### Hosting plan: use Consumption, not Flex Consumption

When creating the Function App in Azure, the **Consumption (Y1)** plan must be used — as
specified in the lab (Part 7.1). **Flex Consumption did not work for this lab.** A few
things to be aware of:

- The lab's deployment steps assume the classic **Consumption** plan, and that's what was
  used here successfully.
- On **Flex Consumption**, the blob trigger behaves differently (it defaults to an
  Event Grid–based source rather than the polling/log-scan source the classic plan uses),
  so the "upload to the `images` container → orchestration starts automatically" flow did
  not trigger as expected.
- Sticking with **Consumption** kept the Durable Functions state storage, blob trigger,
  and Table Storage all working against the single `ImageStorageConnection` storage account.

> **Takeaway:** select **Consumption** when prompted for the hosting plan. If you pick
> Flex Consumption, the automatic blob trigger may not fire.


