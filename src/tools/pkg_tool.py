import subprocess

PKGTOOL_PATH = "../bin/pkgtool"

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

        if parts[4].isdigit():
            name = parts[5]
        else:
            name = parts[4]

        if name == "PARAM_SFO":
            pkg_indexes["PARAM_SFO"] = index
        elif name == "ICON0_PNG":
            pkg_indexes["ICON0_PNG"] = index

    return pkg_indexes

def extract_sfo_data(pkg_indexes):

    param_sfo_index = pkg_indexes["PARAM_SFO"]
    result = subprocess.run(
        [PKGTOOL_PATH, "pkg_extractentry"] + param_sfo_index,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

if __name__ == "__main__":
    import sys
    print(get_data_indexes(sys.argv[1:]))