
"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { Upload, CheckCircle, ArrowRight, LogIn } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"

export default function Home() {
  const { user, session } = useAuth()
  const [isDragging, setIsDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

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
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0])
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const handleAnalyze = async () => {
    if (!file) return

    setIsAnalyzing(true)
    const formData = new FormData()
    formData.append("file", file)

    // Pass user_id if logged in
    if (user) {
      formData.append("user_id", user.id)
    }

    try {
      const headers: Record<string, string> = {}

      // Pass auth token so backend can save history
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`
      }

      const response = await fetch("http://localhost:8000/api/v1/analyze/", {
        method: "POST",
        headers,
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Analysis failed")
      }

      const data = await response.json()

      // Store in localStorage for dashboard display
      localStorage.setItem("analysisResult", JSON.stringify(data))

      // Navigate to Dashboard
      window.location.href = "/dashboard"

    } catch (error) {
      console.error(error)
      alert(error instanceof Error ? error.message : "An error occurred")
    } finally {
      setIsAnalyzing(false)
    }
  }

  return (
    <main className="flex min-h-[calc(100vh-3.5rem)] flex-col items-center justify-center p-6 bg-gradient-to-b from-background to-secondary/20">

      {/* Hero Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center max-w-3xl mb-12"
      >
        <span className="inline-block px-3 py-1 mb-4 text-xs font-medium tracking-wider text-primary uppercase bg-primary/10 rounded-full">
          AI-Powered Analysis
        </span>
        <h1 className="text-4xl font-extrabold tracking-tight lg:text-6xl mb-6">
          Optimize Your Resume with <span className="text-primary">Deep Learning</span>
        </h1>
        <p className="text-xl text-muted-foreground mb-8">
          Get instant feedback, skill gap analysis, and tailored career advice powered by advanced NLP.
        </p>
      </motion.div>

      {/* Auth Prompt */}
      {!user && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="mb-6 flex items-center gap-2 text-sm text-muted-foreground bg-muted/50 rounded-lg px-4 py-2 border"
        >
          <LogIn className="w-4 h-4" />
          <span><a href="/login" className="text-primary font-medium hover:underline">Log in</a> to save your analysis history</span>
        </motion.div>
      )}

      {/* Upload Section */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        className="w-full max-w-xl"
      >
        <Card className="border-2 border-dashed shadow-xl relative overflow-hidden">
          {/* Glassmorphism Efx */}
          <div className="absolute inset-0 bg-background/50 backdrop-blur-sm -z-10" />

          <CardHeader>
            <CardTitle>Upload Resume</CardTitle>
            <CardDescription>Supported formats: PDF, DOCX</CardDescription>
          </CardHeader>
          <CardContent>
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={cn(
                "flex flex-col items-center justify-center h-64 border-2 border-dashed rounded-lg transition-colors cursor-pointer bg-muted/30",
                isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/50",
                file ? "border-green-500/50 bg-green-500/5" : ""
              )}
            >
              <input
                type="file"
                id="resume-upload"
                className="hidden"
                onChange={handleFileChange}
                accept=".pdf,.docx"
              />

              {!file ? (
                <label htmlFor="resume-upload" className="flex flex-col items-center cursor-pointer w-full h-full justify-center">
                  <div className="p-4 bg-background rounded-full shadow-sm mb-4">
                    <Upload className="w-8 h-8 text-primary" />
                  </div>
                  <p className="font-medium text-lg">Drag & drop or click to upload</p>
                  <p className="text-sm text-muted-foreground mt-2">Maximum file size: 10MB</p>
                </label>
              ) : (
                <div className="text-center p-6">
                  <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 mb-4 animate-in zoom-in">
                    <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
                  </div>
                  <h3 className="text-lg font-semibold">{file.name}</h3>
                  <p className="text-sm text-muted-foreground mb-6">{(file.size / 1024 / 1024).toFixed(2)} MB</p>

                  <div className="flex gap-3 justify-center">
                    <Button variant="outline" onClick={(e) => {
                      e.stopPropagation()
                      setFile(null)
                    }} disabled={isAnalyzing}>
                      Remove
                    </Button>
                    <Button onClick={(e) => {
                      e.stopPropagation()
                      handleAnalyze()
                    }} disabled={isAnalyzing}>
                      {isAnalyzing ? "Analyzing..." : "Analyze Resume"} <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </main>
  )
}
