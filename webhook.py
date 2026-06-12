#This is the external link http://victorsserver.duckdns.org:9000/health

import subprocess
import os
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

app = FastAPI()

# Read the secret token from environment variables (fallback for local testing)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "my-super-secret-token")

class DeployPayload(BaseModel):
    registry: str
    image: str
    username: str
    password: str

@app.post("/deploy")
def deploy(payload: DeployPayload, x_webhook_token: str = Header(None)):
    # 1. Verify Authentication
    if x_webhook_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized webhook token")

    try:
        # 2. Docker Login
        # Securely pass the password via stdin
        login_cmd = ['docker', 'login', payload.registry, '-u', payload.username, '--password-stdin']
        subprocess.run(login_cmd, input=payload.password.encode(), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # 3. Pull the latest image
        subprocess.run(['docker', 'pull', payload.image], check=True)

        # 4. Remove the old container if it exists
        container_name = "fastreplai-agents-app"
        subprocess.run(['docker', 'rm', '-f', container_name], check=False)

        # 5. Run the new container with restart policy
        run_cmd = [
            'docker', 'run', '-d',
            '--name', container_name,
            '--restart', 'unless-stopped',
            '-p', '8082:8000',
        ]

        if os.path.exists('/app/app.env'):
            run_cmd.extend(['--env-file', '/app/app.env'])

        run_cmd.append(payload.image)

        subprocess.run(run_cmd, check=True, text=True, capture_output=True)

        # 5. WAIT AND VERIFY
        time.sleep(5) 

        inspect_cmd = ['docker', 'inspect', '-f', '{{.State.Status}}', container_name]
        inspect_result = subprocess.run(inspect_cmd, check=True, text=True, capture_output=True)
        status = inspect_result.stdout.strip()

        if status != "running":
            logs_cmd = ['docker', 'logs', '--tail', '30', container_name]
            logs_result = subprocess.run(logs_cmd, text=True, capture_output=True)
            crash_logs = logs_result.stdout + logs_result.stderr
            raise HTTPException(status_code=500, detail=f"Container crashed! Status: {status}. Logs:\n{crash_logs}")

        return {"status": "success", "message": f"Successfully deployed {payload.image}"}

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        raise HTTPException(status_code=500, detail=f"Deployment failed: {error_msg}")


@app.get("/health")
def health_check():
    """Simple health check to ensure the API is up and Docker is accessible."""
    try:
        # Ping docker to ensure the socket is mounted and working
        subprocess.run(
            ['docker', 'info'], 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        return {"status": "healthy", "docker": "connected"}
    except Exception as e:
        # If docker isn't responding, we return a 500 error
        raise HTTPException(status_code=500, detail=f"API is running, but Docker is unreachable: {str(e)}")
