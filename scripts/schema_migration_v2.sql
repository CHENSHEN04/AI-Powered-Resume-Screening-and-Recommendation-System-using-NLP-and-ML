-- Migration V2: Database Normalization

-- 0. PRE-FLIGHT: Rename legacy 'skills' table to 'resume_skills' if it exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'skills' 
        AND column_name = 'resume_id'
        AND table_schema = 'public'
    ) THEN
        ALTER TABLE skills RENAME TO resume_skills;
    END IF;
END $$;

-- 1. Job Categories
CREATE TABLE IF NOT EXISTS job_categories (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    weights JSONB DEFAULT '{"required": 1.0, "recommended": 0.6, "nice_to_have": 0.3}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Skills (Master List)
CREATE TABLE IF NOT EXISTS skills (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Market Standards (Linking Jobs to Skills)
CREATE TABLE IF NOT EXISTS market_standards (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    job_category_id UUID REFERENCES job_categories(id) ON DELETE CASCADE,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    importance_level TEXT CHECK (importance_level IN ('required', 'recommended', 'nice_to_have')),
    UNIQUE(job_category_id, skill_id)
);

-- 4. Learning Resources
CREATE TABLE IF NOT EXISTS learning_resources (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    resource_type TEXT, -- 'Course', 'Tutorial', etc.
    difficulty TEXT,   -- 'Beginner', 'Intermediate', 'Advanced'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS (Row Level Security) - Optional but good practice
ALTER TABLE job_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_standards ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_resources ENABLE ROW LEVEL SECURITY;

-- 1. READ POLICIES
DROP POLICY IF EXISTS "Public Read Job Categories" ON job_categories;
CREATE POLICY "Public Read Job Categories" ON job_categories FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public Read Skills" ON skills;
CREATE POLICY "Public Read Skills" ON skills FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public Read Market Standards" ON market_standards;
CREATE POLICY "Public Read Market Standards" ON market_standards FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public Read Learning Resources" ON learning_resources;
CREATE POLICY "Public Read Learning Resources" ON learning_resources FOR SELECT USING (true);

-- 2. INSERT POLICIES (FOR SEEDING)
DROP POLICY IF EXISTS "Public Insert Job Categories" ON job_categories;
CREATE POLICY "Public Insert Job Categories" ON job_categories FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Public Insert Skills" ON skills;
CREATE POLICY "Public Insert Skills" ON skills FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Public Insert Market Standards" ON market_standards;
CREATE POLICY "Public Insert Market Standards" ON market_standards FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Public Insert Learning Resources" ON learning_resources;
CREATE POLICY "Public Insert Learning Resources" ON learning_resources FOR INSERT WITH CHECK (true);

-- 3. UPDATE POLICIES (FOR UPSERTS)
DROP POLICY IF EXISTS "Public Update Job Categories" ON job_categories;
CREATE POLICY "Public Update Job Categories" ON job_categories FOR UPDATE USING (true);

DROP POLICY IF EXISTS "Public Update Skills" ON skills;
CREATE POLICY "Public Update Skills" ON skills FOR UPDATE USING (true);

DROP POLICY IF EXISTS "Public Update Market Standards" ON market_standards;
CREATE POLICY "Public Update Market Standards" ON market_standards FOR UPDATE USING (true);

DROP POLICY IF EXISTS "Public Update Learning Resources" ON learning_resources;
CREATE POLICY "Public Update Learning Resources" ON learning_resources FOR UPDATE USING (true);

-- 4. DELETE POLICIES (FOR CUSTOM ROLE RE-SAVES)
DROP POLICY IF EXISTS "Public Delete Market Standards" ON market_standards;
CREATE POLICY "Public Delete Market Standards" ON market_standards FOR DELETE USING (true);

-- 5. ROLE SALARIES (Dynamic compensation metadata)
CREATE TABLE IF NOT EXISTS role_salaries (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    role_slug TEXT NOT NULL UNIQUE REFERENCES job_categories(slug) ON DELETE CASCADE,
    salary_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE role_salaries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public Read Role Salaries" ON role_salaries;
CREATE POLICY "Public Read Role Salaries" ON role_salaries FOR SELECT USING (true);

DROP POLICY IF EXISTS "Public Insert Role Salaries" ON role_salaries;
CREATE POLICY "Public Insert Role Salaries" ON role_salaries FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Public Update Role Salaries" ON role_salaries;
CREATE POLICY "Public Update Role Salaries" ON role_salaries FOR UPDATE USING (true);
