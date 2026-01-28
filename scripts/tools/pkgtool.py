import os
import subprocess

PKGTOOL_PATH = "/usr/local/bin/pkgtool"
DOTNET_GLOBALIZATION_ENV = "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT"


def run_pkgtool(args):
    """Run pkgtool with provided arguments and return stdout."""
    env = os.environ.copy()
    env.setdefault(DOTNET_GLOBALIZATION_ENV, "1")
    result = subprocess.run(
        [PKGTOOL_PATH] + args,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    return result.stdout
