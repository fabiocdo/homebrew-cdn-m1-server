from src.tools.pkg_tool import run_pkgtool

def extract_sfo_data(pkg_path):
    output = tool_extract_sfo_data(pkg_path)
    data = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def extract_icon():
    pass
