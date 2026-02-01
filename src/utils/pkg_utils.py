import os
import subprocess
import tempfile
import struct

PKGTOOL_PATH = "./bin/pkgtool"

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
        param_sfo_path = os.path.join(tmp_dir, "PARAM.SFO")

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
            data = f.read()

    result = {}

    magic, version, key_table_offset, data_table_offset, entry_count = struct.unpack_from(
        "<4sIIII", data, 0
    )

    if magic != b"\x00PSF":
        raise ValueError("PARAM.SFO inválido")

    entries_offset = 0x14

    for i in range(entry_count):
        off = entries_offset + i * 0x10

        key_off, data_fmt, data_len, data_max, data_off = struct.unpack_from(
            "<HHIII", data, off
        )

        key = data[key_table_offset + key_off :].split(b"\x00", 1)[0].decode(
            "utf-8", errors="ignore"
        )

        raw = data[
            data_table_offset + data_off : data_table_offset + data_off + data_len
        ]

        if key == "PUBTOOLVER":
            # trata explicitamente como HEX
            value = raw.hex()

        elif data_fmt == 0x0404:  # string
            value = raw.rstrip(b"\x00").decode("utf-8", errors="ignore")

        elif data_fmt == 0x0402:  # int
            value = struct.unpack("<I", raw[:4])[0]

        else:
            try:
                value = raw.rstrip(b"\x00").decode("utf-8")
            except UnicodeDecodeError:
                value = raw.hex()

        result[key] = value

    return result

def extract_pkg_icon(pkg_path, pkg_indexes, output_dir, output_name):
    os.makedirs(output_dir, exist_ok=True)

    icon_index = pkg_indexes["ICON0_PNG"]

    final_name = f"{output_name}.png"
    final_path = os.path.join(output_dir, final_name)

    subprocess.run(
        [
            PKGTOOL_PATH,
            "pkg_extractentry",
            pkg_path,
            str(icon_index),
            final_path,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    return final_path