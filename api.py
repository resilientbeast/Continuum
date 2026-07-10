import os
import shutil
import uuid
import subprocess
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import threading

app = FastAPI(title="Spatial Audio Pipeline API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS = {}
OUTPUT_DIR = Path("api_output")
OUTPUT_DIR.mkdir(exist_ok=True)

def run_pipeline_task(job_id: str, video_path: str):
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    try:
        JOBS[job_id]["status"] = "processing"
        
        # Call main.py
        cmd = [
            "python3", "main.py",
            "--input-video", str(video_path),
            "--output-dir", str(job_dir),
            # Only run the core pipeline, no dashboard
            "--only", "segment,separate,features,agent,render,binaural"
        ]
        
        # We also pass the env vars so Fireworks API can be hit
        env = os.environ.copy()
        
        process = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
        
        # Check if the expected output exists
        result_file = job_dir / "film_binaural.wav"
        if not result_file.exists():
            # try fallback
            result_file = job_dir / "film_fallback_5.1.wav"
            
        if result_file.exists():
            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["result_path"] = str(result_file)
        else:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = "Pipeline completed but no output file found."
            
    except subprocess.CalledProcessError as e:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = e.stderr or e.stdout
    except Exception as e:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(e)

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    video_path = job_dir / file.filename
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    JOBS[job_id] = {"status": "queued"}
    
    # Run pipeline in a background thread so we don't block the async event loop
    thread = threading.Thread(target=run_pipeline_task, args=(job_id, str(video_path)))
    thread.start()
    
    return {"job_id": job_id, "status": "queued"}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in JOBS:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    
    # Do not return full path to the client
    res = JOBS[job_id].copy()
    if "result_path" in res:
        del res["result_path"]
    return res

@app.get("/download/{job_id}")
async def download_result(job_id: str):
    if job_id not in JOBS:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    
    job = JOBS[job_id]
    if job["status"] != "completed":
        return JSONResponse(status_code=400, content={"error": "Job not completed"})
        
    result_path = job.get("result_path")
    if not result_path or not os.path.exists(result_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
        
    return FileResponse(result_path, media_type="audio/wav", filename="processed_audio.wav")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
