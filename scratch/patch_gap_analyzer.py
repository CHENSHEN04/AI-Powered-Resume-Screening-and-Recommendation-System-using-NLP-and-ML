import os

file_path = "utils/gap_analyzer.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """        # 1. Try DB with each slug variation
        if self.db_manager:
            for _slug in slug_variations:
                role_data = self.db_manager.get_market_standards(_slug)
                if is_standards_usable(role_data):
                    break
                role_data = None

        # 2. Fallback to local JSON with each slug variation
        if not role_data:
            for _slug in slug_variations:
                role_data = self.standards.get("job_categories", {}).get(_slug)
                if is_standards_usable(role_data):
                    break
                role_data = None

        # 3. Fallback to session state (for offline/guest custom roles)
        if not role_data:
            for _slug in slug_variations:
                session_key = f"custom_standards_{_slug}"
                if session_key in st.session_state:
                    role_data = st.session_state[session_key]
                    if not is_standards_usable(role_data):
                        role_data = None
                        continue
                    break

        if not role_data:
            role_title = target_role.replace("_", " ").title()
            role_data, resolve_err = resolve_role_standards(role_title, jd_text=jd_text)
            if role_data and is_standards_usable(role_data):
                slug_name = normalize_role_slug(target_role)
                if self.db_manager:
                    try:
                        success, err = self.db_manager.save_custom_role(
                            role_title=role_title,
                            role_slug=slug_name,
                            required_skills=role_data.get("required_skills", []),
                            recommended_skills=role_data.get("recommended_skills", []),
                            nice_to_have_skills=role_data.get("nice_to_have", []),
                        )
                        if success:
                            salary_ranges = role_data.get("salary_ranges", {})
                            if salary_ranges:
                                self.db_manager.save_role_salary(slug_name, salary_ranges)
                        else:
                            import logging
                            logging.warning(f"Failed to save resolved role standards to DB: {err}")
                    except Exception as db_save_err:
                        import logging
                        logging.warning(f"Failed to auto-harvest dynamic job role standards to DB: {db_save_err}")
                st.session_state[f"custom_standards_{slug_name}"] = role_data
            else:
                role_data = None"""

replacement = """        # 1. Try DB with each slug variation
        db_role_found = False
        db_role_slug = None
        db_role_title = None

        if self.db_manager:
            for _slug in slug_variations:
                try:
                    exists_res = self.db_manager.supabase.table("job_categories").select("id, title, slug").eq("slug", _slug).execute()
                    if exists_res.data:
                        db_role_found = True
                        db_role_slug = _slug
                        db_role_title = exists_res.data[0]["title"]
                        role_data = self.db_manager.get_market_standards(_slug)
                        if is_standards_usable(role_data):
                            break
                        role_data = None
                except Exception:
                    pass

        # Auto-resolve empty DB role
        if db_role_found and not role_data:
            role_title = db_role_title or target_role.replace("_", " ").title()
            resolved, resolve_err = resolve_role_standards(role_title, jd_text=jd_text)
            if resolved and is_standards_usable(resolved):
                if self.db_manager:
                    try:
                        self.db_manager.save_custom_role(
                            role_title=role_title,
                            role_slug=db_role_slug,
                            required_skills=resolved.get("required_skills", []),
                            recommended_skills=resolved.get("recommended_skills", []),
                            nice_to_have_skills=resolved.get("nice_to_have", resolved.get("nice_to_have_skills", [])),
                            salary_ranges=resolved.get("salary_ranges", {}),
                            learning_resources=resolved.get("learning_resources", {}),
                        )
                    except Exception as db_save_err:
                        import logging
                        logging.warning(f"Failed to auto-resolve and save empty DB role standards: {db_save_err}")
                role_data = resolved

        # 2. Fallback to local JSON with each slug variation
        if not role_data:
            for _slug in slug_variations:
                role_data = self.standards.get("job_categories", {}).get(_slug)
                if is_standards_usable(role_data):
                    break
                role_data = None

        # 3. Fallback to session state (for offline/guest custom roles)
        if not role_data:
            for _slug in slug_variations:
                session_key = f"custom_standards_{_slug}"
                if session_key in st.session_state:
                    role_data = st.session_state[session_key]
                    if not is_standards_usable(role_data):
                        role_data = None
                        continue
                    break

        if not role_data:
            role_title = target_role.replace("_", " ").title()
            role_data, resolve_err = resolve_role_standards(role_title, jd_text=jd_text)
            if role_data and is_standards_usable(role_data):
                slug_name = normalize_role_slug(target_role)
                if self.db_manager:
                    try:
                        success, err = self.db_manager.save_custom_role(
                            role_title=role_title,
                            role_slug=slug_name,
                            required_skills=role_data.get("required_skills", []),
                            recommended_skills=role_data.get("recommended_skills", []),
                            nice_to_have_skills=role_data.get("nice_to_have", role_data.get("nice_to_have_skills", [])),
                            salary_ranges=role_data.get("salary_ranges", {}),
                            learning_resources=role_data.get("learning_resources", {}),
                        )
                        if not success:
                            import logging
                            logging.warning(f"Failed to save resolved role standards to DB: {err}")
                    except Exception as db_save_err:
                        import logging
                        logging.warning(f"Failed to auto-harvest dynamic job role standards to DB: {db_save_err}")
                st.session_state[f"custom_standards_{slug_name}"] = role_data
            else:
                role_data = None"""

# Standardize line endings to LF for replacement to match both Windows and Unix endings
content_lf = content.replace("\r\n", "\n")
target_lf = target.replace("\r\n", "\n")
replacement_lf = replacement.replace("\r\n", "\n")

if target_lf in content_lf:
    patched_content = content_lf.replace(target_lf, replacement_lf)
    with open(file_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(patched_content)
    print("Success! Patched gap_analyzer.py.")
else:
    print("Target not found.")
