# Server Deployment

The hackathon notice provides one Ubuntu CPU server per team. Use the PEM key for SSH, then run the app with Docker Compose.

## 1. Prepare the PEM key on Windows

Run these commands in PowerShell, using the actual PEM path:

```powershell
icacls.exe "C:\Users\SSAFY\Documents\카카오톡 받은 파일\H14K010T.pem" /reset
icacls.exe "C:\Users\SSAFY\Documents\카카오톡 받은 파일\H14K010T.pem" /grant:r "$($env:username):(R)"
icacls.exe "C:\Users\SSAFY\Documents\카카오톡 받은 파일\H14K010T.pem" /inheritance:r
```

Connect to the team server:

```powershell
ssh -i "C:\Users\SSAFY\Documents\카카오톡 받은 파일\H14K010T.pem" ubuntu@h14k010.p.ssafy.io
```

## 2. Install Docker on the Ubuntu server

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
newgrp docker
docker --version
docker compose version
```

## 3. Open required ports

The notice says ports `22`, `80`, `443`, and `1024-65535` are externally reachable when allowed by UFW. This compose setup uses:

- Frontend: `80`
- Backend API: `4100`

```bash
sudo ufw allow 80/tcp
sudo ufw allow 4100/tcp
sudo ufw status
```

## 4. Configure and run

On the server, from the project root:

```bash
cp .env.docker.example .env
```

For this team server, `.env.docker.example` already uses the public domain:

```env
NEXT_PUBLIC_HEOGAON_API_BASE_URL=http://h14k010.p.ssafy.io:4100
CORS_ALLOWED_ORIGINS=http://h14k010.p.ssafy.io
LLM_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1
LLM_MODEL=gpt-5.5
LLM_REASONING_EFFORT=low
```

Set `LLM_API_KEY` in `.env` to the team GMS key. Do not commit `.env`.

Then start:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f
```

Open:

```text
http://YOUR_SERVER_IP
```

For this server:

```text
http://h14k010.p.ssafy.io
```

Health check:

```bash
curl http://127.0.0.1:4100/health
```
