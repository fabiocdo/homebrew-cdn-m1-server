import re
import tempfile
from pathlib import Path

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.metadata.param_sfo import (
    ParamSFOKey,
    ParamSFO,
)
from hb_store_m1.models.pkg.metadata.pkg_entry import PKGEntryKey
from hb_store_m1.models.pkg.validation import ValidationFields, Severity
from hb_store_m1.utils.helper.pkgtool import PKGTool
from hb_store_m1.utils.log_utils import LogUtils


class PkgUtils:
    _SFO_LINE_RE = re.compile(r"^(?P<name>[^:]+?)\s*:\s*[^=]*=\s*(?P<value>.*)$")

    @staticmethod
    def parse_param_sfo_entries(lines: list[str]) -> ParamSFO:
        data: dict[ParamSFOKey, str] = {key: "" for key in ParamSFOKey}

        for line in lines:
            match = PkgUtils._SFO_LINE_RE.match(line.strip())
            if not match:
                continue

            name = match.group("name").strip()
            if name == "Entry Name":
                continue

            enum_key = ParamSFOKey.__members__.get(name)
            if enum_key is None:
                continue

            value = match.group("value").strip()
            data[enum_key] = value

        return ParamSFO(data)

    @staticmethod
    def scan():

        LogUtils.log_info("Scanning PKGs...")
        scanned_pkgs = list(
            Path(Globals.PATHS.PKG_DIR_PATH).rglob("*.pkg", case_sensitive=False)
        )
        LogUtils.log_info(f"Scanned {len(scanned_pkgs)} packages")

        return scanned_pkgs

    @staticmethod
    def validate(pkg: Path) -> Output:
        validation_result = PKGTool.validate_pkg(pkg).stdout.splitlines()

        for line in validation_result:
            print(line)
            if "[ERROR]" not in line:
                continue

            for field in ValidationFields:
                name, level = field.value
                if name in line:
                    if level is Severity.CRITICAL:
                        LogUtils.log_error(
                            f"PKG {pkg} validation failed on [{name}] field"
                        )
                        return Output(Status.ERROR, pkg)
                    LogUtils.log_warn(f"PKG {pkg} validation warning on [{name}] field")
                    return Output(Status.WARN, pkg)

        LogUtils.log_debug(f"PKG {pkg} validation successful")
        return Output(Status.OK, pkg)

    @staticmethod
    def extract_pkg_data(
        pkg: Path, extract_sfo: bool = True, extract_medias: bool = True
    ) -> Output:

        # Step 1: Track the entries indexes
        pkg_entries = {}
        entries_result = PKGTool.list_pkg_entries(pkg).stdout.splitlines()

        for line in entries_result[1:]:
            parts = line.split()
            name = str(parts[4])
            index = str(parts[3])

            entry_key = PKGEntryKey.__members__.get(name)
            if entry_key is None:
                continue

            pkg_entries[entry_key] = index

        # Step 2: Extract PARAM.SFO
        param_sfo = None
        if extract_sfo:
            with tempfile.TemporaryDirectory() as tmp:
                LogUtils.log_debug(f"Extracting PARAM.SFO from PKG {pkg}...")
                extracted_sfo_file = Path(tmp) / "param.sfo"
                PKGTool.extract_pkg_entry(
                    pkg, pkg_entries[PKGEntryKey.PARAM_SFO], str(extracted_sfo_file)
                )

                entries_list = PKGTool.list_sfo_entries(
                    extracted_sfo_file
                ).stdout.splitlines()

                param_sfo = PkgUtils.parse_param_sfo_entries(entries_list)
                LogUtils.log_debug(f"PARAM.SFO extracted successfully {param_sfo}")

        # Step 3: Extract ICON0.PNG, PIC0.PNG, PIC1.PNG

        # Step 4: Build PKG
        extracted_medias: dict[PKGEntryKey, Path] = {}
        if extract_medias:
            LogUtils.log_debug(f"Extracting MEDIAS from PKG {pkg}...")
            icon0_file_path = Path(Globals.PATHS.MEDIA_DIR_PATH) / str(
                param_sfo.data[ParamSFOKey.CONTENT_ID] + "_icon0.png"
            )
            pic0_file_path = Path(Globals.PATHS.MEDIA_DIR_PATH) / str(
                param_sfo.data[ParamSFOKey.CONTENT_ID] + "_pic0.png"
            )
            pic1_file_path = Path(Globals.PATHS.MEDIA_DIR_PATH) / str(
                param_sfo.data[ParamSFOKey.CONTENT_ID] + "_pic1.png"
            )

            if not icon0_file_path.exists():
                try:
                    PKGTool.extract_pkg_entry(
                        pkg,
                        pkg_entries[PKGEntryKey.ICON0_PNG],
                        str(icon0_file_path),
                    )
                    extracted_medias[PKGEntryKey.ICON0_PNG] = icon0_file_path
                except KeyError as exception:
                    LogUtils.log_error(f"{exception.args[0]} not found in {pkg}.")
            else:
                LogUtils.log_debug(
                    f"{icon0_file_path} already exists. Skipping extraction."
                )

            if not pic0_file_path.exists():
                try:
                    PKGTool.extract_pkg_entry(
                        pkg,
                        pkg_entries[PKGEntryKey.PIC0_PNG],
                        str(pic0_file_path),
                    )
                    extracted_medias[PKGEntryKey.PIC0_PNG] = pic0_file_path
                except KeyError as exception:
                    LogUtils.log_debug(
                        f"{exception.args[0]} not found in {pkg}. Skipping."
                    )
            else:
                LogUtils.log_debug(
                    f"{pic1_file_path} already exists. Skipping extraction."
                )

            if not pic1_file_path.exists():
                try:
                    PKGTool.extract_pkg_entry(
                        pkg,
                        pkg_entries[PKGEntryKey.PIC1_PNG],
                        str(pic1_file_path),
                    )
                    extracted_medias[PKGEntryKey.PIC1_PNG] = pic1_file_path
                except KeyError as exception:
                    LogUtils.log_debug(
                        f"{exception.args[0]} not found in {pkg}. Skipping."
                    )
            else:
                LogUtils.log_debug(
                    f"{pic1_file_path} already exists. Skipping extraction."
                )

        if extracted_medias:
            print(extracted_medias)


PkgUtils = PkgUtils()
