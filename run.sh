# remove old image
docker stop deploy-webhook
docker rm deploy-webhook

# Build the webhook image
docker build -t deploy-webhook -f Dockerfile.webhook .

# Run the webhook container
docker run -d \
  --name deploy-webhook \
  --network caddy \
  --restart unless-stopped \
  --env-file .env \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /home/victor/Projects/github-auto-deploy/app.env:/app/app.env:ro \
  deploy-webhook