import os
import shutil
import uuid
import subprocess
import threading
import sqlite3
import jwt
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Continuum Audio Pipeline API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path("api_output")
OUTPUT_DIR.mkdir(exist_ok=True)
DB_PATH = "jobs.db"

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_S3_BUCKET_NAME = os.environ.get("AWS_S3_BUCKET_NAME")
CLERK_ISSUER = os.environ.get("CLERK_ISSUER") # e.g. https://clerk.yourdomain.com

# Boto3 uses AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY automatically from env
s3_client = boto3.client('s3', region_name=AWS_REGION)

jwks_client = None
if CLERK_ISSUER:
    jwks_client = jwt.PyJWKClient(f"{CLERK_ISSUER}/.well-known/jwks.json")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id TEXT PRIMARY KEY, user_id TEXT, filename TEXT, status TEXT, message TEXT, s3_key TEXT, result_s3_key TEXT)''')
    conn.commit()
    conn.close()

init_db()

def update_job(job_id, status=None, message=None, result_s3_key=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status:
        c.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
    if message:
        c.execute("UPDATE jobs SET message=? WHERE id=?", (message, job_id))
    if result_s3_key:
        c.execute("UPDATE jobs SET result_s3_key=? WHERE id=?", (result_s3_key, job_id))
    conn.commit()
    conn.close()

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1]
    try:
        if jwks_client:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_signature": True}
            )
        else:
            print("WARNING: CLERK_ISSUER not set, skipping JWT signature verification")
            decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded.get("sub")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

@app.get("/s3/upload-url")
async def get_s3_upload_url(filename: str, user_id: str = Depends(get_current_user)):
    if not AWS_S3_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="S3 is not configured on the backend.")
        
    s3_key = f"uploads/{user_id}/{uuid.uuid4()}_{filename}"
    
    try:
        response = s3_client.generate_presigned_post(
            Bucket=AWS_S3_BUCKET_NAME,
            Key=s3_key,
            Conditions=[
                ["content-length-range", 1, 524288000] # 500MB max limit
            ],
            ExpiresIn=3600 # 1 hour
        )
        return {"url": response["url"], "fields": response["fields"], "s3_key": s3_key}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))

class JobCreate(BaseModel):
    filename: str
    s3_key: str
    target_format: str = "binaural"

def run_pipeline_task(job_id: str, s3_key: str, target_format: str = "binaural"):
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    video_path = job_dir / "input_video.mp4"
    
    try:
        update_job(job_id, status="processing", message="Downloading video from S3...")
        
        # Download from S3
        s3_client.download_file(AWS_S3_BUCKET_NAME, s3_key, str(video_path))
        
        update_job(job_id, message="Initializing pipeline...")
        if target_format == "binaural":
            stages = "segment,separate,features,agent,render,binaural"
            pipeline_target = "5.1"
        else:
            stages = "segment,separate,features,agent,render"
            pipeline_target = target_format

        cmd = [
            "python3", "main.py",
            "--input-video", str(video_path),
            "--output-dir", str(job_dir),
            "--only", stages,
            "--target", pipeline_target
        ]
        
        env = os.environ.copy()
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                print(f"[PIPELINE {job_id}] {line}", flush=True)
                if any(k in line for k in ["Stage", "Starting", "Finished", "Agent", "extracted", "Scene", "Coherence", "WARNING"]):
                    update_job(job_id, message=line)
                
        process.stdout.close()
        return_code = process.wait()
        
        if return_code != 0:
            update_job(job_id, status="failed", message="Pipeline failed. Check logs.")
            return

        if target_format == "binaural":
            result_file = job_dir / "film_binaural.wav"
        else:
            result_file = job_dir / f"film_{target_format}.wav"

        if not result_file.exists():
            result_file = job_dir / "film_fallback_5.1.wav"
            
        if result_file.exists():
            update_job(job_id, message="Uploading mastered audio back to S3...")
            result_s3_key = f"results/{job_id}/mastered.wav"
            s3_client.upload_file(str(result_file), AWS_S3_BUCKET_NAME, result_s3_key)
            
            # Preserve evidence of coherence for judging walkthroughs
            artifacts = ["film.adm.wav", "coherence_memory.json", "scenes_with_features.json", "stem_manifest.json", "scenes.json"]
            for p in job_dir.glob("scene_*_placements.json"):
                artifacts.append(p.name)
            
            for artifact in artifacts:
                apath = job_dir / artifact
                if apath.exists():
                    s3_client.upload_file(str(apath), AWS_S3_BUCKET_NAME, f"results/{job_id}/{artifact}")
            
            update_job(job_id, status="completed", message="Mastering complete!", result_s3_key=result_s3_key)
        else:
            update_job(job_id, status="failed", message="Pipeline completed but no output file found.")
            
    except Exception as e:
        update_job(job_id, status="failed", message=f"Error: {str(e)}")
    finally:
        # Clean up local temporary files
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)

@app.post("/job")
async def create_job(job_req: JobCreate, user_id: str = Depends(get_current_user)):
    job_id = str(uuid.uuid4())
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # We replaced result_path with s3_key and result_s3_key in DB
    c.execute("INSERT INTO jobs (id, user_id, filename, status, message, s3_key) VALUES (?, ?, ?, ?, ?, ?)",
              (job_id, user_id, job_req.filename, "queued", "Waiting in queue...", job_req.s3_key))
    conn.commit()
    conn.close()
    
    thread = threading.Thread(target=run_pipeline_task, args=(job_id, job_req.s3_key, job_req.target_format))
    thread.start()
    
    return {"job_id": job_id, "status": "queued"}

@app.get("/status/{job_id}")
async def get_status(job_id: str, user_id: str = Depends(get_current_user)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT status, message FROM jobs WHERE id=? AND user_id=?", (job_id, user_id))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
        
    return {"status": row[0], "message": row[1]}

@app.get("/history")
async def get_history(user_id: str = Depends(get_current_user)):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, filename, status, message FROM jobs WHERE user_id=? ORDER BY rowid DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/download/{job_id}")
async def download_result(job_id: str, user_id: str = Depends(get_current_user)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT status, result_s3_key FROM jobs WHERE id=? AND user_id=?", (job_id, user_id))
    row = c.fetchone()
    conn.close()

    if not row:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    
    if row[0] != "completed":
        return JSONResponse(status_code=400, content={"error": "Job not completed"})
        
    result_s3_key = row[1]
    if not result_s3_key:
        return JSONResponse(status_code=404, content={"error": "S3 Key not found"})
        
    try:
        # Generate a pre-signed URL for downloading the result
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': AWS_S3_BUCKET_NAME, 'Key': result_s3_key},
            ExpiresIn=3600
        )
        return {"url": url}
    except ClientError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
