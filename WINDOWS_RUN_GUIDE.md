# 🚀 Windows Local Setup Guide (Podman Containers)

Since `podman-compose` is causing path issues on your Windows machine, you can run the exact same setup using raw `podman` commands. This will spin up both your **Database** and your **Application** inside containers, perfectly mimicking what compose does!

Here is the exact copy-paste sequence for Windows PowerShell.

---

## Step 1: Create a Network
Containers need to be on the same network to talk to each other. (Run this once)
```powershell
podman network create smallbiz-network
```

---

## Step 2: Start MongoDB
Start the MongoDB container attached to the network we just created.
```powershell
podman run -d --name smallbiz-mongodb --network smallbiz-network -p 27017:27017 mongo:7.0
```
*(Make sure your `.env` file has `MONGODB_URI=mongodb://smallbiz-mongodb:27017`)*

---

## Step 3: Build the Application Image
Build the backend container from your Dockerfile.
```powershell
podman build -t smallbiz-bot .
```

---

## Step 4: Run the Application Container
Start your backend container! We will attach it to the network, map the port, load your `.env` variables, and mount your `/app` folder so that code changes sync instantly (just like compose does).
```powershell
podman run -d --name smallbiz-bot --network smallbiz-network -p 8000:8000 --env-file .env -v "${PWD}/app:/app/app" smallbiz-bot
```

---

## Step 4.5: Run the Streamlit Admin Dashboard
Start the dashboard container. It will run on port 8501 and attach to the same network so it can read from MongoDB.
```powershell
podman run -d --name smallbiz-dashboard --network smallbiz-network -p 8501:8501 --env-file .env -v "${PWD}:/app" smallbiz-bot streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

---

## Step 5: Start Ngrok (The Tunnel)
Open a **new PowerShell window** and leave it running to route Telegram traffic to your local container:
```powershell
ngrok http 8000 --url=yoga-deem-anyone.ngrok-free.dev
```

---

### 🎉 You're Done!
Your database, application, and admin dashboard are now running in containers. 

- **Admin Dashboard URL:** `http://localhost:8501`
- **FastAPI Backend URL:** `http://localhost:8000`

### 🔁 Daily Workflow (When you restart your laptop):
Because we used `-d` (detached), your containers will stay created. When you reboot your laptop, you just need to start them back up!

1. **Start Database:** `podman start smallbiz-mongodb`
2. **Start App:** `podman start smallbiz-bot`
3. **Start Dashboard:** `podman start smallbiz-dashboard`
4. **Start Ngrok:** `ngrok http 8000 --url=yoga-deem-anyone.ngrok-free.dev`

### 🔄 How to apply code changes:
Because we mounted the volume (`-v "${PWD}/app:/app/app"`), any changes you make to the Python files will automatically sync. You just need to restart the container to apply them:
```powershell
podman restart smallbiz-bot
```

### 🛑 How to stop everything:
```powershell
podman stop smallbiz-bot smallbiz-dashboard smallbiz-mongodb
```
