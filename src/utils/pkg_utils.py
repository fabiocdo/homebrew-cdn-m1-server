import os
import subprocess
import tempfile
import struct
from pathlib import Path
from src import settings


class PkgUtils:
    """
    PkgUtils provides methods to interact with PKG files via pkgtool.

    It handles entry listing, SFO metadata extraction and icon extraction.
    """

    def __init__(self, pkgtool_path: str | None = None):
        """
        Initialize PkgUtils.

        :param pkgtool_path: Path to the pkgtool executable
        """
        self.pkgtool_path = pkgtool_path or os.getenv("CDN_PKGTOOL_PATH", "./src/utils/bin/pkgtool")
        self.env = {
            "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
        }

    def get_data_indexes(self, pkg_args: list[str]) -> dict[str, int]:
        """
        Get indexes for PARAM_SFO and ICON0_PNG from a PKG using pkgtool.

        :param pkg_args: List of arguments to pass to pkg_listentries (e.g. [pkg_path])
        :return: Dictionary mapping entry names to their numeric indexes
        """
        result = subprocess.run(
            [self.pkgtool_path, "pkg_listentries"] + pkg_args,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=self.env,
        )

        pkg_indexes = {}
        lines = result.stdout.strip().splitlines()

        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 5:
                continue
            index = int(parts[3])
            name = parts[5] if parts[4].isdigit() else parts[4]

            if name in ("PARAM_SFO", "ICON0_PNG"):
                pkg_indexes[name] = index

        return pkg_indexes

    def extract_sfo_data(self, pkg_path: str, pkg_indexes: dict[str, int]) -> dict:
        """
        Extract and parse PARAM.SFO data from a PKG.

        :param pkg_path: Path to the PKG file
        :param pkg_indexes: Dictionary containing PKG entry indexes
        :return: Dictionary containing parsed SFO metadata
        :raises KeyError: If PARAM_SFO index is missing
        :raises ValueError: If the extracted SFO is invalid
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            if "PARAM_SFO" not in pkg_indexes:
                raise KeyError("TODO: PARAM_SFO index not found in pkg_indexes")

            param_sfo_index = pkg_indexes["PARAM_SFO"]
            param_sfo_path = os.path.join(tmp_dir, "PARAM.SFO")

            subprocess.run(
                [
                    self.pkgtool_path,
                    "pkg_extractentry",
                    pkg_path,
                    str(param_sfo_index),
                    param_sfo_path,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=self.env,
            )

            with open(param_sfo_path, "rb") as f:
                data = f.read()

        result = {}

        magic, version, key_table_offset, data_table_offset, entry_count = struct.unpack_from(
            "<4sIIII", data, 0
        )

        if magic != b"\x00PSF":
            raise ValueError("Invalid PARAM.SFO")

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
                # explicitly treat as HEX
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

    def extract_pkg_icon(self, pkg_path: str, pkg_indexes: dict[str, int], output_dir: str, output_name: str) -> str:
        """
        Extract ICON0.PNG from a PKG.

        :param pkg_path: Path to the PKG file
        :param pkg_indexes: Dictionary containing PKG entry indexes
        :param output_dir: Directory where the icon will be saved
        :param output_name: Basename for the output file (without extension)
        :return: Full path to the extracted icon
        :raises KeyError: If ICON0_PNG index is missing
        """
        os.makedirs(output_dir, exist_ok=True)

        if "ICON0_PNG" not in pkg_indexes:
            raise KeyError("TODO: ICON0_PNG index not found in pkg_indexes")

        icon_index = pkg_indexes["ICON0_PNG"]

        final_name = f"{output_name}.png"
        final_path = os.path.join(output_dir, final_name)

        subprocess.run(
            [
                self.pkgtool_path,
                "pkg_extractentry",
                pkg_path,
                str(icon_index),
                final_path,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=self.env,
        )

        return final_path
