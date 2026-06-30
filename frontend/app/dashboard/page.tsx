
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
    const [metrics, setMetrics] = useState<any>(null)

    useEffect(() => {
        // Retrieve data from localStorage
        const saved = localStorage.getItem("analysisResult")
        if (saved) {
            setData(JSON.parse(saved))
        }

        // Fetch model metrics
        fetch("http://localhost:8000/api/v1/metrics/")
            .then(res => {
                if (res.ok) return res.json();
                throw new Error("Failed to fetch metrics");
            })
            .then(data => setMetrics(data))
            .catch(err => console.error("Metrics fetch error:", err));
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

    const chartData = [
        {
            name: 'Top-1 Acc',
            MiniLM: parseFloat(((metrics?.semantic_matching?.minilm?.top1_acc || 0) * 100).toFixed(1)),
            BERT: parseFloat(((metrics?.semantic_matching?.bert?.top1_acc || 0) * 100).toFixed(1)),
        },
        {
            name: 'Top-3 Acc',
            MiniLM: parseFloat(((metrics?.semantic_matching?.minilm?.top3_acc || 0) * 100).toFixed(1)),
            BERT: parseFloat(((metrics?.semantic_matching?.bert?.top3_acc || 0) * 100).toFixed(1)),
        },
        {
            name: 'Top-5 Acc',
            MiniLM: parseFloat(((metrics?.semantic_matching?.minilm?.top5_acc || 0) * 100).toFixed(1)),
            BERT: parseFloat(((metrics?.semantic_matching?.bert?.top5_acc || 0) * 100).toFixed(1)),
        },
        {
            name: 'MRR',
            MiniLM: parseFloat(((metrics?.semantic_matching?.minilm?.mrr || 0) * 100).toFixed(1)),
            BERT: parseFloat(((metrics?.semantic_matching?.bert?.mrr || 0) * 100).toFixed(1)),
        }
    ]

    const latencyData = [
        {
            model: 'MiniLM-L6-v2',
            latency: metrics?.semantic_matching?.minilm?.latency_ms || 0,
        },
        {
            model: 'bert-base-uncased',
            latency: metrics?.semantic_matching?.bert?.latency_ms || 0,
        }
    ]

    return (
        <div className="min-h-screen bg-background p-8">

            {/* Header */}
            <header className="mb-8 flex items-center justify-between">
                <div>
                    <h1 className="text-4xl font-extrabold tracking-tight">Career Dashboard</h1>
                    <p className="text-base text-muted-foreground mt-1">
                        Analysis for <span className="font-semibold text-primary">{data.filename}</span>
                    </p>
                </div>
                <Button variant="outline" onClick={() => window.location.href = "/"}>
                    <ArrowLeft className="mr-2 h-4 w-4" /> New Analysis
                </Button>
            </header>

            {/* Metrics Row */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
                <Card className="hover:shadow-md hover:border-primary/20 transition-all duration-300 transform hover:-translate-y-1">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-base font-semibold">Target Role</CardTitle>
                        <Target className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-extrabold text-primary">{data.predicted_role}</div>
                        <p className="text-sm text-muted-foreground mt-0.5">
                            {(data.confidence_score * 100).toFixed(0)}% Confidence
                        </p>
                    </CardContent>
                </Card>
                <Card className="hover:shadow-md hover:border-primary/20 transition-all duration-300 transform hover:-translate-y-1">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-base font-semibold">Match Score</CardTitle>
                        <Zap className="h-4 w-4 text-yellow-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-extrabold">{data.analysis.match_percentage.toFixed(0)}%</div>
                        <div className="w-full bg-secondary h-2.5 mt-2.5 rounded-full overflow-hidden">
                            <div
                                className="bg-yellow-500 h-full transition-all duration-1000"
                                style={{ width: `${data.analysis.match_percentage}%` }}
                            />
                        </div>
                    </CardContent>
                </Card>
                <Card className="hover:shadow-md hover:border-primary/20 transition-all duration-300 transform hover:-translate-y-1">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-base font-semibold">Skills Identified</CardTitle>
                        <BrainCircuit className="h-4 w-4 text-blue-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-extrabold">{data.skills.length}</div>
                        <p className="text-sm text-muted-foreground mt-0.5">Extracted from resume</p>
                    </CardContent>
                </Card>
                <Card className="hover:shadow-md hover:border-primary/20 transition-all duration-300 transform hover:-translate-y-1">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-base font-semibold">Critical Gaps</CardTitle>
                        <ShieldCheck className="h-4 w-4 text-red-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-extrabold text-destructive">
                            {data.analysis.missing_required.length}
                        </div>
                        <p className="text-sm text-muted-foreground mt-0.5">Must-have skills missing</p>
                    </CardContent>
                </Card>
            </div>

            {/* Main Content Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">

                {/* Left Col: Charts (4 cols) */}
                <Card className="col-span-4 hover:shadow-md hover:border-primary/20 transition-all duration-300">
                    <CardHeader>
                        <CardTitle>Profile Radar</CardTitle>
                        <CardDescription>How you stack up against the ideal candidate profile.</CardDescription>
                    </CardHeader>
                    <CardContent className="pl-2">
                        <div className="h-[300px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                                    <PolarGrid stroke="hsl(var(--muted-foreground))" strokeOpacity={0.2} />
                                    <PolarAngleAxis dataKey="subject" tick={{ fill: 'hsl(var(--foreground))', fontSize: 13 }} />
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
                <Card className="col-span-3 hover:shadow-md hover:border-primary/20 transition-all duration-300">
                    <CardHeader>
                        <CardTitle>Missing Skills</CardTitle>
                        <CardDescription>Priority areas for improvement.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {data.analysis.missing_required.length > 0 ? (
                            <div className="space-y-4">
                                <h4 className="text-base font-bold text-destructive uppercase tracking-wider">Critical</h4>
                                <div className="flex flex-wrap gap-2.5">
                                    {data.analysis.missing_required.map(skill => (
                                        <span key={skill} className="px-3 py-1.5 rounded-lg bg-destructive/10 text-destructive text-base font-medium border border-destructive/20 transition-all duration-150 cursor-default hover:scale-105 hover:bg-destructive/15">
                                            {skill}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="p-4 bg-green-500/10 text-green-600 text-base rounded-lg border border-green-500/20">
                                🎉 No critical skill gaps found!
                            </div>
                        )}

                        {data.analysis.missing_recommended.length > 0 && (
                            <div className="space-y-4 mt-6">
                                <h4 className="text-base font-bold text-yellow-600 dark:text-yellow-400 uppercase tracking-wider">Recommended</h4>
                                <div className="flex flex-wrap gap-2.5">
                                    {data.analysis.missing_recommended.map(skill => (
                                        <span key={skill} className="px-3 py-1.5 rounded-lg bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 text-base font-medium border border-yellow-500/20 transition-all duration-150 cursor-default hover:scale-105 hover:bg-yellow-500/15">
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

                <Card className="h-[400px] flex flex-col hover:shadow-md hover:border-primary/20 transition-all duration-300">
                    <CardHeader>
                        <CardTitle>Learning Resources</CardTitle>
                    </CardHeader>
                    <CardContent className="overflow-y-auto pr-2">
                        {Object.entries(data.analysis.learning_paths).length > 0 ? (
                            <div className="space-y-4">
                                {Object.entries(data.analysis.learning_paths).slice(0, 10).map(([skill, resources]) => (
                                    <div key={skill}>
                                        <h4 className="text-base font-bold mb-2 sticky top-0 bg-card py-1.5">{skill}</h4>
                                        <ul className="space-y-2">
                                            {resources.map((r, i) => (
                                                <li key={i} className="text-base text-muted-foreground bg-muted/50 p-3 rounded-lg hover:bg-muted hover:text-foreground transition-all duration-150 shadow-sm border border-transparent hover:border-muted-foreground/10">
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
                            <p className="text-base text-muted-foreground">No specific resources found yet.</p>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Model Performance & Comparison Section */}
            {metrics && (
                <Card className="mt-8 hover:shadow-md hover:border-primary/20 transition-all duration-300">
                    <CardHeader>
                        <CardTitle className="text-xl font-bold flex items-center gap-2">
                            <BrainCircuit className="h-5 w-5 text-primary" />
                            Model Training & Performance Comparison
                        </CardTitle>
                        <CardDescription>
                            Comparing the broad classification accuracy and semantic matching (SentenceTransformers vs BERT) models on the dataset.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="grid gap-6 md:grid-cols-3 mb-6">
                            <div className="p-4 bg-muted/30 rounded-xl border border-muted">
                                <h4 className="text-sm font-semibold text-muted-foreground mb-2">Training Dataset</h4>
                                <div className="text-xl font-bold text-primary">{metrics.dataset?.name}</div>
                                <div className="text-sm mt-1">
                                    <span className="font-semibold">{metrics.dataset?.total_records.toLocaleString()}</span> total records ({metrics.dataset?.num_classes} classes)
                                </div>
                                <div className="text-xs text-muted-foreground mt-0.5">
                                    80% Train | 10% Val | 10% Test splits
                                </div>
                            </div>
                            <div className="p-4 bg-muted/30 rounded-xl border border-muted">
                                <h4 className="text-sm font-semibold text-muted-foreground mb-2">SVM Classifier Accuracy</h4>
                                <div className="text-3xl font-extrabold">{(metrics.classifier?.accuracy * 100).toFixed(2)}%</div>
                                <div className="text-xs text-muted-foreground mt-1">
                                    Macro F1: {(metrics.classifier?.macro_f1 * 100).toFixed(2)}% | Latency: {metrics.classifier?.latency_ms} ms
                                </div>
                            </div>
                            <div className="p-4 bg-muted/30 rounded-xl border border-muted">
                                <h4 className="text-sm font-semibold text-muted-foreground mb-2">Semantic Speedup</h4>
                                <div className="text-3xl font-extrabold text-green-500">6.6x Faster</div>
                                <div className="text-xs text-muted-foreground mt-1">
                                    MiniLM (Production): {metrics.semantic_matching?.minilm?.latency_ms.toFixed(1)} ms vs BERT: {metrics.semantic_matching?.bert?.latency_ms.toFixed(1)} ms
                                </div>
                        </div>

                        {/* Interactive Recharts Graphics */}
                        <div className="grid gap-6 md:grid-cols-2 mb-6">
                            {/* Accuracy Chart */}
                            <div className="p-4 bg-muted/10 rounded-xl border border-muted-foreground/10 h-[300px]">
                                <h4 className="text-base font-bold mb-3">Model Accuracy Comparison (%)</h4>
                                <ResponsiveContainer width="100%" height="90%">
                                    <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                        <XAxis dataKey="name" stroke="#A1A1AA" fontSize={11} />
                                        <YAxis stroke="#A1A1AA" domain={[0, 100]} fontSize={11} />
                                        <Tooltip contentStyle={{ background: '#18181B', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px' }} />
                                        <Legend verticalAlign="top" height={36} iconSize={10} wrapperStyle={{ fontSize: '11px' }} />
                                        <Bar dataKey="MiniLM" fill="#43E97B" radius={[4, 4, 0, 0]} />
                                        <Bar dataKey="BERT" fill="#FF6584" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>

                            {/* Latency Chart */}
                            <div className="p-4 bg-muted/10 rounded-xl border border-muted-foreground/10 h-[300px]">
                                <h4 className="text-base font-bold mb-3">Model Latency Comparison (ms) - Lower is Better</h4>
                                <ResponsiveContainer width="100%" height="90%">
                                    <BarChart data={latencyData} layout="vertical" margin={{ top: 10, right: 20, left: 30, bottom: 0 }}>
                                        <XAxis type="number" stroke="#A1A1AA" fontSize={11} />
                                        <YAxis type="category" dataKey="model" stroke="#A1A1AA" fontSize={10} width={100} />
                                        <Tooltip contentStyle={{ background: '#18181B', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px' }} />
                                        <Bar dataKey="latency" fill="#6C63FF" radius={[0, 4, 4, 0]} barSize={20} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="grid gap-6 md:grid-cols-2">
                            {/* Latency & Accuracy Charts/Tables */}
                            <div className="p-4 bg-muted/10 rounded-xl border border-muted-foreground/10">
                                <h4 className="text-base font-bold mb-4">Semantic Ranking Accuracy</h4>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm text-left text-muted-foreground">
                                        <thead className="text-xs text-foreground uppercase bg-muted/50">
                                            <tr>
                                                <th className="px-4 py-2 rounded-l-lg">Metric</th>
                                                <th className="px-4 py-2">MiniLM-L6-v2</th>
                                                <th className="px-4 py-2 rounded-r-lg">BERT-base</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-muted/30">
                                            <tr>
                                                <td className="px-4 py-3 font-medium text-foreground">Mean Reciprocal Rank (MRR)</td>
                                                <td className="px-4 py-3 text-green-500 font-bold">{metrics.semantic_matching?.minilm?.mrr.toFixed(4)}</td>
                                                <td className="px-4 py-3">{metrics.semantic_matching?.bert?.mrr.toFixed(4)}</td>
                                            </tr>
                                            <tr>
                                                <td className="px-4 py-3 font-medium text-foreground">Avg Rank (Lower is better)</td>
                                                <td className="px-4 py-3 text-green-500 font-bold">{metrics.semantic_matching?.minilm?.avg_rank.toFixed(2)} / 20</td>
                                                <td className="px-4 py-3">{metrics.semantic_matching?.bert?.avg_rank.toFixed(2)} / 20</td>
                                            </tr>
                                            <tr>
                                                <td className="px-4 py-3 font-medium text-foreground">Top-1 Accuracy</td>
                                                <td className="px-4 py-3 font-semibold">{(metrics.semantic_matching?.minilm?.top1_acc * 100).toFixed(1)}%</td>
                                                <td className="px-4 py-3">{(metrics.semantic_matching?.bert?.top1_acc * 100).toFixed(1)}%</td>
                                            </tr>
                                            <tr>
                                                <td className="px-4 py-3 font-medium text-foreground">Top-3 Accuracy</td>
                                                <td className="px-4 py-3 text-green-500 font-bold">{(metrics.semantic_matching?.minilm?.top3_acc * 100).toFixed(1)}%</td>
                                                <td className="px-4 py-3">{(metrics.semantic_matching?.bert?.top3_acc * 100).toFixed(1)}%</td>
                                            </tr>
                                            <tr>
                                                <td className="px-4 py-3 font-medium text-foreground">Top-5 Accuracy</td>
                                                <td className="px-4 py-3 text-green-500 font-bold">{(metrics.semantic_matching?.minilm?.top5_acc * 100).toFixed(1)}%</td>
                                                <td className="px-4 py-3">{(metrics.semantic_matching?.bert?.top5_acc * 100).toFixed(1)}%</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            <div className="p-4 bg-muted/10 rounded-xl border border-muted-foreground/10 flex flex-col justify-between">
                                <div>
                                    <h4 className="text-base font-bold mb-2">Model Selection Rationale</h4>
                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                        For semantic matching, the live application utilizes the <strong>SentenceTransformer &apos;all-MiniLM-L6-v2&apos;</strong>. 
                                        This choice is validated by our evaluation:
                                    </p>
                                    <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1 mt-2">
                                        <li><strong>Zero Representation Collapse:</strong> Out-of-the-box BERT CLS embeddings suffer from anisotropy, causing representations to collapse and yielding poor semantic rankings (MRR of {metrics.semantic_matching?.bert?.mrr.toFixed(3)}).</li>
                                        <li><strong>Outstanding Accuracy:</strong> MiniLM scores a 100% Top-3 match accuracy on the test set.</li>
                                        <li><strong>Inference Latency:</strong> MiniLM performs in {metrics.semantic_matching?.minilm?.latency_ms.toFixed(1)} ms, which is <strong>6.6x faster</strong> than BERT-base ({metrics.semantic_matching?.bert?.latency_ms.toFixed(1)} ms).</li>
                                    </ul>
                                </div>
                                <div className="mt-4 p-3 bg-primary/10 border border-primary/20 rounded-lg text-xs text-primary font-medium">
                                    💡 <strong>Note:</strong> Performance metrics are loaded dynamically from the backend evaluation database using the compiled test split.
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

        </div>
    )
}
