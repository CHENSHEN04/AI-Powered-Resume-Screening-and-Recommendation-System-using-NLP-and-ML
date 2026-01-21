-- AI-Powered Resume Screening System
-- Supabase SQL Schema

-- 1. Profiles Table (Extends Supabase Auth)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID REFERENCES auth.users ON DELETE CASCADE PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    role TEXT DEFAULT 'candidate',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Resumes Table
CREATE TABLE IF NOT EXISTS public.resumes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    parsed_text TEXT,
    page_count INTEGER,
    confidence_score FLOAT,
    predicted_role TEXT,
    match_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Skills Table
CREATE TABLE IF NOT EXISTS public.skills (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    resume_id UUID REFERENCES public.resumes(id) ON DELETE CASCADE,
    skill_name TEXT NOT NULL,
    category TEXT, -- e.g., 'required', 'recommended'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Enable Row Level Security (RLS)
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.skills ENABLE ROW LEVEL SECURITY;

-- 5. Policies
-- Users can only see their own profile
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

-- Users can only see their own resumes
CREATE POLICY "Users can view own resumes" ON public.resumes
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY "Users can insert own resumes" ON public.resumes
    FOR INSERT WITH CHECK (user_id = auth.uid());

-- Users can only see their own skills (via resume join)
CREATE POLICY "Users can view own skills" ON public.skills
    FOR SELECT USING (
        resume_id IN (SELECT id FROM public.resumes WHERE user_id = auth.uid())
    );
