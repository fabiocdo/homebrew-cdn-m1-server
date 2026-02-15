import re
import subprocess
import tempfile
from pathlib import Path

from hb_store_m1.helpers.pkgtool import PKGTool
from hb_store_m1.models.globals import Globals
from hb_store_m1.models.log import LogModule
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.metadata.param_sfo import (
    ParamSFOKey,
    ParamSFO,
)
from hb_store_m1.models.pkg.metadata.pkg_entry import PKGEntryKey
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.models.pkg.section import Section
from hb_store_m1.models.pkg.validation import ValidationFields, Severity
from hb_store_m1.utils.log_utils import LogUtils

log = LogUtils(LogModule.PKG_UTIL)


class PkgUtils:
    _PARAM_REGEX = re.compile(r"^(?P<name>[^:]+?)\s*:\s*[^=]*=\s*(?P<value>.*)$")

    @staticmethod
    def _list_pkg_entries(pkg: Path) -> dict[PKGEntryKey, str]:
        pkg_entries: dict[PKGEntryKey, str] = {}
        entries_result = PKGTool.list_pkg_entries(pkg).stdout.splitlines()
        for line in entries_result[1:]:
            parts = line.split()
            if len(parts) < 5:
                continue
            name = str(parts[4])
            index = str(parts[3])
            entry_key = PKGEntryKey.__members__.get(name)
            if entry_key is None:
                continue
            pkg_entries[entry_key] = index
        return pkg_entries

    @staticmethod
    def _media_targets(content_id: str) -> list[tuple[PKGEntryKey, bool, Path]]:
        media_dir = Path(Globals.PATHS.MEDIA_DIR_PATH)
        return [
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

    @staticmethod
    def parse_param_sfo_entries(lines: list[str]) -> ParamSFO:
        data: dict[ParamSFOKey, str] = {key: "" for key in ParamSFOKey}

        for line in lines:
            match = PkgUtils._PARAM_REGEX.match(line.strip())
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
    def read_content_id(pkg: Path) -> str | None:
        validation = PkgUtils.validate(pkg)
        if validation.status not in (Status.OK, Status.WARN):
            return None

        extract_output = PkgUtils.extract_pkg_data(pkg)
        if extract_output.status is not Status.OK or not extract_output.content:
            return None

        param_sfo = extract_output.content
        content_id = (param_sfo.data.get(ParamSFOKey.CONTENT_ID) or "").strip()
        return content_id or None

    @staticmethod
    def scan(sections: list[str] | None = None) -> list[Path]:
        section_by_name = {section.name: section for section in Section.ALL}
        scan_targets = sections or list(section_by_name.keys())
        log.log_info("Scanning PKGs...")

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

        log.log_info(
            f"Scanned {len(scanned_pkgs)} PKGs. "
            + ", ".join(f"{name.upper()}: {counts[name]}" for name in scan_targets)
        )

        return scanned_pkgs

    @staticmethod
    def validate(pkg: Path) -> Output:
        command_failed = False
        command_error_message = ""
        try:
            validation_result = PKGTool.validate_pkg(pkg).stdout.splitlines()
        except subprocess.CalledProcessError as exc:
            command_failed = True
            validation_result = (exc.stdout or "").splitlines()
            command_error_message = (exc.stderr or "").strip()
        except (subprocess.TimeoutExpired, OSError) as exc:
            log.log_error(f"PKG {pkg.name} validation failed: {exc}")
            return Output(Status.ERROR, pkg)

        for line in validation_result:
            if "[ERROR]" not in line:
                continue

            for field in ValidationFields:
                name, level = field.value
                if name in line:
                    if level is Severity.CRITICAL:
                        log.log_error(
                            f"PKG {pkg.name} validation failed on [{name}] field"
                        )
                        return Output(Status.ERROR, pkg)
                    log.log_warn(f"PKG {pkg.name} validation warning on [{name}] field")
                    return Output(Status.WARN, pkg)

            log.log_error(f"PKG {pkg.name} validation failed: {line.strip()}")
            return Output(Status.ERROR, pkg)

        if command_failed:
            details = f": {command_error_message}" if command_error_message else ""
            log.log_error(f"PKG {pkg.name} validation failed{details}")
            return Output(Status.ERROR, pkg)

        log.log_debug(f"PKG {pkg.name} validation successful")
        return Output(Status.OK, pkg)

    @staticmethod
    def extract_pkg_data(
        pkg: Path,
    ) -> Output[ParamSFO | Path]:

        if not pkg.is_file():
            log.log_error(f"PKG not found: {pkg}")
            return Output(Status.NOT_FOUND, pkg)

        try:
            pkg_entries = PkgUtils._list_pkg_entries(pkg)

            # Step 2: Extract PARAM.SFO
            param_sfo = None
            with tempfile.TemporaryDirectory() as tmp:
                log.log_debug(f"Extracting PARAM.SFO from PKG {pkg.name}...")
                extracted_sfo_file = Path(tmp) / "param.sfo"
                PKGTool.extract_pkg_entry(
                    pkg, pkg_entries[PKGEntryKey.PARAM_SFO], str(extracted_sfo_file)
                )

                entries_list = PKGTool.list_sfo_entries(
                    extracted_sfo_file
                ).stdout.splitlines()

                param_sfo = PkgUtils.parse_param_sfo_entries(entries_list)
                log.log_debug(f"PARAM.SFO extracted successfully")

            log.log_debug(f"Extracted data successfully from PKG {pkg.name}")
            return Output(Status.OK, param_sfo)

        except Exception as exc:
            log.log_error(f"Failed to extract data from PKG {pkg.name}: {exc}")
            return Output(Status.ERROR, pkg)

    @staticmethod
    def extract_pkg_medias(
        pkg: Path, content_id: str
    ) -> Output[dict[PKGEntryKey, Path | None] | Path]:
        if not pkg.is_file():
            log.log_error(f"PKG not found: {pkg}")
            return Output(Status.NOT_FOUND, pkg)

        if not (content_id or "").strip():
            log.log_error(f"Cannot extract medias from {pkg.name}. Missing content_id")
            return Output(Status.ERROR, pkg)

        try:
            pkg_entries = PkgUtils._list_pkg_entries(pkg)

            extracted_medias: dict[PKGEntryKey, Path | None] = {}
            log.log_debug(f"Extracting MEDIAS from PKG {pkg.name}...")

            for entry_key, is_critical, file_path in PkgUtils._media_targets(
                content_id
            ):
                entry_index = pkg_entries.get(entry_key)
                if entry_index is None:
                    if is_critical:
                        log.log_error(
                            f"Cannot extract media from {pkg.name}. {entry_key} was not found"
                        )
                        return Output(Status.ERROR, pkg)

                    log.log_debug(
                        f"Skipping {entry_key} extraction. {entry_key} was not found in {pkg.name}"
                    )
                    extracted_medias[entry_key] = None
                    continue

                if file_path.exists():
                    log.log_debug(
                        f"Skipping {entry_key} extraction. {file_path.name} already exists"
                    )
                    extracted_medias[entry_key] = file_path
                    continue

                PKGTool.extract_pkg_entry(pkg, entry_index, str(file_path))
                log.log_debug(f"Extracted {entry_key} from {pkg.name} successfully.")
                extracted_medias[entry_key] = file_path

            log.log_debug(f"Extracted medias successfully from PKG {pkg.name}")
            return Output(Status.OK, extracted_medias)

        except Exception as exc:
            log.log_error(f"Failed to extract medias from PKG {pkg.name}: {exc}")
            return Output(Status.ERROR, pkg)

    @staticmethod
    def build_pkg(
        pkg_path: Path, param_sfo: ParamSFO, medias: dict[PKGEntryKey, Path | None]
    ) -> Output[PKG]:

        pkg = PKG(
            title=param_sfo.data[ParamSFOKey.TITLE],
            title_id=param_sfo.data[ParamSFOKey.TITLE_ID],
            content_id=param_sfo.data[ParamSFOKey.CONTENT_ID],
            category=param_sfo.data[ParamSFOKey.CATEGORY],
            version=param_sfo.data[ParamSFOKey.VERSION],
            pubtoolinfo=param_sfo.data[ParamSFOKey.PUBTOOLINFO],
            system_ver=(param_sfo.data.get(ParamSFOKey.SYSTEM_VER) or ""),
            icon0_png_path=medias[PKGEntryKey.ICON0_PNG],
            pic0_png_path=(
                medias[PKGEntryKey.PIC0_PNG] if medias[PKGEntryKey.PIC0_PNG] else None
            ),
            pic1_png_path=(
                medias[PKGEntryKey.PIC1_PNG] if medias[PKGEntryKey.PIC1_PNG] else None
            ),
            pkg_path=pkg_path,
        )
        log.log_debug(f"PKG built successfully {pkg.pkg_path.name}")
        return Output(Status.OK, pkg)
