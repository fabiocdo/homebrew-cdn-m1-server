from src.utils.log_utils import log

def dry_run(sfo_data, template, mode):
    """Plan renames and report which entries can be renamed."""
    template_value = template or ""

    class SafeDict(dict):
        def __missing__(self, key):
            return ""

    def normalize_value(key, value):
        if value is None:
            return ""
        if key == "title":
            title_value = str(value)
            if mode == "uppercase":
                return title_value.upper()
            if mode == "lowercase":
                return title_value.lower()
            if mode == "capitalize":
                return " ".join(part.capitalize() for part in title_value.split())
            return title_value
        return str(value)

    safe = {key: normalize_value(key, value) for key, value in (sfo_data or {}).items()}
    planned_name = template_value.format_map(SafeDict(safe)).strip()
    if planned_name and not planned_name.lower().endswith(".pkg"):
        planned_name = f"{planned_name}.pkg"
    return planned_name

def run(pkg, sfo_data, template, mode):
    """Rename PKGs based on SFO metadata."""
    planned_name = dry_run(sfo_data, template, mode)
    if not planned_name:
        return None
    if pkg.name == planned_name:
        return None
    try:
        pkg.rename(pkg.with_name(planned_name))
    except Exception:
        log("error", "TODO - AUTO FORMATTER ERROR", module="AUTO_FORMATTER")
        return None
    return planned_name
