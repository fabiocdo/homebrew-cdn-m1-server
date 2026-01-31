import os
import subprocess
import tempfile

PKGTOOL_PATH = "./pkgtool"

env = {
    "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
}

def get_data_indexes(pkg_args):
    result = subprocess.run(
        [PKGTOOL_PATH, "pkg_listentries"] + pkg_args,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    pkg_indexes = {}
    lines = result.stdout.strip().splitlines()

    for line in lines[1:]:
        parts = line.split()
        index = int(parts[3])

        name = parts[5] if parts[4].isdigit() else parts[4]

        if name in ("PARAM_SFO", "ICON0_PNG"):
            pkg_indexes[name] = index

    return pkg_indexes


def extract_sfo_data(pkg_path, pkg_indexes):
    with tempfile.TemporaryDirectory() as tmp_dir:
        param_sfo_index = pkg_indexes["PARAM_SFO"]
        param_sfo_path = os.path.join(tmp_dir, "param.sfo")

        subprocess.run(
            [
                PKGTOOL_PATH,
                "pkg_extractentry",
                pkg_path,
                str(param_sfo_index),
                param_sfo_path,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )

        with open(param_sfo_path, "rb") as f:
            return f.read()


if __name__ == "__main__":
    import sys

    pkg_path = sys.argv[1]

    indexes = get_data_indexes([pkg_path])
    print("Indexes:", indexes)

    sfo_data = extract_sfo_data(pkg_path, indexes)
    print("PARAM.SFO size:", len(sfo_data), "bytes")
