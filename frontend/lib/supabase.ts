
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
        persistSession: true,         // Keeps session in localStorage (survives browser restarts)
        autoRefreshToken: true,       // Auto-refresh tokens before expiry
        detectSessionInUrl: true,     // Handle OAuth/magic-link redirects
    },
})
