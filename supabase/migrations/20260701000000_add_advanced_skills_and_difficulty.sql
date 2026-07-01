-- Migration: Rename Intern roles and add Advanced Skills + Difficulty columns
-- Target: public.market_standards & public.job_categories

-- 1. Rename existing "Intern" roles in job_categories
UPDATE public.job_categories 
SET title = 'AI Engineer', slug = 'ai_engineer' 
WHERE slug = 'ai_engineer_intern';

UPDATE public.job_categories 
SET title = 'Data Management', slug = 'data_management' 
WHERE slug = 'data_management_intern';

UPDATE public.job_categories 
SET title = 'Machine Learning Engineer', slug = 'machine_learning_engineer' 
WHERE slug = 'machine_learning_engineer_intern';

-- 2. Modify importance_level check constraint in market_standards to support 'advanced'
ALTER TABLE public.market_standards 
  DROP CONSTRAINT IF EXISTS market_standards_importance_level_check;

ALTER TABLE public.market_standards 
  ADD CONSTRAINT market_standards_importance_level_check 
  CHECK (importance_level IN ('required', 'recommended', 'nice_to_have', 'advanced'));

-- 3. Add difficulty column to market_standards
ALTER TABLE public.market_standards 
  ADD COLUMN IF NOT EXISTS difficulty TEXT 
  CHECK (difficulty IN ('Beginner', 'Intermediate', 'Advanced'));
