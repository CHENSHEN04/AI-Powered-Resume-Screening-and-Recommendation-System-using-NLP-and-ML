-- Migration: Fix RLS Policies for Authenticated Users to use modern 'TO authenticated' and prevent silent failures.

-- 1. SKILLS Policies
DROP POLICY IF EXISTS "Authenticated users can insert skills" ON public.skills;
CREATE POLICY "Authenticated users can insert skills" ON public.skills
  FOR INSERT TO authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "Authenticated users can update skills" ON public.skills;
CREATE POLICY "Authenticated users can update skills" ON public.skills
  FOR UPDATE TO authenticated USING (true);

-- 2. MARKET STANDARDS Policies
DROP POLICY IF EXISTS "Authenticated users can insert market standards" ON public.market_standards;
CREATE POLICY "Authenticated users can insert market standards" ON public.market_standards
  FOR INSERT TO authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "Authenticated users can update market standards" ON public.market_standards;
CREATE POLICY "Authenticated users can update market standards" ON public.market_standards
  FOR UPDATE TO authenticated USING (true);

DROP POLICY IF EXISTS "Authenticated users can delete market standards" ON public.market_standards;
CREATE POLICY "Authenticated users can delete market standards" ON public.market_standards
  FOR DELETE TO authenticated USING (true);

-- 3. LEARNING RESOURCES Policies
DROP POLICY IF EXISTS "Authenticated users can insert learning resources" ON public.learning_resources;
CREATE POLICY "Authenticated users can insert learning resources" ON public.learning_resources
  FOR INSERT TO authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "Authenticated users can update learning resources" ON public.learning_resources;
CREATE POLICY "Authenticated users can update learning resources" ON public.learning_resources
  FOR UPDATE TO authenticated USING (true);

-- 4. ROLE SALARIES Policies
DROP POLICY IF EXISTS "Authenticated users can insert role salaries" ON public.role_salaries;
CREATE POLICY "Authenticated users can insert role salaries" ON public.role_salaries
  FOR INSERT TO authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "Authenticated users can update role salaries" ON public.role_salaries;
CREATE POLICY "Authenticated users can update role salaries" ON public.role_salaries
  FOR UPDATE TO authenticated USING (true);
