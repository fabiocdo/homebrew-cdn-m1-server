import re
import tempfile
from pathlib import Path

from hb_store_m1.models.globals import Globals
from hb_store_m1.models.output import Output, Status
from hb_store_m1.models.pkg.metadata.param_sfo import (
    ParamSFOKey,
    ParamSFOValue,
    ParamSFO,
)
from hb_store_m1.models.pkg.metadata.pkg_entry import PKGEntryKey
from hb_store_m1.models.pkg.pkg import PKG
from hb_store_m1.models.pkg.validation import ValidationFields, Severity
from hb_store_m1.utils.helper.pkgtool import PKGTool
from hb_store_m1.utils.log_utils import LogUtils


class PkgUtils:

    @staticmethod
    def parse_sfo_entries(lines: list[str]) -> dict[str, dict[str, object]]:
        entries: dict[str, dict[str, object]] = {}
        entries_regex = re.compile(
            r"^(?P<name>[^:]+?)\s*:\s*(?P<type>[^()]+)\((?P<size>\d+)/(?:\s*)"
            r"(?P<max_size>\d+)\)\s*=\s*(?P<value>.*)$"
        )

        for line in lines:
            match = entries_regex.match(line.strip())
            if not match:
                continue

            name = match.group("name").strip()
            entry_type = match.group("type").strip()
            size = int(match.group("size"))
            max_size = int(match.group("max_size"))
            value = match.group("value")

            entries[name] = {
                "type": entry_type,
                "size": size,
                "max_size": max_size,
                "value": value,
            }

        return entries

    @staticmethod
    def parse_param_sfo_entries(
        lines: list[str],
    ) -> dict[ParamSFOKey, ParamSFOValue]:
        entries = PkgUtils.parse_sfo_entries(lines)
        mapped: dict[ParamSFOKey, ParamSFOValue] = {}

        for key, entry in entries.items():
            enum_key = ParamSFOKey.__members__.get(key)
            if enum_key is None:
                continue
            mapped[enum_key] = value

        return mapped

    @staticmethod
    def parse_param_sfo(lines: list[str]) -> ParamSFO:
        entries = PkgUtils.parse_param_sfo_entries(lines)
        return ParamSFO(entries)

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
    ) -> PKG:

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

        # Step 2: Extract entries
        if extract_sfo:
            with tempfile.TemporaryDirectory() as tmp:

                param_sfo = Path(tmp) / "param.sfo"
                PKGTool.extract_pkg_entry(
                    pkg, pkg_entries[PKGEntryKey.PARAM_SFO], str(param_sfo)
                )

                response = PKGTool.list_sfo_entries(param_sfo).stdout.splitlines()

                sfo_entries = PkgUtils.parse_sfo_entries(response)

                print(sfo_entries)
                for field in sfo_entries:
                    print(field)

        # files_to_extract = {}
        # if extract_medias:
        #     files_to_extract = {
        #             EntryKey.ICON0_PNG: "icon0.png",
        #             EntryKey.PIC0_PNG: "pic0.png",
        #             EntryKey.PIC1_PNG: "pic1.png",
        #     }

        # extracted = {}
        # with tempfile.TemporaryDirectory() as tmp:
        #     tmp_dir = Path(tmp)
        #
        #     for key, filename in files_to_extract.items():
        #         entry_index = pkg_entries.get(key)
        #         if entry_index is None:
        #             continue
        #
        #         out_path = tmp_dir / filename
        #         _run_pkgtool(
        #             pkg_path,
        #             _PKGToolCommand.EXTRACT_PKG_ENTRY,
        #             str(entry_index),
        #             str(out_path),
        #         )
        #
        #         extracted[key] = out_path
        #
        # # Step 4: Build PKG
        # print(extracted[EntryKey.PARAM_SFO])
        # print(extracted[EntryKey.ICON0_PNG])
        # print(extracted[EntryKey.PIC0_PNG])
        # print(extracted[EntryKey.PIC1_PNG])


PkgUtils = PkgUtils()
