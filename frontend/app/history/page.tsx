
"use client"

import { useEffect, useState } from "react"
import { useAuth } from "@/lib/auth-context"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ArrowLeft, FileText, Target, Calendar, TrendingUp, Loader2 } from "lucide-react"

interface HistoryItem {
    id: string
    filename: string
    predicted_role: string
    confidence_score: number
    match_score: number
    skills: string[]
    created_at: string
}

export default function HistoryPage() {
    const { user, session, loading: authLoading } = useAuth()
    const [history, setHistory] = useState<HistoryItem[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (authLoading) return

        if (!user || !session) {
            setLoading(false)
            return
        }

        const fetchHistory = async () => {
            try {
                const res = await fetch("http://localhost:8000/api/v1/history/", {
                    headers: {
                        "Authorization": `Bearer ${session.access_token}`
                    }
                })

                if (!res.ok) {
                    throw new Error("Failed to fetch history")
                }

                const data = await res.json()
                setHistory(data.items)
            } catch (e) {
                setError(e instanceof Error ? e.message : "An error occurred")
            } finally {
                setLoading(false)
            }
        }

        fetchHistory()
    }, [user, session, authLoading])

    // Not logged in
    if (!authLoading && !user) {
        return (
            <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center p-6">
                <div className="text-center">
                    <h2 className="text-2xl font-bold mb-4">Sign In Required</h2>
                    <p className="text-muted-foreground mb-6">Please log in to view your analysis history.</p>
                    <a href="/login">
                        <Button>Sign In</Button>
                    </a>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-[calc(100vh-3.5rem)] bg-background p-8">
            <header className="mb-8 flex items-center justify-between max-w-5xl mx-auto">
                <div>
                    <h1 className="text-4xl font-extrabold tracking-tight">Analysis History</h1>
                    <p className="text-base text-muted-foreground mt-1">Your past resume analyses</p>
                </div>
                <a href="/">
                    <Button variant="outline">
                        <ArrowLeft className="mr-2 h-4 w-4" /> New Analysis
                    </Button>
                </a>
            </header>

            <div className="max-w-5xl mx-auto">
                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="w-8 h-8 animate-spin text-primary" />
                    </div>
                ) : error ? (
                    <div className="text-center py-20">
                        <p className="text-destructive mb-4">{error}</p>
                        <Button variant="outline" onClick={() => window.location.reload()}>Retry</Button>
                    </div>
                ) : history.length === 0 ? (
                    <div className="text-center py-20">
                        <FileText className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
                        <h3 className="text-2xl font-bold mb-3">No analyses yet</h3>
                        <p className="text-base text-muted-foreground mb-6">Upload a resume to get started!</p>
                        <a href="/">
                            <Button>Upload Resume</Button>
                        </a>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {history.map((item) => (
                            <Card key={item.id} className="hover:shadow-xl hover:border-primary/20 transition-all duration-300 transform hover:-translate-y-1 cursor-pointer">
                                <CardContent className="p-6">
                                    <div className="flex items-start justify-between">
                                        <div className="flex items-center gap-4">
                                            <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center shrink-0">
                                                <FileText className="w-6 h-6 text-primary" />
                                            </div>
                                            <div>
                                                <h3 className="font-bold text-xl">{item.filename}</h3>
                                                <div className="flex items-center gap-4 mt-1.5 text-base text-muted-foreground">
                                                    <span className="flex items-center gap-1.5">
                                                        <Target className="w-4 h-4 text-muted-foreground/80" />
                                                        {item.predicted_role}
                                                    </span>
                                                    <span className="flex items-center gap-1.5">
                                                        <Calendar className="w-4 h-4 text-muted-foreground/80" />
                                                        {new Date(item.created_at).toLocaleDateString()}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-8 text-right">
                                            <div>
                                                <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Match</p>
                                                <p className="text-2xl font-extrabold text-primary">{item.match_score.toFixed(0)}%</p>
                                            </div>
                                            <div>
                                                <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Confidence</p>
                                                <p className="text-2xl font-extrabold">{(item.confidence_score * 100).toFixed(0)}%</p>
                                            </div>
                                            <div>
                                                <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Skills</p>
                                                <p className="text-2xl font-extrabold">{item.skills.length}</p>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Skill tags */}
                                    {item.skills.length > 0 && (
                                        <div className="mt-4 flex flex-wrap gap-2">
                                            {item.skills.slice(0, 8).map(skill => (
                                                <span key={skill} className="px-3 py-1 text-sm bg-secondary rounded-full text-muted-foreground font-medium transition-all duration-150 hover:bg-muted-foreground/10 hover:text-foreground cursor-default">
                                                    {skill}
                                                </span>
                                            ))}
                                            {item.skills.length > 8 && (
                                                <span className="px-3 py-1 text-sm bg-muted rounded-full text-muted-foreground font-medium">
                                                    +{item.skills.length - 8} more
                                                </span>
                                            )}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
