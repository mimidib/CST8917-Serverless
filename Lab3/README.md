# Fleetbook Webapp Lab 3 

## Demo Video

▶️ **https://youtu.be/iuYYH1pk_Z8**

The 5-minute demo shows: the Service Bus namespace (queue, topic, and both filtered subscriptions `confirmed-sub` / `rejected-sub` with their `label='confirmed'` and `label='rejected'` filters); a **confirmed** booking end-to-end (Logic App run history → **Condition** takes the **True** branch → confirmation email received); a **rejected** booking (Condition → **False** branch → rejection email received); and the topic subscriptions showing the filtered message counts.

## Deliverables

| File | Description |
|------|-------------|
| `function_app.py` | Azure Function `check-booking` — booking evaluation + pricing logic |
| `requirements.txt` | Function app Python dependencies |
| `test-function.http` | REST Client tests for the function |
| `client.html` | FleetBook web app |
| `local.settings.json.example` | Config template with placeholder values (the real `local.settings.json` is gitignored — never commit keys) |
| `README.md` | This file — setup instructions |


## Architecture

```
client.html  →  SB Queue (booking-queue)  →  Logic App  →  Azure Function (check-booking)
                                                                      │
                                                                      ▼
                                              SB Topic (booking-results)
                                                 ├─ confirmed-sub  (filter: label = 'confirmed')  →  confirmation email
                                                 └─ rejected-sub   (filter: label = 'rejected')   →  rejection email
```
The client also polls both subscriptions to display each booking's result on the dashboard.

## Setup Instructions

### 1. Azure — Service Bus
1. Create a **Service Bus namespace** (Standard tier — required for topics).
2. Add a **queue** named `booking-queue`.
3. Add a **topic** named `booking-results`, with two subscriptions:
   - `confirmed-sub` — SQL filter: `label = 'confirmed'`
   - `rejected-sub` — SQL filter: `label = 'rejected'`
4. Under **Shared access policies → RootManageSharedAccessKey**, copy the **Primary Connection String** (for the Logic App) and the **Primary Key** (for the web app).

### 2. Azure Function — `check-booking`
Run locally:
```powershell
cd FleetBookFunctionApp
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
func start          # requires Azure Functions Core Tools
```
- Health check: `GET http://localhost:7071/api/health`
- Test all endpoints with `test-function.http` (VS Code REST Client extension).

Deploy to Azure:
```powershell
func azure functionapp publish <your-function-app-name>
```

### 3. Logic App
Create a Consumption Logic App that:
1. **Triggers** on a new message in the `booking-queue` queue (Service Bus connection = Primary Connection String).
2. Calls the deployed **`check-booking`** function (POST, JSON body = the booking message).
3. Uses a **Condition** on `status == 'confirmed'`:
   - **True** branch → send message to topic `booking-results` with **label `confirmed`**.
   - **False** branch → send message to topic `booking-results` with **label `rejected`**.

### 4. Web App — `client.html`
1. Open `client.html` over `http://localhost` (e.g. `python -m http.server 8080`), **not** `file://` — the Web Crypto SAS-signing code only runs in a secure context.
2. Expand **Service Bus Configuration** and enter:
   - **Namespace** (e.g. `yourname-booking-sb`)
   - **SAS Policy Name**: `RootManageSharedAccessKey`
   - **SAS Key**: the namespace **Primary Key** (not the connection string)
3. Submit a booking — it flows through the queue → Logic App → function → topic, and the dashboard updates when the result arrives.

### Notes
- Copy `local.settings.json.example` values into your own local config; **never commit** `local.settings.json` or real keys (already in `.gitignore`).
- If the client shows `Cannot read properties of undefined (reading 'importKey')`, you're on `file://` — serve over `http://localhost` instead.
