
"use client"

import { useState, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Briefcase,
  Upload,
  Linkedin,
  FileText,
  ArrowRight,
  CheckCircle,
  X,
  Loader2,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"

/* ─── tiny helpers ─────────────────────────────────────────── */
function cn(...classes: (string | undefined | false | null)[]) {
  return classes.filter(Boolean).join(" ")
}

/* ─── types ─────────────────────────────────────────────────── */
type Option = "industry" | "upload" | "linkedin" | null

/* ─── main page ─────────────────────────────────────────────── */
export default function Home() {
  const { user, session } = useAuth()
  const [selected, setSelected] = useState<Option>(null)

  // upload-flow state
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  /* ── handlers ── */
  const handleCardClick = (opt: Option) => {
    if (opt === "upload") {
      setSelected("upload")
    } else if (opt === "industry") {
      window.location.href = "/dashboard"
    } else if (opt === "linkedin") {
      alert("LinkedIn import coming soon!")
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const dropped = e.dataTransfer.files?.[0]
    if (dropped) setFile(dropped)
  }
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0]
    if (picked) setFile(picked)
  }

  const handleAnalyze = async () => {
    if (!file) return
    setIsAnalyzing(true)
    const formData = new FormData()
    formData.append("file", file)
    if (user) formData.append("user_id", user.id)

    try {
      const headers: Record<string, string> = {}
      if (session?.access_token)
        headers["Authorization"] = `Bearer ${session.access_token}`

      const res = await fetch("http://localhost:8000/api/v1/analyze/", {
        method: "POST",
        headers,
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Analysis failed")
      }
      const data = await res.json()
      localStorage.setItem("analysisResult", JSON.stringify(data))
      window.location.href = "/dashboard"
    } catch (err) {
      alert(err instanceof Error ? err.message : "An error occurred")
    } finally {
      setIsAnalyzing(false)
    }
  }

  /* ── card definitions ── */
  const cards = [
    {
      id: "industry" as Option,
      icon: <Briefcase className="w-8 h-8" />,
      label: "Start with an\nIndustry Example",
    },
    {
      id: "upload" as Option,
      icon: <Upload className="w-8 h-8" />,
      label: "Upload an Existing\nResumé",
    },
    {
      id: "linkedin" as Option,
      icon: <Linkedin className="w-8 h-8" />,
      label: "Import your LinkedIn\nProfile",
    },
  ]

  return (
    <>
      {/* ── global style injection ── */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        .home-bg {
          min-height: calc(100vh - 3.5rem);
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 2rem 1rem;
          background: radial-gradient(ellipse 80% 60% at 50% -10%,
            hsl(220 60% 18% / 0.55) 0%,
            transparent 70%),
            hsl(222.2 84% 4.9%);
          font-family: 'Inter', sans-serif;
        }

        /* ── question heading ── */
        .home-heading {
          font-size: clamp(1.6rem, 3.5vw, 2.1rem);
          font-weight: 700;
          color: hsl(210 40% 95%);
          text-align: center;
          margin-bottom: 2.5rem;
          letter-spacing: -0.02em;
        }

        /* ── card grid ── */
        .card-grid {
          display: flex;
          gap: 1.25rem;
          flex-wrap: wrap;
          justify-content: center;
          margin-bottom: 2rem;
        }

        .option-card {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 1rem;
          width: 185px;
          padding: 1.75rem 1.25rem;
          border-radius: 16px;
          border: 1.5px solid hsl(217 30% 22%);
          background: hsl(222 60% 8% / 0.7);
          backdrop-filter: blur(10px);
          cursor: pointer;
          transition: border-color 0.2s, background 0.2s, transform 0.2s, box-shadow 0.2s;
          text-align: center;
          color: hsl(215 20% 65%);
          user-select: none;
        }

        .option-card:hover {
          border-color: hsl(210 80% 65%);
          background: hsl(213 60% 14% / 0.85);
          transform: translateY(-5px) scale(1.03);
          box-shadow: 0 12px 35px hsl(210 80% 50% / 0.25);
          color: hsl(210 40% 95%);
        }

        .option-card.active {
          border-color: hsl(210 80% 60%);
          background: hsl(213 60% 14% / 0.9);
          color: hsl(210 40% 95%);
          box-shadow: 0 0 0 3px hsl(210 80% 60% / 0.25);
        }

        .option-card .icon-wrap {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 56px;
          height: 56px;
          border-radius: 50%;
          background: hsl(217 32% 17%);
          transition: background 0.2s;
        }

        .option-card:hover .icon-wrap,
        .option-card.active .icon-wrap {
          background: hsl(210 70% 22%);
        }

        .option-card .label {
          font-size: 0.85rem;
          font-weight: 600;
          letter-spacing: 0.04em;
          text-transform: uppercase;
          line-height: 1.45;
          white-space: pre-line;
        }

        /* ── blank doc link ── */
        .blank-link {
          font-size: 0.95rem;
          color: hsl(215 20% 52%);
          text-decoration: none;
          transition: color 0.15s, transform 0.15s;
          display: inline-block;
        }
        .blank-link:hover {
          color: hsl(210 80% 65%);
          transform: scale(1.02);
        }
        .blank-link span { text-decoration: underline; }

        /* ── upload modal / panel ── */
        .upload-panel {
          width: min(550px, 92vw);
          border-radius: 20px;
          border: 1.5px solid hsl(217 30% 22%);
          background: hsl(222 60% 7% / 0.92);
          backdrop-filter: blur(16px);
          padding: 2.25rem;
          box-shadow: 0 24px 60px hsl(0 0% 0% / 0.45);
        }

        .upload-panel h2 {
          font-size: 1.35rem;
          font-weight: 600;
          color: hsl(210 40% 95%);
          margin-bottom: 0.5rem;
        }
        .upload-panel p {
          font-size: 0.92rem;
          color: hsl(215 20% 55%);
          margin-bottom: 1.5rem;
        }

        .drop-zone {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 200px;
          border-radius: 14px;
          border: 2px dashed hsl(217 30% 28%);
          background: hsl(217 32% 11% / 0.6);
          cursor: pointer;
          transition: border-color 0.2s, background 0.2s, transform 0.15s;
          gap: 0.75rem;
        }
        .drop-zone:hover {
          transform: scale(1.01);
        }
        .drop-zone.dragging {
          border-color: hsl(210 80% 60%);
          background: hsl(213 60% 14% / 0.6);
        }
        .drop-zone.has-file {
          border-color: hsl(142 70% 40%);
          background: hsl(142 60% 10% / 0.5);
        }

        .drop-zone .dz-icon {
          width: 54px; height: 54px;
          border-radius: 50%;
          background: hsl(217 32% 17%);
          display: flex; align-items: center; justify-content: center;
          color: hsl(210 80% 65%);
        }
        .drop-zone .dz-text {
          font-size: 1rem;
          font-weight: 500;
          color: hsl(210 40% 85%);
        }
        .drop-zone .dz-sub {
          font-size: 0.85rem;
          color: hsl(215 20% 52%);
        }

        .file-info {
          display: flex; align-items: center; gap: 0.85rem;
          padding: 0.85rem 1.15rem;
          background: hsl(217 32% 13%);
          border-radius: 12px;
          margin-top: 1rem;
        }
        .file-info .fi-name {
          flex: 1; font-size: 0.95rem; font-weight: 500;
          color: hsl(210 40% 85%); overflow: hidden;
          text-overflow: ellipsis; white-space: nowrap;
        }
        .file-info .fi-size {
          font-size: 0.85rem; color: hsl(215 20% 52%);
        }
        .file-info button {
          background: none; border: none; cursor: pointer;
          color: hsl(215 20% 50%); padding: 2px;
          transition: color 0.15s;
        }
        .file-info button:hover { color: hsl(0 65% 55%); }

        .btn-primary {
          display: flex; align-items: center; justify-content: center;
          gap: 0.5rem;
          width: 100%; margin-top: 1rem; padding: 0.85rem;
          border-radius: 12px; border: none; cursor: pointer;
          font-size: 1rem; font-weight: 600;
          background: hsl(210 80% 55%);
          color: #fff;
          transition: background 0.2s, transform 0.15s, box-shadow 0.2s;
        }
        .btn-primary:hover:not(:disabled) {
          background: hsl(210 80% 48%);
          transform: translateY(-2px);
          box-shadow: 0 8px 25px hsl(210 80% 45% / 0.4);
        }
        .btn-primary:active:not(:disabled) {
          transform: translateY(0) scale(0.98);
        }
        .btn-primary:disabled {
          opacity: 0.6; cursor: not-allowed;
        }

        .btn-back {
          display: inline-flex; align-items: center; gap: 0.35rem;
          background: none; border: none; cursor: pointer;
          font-size: 0.92rem; color: hsl(215 20% 52%);
          margin-bottom: 1.25rem; padding: 0; transition: color 0.15s, transform 0.15s;
        }
        .btn-back:hover {
          color: hsl(210 40% 80%);
          transform: translateX(-2px);
        }

        .success-icon {
          display: flex; align-items: center; justify-content: center;
          width: 52px; height: 52px; border-radius: 50%;
          background: hsl(142 60% 12%);
          color: hsl(142 70% 45%);
        }
      `}</style>

      <div className="home-bg">
        <AnimatePresence mode="wait">
          {selected === "upload" ? (
            /* ── UPLOAD PANEL ── */
            <motion.div
              key="upload-panel"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.28 }}
            >
              <div className="upload-panel">
                <button className="btn-back" onClick={() => { setSelected(null); setFile(null) }}>
                  ← Back
                </button>
                <h2>Upload your resumé</h2>
                <p>Supported formats: PDF, DOCX &nbsp;·&nbsp; Max 10 MB</p>

                {!file ? (
                  <div
                    className={cn("drop-zone", isDragging && "dragging")}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      id="resume-upload"
                      className="hidden"
                      accept=".pdf,.docx"
                      onChange={handleFileChange}
                      style={{ display: "none" }}
                    />
                    <div className="dz-icon">
                      <Upload className="w-6 h-6" />
                    </div>
                    <span className="dz-text">Drag &amp; drop or click to upload</span>
                    <span className="dz-sub">PDF or DOCX</span>
                  </div>
                ) : (
                  <div className={cn("drop-zone has-file")} style={{ cursor: "default" }}>
                    <div className="success-icon">
                      <CheckCircle className="w-6 h-6" />
                    </div>
                    <span className="dz-text">File ready</span>
                  </div>
                )}

                {file && (
                  <motion.div
                    className="file-info"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <FileText className="w-5 h-5" style={{ color: "hsl(210 80% 65%)", flexShrink: 0 }} />
                    <span className="fi-name">{file.name}</span>
                    <span className="fi-size">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                    <button onClick={() => setFile(null)} aria-label="Remove file">
                      <X className="w-5 h-5" />
                    </button>
                  </motion.div>
                )}

                <button
                  className="btn-primary"
                  onClick={handleAnalyze}
                  disabled={!file || isAnalyzing}
                >
                  {isAnalyzing ? (
                    <><Loader2 className="w-5 h-5 animate-spin" /> Analysing…</>
                  ) : (
                    <>Analyse Resumé <ArrowRight className="w-5 h-5" /></>
                  )}
                </button>
              </div>
            </motion.div>
          ) : (
            /* ── ONBOARDING CARDS ── */
            <motion.div
              key="onboarding"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.3 }}
              style={{ display: "flex", flexDirection: "column", alignItems: "center" }}
            >
              <motion.h1
                className="home-heading"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05 }}
              >
                How would you like to start creating your resume?
              </motion.h1>

              <div className="card-grid">
                {cards.map((card, i) => (
                  <motion.div
                    key={card.id}
                    className={cn("option-card", selected === card.id && "active")}
                    onClick={() => handleCardClick(card.id)}
                    initial={{ opacity: 0, y: 18 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 + i * 0.07 }}
                    whileTap={{ scale: 0.97 }}
                  >
                    <div className="icon-wrap">{card.icon}</div>
                    <span className="label">{card.label}</span>
                  </motion.div>
                ))}
              </div>

              <motion.a
                href="/dashboard"
                className="blank-link"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.38 }}
              >
                … or <span>start with a blank document</span>.
              </motion.a>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </>
  )
}
