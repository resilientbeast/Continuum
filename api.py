import os
import shutil
import uuid
import subprocess
import threading
import sqlite3
import jwt
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

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

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id TEXT PRIMARY KEY, user_id TEXT, filename TEXT, status TEXT, message TEXT, result_path TEXT)''')
    conn.commit()
    conn.close()

init_db()

def update_job(job_id, status=None, message=None, result_path=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status:
        c.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
    if message:
        c.execute("UPDATE jobs SET message=? WHERE id=?", (message, job_id))
    if result_path:
        c.execute("UPDATE jobs SET result_path=? WHERE id=?", (result_path, job_id))
    conn.commit()
    conn.close()

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1]
    try:
        # For ease of hackathon deployment, we decode without strict signature verification.
        # In production, fetch the Clerk JWKS keys and verify the signature.
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded.get("sub")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

def run_pipeline_task(job_id: str, video_path: str):
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    try:
        update_job(job_id, status="processing", message="Initializing pipeline...")
        
        cmd = [
            "python3", "main.py",
            "--input-video", str(video_path),
            "--output-dir", str(job_dir),
            "--only", "segment,separate,features,agent,render,binaural"
        ]
        
        env = os.environ.copy()
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        
        # Read stdout line by line to get real-time progress
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                if "Stage" in line or "Starting" in line or "Finished" in line or "Agent" in line or "extracted" in line:
                    update_job(job_id, message=line)
                
        process.stdout.close()
        return_code = process.wait()
        
        if return_code != 0:
            update_job(job_id, status="failed", message="Pipeline failed. Check logs.")
            return

        result_file = job_dir / "film_binaural.wav"
        if not result_file.exists():
            result_file = job_dir / "film_fallback_5.1.wav"
            
        if result_file.exists():
            update_job(job_id, status="completed", message="Mastering complete!", result_path=str(result_file))
        else:
            update_job(job_id, status="failed", message="Pipeline completed but no output file found.")
            
    except Exception as e:
        update_job(job_id, status="failed", message=f"Error: {str(e)}")

@app.post("/upload")
async def upload_video(file: UploadFile = File(...), user_id: str = Depends(get_current_user)):
    job_id = str(uuid.uuid4())
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    video_path = job_dir / file.filename
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO jobs (id, user_id, filename, status, message) VALUES (?, ?, ?, ?, ?)",
              (job_id, user_id, file.filename, "queued", "Waiting in queue..."))
    conn.commit()
    conn.close()
    
    thread = threading.Thread(target=run_pipeline_task, args=(job_id, str(video_path)))
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
async def download_result(job_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT status, result_path FROM jobs WHERE id=?", (job_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    
    if row[0] != "completed":
        return JSONResponse(status_code=400, content={"error": "Job not completed"})
        
    result_path = row[1]
    if not result_path or not os.path.exists(result_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
        
    return FileResponse(result_path, media_type="audio/wav", filename="processed_audio.wav")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
