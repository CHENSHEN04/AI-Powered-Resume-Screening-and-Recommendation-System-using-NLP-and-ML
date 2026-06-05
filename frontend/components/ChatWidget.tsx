
"use client"

import { useState, useRef, useEffect } from "react"
import { Send, Bot, User, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"

interface Message {
    role: 'user' | 'assistant'
    content: string
}

export function ChatWidget({ className }: { className?: string }) {
    const { user } = useAuth()
    const [messages, setMessages] = useState<Message[]>([
        { role: 'assistant', content: "Hi! I'm your AI Career Coach. Ask me anything about your resume or career path." }
    ])
    const [input, setInput] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages])

    const handleSend = async () => {
        if (!input.trim() || isLoading) return

        const userMsg = input.trim()
        setInput("")
        setMessages(prev => [...prev, { role: 'user', content: userMsg }])
        setIsLoading(true)

        // Retrieve latest resume context from localStorage
        let resumeContext = null
        try {
            const savedAnalysis = localStorage.getItem("analysisResult")
            if (savedAnalysis) {
                const parsed = JSON.parse(savedAnalysis)
                if (parsed) {
                    resumeContext = {
                        predicted_role: parsed.predicted_role || "Unknown",
                        match_score: parsed.analysis?.match_percentage || 0,
                        skills: parsed.skills || [],
                        missing_required: parsed.analysis?.missing_required || [],
                        missing_recommended: parsed.analysis?.missing_recommended || [],
                        verdict: parsed.analysis?.match_percentage >= 85 ? "Strong Match" : parsed.analysis?.match_percentage >= 65 ? "Moderate Match" : "Weak Match"
                    }
                }
            }
        } catch (err) {
            console.error("Failed to load resume context for Career Coach chat:", err)
        }

        try {
            const response = await fetch("http://localhost:8000/api/v1/chat/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: userMsg,
                    user_id: user?.id || "guest",
                    resume_context: resumeContext
                }),
            })

            if (!response.ok) throw new Error("Failed to get response")

            const data = await response.json()
            setMessages(prev => [...prev, { role: 'assistant', content: data.response }])
        } catch (error) {
            setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I encountered an error. Please try again." }])
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <Card className={cn("flex flex-col h-[500px]", className)}>
            <CardHeader className="py-4 px-5 border-b bg-muted/20">
                <CardTitle className="flex items-center gap-2.5 text-lg font-bold">
                    <Bot className="w-5 h-5 text-primary" />
                    AI Career Coach
                </CardTitle>
            </CardHeader>

            <CardContent className="flex-1 overflow-y-auto p-5 space-y-5">
                {messages.map((msg, i) => (
                    <div
                        key={i}
                        className={cn(
                            "flex gap-3 max-w-[85%]",
                            msg.role === 'user' ? "ml-auto flex-row-reverse" : "mr-auto"
                        )}
                    >
                        <div className={cn(
                            "w-9 h-9 rounded-full flex items-center justify-center shrink-0 shadow-sm",
                            msg.role === 'user' ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                        )}>
                            {msg.role === 'user' ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
                        </div>

                        <div className={cn(
                            "rounded-lg px-4 py-2.5 text-base shadow-sm leading-relaxed",
                            msg.role === 'user'
                                ? "bg-primary text-primary-foreground rounded-tr-none"
                                : "bg-muted text-foreground rounded-tl-none"
                        )}>
                            {msg.content}
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="flex gap-3 mr-auto max-w-[85%]">
                        <div className="w-9 h-9 rounded-full bg-muted flex items-center justify-center shrink-0 shadow-sm">
                            <Bot className="w-5 h-5 text-muted-foreground" />
                        </div>
                        <div className="bg-muted rounded-lg rounded-tl-none px-4 py-2.5 flex items-center shadow-sm">
                            <RefreshCw className="w-4 h-4 animate-spin text-muted-foreground" />
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </CardContent>

            <CardFooter className="p-4 border-t bg-background">
                <form
                    className="flex w-full gap-2.5"
                    onSubmit={(e) => {
                        e.preventDefault()
                        handleSend()
                    }}
                >
                    <Input
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask a follow-up question..."
                        disabled={isLoading}
                        className="flex-1"
                    />
                    <Button type="submit" size="icon" disabled={isLoading || !input.trim()}>
                        <Send className="w-5 h-5" />
                    </Button>
                </form>
            </CardFooter>
        </Card>
    )
}
