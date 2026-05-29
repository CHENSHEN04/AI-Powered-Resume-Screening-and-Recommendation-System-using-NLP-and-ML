import os

file_path = "app.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """def _create_custom_role_and_run(db, role_title, jd_text, file_bytes, filename):
    \"\"\"Resolve, persist, and use a custom role without allowing empty coverage.\"\"\"
    from utils.role_standards_resolver import normalize_role_slug, resolve_role_standards

    role_slug = normalize_role_slug(role_title)
    standards, err = resolve_role_standards(role_title, jd_text=jd_text)
    if not standards:
        st.error(err)
        st.info("Paste a detailed job description for this role, then try again.")
        return

    success, save_err = db.save_custom_role(
        role_title=role_title,
        role_slug=role_slug,
        required_skills=standards.get("required_skills", []),
        recommended_skills=standards.get("recommended_skills", []),
        nice_to_have_skills=standards.get("nice_to_have", standards.get("nice_to_have_skills", [])),
    )
    if not success:
        st.warning(f"Could not save custom role to database: {save_err}")
        st.info("The analysis will continue using this role for the current session only.")

    salary_ranges = standards.get("salary_ranges", {})
    if salary_ranges:
        try:
            db.save_role_salary(role_slug, salary_ranges)
        except Exception:
            pass
        _persist_salary_json(role_slug, salary_ranges)

    st.session_state[f"custom_standards_{role_slug}"] = standards
    st.session_state["target_role"] = role_slug
    st.session_state["sim_checked"] = False
    st.session_state["similar_role_found"] = None
    st.session_state["similar_role_slug"] = None
    _run_analysis_pipeline(file_bytes, filename, jd_text)"""

replacement = """def _create_custom_role_and_run(db, role_title, jd_text, file_bytes, filename):
    \"\"\"Resolve, persist, and use a custom role without allowing empty coverage.\"\"\"
    from utils.role_standards_resolver import normalize_role_slug, resolve_role_standards

    role_slug = normalize_role_slug(role_title)
    standards, err = resolve_role_standards(role_title, jd_text=jd_text)
    if not standards:
        st.error(err)
        if not jd_text or not jd_text.strip():
            st.info("Please provide a Job Description (JD) to extract fallback skills when AI is unavailable or generic.")
        return

    success, save_err = db.save_custom_role(
        role_title=role_title,
        role_slug=role_slug,
        required_skills=standards.get("required_skills", []),
        recommended_skills=standards.get("recommended_skills", []),
        nice_to_have_skills=standards.get("nice_to_have", standards.get("nice_to_have_skills", [])),
        salary_ranges=standards.get("salary_ranges", {}),
        learning_resources=standards.get("learning_resources", {}),
    )
    if not success:
        st.error(f"Failed to save custom role to database: {save_err}")
        st.info("The analysis will continue using this role for the current session only.")
    else:
        st.success(f"Successfully saved '{role_title}' and all its requirements to the database!")

    salary_ranges = standards.get("salary_ranges", {})
    if salary_ranges:
        _persist_salary_json(role_slug, salary_ranges)

    st.session_state[f"custom_standards_{role_slug}"] = standards
    st.session_state["target_role"] = role_slug
    st.session_state["sim_checked"] = False
    st.session_state["similar_role_found"] = None
    st.session_state["similar_role_slug"] = None
    _run_analysis_pipeline(file_bytes, filename, jd_text)"""

# Standardize line endings to LF for replacement
content_lf = content.replace("\r\n", "\n")
target_lf = target.replace("\r\n", "\n")
replacement_lf = replacement.replace("\r\n", "\n")

if target_lf in content_lf:
    patched_content = content_lf.replace(target_lf, replacement_lf)
    with open(file_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(patched_content)
    print("Success! Patched app.py.")
else:
    print("Target not found.")
