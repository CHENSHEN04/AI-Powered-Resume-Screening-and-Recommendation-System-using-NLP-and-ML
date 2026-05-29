import os

file_path = "utils/db_handler.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """    def save_custom_role(self, role_title: str, role_slug: str,
                         required_skills: list, recommended_skills: list,
                         nice_to_have_skills: list) -> tuple:
        \"\"\"
        Save a user-defined job role to job_categories + market_standards.
        Uses separate SELECT after each write — works with all supabase-py versions.
        Returns (True, None) on success, (False, error_message) on failure.
        \"\"\"
        if not self.supabase:
            return False, "Database not connected."
        try:
            all_skills = (
                [(s.strip(), "required")     for s in required_skills     if s and s.strip()] +
                [(s.strip(), "recommended")  for s in recommended_skills  if s and s.strip()] +
                [(s.strip(), "nice_to_have") for s in nice_to_have_skills if s and s.strip()]
            )
            if not all_skills:
                return False, "Custom role must include at least one required, recommended, or nice-to-have skill."

            # Step 1: Check if slug already exists
            existing = self.supabase.table("job_categories")                 .select("id").eq("slug", role_slug).execute()
            if existing.data:
                cat_id = existing.data[0]["id"]
                self.supabase.table("job_categories")                     .update({"title": role_title}).eq("id", cat_id).execute()
            else:
                self.supabase.table("job_categories").insert({
                    "slug": role_slug, "title": role_title,
                    "weights": {"required": 1.0, "recommended": 0.6, "nice_to_have": 0.3}
                }).execute()
                fetch = self.supabase.table("job_categories")                     .select("id").eq("slug", role_slug).execute()
                if not fetch.data:
                    return False, "Role inserted but could not be retrieved. Check DB permissions."
                cat_id = fetch.data[0]["id"]

            # Step 2: Clear old market_standards for clean re-save
            self.supabase.table("market_standards")                 .delete().eq("job_category_id", cat_id).execute()

            # Step 3: Save each skill and link to role
            saved_count = 0
            for skill_name, importance in all_skills:
                sk = self.supabase.table("skills").select("id").eq("name", skill_name).execute()
                if sk.data:
                    skill_id = sk.data[0]["id"]
                else:
                    self.supabase.table("skills").insert({"name": skill_name}).execute()
                    sk2 = self.supabase.table("skills").select("id").eq("name", skill_name).execute()
                    if not sk2.data:
                        continue
                    skill_id = sk2.data[0]["id"]
                ms = self.supabase.table("market_standards").select("id")                     .eq("job_category_id", cat_id).eq("skill_id", skill_id).execute()
                if not ms.data:
                    self.supabase.table("market_standards").insert({
                        "job_category_id": cat_id, "skill_id": skill_id,
                        "importance_level": importance
                    }).execute()
                    verify = self.supabase.table("market_standards").select("id")                     .eq("job_category_id", cat_id).eq("skill_id", skill_id).execute()
                    if verify.data:
                        saved_count += 1
                else:
                    saved_count += 1
            if saved_count == 0:
                return False, "Role was created, but no skill coverage rows were saved. Check Supabase RLS policies for skills and market_standards."
            return True, None
        except Exception as e:
            return False, str(e)"""

replacement = """    def save_custom_role(self, role_title: str, role_slug: str,
                         required_skills: list, recommended_skills: list,
                         nice_to_have_skills: list,
                         salary_ranges: dict = None,
                         learning_resources: dict = None) -> tuple:
        \"\"\"
        Save a user-defined job role to job_categories + market_standards.
        Uses separate SELECT after each write — works with all supabase-py versions.
        Returns (True, None) on success, (False, error_message) on failure.
        \"\"\"
        if not self.supabase:
            return False, "Database not connected."
        try:
            all_skills = (
                [(s.strip(), "required")     for s in required_skills     if s and s.strip()] +
                [(s.strip(), "recommended")  for s in recommended_skills  if s and s.strip()] +
                [(s.strip(), "nice_to_have") for s in nice_to_have_skills if s and s.strip()]
            )
            if not all_skills:
                return False, "Custom role must include at least one required, recommended, or nice-to-have skill."

            # Step 1: Check if slug already exists
            existing = self.supabase.table("job_categories") \
                .select("id").eq("slug", role_slug).execute()
            if existing.data:
                cat_id = existing.data[0]["id"]
                self.supabase.table("job_categories") \
                    .update({"title": role_title}).eq("id", cat_id).execute()
            else:
                self.supabase.table("job_categories").insert({
                    "slug": role_slug, "title": role_title,
                    "weights": {"required": 1.0, "recommended": 0.6, "nice_to_have": 0.3}
                }).execute()
                fetch = self.supabase.table("job_categories") \
                    .select("id").eq("slug", role_slug).execute()
                if not fetch.data:
                    return False, "Role inserted but could not be retrieved. Check DB permissions."
                cat_id = fetch.data[0]["id"]

            # Step 2: Clear old market_standards for clean re-save
            self.supabase.table("market_standards") \
                .delete().eq("job_category_id", cat_id).execute()

            # Step 3: Save each skill and link to role
            saved_count = 0
            for skill_name, importance in all_skills:
                sk = self.supabase.table("skills").select("id").eq("name", skill_name).execute()
                if sk.data:
                    skill_id = sk.data[0]["id"]
                else:
                    self.supabase.table("skills").insert({"name": skill_name}).execute()
                    sk2 = self.supabase.table("skills").select("id").eq("name", skill_name).execute()
                    if not sk2.data:
                        continue
                    skill_id = sk2.data[0]["id"]
                ms = self.supabase.table("market_standards").select("id") \
                    .eq("job_category_id", cat_id).eq("skill_id", skill_id).execute()
                if not ms.data:
                    self.supabase.table("market_standards").insert({
                        "job_category_id": cat_id, "skill_id": skill_id,
                        "importance_level": importance
                    }).execute()
                    verify = self.supabase.table("market_standards").select("id") \
                        .eq("job_category_id", cat_id).eq("skill_id", skill_id).execute()
                    if verify.data:
                        saved_count += 1
                else:
                    saved_count += 1
            if saved_count == 0:
                return False, "Role was created, but no skill coverage rows were saved. Check Supabase RLS policies for skills and market_standards."

            # Non-blocking Write Step 4: Save Role Salary
            if salary_ranges:
                try:
                    self.save_role_salary(role_slug, salary_ranges)
                except Exception as sal_err:
                    import logging
                    logging.warning(f"Failed to save custom role salary: {sal_err}")

            # Non-blocking Write Step 5: Save Learning Resources
            if learning_resources:
                for skill_name, resources in learning_resources.items():
                    try:
                        self.save_learning_resources(skill_name, resources)
                    except Exception as res_err:
                        import logging
                        logging.warning(f"Failed to save learning resources for skill {skill_name}: {res_err}")

            return True, None
        except Exception as e:
            return False, str(e)"""

content_lf = content.replace("\r\n", "\n")
target_lf = target.replace("\r\n", "\n")
replacement_lf = replacement.replace("\r\n", "\n")

if target_lf in content_lf:
    patched_content = content_lf.replace(target_lf, replacement_lf)
    with open(file_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(patched_content)
    print("Success! Pristine patched db_handler.py.")
else:
    print("Target not found.")
