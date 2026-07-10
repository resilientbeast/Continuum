"use client";

import { useState, useRef, useEffect } from "react";
import { UserButton } from "@clerk/nextjs";
import { UploadCloud, FileVideo, Loader2, CheckCircle2, Download, AlertCircle, AudioWaveform } from "lucide-react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";

export default function Dashboard() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "queued" | "processing" | "completed" | "failed">("idle");
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Polling for job status
  useEffect(() => {
    let interval: NodeJS.Timeout;
    
    if (jobId && (status === "queued" || status === "processing")) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_URL}/status/${jobId}`);
          if (res.ok) {
            const data = await res.json();
            if (data.status === "completed") {
              setStatus("completed");
            } else if (data.status === "failed") {
              setStatus("failed");
              setError(data.error || "An unknown error occurred during processing.");
            } else {
              setStatus(data.status); // queued or processing
            }
          }
        } catch (err) {
          console.error("Error polling status:", err);
        }
      }, 5000); // poll every 5s
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
      
      const formData = new FormData();
      formData.append("file", file);
      
      const res = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });
      
      if (!res.ok) {
        throw new Error("Failed to upload video");
      }
      
      const data = await res.json();
      setJobId(data.job_id);
      setStatus("queued");
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
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Header */}
      <header className="border-b border-white/10 bg-slate-950/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 transition-opacity hover:opacity-80">
            <div className="p-1.5 bg-indigo-500/10 rounded-lg border border-indigo-500/20">
              <AudioWaveform className="w-5 h-5 text-indigo-400" />
            </div>
            <span className="text-lg font-bold text-white">Continuum</span>
          </Link>
          <div className="flex items-center gap-4">
            <UserButton afterSignOutUrl="/" />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-6 py-12">
        <div className="mb-10 text-center md:text-left">
          <h1 className="text-3xl font-bold text-white mb-2">Mastering Dashboard</h1>
          <p className="text-slate-400">Upload your video to generate a cinematic spatial audio mix.</p>
        </div>

        <div className="bg-slate-900/50 border border-white/5 rounded-2xl p-8 backdrop-blur-sm shadow-2xl relative overflow-hidden">
          {/* Subtle gradient background effect */}
          <div className="absolute inset-0 pointer-events-none bg-gradient-to-br from-indigo-500/5 to-purple-500/5" />
          
          <AnimatePresence mode="wait">
            {/* Upload State */}
            {(status === "idle" || status === "uploading") && (
              <motion.div
                key="upload"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="relative z-10 flex flex-col items-center"
              >
                <div 
                  className={`w-full max-w-2xl border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center transition-all ${
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
                      <p className="text-slate-400 text-sm mt-2">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                      
                      <div className="flex gap-4 mt-8">
                        <button 
                          onClick={handleReset}
                          className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
                          disabled={status === "uploading"}
                        >
                          Clear
                        </button>
                        <button 
                          onClick={handleUpload}
                          disabled={status === "uploading"}
                          className="flex items-center gap-2 px-6 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg transition-all shadow-[0_0_15px_rgba(99,102,241,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
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
                      <div className="w-20 h-20 bg-slate-800 rounded-full flex items-center justify-center mb-6">
                        <UploadCloud className="w-10 h-10 text-slate-400" />
                      </div>
                      <p className="text-white text-lg font-medium mb-2">Drag and drop your video here</p>
                      <p className="text-slate-400 mb-6 max-w-sm">MP4, MOV, or WEBM up to 500MB</p>
                      <button 
                        onClick={() => fileInputRef.current?.click()}
                        className="px-6 py-2.5 text-sm font-medium text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 hover:bg-indigo-500/20 rounded-lg transition-colors"
                      >
                        Browse Files
                      </button>
                    </div>
                  )}
                </div>
                
                {error && (
                  <div className="mt-6 flex items-center gap-2 text-red-400 bg-red-400/10 px-4 py-3 rounded-lg border border-red-400/20">
                    <AlertCircle className="w-5 h-5" />
                    <span>{error}</span>
                  </div>
                )}
              </motion.div>
            )}

            {/* Processing State */}
            {(status === "queued" || status === "processing") && (
              <motion.div
                key="processing"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="relative z-10 flex flex-col items-center justify-center py-16"
              >
                <div className="relative">
                  <div className="w-24 h-24 border-4 border-slate-700 border-t-indigo-500 rounded-full animate-spin" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <AudioWaveform className="w-8 h-8 text-indigo-400 animate-pulse" />
                  </div>
                </div>
                <h3 className="text-xl font-bold text-white mt-8 mb-2">
                  {status === "queued" ? "Waiting in Queue" : "Mastering in Progress"}
                </h3>
                <p className="text-slate-400 max-w-sm text-center">
                  Our AI agents are analyzing visual context, isolating stems, and placing audio objects in 3D space. This usually takes a few minutes.
                </p>
              </motion.div>
            )}

            {/* Completed State */}
            {status === "completed" && (
              <motion.div
                key="completed"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="relative z-10 flex flex-col items-center py-12"
              >
                <div className="w-20 h-20 bg-green-500/10 border border-green-500/20 rounded-full flex items-center justify-center mb-6">
                  <CheckCircle2 className="w-10 h-10 text-green-400" />
                </div>
                <h3 className="text-2xl font-bold text-white mb-2">Mastering Complete!</h3>
                <p className="text-slate-400 mb-8 text-center max-w-sm">
                  Your cinematic spatial audio mix has been rendered to a 5.1 binaural stereo file.
                </p>
                
                <div className="flex gap-4">
                  <button 
                    onClick={handleReset}
                    className="px-6 py-3 text-sm font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition-colors"
                  >
                    Process Another
                  </button>
                  <a 
                    href={`${API_URL}/download/${jobId}`}
                    download
                    className="flex items-center gap-2 px-8 py-3 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl transition-all shadow-[0_0_20px_rgba(99,102,241,0.4)]"
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
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="relative z-10 flex flex-col items-center py-12"
              >
                <div className="w-20 h-20 bg-red-500/10 border border-red-500/20 rounded-full flex items-center justify-center mb-6">
                  <AlertCircle className="w-10 h-10 text-red-400" />
                </div>
                <h3 className="text-2xl font-bold text-white mb-2">Processing Failed</h3>
                <p className="text-red-400 mb-8 max-w-md text-center bg-red-400/5 p-4 rounded-lg border border-red-400/10 overflow-auto max-h-32 text-sm">
                  {error}
                </p>
                
                <button 
                  onClick={handleReset}
                  className="px-6 py-3 text-sm font-medium text-white bg-slate-700 hover:bg-slate-600 rounded-xl transition-colors"
                >
                  Try Again
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
