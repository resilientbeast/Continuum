"use client";

import { motion } from "framer-motion";
import { ArrowRight, AudioWaveform, Sparkles, Wand2, Layers, BrainCircuit, Headphones } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { SignInButton, UserButton, useUser } from "@clerk/nextjs";

export default function LandingPage() {
  const { isLoaded, isSignedIn } = useUser();

  return (
    <div className="relative min-h-screen bg-slate-950 selection:bg-indigo-500/30">
      
      {/* Navigation */}
      <nav className="fixed top-0 inset-x-0 z-50 border-b border-white/5 bg-slate-950/50 backdrop-blur-md">
        <div className="flex items-center justify-between px-6 py-4 max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/10 rounded-xl border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.2)]">
              <AudioWaveform className="w-6 h-6 text-indigo-400" />
            </div>
            <span className="text-xl font-bold tracking-tight text-white">
              Continuum
            </span>
          </div>
          <div className="flex items-center gap-4">
            {(!isLoaded || !isSignedIn) && (
              <>
                <SignInButton mode="modal" forceRedirectUrl="/dashboard" signUpForceRedirectUrl="/dashboard">
                  <button className="text-sm font-medium text-slate-300 hover:text-white transition-colors">
                    Sign In
                  </button>
                </SignInButton>
                <SignInButton mode="modal" forceRedirectUrl="/dashboard" signUpForceRedirectUrl="/dashboard">
                  <button className="px-5 py-2.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg shadow-[0_0_20px_rgba(99,102,241,0.4)] transition-all">
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
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 md:pt-48 md:pb-32 overflow-hidden min-h-[90vh] flex items-center">
        {/* Background Image & Overlay */}
        <div className="absolute inset-0 z-0 select-none pointer-events-none">
          <Image 
            src="/hero-bg.png" 
            alt="Spatial Audio Waves" 
            fill 
            className="object-cover opacity-60 mix-blend-screen" 
            style={{ 
              maskImage: "linear-gradient(to bottom, black 30%, transparent 100%)", 
              WebkitMaskImage: "linear-gradient(to bottom, black 30%, transparent 100%)" 
            }}
            priority
          />
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-slate-950/80 to-slate-950" />
          <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-indigo-600/20 blur-[120px]" />
          <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-purple-600/20 blur-[120px]" />
        </div>

        <div className="relative z-10 max-w-7xl mx-auto px-6 text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-2 px-4 py-2 mb-8 text-sm font-medium text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 rounded-full backdrop-blur-sm shadow-[0_0_20px_rgba(99,102,241,0.15)]"
          >
            <Sparkles className="w-4 h-4 text-indigo-400" />
            Powered by Fireworks AI & Gemma
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
            className="max-w-5xl mx-auto text-5xl md:text-8xl font-bold tracking-tighter text-white mb-8 leading-[1.1]"
          >
            Cinematic Spatial Audio, <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 drop-shadow-lg">
              Mastered by AI.
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.2 }}
            className="max-w-2xl mx-auto text-lg md:text-2xl text-slate-400 mb-12 font-light"
          >
            Upload your video and let our intelligent agents separate stems, analyze visual context, and craft a coherent 5.1 binaural mix automatically.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.3 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            {(!isLoaded || !isSignedIn) && (
              <SignInButton mode="modal" forceRedirectUrl="/dashboard" signUpForceRedirectUrl="/dashboard">
                <button className="group relative inline-flex items-center justify-center gap-3 px-8 py-4 text-lg font-semibold text-white bg-indigo-600 rounded-xl overflow-hidden shadow-[0_0_40px_rgba(99,102,241,0.5)] hover:shadow-[0_0_60px_rgba(99,102,241,0.6)] transition-all hover:scale-105 hover:bg-indigo-500 w-full sm:w-auto">
                  <Wand2 className="w-5 h-5" />
                  Start Mastering Free
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </button>
              </SignInButton>
            )}
            {isSignedIn && (
              <Link href="/dashboard" className="group relative inline-flex items-center justify-center gap-3 px-8 py-4 text-lg font-semibold text-white bg-indigo-600 rounded-xl overflow-hidden shadow-[0_0_40px_rgba(99,102,241,0.5)] hover:shadow-[0_0_60px_rgba(99,102,241,0.6)] transition-all hover:scale-105 hover:bg-indigo-500 w-full sm:w-auto">
                <Wand2 className="w-5 h-5" />
                Go to Dashboard
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </Link>
            )}
            <button className="px-8 py-4 text-lg font-semibold text-slate-300 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl transition-all w-full sm:w-auto hover:text-white">
              View Architecture
            </button>
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section className="relative z-10 py-24 bg-slate-950 border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-bold text-white mb-4 tracking-tight">The Future of Audio Engineering</h2>
            <p className="text-slate-400 text-lg md:text-xl max-w-2xl mx-auto font-light">
              Our multi-agent pipeline handles the tedious aspects of audio post-production so you can focus on the creative vision.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <motion.div 
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="p-8 rounded-3xl bg-gradient-to-b from-slate-900 to-slate-900/40 border border-white/5 hover:border-indigo-500/30 transition-all duration-300 group hover:-translate-y-2 shadow-lg hover:shadow-[0_10px_40px_rgba(99,102,241,0.1)]"
            >
              <div className="w-14 h-14 bg-indigo-500/10 rounded-2xl flex items-center justify-center border border-indigo-500/20 mb-6 group-hover:scale-110 transition-transform duration-300 shadow-[0_0_15px_rgba(99,102,241,0.2)]">
                <Layers className="w-7 h-7 text-indigo-400" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3 tracking-tight">Intelligent Stem Separation</h3>
              <p className="text-slate-400 leading-relaxed font-light">
                Automatically isolate dialogue, music, and sound effects from your master track using state-of-the-art Demucs architecture.
              </p>
            </motion.div>

            {/* Feature 2 */}
            <motion.div 
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="p-8 rounded-3xl bg-gradient-to-b from-slate-900 to-slate-900/40 border border-white/5 hover:border-purple-500/30 transition-all duration-300 group hover:-translate-y-2 shadow-lg hover:shadow-[0_10px_40px_rgba(168,85,247,0.1)]"
            >
              <div className="w-14 h-14 bg-purple-500/10 rounded-2xl flex items-center justify-center border border-purple-500/20 mb-6 group-hover:scale-110 transition-transform duration-300 shadow-[0_0_15px_rgba(168,85,247,0.2)]">
                <BrainCircuit className="w-7 h-7 text-purple-400" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3 tracking-tight">Context-Aware Placement</h3>
              <p className="text-slate-400 leading-relaxed font-light">
                Our vision-language models watch your video to understand where sounds are originating, placing them perfectly in 3D space.
              </p>
            </motion.div>

            {/* Feature 3 */}
            <motion.div 
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="p-8 rounded-3xl bg-gradient-to-b from-slate-900 to-slate-900/40 border border-white/5 hover:border-pink-500/30 transition-all duration-300 group hover:-translate-y-2 shadow-lg hover:shadow-[0_10px_40px_rgba(236,72,153,0.1)]"
            >
              <div className="w-14 h-14 bg-pink-500/10 rounded-2xl flex items-center justify-center border border-pink-500/20 mb-6 group-hover:scale-110 transition-transform duration-300 shadow-[0_0_15px_rgba(236,72,153,0.2)]">
                <Headphones className="w-7 h-7 text-pink-400" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3 tracking-tight">5.1 Binaural Render</h3>
              <p className="text-slate-400 leading-relaxed font-light">
                Export directly to a cinematic 5.1 surround mix folded down to binaural stereo for immersive listening on any standard headphones.
              </p>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-12 text-center text-slate-500">
        <p>© 2026 Continuum Audio. All rights reserved.</p>
      </footer>
    </div>
  );
}
