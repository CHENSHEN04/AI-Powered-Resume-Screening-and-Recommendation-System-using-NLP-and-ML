
"use client"

import { useEffect, useState } from "react"
import {
    Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
    BarChart, Bar, XAxis, YAxis, Tooltip, Legend
} from 'recharts'
import { ArrowLeft, BrainCircuit, ShieldCheck, Target, Zap } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChatWidget } from "@/components/ChatWidget"

// Types matching backend/schemas.py
interface AnalysisData {
    filename: string
    parsed_text: string
    skills: string[]
    predicted_role: string
    confidence_score: number
    analysis: {
        match_percentage: number
        missing_required: string[]
        missing_recommended: string[]
        recommendations: string[]
        learning_paths: Record<string, any[]>
    }
}

export default function Dashboard() {
    const [data, setData] = useState<AnalysisData | null>(null)

    useEffect(() => {
        // Retrieve data from localStorage
        const saved = localStorage.getItem("analysisResult")
        if (saved) {
            setData(JSON.parse(saved))
        }
    }, [])

    if (!data) {
        return (
            <div className="flex h-screen items-center justify-center bg-background">
                <div className="text-center">
                    <h2 className="text-2xl font-bold mb-4">No Analysis Found</h2>
                    <Button onClick={() => window.location.href = "/"}>
                        <ArrowLeft className="mr-2 h-4 w-4" /> Upload a Resume
                    </Button>
                </div>
            </div>
        )
    }

    // Prepare chart data
    const radarData = [
        { subject: 'Required Skills', A: 100 - (data.analysis.missing_required.length * 10), fullMark: 100 },
        { subject: 'Recommended', A: 100 - (data.analysis.missing_recommended.length * 5), fullMark: 100 },
        { subject: 'Role Match', A: data.analysis.match_percentage, fullMark: 100 },
        { subject: 'Confidence', A: data.confidence_score * 100, fullMark: 100 },
        { subject: 'Keyword Density', A: Math.min(data.skills.length * 2, 100), fullMark: 100 },
    ]

    return (
        <div className="min-h-screen bg-background p-8">

            {/* Header */}
            <header className="mb-8 flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-extrabold tracking-tight">Career Dashboard</h1>
                    <p className="text-muted-foreground">
                        Analysis for <span className="font-semibold text-primary">{data.filename}</span>
                    </p>
                </div>
                <Button variant="outline" onClick={() => window.location.href = "/"}>
                    <ArrowLeft className="mr-2 h-4 w-4" /> New Analysis
                </Button>
            </header>

            {/* Metrics Row */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Target Role</CardTitle>
                        <Target className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-primary">{data.predicted_role}</div>
                        <p className="text-xs text-muted-foreground">
                            {(data.confidence_score * 100).toFixed(0)}% Confidence
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Match Score</CardTitle>
                        <Zap className="h-4 w-4 text-yellow-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{data.analysis.match_percentage.toFixed(0)}%</div>
                        <div className="w-full bg-secondary h-2 mt-2 rounded-full overflow-hidden">
                            <div
                                className="bg-yellow-500 h-full transition-all duration-1000"
                                style={{ width: `${data.analysis.match_percentage}%` }}
                            />
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Skills Identified</CardTitle>
                        <BrainCircuit className="h-4 w-4 text-blue-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{data.skills.length}</div>
                        <p className="text-xs text-muted-foreground">Extracted from resume</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Critical Gaps</CardTitle>
                        <ShieldCheck className="h-4 w-4 text-red-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-destructive">
                            {data.analysis.missing_required.length}
                        </div>
                        <p className="text-xs text-muted-foreground">Must-have skills missing</p>
                    </CardContent>
                </Card>
            </div>

            {/* Main Content Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">

                {/* Left Col: Charts (4 cols) */}
                <Card className="col-span-4">
                    <CardHeader>
                        <CardTitle>Profile Radar</CardTitle>
                        <CardDescription>How you stack up against the ideal candidate profile.</CardDescription>
                    </CardHeader>
                    <CardContent className="pl-2">
                        <div className="h-[300px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                                    <PolarGrid stroke="hsl(var(--muted-foreground))" strokeOpacity={0.2} />
                                    <PolarAngleAxis dataKey="subject" tick={{ fill: 'hsl(var(--foreground))', fontSize: 12 }} />
                                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                                    <Radar
                                        name="Candidate"
                                        dataKey="A"
                                        stroke="hsl(var(--primary))"
                                        fill="hsl(var(--primary))"
                                        fillOpacity={0.3}
                                    />
                                    <Tooltip
                                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                                    />
                                </RadarChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>

                {/* Right Col: Gaps & Actions (3 cols) */}
                <Card className="col-span-3">
                    <CardHeader>
                        <CardTitle>Missing Skills</CardTitle>
                        <CardDescription>Priority areas for improvement.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {data.analysis.missing_required.length > 0 ? (
                            <div className="space-y-4">
                                <h4 className="text-sm font-semibold text-destructive uppercase tracking-wide">Critical</h4>
                                <div className="flex flex-wrap gap-2">
                                    {data.analysis.missing_required.map(skill => (
                                        <span key={skill} className="px-2 py-1 rounded-md bg-destructive/10 text-destructive text-sm font-medium border border-destructive/20">
                                            {skill}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="p-4 bg-green-500/10 text-green-600 rounded-lg border border-green-500/20">
                                🎉 No critical skill gaps found!
                            </div>
                        )}

                        {data.analysis.missing_recommended.length > 0 && (
                            <div className="space-y-4 mt-6">
                                <h4 className="text-sm font-semibold text-yellow-600 dark:text-yellow-400 uppercase tracking-wide">Recommended</h4>
                                <div className="flex flex-wrap gap-2">
                                    {data.analysis.missing_recommended.map(skill => (
                                        <span key={skill} className="px-2 py-1 rounded-md bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 text-sm font-medium border border-yellow-500/20">
                                            {skill}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Recommendations & Chat */}
            <div className="grid gap-4 md:grid-cols-2 mt-8">
                <ChatWidget className="h-[400px]" />

                <Card className="h-[400px] flex flex-col">
                    <CardHeader>
                        <CardTitle>Learning Resources</CardTitle>
                    </CardHeader>
                    <CardContent className="overflow-y-auto pr-2">
                        {Object.entries(data.analysis.learning_paths).length > 0 ? (
                            <div className="space-y-4">
                                {Object.entries(data.analysis.learning_paths).slice(0, 10).map(([skill, resources]) => (
                                    <div key={skill}>
                                        <h4 className="text-sm font-semibold mb-1 sticky top-0 bg-card py-1">{skill}</h4>
                                        <ul className="space-y-2">
                                            {resources.map((r, i) => (
                                                <li key={i} className="text-sm text-muted-foreground bg-muted/50 p-2 rounded hover:bg-muted transition-colors">
                                                    <a href={r.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2">
                                                        <span className="truncate">{r.title}</span>
                                                    </a>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground">No specific resources found yet.</p>
                        )}
                    </CardContent>
                </Card>
            </div>

        </div>
    )
}
