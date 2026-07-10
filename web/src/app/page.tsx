"use client";

import { motion } from "framer-motion";
import { ArrowRight, AudioWaveform, Sparkles, Wand2 } from "lucide-react";
import Link from "next/link";
import { SignInButton, UserButton, useUser } from "@clerk/nextjs";

export default function LandingPage() {
  const { isLoaded, isSignedIn } = useUser();
  
  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* Background gradients */}
      <div className="absolute inset-0 z-0 bg-slate-950">
        <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-indigo-600/20 blur-[120px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-purple-600/20 blur-[120px]" />
      </div>

      <nav className="relative z-10 flex items-center justify-between p-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-indigo-500/10 rounded-xl border border-indigo-500/20">
            <AudioWaveform className="w-6 h-6 text-indigo-400" />
          </div>
          <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
            Continuum
          </span>
        </div>
        <div className="flex items-center gap-4">
          {(!isLoaded || !isSignedIn) && (
            <>
              <SignInButton mode="modal">
                <button className="text-sm font-medium text-slate-300 hover:text-white transition-colors">
                  Sign In
                </button>
              </SignInButton>
              <SignInButton mode="modal">
                <button className="px-4 py-2 text-sm font-medium text-white bg-indigo-500 hover:bg-indigo-600 rounded-lg shadow-[0_0_15px_rgba(99,102,241,0.3)] transition-all">
                  Get Started
                </button>
              </SignInButton>
            </>
          )}
          {isSignedIn && (
            <>
              <Link href="/dashboard" className="text-sm font-medium text-slate-300 hover:text-white transition-colors">
                Dashboard
              </Link>
              <UserButton />
            </>
          )}
        </div>
      </nav>

      <main className="relative z-10 flex flex-col items-center justify-center min-h-[calc(100vh-88px)] px-6 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-3 py-1 mb-8 text-sm text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 rounded-full"
        >
          <Sparkles className="w-4 h-4" />
          Powered by Fireworks AI & Gemma
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="max-w-4xl text-5xl md:text-7xl font-bold tracking-tight text-white mb-6"
        >
          Cinematic Spatial Audio, <br className="hidden md:block" />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400">
            Mastered by AI.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="max-w-2xl text-lg md:text-xl text-slate-400 mb-10"
        >
          Upload your video and let our intelligent agents separate stems, analyze visual context, and craft a coherent 5.1 binaural mix automatically.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          {(!isLoaded || !isSignedIn) && (
            <SignInButton mode="modal">
              <button className="group relative inline-flex items-center gap-2 px-8 py-4 text-lg font-medium text-white bg-indigo-600 rounded-xl overflow-hidden shadow-[0_0_30px_rgba(99,102,241,0.4)] transition-all hover:bg-indigo-500 hover:scale-105">
                <Wand2 className="w-5 h-5" />
                Start Mastering Free
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </button>
            </SignInButton>
          )}
          {isSignedIn && (
            <Link href="/dashboard" className="group relative inline-flex items-center gap-2 px-8 py-4 text-lg font-medium text-white bg-indigo-600 rounded-xl overflow-hidden shadow-[0_0_30px_rgba(99,102,241,0.4)] transition-all hover:bg-indigo-500 hover:scale-105">
              <Wand2 className="w-5 h-5" />
              Go to Dashboard
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>
          )}
        </motion.div>
      </main>
    </div>
  );
}
