import subprocess
import tempfile
import struct
from pathlib import Path
import os
from src.utils.models.pkg_models import ExtractResult, REGION_MAP, APP_TYPE_MAP, SELECTED_FIELDS


class PkgUtils:
    """
    PkgUtils provides methods to interact with PKG files via pkgtool.

    It handles entry listing, SFO metadata extraction and icon extraction.
    """

    ExtractResult = ExtractResult

    def __init__(self):
        """
        Initialize PkgUtils.
        """
        self.pkgtool_path = os.environ["PKGTOOL_PATH"]
        self.env = {
            "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": os.environ["DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"],
        }

    def extract_pkg_data(self, pkg: Path) -> tuple[ExtractResult, dict | str]:
        """
        Extract and parse PARAM.SFO data from a PKG.

        :param pkg: Path to the PKG file
        :return: Tuple of (ExtractResult, dict or pkg path)
        """

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                result = subprocess.run(
                    [self.pkgtool_path, "pkg_listentries", str(pkg)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=self.env,
                )

                param_sfo_index = None
                lines = result.stdout.strip().splitlines()
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) < 5:
                        continue
                    index = int(parts[3])
                    name = parts[5] if parts[4].isdigit() else parts[4]
                    if name == "PARAM_SFO":
                        param_sfo_index = index
                        break

                if param_sfo_index is None:
                    return self.ExtractResult.NOT_FOUND, str(pkg)

                param_sfo_path = os.path.join(tmp_dir, "PARAM.SFO")

                subprocess.run(
                    [
                        self.pkgtool_path,
                        "pkg_extractentry",
                        str(pkg),
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
        except subprocess.CalledProcessError:
            return self.ExtractResult.ERROR, str(pkg)

        result = {}

        magic, version, key_table_offset, data_table_offset, entry_count = struct.unpack_from(
            "<4sIIII", data, 0
        )

        if magic != b"\x00PSF":
            return self.ExtractResult.INVALID, str(pkg)

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

            if key == "PUBTOOLINFO" and isinstance(value, str):
                for part in value.split(","):
                    if part.startswith("c_date="):
                        c_date = part.split("=", 1)[1].strip()
                        if len(c_date) == 8 and c_date.isdigit():
                            result["RELEASE_DATE"] = f"{c_date[:4]}-{c_date[4:6]}-{c_date[6:8]}"
                        break

        content_id = result.get("CONTENT_ID", "")
        prefix = content_id[:2].upper() if content_id else ""
        result["REGION"] = REGION_MAP.get(prefix, "UNK")

        category = str(result.get("CATEGORY", "")).lower()
        result["APP_TYPE"] = APP_TYPE_MAP.get(category, "_unknown")

        selected = {}
        for field in SELECTED_FIELDS:
            if field in result and result[field] is not None:
                selected[field] = result[field]

        return self.ExtractResult.OK, {key.lower(): value for key, value in selected.items()}

    def extract_pkg_icon(
        self,
        pkg: Path,
        content_id: str,
        dry_run: bool = False,
    ) -> Path | None:
        """
        Extract ICON0.PNG from a PKG.

        :param pkg: Path to the PKG file
        :param content_id: Content ID used as icon filename (without extension)
        :param dry_run: When True, do not extract; only return the expected output path
        :return: Path to the icon or None if not found
        """
        output_dir = Path(os.environ["MEDIA_DIR"])
        output_dir.mkdir(parents=True, exist_ok=True)
        final_path = output_dir / f"{content_id}.png"

        try:
            result = subprocess.run(
                [self.pkgtool_path, "pkg_listentries", str(pkg)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=self.env,
            )
        except subprocess.CalledProcessError:
            return None

        icon_index = None
        lines = result.stdout.strip().splitlines()
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 5:
                continue
            index = int(parts[3])
            name = parts[5] if parts[4].isdigit() else parts[4]
            if name == "ICON0_PNG":
                icon_index = index
                break

        if icon_index is None:
            return None

        if final_path.exists():
            return final_path

        if not dry_run:
            try:
                subprocess.run(
                    [
                        self.pkgtool_path,
                        "pkg_extractentry",
                        str(pkg),
                        str(icon_index),
                        str(final_path),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=self.env,
                )
            except subprocess.CalledProcessError:
                return None

        return final_path
