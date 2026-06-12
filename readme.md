# Docker Webhook Auto-Deployer

### Purpose
This project is a lightweight, secure FastAPI webhook server designed to automate Docker deployments directly from your VM. When triggered by a CI/CD pipeline (like GitHub Actions), it securely logs into a container registry, pulls the latest image, stops the old container, and spins up the new one. It includes built-in failure verification: if your newly deployed app crashes on startup, the webhook grabs the error logs and fails the CI/CD pipeline so you are immediately alerted.

---

### Setup Instructions

#### 1. Create Environment Files
On your server, create two environment files. 

First, a `.env` file for the webhook's own security token:
```env
# .env (Webhook config)
WEBHOOK_SECRET=your_super_secret_generated_token
```

Second, an `app.env` file containing the environment variables for your actual Python application:
```env
# app.env (Deployed app config)
OPENAI_API_KEY=sk-...
ENVIRONMENT=production
```

#### 2. Build and Run the Webhook Server
Build the webhook Docker image and run it. We mount `/var/run/docker.sock` so it can control Docker, and `app.env` so it can inject your app's secrets.

```bash
# Build the image
docker build -t deploy-webhook -f Dockerfile.webhook .

# Run the container
# Note: Update the absolute path to your app.env file!
# Node: for --network, its recomended to use TLS e.g. via caddy for https. If use network, no need for -p
docker run -d \
  --name deploy-webhook \
  --restart unless-stopped \
  --network caddy \
  -p 9000:9000 \
  --env-file .env \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /absolute/path/to/your/app.env:/app/app.env:ro \
  deploy-webhook
```

#### 3. GitHub Actions Configuration
Add the following step to the end of your GitHub Actions `.yml` workflow (after the image is built and pushed).

Make sure to add `WEBHOOK_URL` (e.g., `http://YOUR_SERVER_IP:9000/deploy`) and `WEBHOOK_SECRET` to your GitHub Repository Secrets.

```yml
      - name: Trigger Webhook Deployment
        run: |
          curl -sS --fail-with-body -X POST ${{ secrets.WEBHOOK_URL }} \
            -H "Content-Type: application/json" \
            -H "X-Webhook-Token: ${{ secrets.WEBHOOK_SECRET }}" \
            -d '{
              "registry": "ghcr.io",
              "image": "ghcr.io/${{ github.repository_owner }}/YOUR_IMAGE_NAME:latest",
              "username": "${{ github.actor }}",
              "password": "${{ secrets.GITHUB_TOKEN }}"
            }'
```

**That's it!** Now, every push to `main` will build the image, notify the webhook, and seamlessly restart your application.

#### Example github workflow

```yml
name: Build and Push Docker Image (latest)

on:
  push:
    branches: ["main"]

permissions:
  contents: read
  packages: write

jobs:
  build-and-push:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push image
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository_owner }}/${{ SOME PROJECT NAME }}:latest
            ghcr.io/${{ github.repository_owner }}/${{ SOME PROJECT NAME }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Trigger Webhook Deployment
        run: |
          curl -sS --fail-with-body -X POST ${{ secrets.WEBHOOK_URL }} \
            -H "Content-Type: application/json" \
            -H "X-Webhook-Token: ${{ secrets.WEBHOOK_SECRET }}" \
            -d '{
              "registry": "ghcr.io",
              "image": "ghcr.io/${{ github.repository_owner }}/${{ SOME PROJECT NAME }}:latest",
              "username": "${{ github.actor }}",
              "password": "${{ secrets.GITHUB_TOKEN }}"
            }'
```