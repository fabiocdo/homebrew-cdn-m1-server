import re
import tempfile
from pathlib import Path

from hb_store_m1.models.pkg.section import Section
from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.metadata.param_sfo import (
    ParamSFOKey,
    ParamSFO,
)
from hb_store_m1.models.pkg.metadata.pkg_entry import PKGEntryKey
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.models.pkg.validation import ValidationFields, Severity
from hb_store_m1.helpers.pkgtool import PKGTool
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
    def scan(sections: list[str] | None = None) -> list[Path]:
        section_by_name = {section.name: section for section in Section.ALL}
        scan_targets = sections or list(section_by_name.keys())
        LogUtils.log_info("Scanning PKGs...", LogModule.PKG_UTIL)

        scanned_pkgs: list[Path] = []
        counts = {name: 0 for name in scan_targets}
        for name in scan_targets:
            root = section_by_name[name].path
            if not root.exists():
                continue
            for pkg_path in root.iterdir():
                if pkg_path.is_file() and pkg_path.suffix.lower() == ".pkg":
                    scanned_pkgs.append(pkg_path)
                    counts[name] += 1

        LogUtils.log_info(
            f"Scanned {len(scanned_pkgs)} PKGs. "
            + ", ".join(f"{name.upper()}: {counts[name]}" for name in scan_targets),
            LogModule.PKG_UTIL,
        )

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
                            f"PKG {pkg.name} validation failed on [{name}] field",
                            LogModule.PKG_UTIL,
                        )
                        return Output(Status.ERROR, pkg)
                    LogUtils.log_warn(
                        f"PKG {pkg.name} validation warning on [{name}] field",
                        LogModule.PKG_UTIL,
                    )
                    return Output(Status.WARN, pkg)

        LogUtils.log_debug(f"PKG {pkg.name} validation successful", LogModule.PKG_UTIL)
        return Output(Status.OK, pkg)

    @staticmethod
    def extract_pkg_data(pkg: Path) -> Output:
        if not pkg.is_file():
            LogUtils.log_error(f"PKG not found: {pkg}", LogModule.PKG_UTIL)
            return Output(Status.NOT_FOUND, pkg)

        try:
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
            with tempfile.TemporaryDirectory() as tmp:
                LogUtils.log_debug(
                    f"Extracting PARAM.SFO from PKG {pkg.name}...", LogModule.PKG_UTIL
                )
                extracted_sfo_file = Path(tmp) / "param.sfo"
                PKGTool.extract_pkg_entry(
                    pkg, pkg_entries[PKGEntryKey.PARAM_SFO], str(extracted_sfo_file)
                )

                entries_list = PKGTool.list_sfo_entries(
                    extracted_sfo_file
                ).stdout.splitlines()

                param_sfo = PkgUtils.parse_param_sfo_entries(entries_list)
                LogUtils.log_debug(
                    f"PARAM.SFO extracted successfully", LogModule.PKG_UTIL
                )

            # Step 3: Extract ICON0.PNG, PIC0.PNG, PIC1.PNG
            extracted_medias: dict[PKGEntryKey, Path | None] = {}
            LogUtils.log_debug(
                f"Extracting MEDIAS from PKG {pkg.name}...", LogModule.PKG_UTIL
            )

            content_id = param_sfo.data[ParamSFOKey.CONTENT_ID]
            media_dir = Path(Globals.PATHS.MEDIA_DIR_PATH)

            targets: list[tuple[PKGEntryKey, bool, Path]] = [
                (
                    PKGEntryKey.ICON0_PNG,
                    True,
                    media_dir / f"{content_id}_icon0.png",
                ),
                (
                    PKGEntryKey.PIC0_PNG,
                    False,
                    media_dir / f"{content_id}_pic0.png",
                ),
                (
                    PKGEntryKey.PIC1_PNG,
                    False,
                    media_dir / f"{content_id}_pic1.png",
                ),
            ]

            for entry_key, is_critical, file_path in targets:
                entry_index = pkg_entries.get(entry_key)
                if entry_index is None:
                    if is_critical:
                        LogUtils.log_error(
                            f"Cannot extract media from {pkg.name}. {entry_key} was not found",
                            LogModule.PKG_UTIL,
                        )
                        return Output(Status.ERROR, pkg)

                    else:
                        LogUtils.log_debug(
                            f"Skipping {entry_key} extraction. {entry_key} was not found in {pkg.name}",
                            LogModule.PKG_UTIL,
                        )
                        extracted_medias[entry_key] = None
                    continue

                if file_path.exists():
                    LogUtils.log_debug(
                        f"Skipping {entry_key} extraction. {file_path.name} already exists",
                        LogModule.PKG_UTIL,
                    )
                    extracted_medias[entry_key] = file_path
                    continue

                PKGTool.extract_pkg_entry(pkg, entry_index, str(file_path))
                extracted_medias[entry_key] = file_path

            # Step 4: Build PKG
            extracted_pkg = PKG(
                title=param_sfo.data[ParamSFOKey.TITLE],
                title_id=param_sfo.data[ParamSFOKey.TITLE_ID],
                content_id=param_sfo.data[ParamSFOKey.CONTENT_ID],
                category=param_sfo.data[ParamSFOKey.CATEGORY],
                version=param_sfo.data[ParamSFOKey.VERSION],
                pubtoolinfo=param_sfo.data[ParamSFOKey.PUBTOOLINFO],
                icon0_png_path=extracted_medias[PKGEntryKey.ICON0_PNG],
                pic0_png_path=(
                    extracted_medias[PKGEntryKey.PIC0_PNG]
                    if extracted_medias[PKGEntryKey.PIC0_PNG]
                    else None
                ),
                pic1_png_path=(
                    extracted_medias[PKGEntryKey.PIC1_PNG]
                    if extracted_medias[PKGEntryKey.PIC1_PNG]
                    else None
                ),
                pkg_path=pkg,
            )
            LogUtils.log_debug(
                f"Extracted data successfully from PKG {pkg.name}", LogModule.PKG_UTIL
            )
            return Output(Status.OK, extracted_pkg)
        except Exception as exc:
            LogUtils.log_error(
                f"Failed to extract data from PKG {pkg.name}: {exc}", LogModule.PKG_UTIL
            )
            return Output(Status.ERROR, pkg)


PkgUtils = PkgUtils()
