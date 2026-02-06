# import shutil
# import tempfile
# import struct
import subprocess
from pathlib import Path
from subprocess import CompletedProcess

from hb_store_m1.models import Global, PKG
from hb_store_m1.utils.log import log_debug, log_info, log_warn

# import os
# from src.models.extraction_result import ExtractResult, REGION_MAP, APP_TYPE_MAP, SELECTED_FIELDS


def _run_pkgtool(pkg: Path, command: PKG.ToolCommand):
    return subprocess.run(
        [Global.FILES.PKGTOOL_FILE_PATH, command, pkg],
        check=True,
        capture_output=True,
        text=True,
        env={"DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1"},
        timeout=120,
    )


class PkgUtils:

    @staticmethod
    def scan():

        log_info("Scanning PKGs...")
        scanned_pkgs = list(
            Path(Global.PATHS.PKG_DIR_PATH).rglob("*.pkg", case_sensitive=False)
        )
        log_info(f"Scanned {len(scanned_pkgs)} packages")

        return scanned_pkgs

    @staticmethod
    def validate(pkg: Path):
        result: CompletedProcess
        # try:
        # TODO Capturar saude do pkg, param, icon0, pic0, pic1,
        # PKG = {
        #     "Content Digest",
        #     "PKG Header Digest",
        #     "PKG Header Signature",
        #     "Body Digest",
        #     "PFS Signed Digest",
        #     "PFS Image Digest",
        # }
        # MEDIA = {
        #     "ICON0_PNG digest",
        #     "PIC0_PNG digest",
        #     "PIC1_PNG digest",
        # }
        if not pkg.exists():
            log_warn(f"PKG not found: {pkg}")
            return False
        try:
            result = _run_pkgtool(pkg, PKG.ToolCommand.VALIDATE_PKG)
        except subprocess.CalledProcessError as exc:
            log_warn(f"pkgtool validate failed for {pkg} (code={exc.returncode})")
            if exc.stdout:
                log_debug(exc.stdout.strip())
            if exc.stderr:
                log_debug(exc.stderr.strip())
            return False
        except subprocess.TimeoutExpired:
            log_warn(f"pkgtool validate timed out for {pkg}")
            return False

        log_info(f"PKG validated: {pkg}")
        if result.stdout:
            log_debug(result.stdout.strip())
        if result.stderr:
            log_debug(result.stderr.strip())
        return True
        # except subprocess.CalledProcessError as e:
        #     print(e)
        #     TODO jogar pro error_dir com mensagem custom

    @staticmethod
    def extract_data(pkg: Path):
        pass  # TODO implement

    # @staticmethod
    # def extract_pkg_data(
    #     pkg: Path, extract_sfo: bool, extract_icon: bool
    # ) -> tuple[Output, Output]:
    #
    # try:
    #     with tempfile.TemporaryDirectory() as tmp_dir:
    #         result = subprocess.run(
    #             [self.pkgtool_path, "pkg_listentries", str(pkg)],
    #             check=True,
    #             stdout=subprocess.PIPE,
    #             stderr=subprocess.STDOUT,
    #             text=True,
    #             env=self.env,
    #             timeout=self.timeout_seconds,
    #         )
    #
    #         param_sfo_index = None
    #         lines = result.stdout.strip().splitlines()
    #         for line in lines[1:]:
    #             parts = line.split()
    #             if len(parts) < 5:
    #                 continue
    #             index = int(parts[3])
    #             name = parts[5] if parts[4].isdigit() else parts[4]
    #             if name == "PARAM_SFO":
    #                 param_sfo_index = index
    #                 break
    #
    #         if param_sfo_index is None:
    #             return self.ExtractResult.NOT_FOUND, str(pkg)
    #
    #         param_sfo_path = os.path.join(tmp_dir, "PARAM.SFO")
    #
    #         subprocess.run(
    #             [
    #                 self.pkgtool_path,
    #                 "pkg_extractentry",
    #                 str(pkg),
    #                 str(param_sfo_index),
    #                 param_sfo_path,
    #             ],
    #             check=True,
    #             stdout=subprocess.PIPE,
    #             stderr=subprocess.STDOUT,
    #             text=True,
    #             env=self.env,
    #             timeout=self.timeout_seconds,
    #         )
    #
    #         with open(param_sfo_path, "rb") as f:
    #             data = f.read()
    # except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
    #     return self.ExtractResult.ERROR, str(pkg)
    #
    # result = {}
    #
    # magic, version, key_table_offset, data_table_offset, entry_count = (
    #     struct.unpack_from("<4sIIII", data, 0)
    # )
    #
    # if magic != b"\x00PSF":
    #     return self.ExtractResult.INVALID, str(pkg)
    #
    # entries_offset = 0x14
    #
    # for i in range(entry_count):
    #     off = entries_offset + i * 0x10
    #
    #     key_off, data_fmt, data_len, data_max, data_off = struct.unpack_from(
    #         "<HHIII", data, off
    #     )
    #
    #     key = (
    #         data[key_table_offset + key_off :]
    #         .split(b"\x00", 1)[0]
    #         .decode("utf-8", errors="ignore")
    #     )
    #
    #     raw = data[
    #         data_table_offset + data_off : data_table_offset + data_off + data_len
    #     ]
    #
    #     if key == "PUBTOOLVER":
    #         # explicitly treat as HEX
    #         value = raw.hex()
    #
    #     elif data_fmt == 0x0404:  # string
    #         value = raw.rstrip(b"\x00").decode("utf-8", errors="ignore")
    #
    #     elif data_fmt == 0x0402:  # int
    #         value = struct.unpack("<I", raw[:4])[0]
    #
    #     else:
    #         try:
    #             value = raw.rstrip(b"\x00").decode("utf-8")
    #         except UnicodeDecodeError:
    #             value = raw.hex()
    #
    #     result[key] = value
    #
    #     if key == "PUBTOOLINFO" and isinstance(value, str):
    #         for part in value.split(","):
    #             if part.startswith("c_date="):
    #                 c_date = part.split("=", 1)[1].strip()
    #                 if len(c_date) == 8 and c_date.isdigit():
    #                     result["RELEASE_DATE"] = (
    #                         f"{c_date[:4]}-{c_date[4:6]}-{c_date[6:8]}"
    #                     )
    #                 break
    #
    # content_id = result.get("CONTENT_ID", "")
    # prefix = content_id[:2].upper() if content_id else ""
    # result["REGION"] = REGION_MAP.get(prefix, "UNK")
    #
    # category = str(result.get("CATEGORY", "")).lower()
    # result["APP_TYPE"] = APP_TYPE_MAP.get(category, "unknown")
    #
    # selected = {}
    # for field in SELECTED_FIELDS:
    #     if field in result and result[field] is not None:
    #         selected[field] = result[field]
    #
    # return self.ExtractResult.OK, {
    #     key.lower(): value for key, value in selected.items()
    # }

    # @staticmethod
    # def is_valid_png(path: Path, max_bytes: int = 8 * 1024 * 1024) -> bool:
    #
    #     try:
    #         if not path.exists():
    #             return False
    #         size = path.stat().st_size
    #         if size <= 0 or size > max_bytes:
    #             return False
    #         with path.open("rb") as handle:
    #             data = handle.read(33)
    #         if len(data) < 24:
    #             return False
    #         if data[:8] != b"\x89PNG\r\n\x1a\n":
    #             return False
    #         ihdr_len = int.from_bytes(data[8:12], "big")
    #         if data[12:16] != b"IHDR" or ihdr_len < 13:
    #             return False
    #         width = int.from_bytes(data[16:20], "big")
    #         height = int.from_bytes(data[20:24], "big")
    #         if width <= 0 or height <= 0:
    #             return False
    #         return True
    #     except Exception:
    #         return False
    #
    # @staticmethod
    # def optimize_png(path: Path) -> bool:
    #
    #     try:
    #         if not path.exists():
    #             return False
    #         tool = shutil.which("optipng")
    #         if not tool:
    #             return False
    #         subprocess.run(
    #             [tool, "-o2", "-strip", "all", "-quiet", str(path)],
    #             check=False,
    #             stdout=subprocess.DEVNULL,
    #             stderr=subprocess.DEVNULL,
    #         )
    #         return True
    #     except Exception:
    #         return False
    #

    #
    # def extract_pkg_icon(
    #         self,
    #         pkg: Path,
    #         content_id: str,
    #         dry_run: bool = False,
    # ) -> Path | None:
    #
    #     output_dir = Path(os.environ["MEDIA_DIR"])
    #     output_dir.mkdir(parents=True, exist_ok=True)
    #     final_path = output_dir / f"{content_id}.png"
    #
    #     try:
    #         result = subprocess.run(
    #             [self.pkgtool_path, "pkg_listentries", str(pkg)],
    #             check=True,
    #             stdout=subprocess.PIPE,
    #             stderr=subprocess.STDOUT,
    #             text=True,
    #             env=self.env,
    #             timeout=self.timeout_seconds,
    #         )
    #     except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
    #         return None
    #
    #     icon_index = None
    #     lines = result.stdout.strip().splitlines()
    #     for line in lines[1:]:
    #         parts = line.split()
    #         if len(parts) < 5:
    #             continue
    #         index = int(parts[3])
    #         name = parts[5] if parts[4].isdigit() else parts[4]
    #         if name == "ICON0_PNG":
    #             icon_index = index
    #             break
    #
    #     if icon_index is None:
    #         return None
    #
    #     if final_path.exists():
    #         return final_path
    #
    #     if not dry_run:
    #         try:
    #             subprocess.run(
    #                 [
    #                     self.pkgtool_path,
    #                     "pkg_extractentry",
    #                     str(pkg),
    #                     str(icon_index),
    #                     str(final_path),
    #                 ],
    #                 check=True,
    #                 stdout=subprocess.PIPE,
    #                 stderr=subprocess.STDOUT,
    #                 text=True,
    #                 env=self.env,
    #                 timeout=self.timeout_seconds,
    #             )
    #         except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
    #             return None
    #
    #     return final_path


scan = PkgUtils.scan
extract_data = PkgUtils.extract_data
validate = PkgUtils.validate
