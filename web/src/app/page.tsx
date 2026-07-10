"use client";

import { motion } from "framer-motion";
import { ArrowRight, AudioWaveform, Sparkles, Wand2, Layers, BrainCircuit, Headphones, GitBranch, Link as LinkIcon, SplitSquareHorizontal, Activity, Eye, Network, Waves, Video, CheckCircle2, Speaker } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { SignInButton, UserButton, useUser } from "@clerk/nextjs";

export default function LandingPage() {
  const { isLoaded, isSignedIn } = useUser();

  return (
    <div className="relative min-h-screen bg-slate-950 selection:bg-indigo-500/30 font-sans">
      
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
          <div className="flex items-center gap-6">
            <a href="https://github.com/resilientbeast/Continuum" target="_blank" rel="noreferrer" className="text-slate-400 hover:text-white transition-colors">
              <GitBranch className="w-5 h-5" />
            </a>
            <div className="h-4 w-px bg-white/10" />
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
      <section className="relative pt-32 pb-20 md:pt-48 md:pb-32 overflow-hidden min-h-[90vh] flex items-center border-b border-white/5">
        <div className="absolute inset-0 z-0 select-none pointer-events-none">
          <Image 
            src="/hero-bg.png" 
            alt="Spatial Audio Waves" 
            fill 
            className="object-cover opacity-50 mix-blend-screen" 
            style={{ maskImage: "linear-gradient(to bottom, black 30%, transparent 100%)", WebkitMaskImage: "linear-gradient(to bottom, black 30%, transparent 100%)" }}
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
            Powered by Fireworks AI
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
            className="max-w-5xl mx-auto text-5xl md:text-7xl lg:text-8xl font-bold tracking-tighter text-white mb-8 leading-[1.1]"
          >
            Spatially Coherent Audio <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 drop-shadow-lg">
              for AI Video.
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.2 }}
            className="max-w-3xl mx-auto text-lg md:text-2xl text-slate-400 mb-12 font-light leading-relaxed"
          >
            Upload your video and let our intelligent agents separate stems, analyze visual context, and maintain persistent spatial placements across scene cuts using cross-scene coherence memory.
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
            <a href="https://github.com/resilientbeast/Continuum" target="_blank" rel="noreferrer" className="px-8 py-4 text-lg font-semibold text-slate-300 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl transition-all w-full sm:w-auto hover:text-white flex items-center justify-center gap-2">
              <GitBranch className="w-5 h-5" />
              View Architecture
            </a>
          </motion.div>
        </div>
      </section>

      {/* Market Positioning */}
      <section className="relative z-10 py-24 bg-slate-950 border-b border-white/5">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold text-white mb-6">The Missing Spatial Layer for Generative Video</h2>
          <p className="text-xl text-slate-400 font-light leading-relaxed">
            AI video generators like Veo, Runway, and Kling produce stunning visuals, but leave you with flat, disjointed mono or stereo audio. Standard upmixers randomly pan stems on every camera cut, destroying immersion. <strong className="text-white font-medium">Continuum solves this.</strong> By tracking stems natively across cuts, we deliver true cinematic spatial audio that anchors the narrative.
          </p>
        </div>
      </section>

      {/* Coherence Showcase */}
      <section className="relative z-10 py-24 bg-gradient-to-b from-slate-950 to-indigo-950/20 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            <div>
              <div className="inline-flex items-center justify-center p-3 bg-indigo-500/10 rounded-xl border border-indigo-500/20 mb-6">
                <Network className="w-8 h-8 text-indigo-400" />
              </div>
              <h2 className="text-4xl font-bold text-white mb-6">Cross-Scene Coherence Memory</h2>
              <p className="text-lg text-slate-400 font-light leading-relaxed mb-8">
                The centerpiece of Continuum. We persist a JSON state of every object's spatial placement. When a scene cuts, recurring elements (ambient beds, character dialogue, musical motifs) are checked against this memory and intelligently hold their position in the 3D room, rather than jumping randomly between speakers.
              </p>
              
              <div className="bg-slate-900/50 border border-white/10 rounded-2xl p-6">
                <div className="flex items-center gap-4 mb-2">
                  <div className="p-2 bg-green-500/20 rounded-lg">
                    <CheckCircle2 className="w-6 h-6 text-green-400" />
                  </div>
                  <h4 className="text-xl font-semibold text-white">Proven Consistency</h4>
                </div>
                <p className="text-slate-300">
                  In a complex 8-scene cinematic test sequence, <strong className="text-indigo-400 font-bold text-xl">27 / 28</strong> recurring elements perfectly retained placement across cuts, only re-panning when justified by on-screen visual shifts.
                </p>
              </div>
            </div>
            
            <div className="space-y-6">
              {/* Visual Showcase Box */}
              <div className="bg-slate-900 border border-white/10 rounded-3xl p-8 relative overflow-hidden shadow-2xl">
                <div className="absolute top-0 right-0 p-4 opacity-10">
                  <Network className="w-32 h-32" />
                </div>
                <h4 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-6">Pipeline Trace: "Ambient Hum"</h4>
                
                <div className="space-y-8 relative">
                  <div className="absolute left-6 top-6 bottom-6 w-px bg-slate-800" />
                  
                  <div className="flex gap-6 relative z-10">
                    <div className="w-12 h-12 rounded-full bg-slate-800 border-2 border-indigo-500 flex items-center justify-center shrink-0">
                      <span className="text-indigo-400 font-bold">S1</span>
                    </div>
                    <div>
                      <h5 className="text-white font-medium text-lg">Scene 1 Cut</h5>
                      <p className="text-slate-400 text-sm mt-1">Vision model detects wide shot. <br/>Placed at: <span className="text-indigo-300 font-mono bg-indigo-500/10 px-2 py-0.5 rounded">surround-left (-110°)</span></p>
                    </div>
                  </div>
                  
                  <div className="flex gap-6 relative z-10 opacity-50">
                    <div className="w-12 h-12 rounded-full bg-slate-800 border-2 border-slate-600 flex items-center justify-center shrink-0">
                      <span className="text-slate-400 font-bold">...</span>
                    </div>
                    <div className="flex items-center">
                      <p className="text-slate-500 text-sm">Multiple scene transitions...</p>
                    </div>
                  </div>

                  <div className="flex gap-6 relative z-10">
                    <div className="w-12 h-12 rounded-full bg-slate-800 border-2 border-green-500 flex items-center justify-center shrink-0">
                      <span className="text-green-400 font-bold">S6</span>
                    </div>
                    <div>
                      <h5 className="text-white font-medium text-lg flex items-center gap-2">
                        Scene 6 Cut <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-full uppercase tracking-wide font-bold">Memory Match</span>
                      </h5>
                      <p className="text-slate-400 text-sm mt-1">Continuum anchors the stem to its original placement. <br/>Persisted at: <span className="text-green-300 font-mono bg-green-500/10 px-2 py-0.5 rounded">surround-left (-110°)</span></p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* The Multi-Agent Pipeline */}
      <section className="relative z-10 py-24 bg-slate-950 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-bold text-white mb-4 tracking-tight">The Architecture</h2>
            <p className="text-slate-400 text-lg md:text-xl max-w-2xl mx-auto font-light">
              An end-to-end multi-agent pipeline built on commodity tools, supercharged by our novel coherence logic.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-6 gap-4 text-center">
            {[
              { icon: SplitSquareHorizontal, label: "1. Scene Segmentation" },
              { icon: Waves, label: "2. Stem Separation" },
              { icon: Eye, label: "3. Context Captioning" },
              { icon: BrainCircuit, label: "4. Placement Reasoning" },
              { icon: Network, label: "5. Coherence Check" },
              { icon: AudioWaveform, label: "6. Spatial Render" }
            ].map((step, i) => (
              <div key={i} className="flex flex-col items-center p-4 bg-slate-900/50 rounded-2xl border border-white/5 hover:bg-slate-800/50 transition-colors">
                <step.icon className="w-8 h-8 text-indigo-400 mb-4" />
                <span className="text-sm font-medium text-slate-300">{step.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="relative z-10 py-24 bg-slate-950 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid md:grid-cols-3 gap-8">
            <motion.div 
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              className="p-8 rounded-3xl bg-gradient-to-b from-slate-900 to-slate-900/40 border border-white/5 hover:border-indigo-500/30 transition-all duration-300 group shadow-lg"
            >
              <div className="w-14 h-14 bg-indigo-500/10 rounded-2xl flex items-center justify-center border border-indigo-500/20 mb-6 shadow-[0_0_15px_rgba(99,102,241,0.2)]">
                <Network className="w-7 h-7 text-indigo-400" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3 tracking-tight">Cross-Scene Coherence</h3>
              <p className="text-slate-400 leading-relaxed font-light">
                The first AI upmixer to track objects across cuts. Our memory state anchors stems structurally over time, yielding a continuous, highly immersive experience.
              </p>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ delay: 0.1 }}
              className="p-8 rounded-3xl bg-gradient-to-b from-slate-900 to-slate-900/40 border border-white/5 hover:border-purple-500/30 transition-all duration-300 group shadow-lg"
            >
              <div className="w-14 h-14 bg-purple-500/10 rounded-2xl flex items-center justify-center border border-purple-500/20 mb-6 shadow-[0_0_15px_rgba(168,85,247,0.2)]">
                <Layers className="w-7 h-7 text-purple-400" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3 tracking-tight">Intelligent Separation</h3>
              <p className="text-slate-400 leading-relaxed font-light">
                Automatically isolate dialogue, music, and sound effects from your flat master track using state-of-the-art Demucs architecture.
              </p>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ delay: 0.2 }}
              className="p-8 rounded-3xl bg-gradient-to-b from-slate-900 to-slate-900/40 border border-white/5 hover:border-pink-500/30 transition-all duration-300 group shadow-lg"
            >
              <div className="w-14 h-14 bg-pink-500/10 rounded-2xl flex items-center justify-center border border-pink-500/20 mb-6 shadow-[0_0_15px_rgba(236,72,153,0.2)]">
                <BrainCircuit className="w-7 h-7 text-pink-400" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3 tracking-tight">Context-Aware Placement</h3>
              <p className="text-slate-400 leading-relaxed font-light">
                Vision-language models watch your video to understand where sounds are originating, placing them logically within the 3D space.
              </p>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Render Outputs Section */}
      <section className="relative z-10 py-24 bg-slate-950 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-bold text-white mb-4 tracking-tight">Four Selectable Output Formats</h2>
            <p className="text-slate-400 text-lg md:text-xl max-w-2xl mx-auto font-light">
              Continuum exports true, standards-compliant spatial audio. No proprietary black boxes.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { title: "Stereo Binaural", type: "HRTF Convolution", desc: "For headphones. Convolved using spaudiopy for immersive 3D simulation on any standard headset." },
              { title: "5.1 Surround", type: "Channel-Based", desc: "Standard cinematic surround bed with discrete front, rear, and LFE channels via FFmpeg." },
              { title: "5.1.4 Immersive", type: "Object-Based ADM", desc: "Open standard spatial rendering via EBU EAR to a 10-speaker BS.2051 layout, including height." },
              { title: "7.1.4 Immersive", type: "Object-Based ADM", desc: "The ultimate cinematic target. 12-speaker spatial render fully supporting overhead and rear panning." }
            ].map((format, idx) => (
              <div key={idx} className="p-6 bg-slate-900/30 rounded-2xl border border-white/10 hover:bg-slate-900/60 transition-colors">
                <Speaker className="w-8 h-8 text-slate-400 mb-4" />
                <h4 className="text-xl font-bold text-white mb-1">{format.title}</h4>
                <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-4">{format.type}</p>
                <p className="text-slate-400 text-sm leading-relaxed">{format.desc}</p>
              </div>
            ))}
          </div>
          <div className="mt-8 text-center text-slate-500 text-sm">
            <p><strong>Note:</strong> We exclusively use open, object-based spatial rendering via ADM. We do not require or use proprietary Dolby Atmos encoders.</p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-12 bg-slate-950 text-center text-slate-500">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-6">
          <p>© 2026 Continuum Audio. All rights reserved.</p>
          <div className="flex gap-6">
            <a href="https://github.com/resilientbeast/Continuum" target="_blank" rel="noreferrer" className="hover:text-white transition-colors flex items-center gap-2">
              <GitBranch className="w-4 h-4" />
              Source Code
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
