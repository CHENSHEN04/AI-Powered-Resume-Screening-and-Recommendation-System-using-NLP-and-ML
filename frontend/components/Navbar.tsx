
"use client"

import { useAuth } from "@/lib/auth-context"
import { Button } from "@/components/ui/button"
import { LogOut, User, History, Trash2 } from "lucide-react"
import { useState } from "react"

export function Navbar() {
    const { user, loading, signOut, deleteProfile } = useAuth()
    const [showMenu, setShowMenu] = useState(false)
    const [deleting, setDeleting] = useState(false)

    const handleDelete = async () => {
        if (!confirm("Are you sure? This will permanently delete your account and all saved analyses.")) return
        setDeleting(true)
        const { error } = await deleteProfile()
        if (error) {
            alert(error)
            setDeleting(false)
        } else {
            window.location.href = "/"
        }
    }

    return (
        <nav className="sticky top-0 z-50 w-full border-b bg-background/80 backdrop-blur-md">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex h-16 items-center justify-between">

                    {/* Logo */}
                    <a href="/" className="flex items-center gap-2 hover:scale-[1.02] active:scale-[0.98] transition-all duration-150">
                        <span className="text-2xl font-bold tracking-tight">
                            Resume<span className="text-primary">AI</span>
                        </span>
                    </a>

                    {/* Right Side */}
                    <div className="flex items-center gap-3">
                        {loading ? (
                            <div className="h-8 w-20 animate-pulse bg-muted rounded" />
                        ) : user ? (
                            <>
                                <a href="/history">
                                    <Button variant="ghost" size="sm">
                                        <History className="w-4 h-4 mr-1" /> History
                                    </Button>
                                </a>

                                <div className="relative">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setShowMenu(!showMenu)}
                                        className="gap-2"
                                    >
                                        <User className="w-4 h-4" />
                                        <span className="hidden sm:inline max-w-[120px] truncate">
                                            {user.email}
                                        </span>
                                    </Button>

                                    {showMenu && (
                                        <div className="absolute right-0 mt-2 w-48 bg-card border rounded-lg shadow-lg py-1 z-50">
                                            <button
                                                onClick={() => { signOut(); setShowMenu(false) }}
                                                className="flex items-center gap-2 w-full px-4 py-2 text-sm hover:bg-muted transition-colors"
                                            >
                                                <LogOut className="w-4 h-4" /> Sign Out
                                            </button>
                                            <hr className="my-1 border-border" />
                                            <button
                                                onClick={handleDelete}
                                                disabled={deleting}
                                                className="flex items-center gap-2 w-full px-4 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors"
                                            >
                                                <Trash2 className="w-4 h-4" /> {deleting ? "Deleting..." : "Delete Account"}
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </>
                        ) : (
                            <>
                                <a href="/login">
                                    <Button variant="ghost" size="sm">Login</Button>
                                </a>
                                <a href="/signup">
                                    <Button size="sm">Sign Up</Button>
                                </a>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </nav>
    )
}
