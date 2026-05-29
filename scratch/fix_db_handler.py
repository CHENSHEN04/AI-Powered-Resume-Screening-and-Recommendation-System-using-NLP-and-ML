import os

file_path = "utils/db_handler.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """            return True, None
            # Check if category exists first (needs to exist to references public.job_categories(slug))
            cat = self.supabase.table("job_categories").select("id").eq("slug", role_slug.lower().strip()).execute()
            if not cat.data:
                # Insert dynamic category skeleton so reference passes successfully
                role_title = role_slug.replace("_", " ").title()
                self.supabase.table("job_categories").insert({
                    "slug": role_slug.lower().strip(),
                    "title": role_title,
                    "weights": {"required": 1.0, "recommended": 0.6, "nice_to_have": 0.3}
                }).execute()
            
            self.supabase.table("role_salaries").upsert({
                "role_slug": role_slug.lower().strip(),
                "salary_data": salary_data
            }).execute()
            return True
        except Exception:
            return False"""

replacement = """            return True, None
        except Exception as e:
            return False, str(e)

    def save_role_salary(self, role_slug: str, salary_data: dict) -> bool:
        \"\"\"Save or update country-specific salary data for a given role slug.\"\"\"
        if not self.supabase or not role_slug or not salary_data:
            return False
        try:
            # Check if category exists first (needs to exist to references public.job_categories(slug))
            cat = self.supabase.table("job_categories").select("id").eq("slug", role_slug.lower().strip()).execute()
            if not cat.data:
                # Insert dynamic category skeleton so reference passes successfully
                role_title = role_slug.replace("_", " ").title()
                self.supabase.table("job_categories").insert({
                    "slug": role_slug.lower().strip(),
                    "title": role_title,
                    "weights": {"required": 1.0, "recommended": 0.6, "nice_to_have": 0.3}
                }).execute()
            
            self.supabase.table("role_salaries").upsert({
                "role_slug": role_slug.lower().strip(),
                "salary_data": salary_data
            }).execute()
            return True
        except Exception:
            return False"""

# Standardize line endings to LF for replacement to match both Windows and Unix endings
content_lf = content.replace("\r\n", "\n")
target_lf = target.replace("\r\n", "\n")
replacement_lf = replacement.replace("\r\n", "\n")

if target_lf in content_lf:
    patched_content = content_lf.replace(target_lf, replacement_lf)
    with open(file_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(patched_content)
    print("Success! Patched db_handler.py.")
else:
    # Try finding with double check
    print("Target not found.")
