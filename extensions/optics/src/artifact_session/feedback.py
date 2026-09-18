"""Deterministic online-only diagnostics; never chooses a search mechanism."""

from optics_backend.artifacts import canonical, digest


def online_diagnostics(facts):
    if facts["mode"] != "online":
        raise ValueError("ONLINE_FEEDBACK_REQUIRED")
    constraints = facts["constraints"]
    configurations = []
    for profile_id, profile in facts.get("profile_results", {}).items():
        for index, configuration in enumerate(profile.get("configurations", [])):
            signed = configuration.get("focus_error_mm")
            sensor = configuration.get("sensor_z_mm")
            configurations.append({
                "profile_id": profile_id, "configuration_index": index,
                "signed_focus_error_mm": signed,
                "absolute_focus_error_mm": abs(signed) if signed is not None else None,
                "sensor_z_mm": sensor,
                "paraxial_focus_plane_z_mm": sensor - signed if sensor is not None and signed is not None else None,
                "paraxial": configuration.get("paraxial"),
                "fields": [{"field_label": f.get("field_label"),
                            "quality_q": f.get("image", {}).get("quality_q"),
                            "mtf": f.get("image", {}).get("mtf")}
                           for f in configuration.get("fields", [])],
            })
    focus = constraints.get("focus", {})
    margin = None
    if focus.get("operator") == "<=" and focus.get("metric") == "maximum_abs_paraxial_focus_error_mm":
        margin = focus["target"] + focus.get("tolerance", 0) - focus["observed"]
    return {"quality_q": facts["quality_q"], "online_feasible": facts["online_feasible"],
            "constraints": constraints, "configurations": configurations,
            "focus_constraint_margin_mm": margin,
            "focus_normalized_margin": focus.get("normalized_margin"),
            "focus_convention": "signed_error = sensor_z - paraxial_focus_plane_z; for unchanged geometry, sensor_delta = target_signed_error - measured_signed_error",
            "failed_constraints": [k for k, v in constraints.items() if v.get("passed") is False]}


def pointer(value, path):
    for part in path.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def prescription_delta(parent, candidate, task, plan):
    changes = []
    for variable in task["variables"]:
        for path in variable.get("paths", [variable.get("path")]):
            before, after = pointer(parent, path), pointer(candidate, path)
            if before != after:
                changes.append({"variable_id": variable["variable_id"], "path": path,
                                "before": before, "after": after,
                                "delta": after - before if type(before) in (int, float) and type(after) in (int, float) else None})
    changed = {c["variable_id"] for c in changes}
    return {"parent_sha256": digest(canonical(parent)), "candidate_sha256": digest(canonical(candidate)),
            "duplicate_parent": canonical(parent) == canonical(candidate), "changes": changes,
            "selected_but_unchanged": [v for v in plan["variables_to_adjust"] if v not in changed],
            "note": "Selected variables are permissions, not required changes; hypothesis alignment remains an Agent judgment."}
