-- =============================================================================
-- AI-Powered Resume Screening System - Database Schema
-- Platform: Supabase (PostgreSQL)
-- Version: 1.0
-- =============================================================================

-- 1. PROFILES (Extends auth.users)
-- -----------------------------------------------------------------------------
create table public.profiles (
  id uuid references auth.users not null primary key,
  full_name text,
  email text,
  role text check (role in ('student', 'admin')) default 'student',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.profiles enable row level security;

create policy "Public profiles are viewable by everyone."
  on profiles for select
  using ( true );

create policy "Users can insert their own profile."
  on profiles for insert
  with check ( auth.uid() = id );

create policy "Users can update own profile."
  on profiles for update
  using ( auth.uid() = id );

-- Trigger to create profile on sign up
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, full_name, email)
  values (new.id, new.raw_user_meta_data->>'full_name', new.email);
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- 2. JOB CATEGORIES
-- -----------------------------------------------------------------------------
create table public.job_categories (
  id uuid default gen_random_uuid() primary key,
  title text not null,
  slug text not null unique,
  description text,
  weights jsonb default '{}'::jsonb, -- e.g. {"education": 0.4, "projects": 0.4}
  status text check (status in ('official', 'pending')) default 'official',
  created_at timestamptz default now()
);

alter table public.job_categories enable row level security;
create policy "Read access for all" on job_categories for select using (true);
create policy "Insert for authenticated users (pending)" on job_categories for insert with check (auth.role() = 'authenticated');

-- 3. SKILLS
-- -----------------------------------------------------------------------------
create table public.skills (
  id uuid default gen_random_uuid() primary key,
  name text not null unique,
  category text, -- e.g. 'Language', 'Framework', 'Soft Skill'
  created_at timestamptz default now()
);

alter table public.skills enable row level security;
create policy "Read access for all" on skills for select using (true);

-- 4. MARKET STANDARDS (Job <-> Skill Mappings)
-- -----------------------------------------------------------------------------
create table public.market_standards (
  id uuid default gen_random_uuid() primary key,
  job_category_id uuid references public.job_categories(id) on delete cascade,
  skill_id uuid references public.skills(id) on delete cascade,
  importance_level text check (importance_level in ('required', 'recommended', 'nice_to_have')),
  created_at timestamptz default now(),
  unique(job_category_id, skill_id)
);

alter table public.market_standards enable row level security;
create policy "Read access for all" on market_standards for select using (true);

-- 5. LEARNING RESOURCES
-- -----------------------------------------------------------------------------
create table public.learning_resources (
  id uuid default gen_random_uuid() primary key,
  skill_id uuid references public.skills(id) on delete cascade,
  title text not null,
  url text not null,
  resource_type text check (resource_type in ('Course', 'Article', 'Video', 'Project')),
  difficulty text check (difficulty in ('Beginner', 'Intermediate', 'Advanced')),
  language text default 'en',
  upvotes int default 0,
  is_active boolean default true, -- For Link Rot checker
  created_at timestamptz default now()
);

alter table public.learning_resources enable row level security;
create policy "Read access for all" on learning_resources for select using (true);

-- 6. RESUMES
-- -----------------------------------------------------------------------------
create table public.resumes (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id), -- Nullable for anonymous uploads first
  filename text not null,
  storage_path text not null, -- Path in Supabase Storage bucket
  parsed_text text,
  page_count int,
  predicted_role text,
  confidence_score float,
  match_score float,
  created_at timestamptz default now()
);

alter table public.resumes enable row level security;
create policy "Users see their own" on resumes for select using (auth.uid() = user_id);
create policy "Users insert own" on resumes for insert with check (auth.uid() = user_id);
-- Note: You might need specific policies for anonymous uploads if supported

-- 7. RESUME SKILLS (Extracted)
-- -----------------------------------------------------------------------------
create table public.resume_skills (
  id uuid default gen_random_uuid() primary key,
  resume_id uuid references public.resumes(id) on delete cascade,
  skill_name text not null,
  category text,
  proficiency_level int check (proficiency_level between 1 and 5), -- 1-5 Scale
  source text default 'extracted', -- 'extracted', 'user_added', 'inferred'
  created_at timestamptz default now()
);

alter table public.resume_skills enable row level security;
create policy "Users see own skills" on resume_skills for select using (
  exists (select 1 from resumes where id = resume_skills.resume_id and user_id = auth.uid())
);

-- 8. SYSTEM LOGS
-- -----------------------------------------------------------------------------
create table public.system_logs (
  id uuid default gen_random_uuid() primary key,
  level text check (level in ('INFO', 'WARNING', 'ERROR')),
  message text not null,
  details jsonb,
  created_at timestamptz default now()
);

alter table public.system_logs enable row level security;
-- Only admin should see logs? For now, let's keep it restricted.
-- create policy "Admins read logs" ... 

-- 9. ROLE SALARIES (Compensation Mapping)
-- -----------------------------------------------------------------------------
create table public.role_salaries (
  id uuid default gen_random_uuid() primary key,
  role_slug text not null unique references public.job_categories(slug) on delete cascade,
  salary_data jsonb not null default '{}'::jsonb,
  created_at timestamptz default now()
);

alter table public.role_salaries enable row level security;
create policy "Read access for all" on role_salaries for select using (true);

