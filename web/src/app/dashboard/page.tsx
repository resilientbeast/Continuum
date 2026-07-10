"use client";

import { useState, useRef, useEffect } from "react";
import { UserButton, useAuth } from "@clerk/nextjs";
import { UploadCloud, FileVideo, Loader2, CheckCircle2, Download, AlertCircle, AudioWaveform, History, RefreshCcw } from "lucide-react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";

type Job = {
  id: string;
  filename: string;
  status: string;
  message: string;
};

export default function Dashboard() {
  const { getToken } = useAuth();
  
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "queued" | "processing" | "completed" | "failed">("idle");
  const [progressMessage, setProgressMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [history, setHistory] = useState<Job[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchHistory = async () => {
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(`${API_URL}/history`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (err) {
      console.error("Failed to fetch history:", err);
    } finally {
      setIsHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  // Polling for job status
  useEffect(() => {
    let interval: NodeJS.Timeout;
    
    if (jobId && (status === "queued" || status === "processing")) {
      interval = setInterval(async () => {
        try {
          const token = await getToken();
          const res = await fetch(`${API_URL}/status/${jobId}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          if (res.ok) {
            const data = await res.json();
            setProgressMessage(data.message);
            if (data.status === "completed") {
              setStatus("completed");
              fetchHistory(); // refresh history when done
            } else if (data.status === "failed") {
              setStatus("failed");
              setError(data.message || "An unknown error occurred.");
              fetchHistory();
            } else {
              setStatus(data.status); // queued or processing
            }
          }
        } catch (err) {
          console.error("Error polling status:", err);
        }
      }, 3000); // poll every 3s for faster log updates
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [jobId, status, API_URL]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected && selected.type.startsWith("video/")) {
      setFile(selected);
      setStatus("idle");
      setError(null);
    } else {
      setError("Please select a valid video file.");
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped && dropped.type.startsWith("video/")) {
      setFile(dropped);
      setStatus("idle");
      setError(null);
    } else {
      setError("Please drop a valid video file.");
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    
    try {
      setStatus("uploading");
      setError(null);
      setProgressMessage("Requesting secure upload URL...");
      
      const token = await getToken();
      if (!token) throw new Error("Authentication failed");
      
      // 1. Get pre-signed URL from our backend
      const presignRes = await fetch(`${API_URL}/s3/upload-url?filename=${encodeURIComponent(file.name)}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (!presignRes.ok) {
        throw new Error("Failed to get S3 upload URL");
      }
      
      const presignData = await presignRes.json();
      
      setProgressMessage("Uploading to AWS S3...");
      
      // 2. Upload directly to S3
      const s3FormData = new FormData();
      Object.entries(presignData.fields).forEach(([k, v]) => {
        s3FormData.append(k, v as string);
      });
      s3FormData.append("file", file);
      
      const uploadRes = await fetch(presignData.url, {
        method: "POST",
        body: s3FormData,
      });
      
      if (!uploadRes.ok) {
        throw new Error("Failed to upload file to S3");
      }
      
      setProgressMessage("Starting backend job...");
      
      // 3. Tell backend to start processing
      const jobRes = await fetch(`${API_URL}/job`, {
        method: "POST",
        headers: { 
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          filename: file.name,
          s3_key: presignData.s3_key
        }),
      });
      
      if (!jobRes.ok) {
        throw new Error("Failed to start job");
      }
      
      const data = await jobRes.json();
      setJobId(data.job_id);
      setStatus("queued");
      setProgressMessage("Waiting in queue...");
      fetchHistory(); // update history to show the queued job
    } catch (err) {
      console.error(err);
      setStatus("failed");
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  const handleReset = () => {
    setFile(null);
    setJobId(null);
    setStatus("idle");
    setError(null);
    setProgressMessage(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };
  
  const selectHistoryJob = (job: Job) => {
    setJobId(job.id);
    setStatus(job.status as any);
    setProgressMessage(job.message);
    setFile(new File([], job.filename)); // fake file for UI
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-white/10 bg-slate-950/50 backdrop-blur-md sticky top-0 z-50 flex-none">
        <div className="max-w-[1400px] mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 transition-opacity hover:opacity-80">
            <div className="p-1.5 bg-indigo-500/10 rounded-lg border border-indigo-500/20">
              <AudioWaveform className="w-5 h-5 text-indigo-400" />
            </div>
            <span className="text-lg font-bold text-white tracking-tight">Continuum</span>
          </Link>
          <div className="flex items-center gap-4">
            <UserButton />
          </div>
        </div>
      </header>

      {/* Layout */}
      <div className="flex flex-1 max-w-[1400px] w-full mx-auto overflow-hidden">
        
        {/* Sidebar History */}
        <aside className="w-80 border-r border-white/10 bg-slate-900/30 flex flex-col hidden md:flex">
          <div className="p-6 border-b border-white/5 flex items-center justify-between">
            <h2 className="text-white font-semibold flex items-center gap-2">
              <History className="w-4 h-4 text-slate-400" />
              Job History
            </h2>
            <button onClick={fetchHistory} className="text-slate-400 hover:text-white transition-colors" title="Refresh">
              <RefreshCcw className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {isHistoryLoading ? (
              <div className="text-center py-8 text-slate-500 text-sm">Loading history...</div>
            ) : history.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-sm">No recent jobs found.</div>
            ) : (
              history.map(job => (
                <button
                  key={job.id}
                  onClick={() => selectHistoryJob(job)}
                  className={`w-full text-left p-4 rounded-xl border transition-all ${jobId === job.id ? 'bg-indigo-500/10 border-indigo-500/30' : 'bg-slate-800/20 border-white/5 hover:bg-slate-800/40 hover:border-white/10'}`}
                >
                  <p className="text-sm font-medium text-white truncate mb-1">{job.filename}</p>
                  <div className="flex items-center justify-between text-xs">
                    <span className={`px-2 py-0.5 rounded-md ${
                      job.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                      job.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                      'bg-indigo-500/20 text-indigo-400'
                    }`}>
                      {job.status}
                    </span>
                    <span className="text-slate-500 truncate ml-2 max-w-[120px]">{job.message}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 px-6 py-12 overflow-y-auto">
          <div className="max-w-3xl mx-auto">
            <div className="mb-10 text-center md:text-left flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-white mb-2 tracking-tight">Mastering Dashboard</h1>
                <p className="text-slate-400">Upload your video to generate a cinematic spatial audio mix.</p>
              </div>
              {(jobId || file) && (
                <button 
                  onClick={handleReset}
                  className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
                >
                  New Job
                </button>
              )}
            </div>

            <div className="bg-slate-900/50 border border-white/5 rounded-3xl p-8 backdrop-blur-md shadow-2xl relative overflow-hidden">
              <div className="absolute inset-0 pointer-events-none bg-gradient-to-br from-indigo-500/5 to-purple-500/5" />
              
              <AnimatePresence mode="wait">
                {/* Upload State */}
                {(status === "idle" || status === "uploading") && (
                  <motion.div
                    key="upload"
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    className="relative z-10 flex flex-col items-center"
                  >
                    <div 
                      className={`w-full border-2 border-dashed rounded-2xl p-16 flex flex-col items-center justify-center transition-all ${
                        isDragging 
                          ? "border-indigo-500 bg-indigo-500/10" 
                          : "border-slate-700 bg-slate-800/30 hover:bg-slate-800/50 hover:border-slate-500"
                      }`}
                      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                      onDragLeave={() => setIsDragging(false)}
                      onDrop={handleDrop}
                    >
                      <input 
                        type="file" 
                        accept="video/*" 
                        className="hidden" 
                        ref={fileInputRef}
                        onChange={handleFileChange}
                      />
                      
                      {file ? (
                        <div className="flex flex-col items-center">
                          <FileVideo className="w-16 h-16 text-indigo-400 mb-4" />
                          <p className="text-white font-medium text-lg text-center break-all">{file.name}</p>
                          <p className="text-slate-400 text-sm mt-2">{file.size ? (file.size / (1024 * 1024)).toFixed(2) : "Unknown size"} MB</p>
                          
                          <div className="flex gap-4 mt-8">
                            <button 
                              onClick={handleReset}
                              className="px-6 py-3 text-sm font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition-colors"
                              disabled={status === "uploading"}
                            >
                              Clear
                            </button>
                            <button 
                              onClick={handleUpload}
                              disabled={status === "uploading"}
                              className="flex items-center gap-2 px-8 py-3 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl transition-all shadow-[0_0_20px_rgba(99,102,241,0.4)] disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {status === "uploading" ? (
                                <><Loader2 className="w-4 h-4 animate-spin" /> Uploading...</>
                              ) : (
                                <><UploadCloud className="w-4 h-4" /> Start Processing</>
                              )}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col items-center text-center">
                          <div className="w-20 h-20 bg-slate-800 rounded-full flex items-center justify-center mb-6 shadow-inner">
                            <UploadCloud className="w-10 h-10 text-slate-400" />
                          </div>
                          <p className="text-white text-xl font-semibold tracking-tight mb-2">Drag and drop your video here</p>
                          <p className="text-slate-400 mb-8 max-w-sm font-light">MP4, MOV, or WEBM up to 500MB</p>
                          <button 
                            onClick={() => fileInputRef.current?.click()}
                            className="px-8 py-3 text-sm font-medium text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 hover:bg-indigo-500/20 rounded-xl transition-colors shadow-lg"
                          >
                            Browse Files
                          </button>
                        </div>
                      )}
                    </div>
                    
                    {error && (
                      <div className="mt-6 w-full flex items-center gap-3 text-red-400 bg-red-400/10 px-5 py-4 rounded-xl border border-red-400/20">
                        <AlertCircle className="w-5 h-5 flex-none" />
                        <span className="text-sm">{error}</span>
                      </div>
                    )}
                  </motion.div>
                )}

                {/* Processing State */}
                {(status === "queued" || status === "processing") && (
                  <motion.div
                    key="processing"
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    className="relative z-10 flex flex-col items-center justify-center py-20"
                  >
                    <div className="relative mb-10">
                      <div className="w-32 h-32 border-4 border-slate-700/50 border-t-indigo-500 rounded-full animate-spin" />
                      <div className="absolute inset-0 flex items-center justify-center">
                        <AudioWaveform className="w-10 h-10 text-indigo-400 animate-pulse" />
                      </div>
                    </div>
                    <h3 className="text-2xl font-bold text-white mb-3 tracking-tight">
                      {status === "queued" ? "Waiting in Queue" : "Mastering in Progress"}
                    </h3>
                    
                    {/* Live Progress Terminal Output */}
                    <div className="w-full max-w-lg mt-6 bg-black/40 border border-white/10 rounded-xl p-4 font-mono text-sm text-indigo-300 relative overflow-hidden shadow-inner">
                      <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-indigo-500/50 to-transparent" />
                      <div className="flex items-start gap-3">
                        <Loader2 className="w-4 h-4 animate-spin text-slate-500 mt-0.5 flex-none" />
                        <span className="break-all">{progressMessage || "Initializing pipeline..."}</span>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Completed State */}
                {status === "completed" && (
                  <motion.div
                    key="completed"
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    className="relative z-10 flex flex-col items-center py-16"
                  >
                    <div className="w-24 h-24 bg-green-500/10 border border-green-500/20 rounded-full flex items-center justify-center mb-8 shadow-[0_0_30px_rgba(34,197,94,0.15)]">
                      <CheckCircle2 className="w-12 h-12 text-green-400" />
                    </div>
                    <h3 className="text-3xl font-bold text-white mb-3 tracking-tight">Mastering Complete!</h3>
                    <p className="text-slate-400 mb-10 text-center max-w-md font-light text-lg">
                      Your cinematic spatial audio mix has been rendered to a 5.1 binaural stereo file.
                    </p>
                    
                    <div className="flex gap-4">
                      <a 
                        href={`${API_URL}/download/${jobId}`}
                        download
                        className="flex items-center gap-3 px-10 py-4 text-base font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl transition-all shadow-[0_0_30px_rgba(99,102,241,0.4)] hover:scale-105"
                      >
                        <Download className="w-5 h-5" />
                        Download Mix
                      </a>
                    </div>
                  </motion.div>
                )}

                {/* Failed State */}
                {status === "failed" && !error?.includes("upload") && (
                  <motion.div
                    key="failed"
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    className="relative z-10 flex flex-col items-center py-16"
                  >
                    <div className="w-24 h-24 bg-red-500/10 border border-red-500/20 rounded-full flex items-center justify-center mb-8 shadow-[0_0_30px_rgba(239,68,68,0.15)]">
                      <AlertCircle className="w-12 h-12 text-red-400" />
                    </div>
                    <h3 className="text-3xl font-bold text-white mb-3 tracking-tight">Processing Failed</h3>
                    <div className="bg-black/40 w-full max-w-lg rounded-xl border border-red-500/20 p-5 mb-8 overflow-auto max-h-48 text-sm font-mono text-red-300 shadow-inner">
                      {error || progressMessage}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
