import os
import tomllib
from functools import cache
from pathlib import Path
from shutil import which, rmtree
from typing import Any

import nox

root = Path(__file__).parent
root_env = {"PYTHONPATH": str(root)}

nox.options.envdir = "/tmp/nox"
nox.options.sessions = ["tidy", "check"]

pyproject_toml = "pyproject.toml"
VENV_DIR = Path("./.venv").resolve()
python = str(VENV_DIR / "bin" / "python")

PYTHON_VERSIONS = ["3.8", "3.9", "3.10", "3.11"]


@cache
def get_pyproject() -> dict[str, Any] | None:
    if not os.path.isfile(pyproject_toml):
        return None
    with open(pyproject_toml, "rb") as pp_file:
        pyproject_dict = tomllib.load(pp_file)
    return pyproject_dict


@cache
def get_deps() -> list[tuple[str, str]] | None:
    if not (pyproject := get_pyproject()):
        return None
    dependencies = pyproject["project"]["dependencies"]
    dependencies += pyproject["project"]["optional-dependencies"]["performance"]
    dependencies = [dep.split(" ", 1) for dep in dependencies]
    return dependencies  # type: ignore [no-any-return]


@cache
def get_version() -> str | None:
    if not (pyproject := get_pyproject()):
        return None
    return str(pyproject["project"]["version"])


def get_packages(session: nox.Session) -> tuple[Path, Path]:
    if not (version := get_version()):
        session.error("Could not get version from pyproject.toml")
    package_whl = root / "dist" / f"recipe2txt-{version}-py3-none-any.whl"
    package_tar = root / "dist" / f"recipe2txt-{version}.tar.gz"

    if not package_whl.is_file() or not package_tar.is_file():
        run(session, "pyproject-build", use_root_env=True)
    return package_whl, package_tar


def install_deps(session: nox.Session, python_path: str = "python") -> None:
    if not (dependencies := get_deps()):
        session.error(pyproject_toml + " does not exist")
    to_install = [
        f"{name}{constraint.replace(' ', '')}"
        for name, constraint in dependencies
        if not is_available(session, name, python_path)
    ]
    if to_install:
        session.run(
            python_path, "-m", "pip", "install", *to_install, external=True, silent=True
        )


def run(
    session: nox.Session, program: str, *args: str, use_root_env: bool = False
) -> None:
    if not which(program):
        session.install(program)
    if use_root_env:
        session.run(program, *args, env=root_env, external=True)
    else:
        session.run(program, *args, external=True)


def is_available(
    session: nox.Session,
    package_name: str,
    python_path: str = "python3",
) -> bool:
    out = session.run(
        python_path,
        "-c",
        f"import {package_name.replace('-', '_')}",
        success_codes=[0, 1],
        external=True,
        silent=True,
    )
    return False if out else True


def is_applicable(session: nox.Session, constraints: str) -> bool:
    constraints_list = [
        [component for component in con.split(" ") if component]
        for con in constraints.split(";")
        if con
    ][1:]
    if not constraints_list:
        return True
    if not (out := session.run("python", "--version", silent=True)):
        session.error("python not found")
    _, py_vers = out.split(" ")
    py_vers = py_vers.strip()
    for con in constraints_list:
        if not con:
            continue
        if con[0] == "python_version":
            if con[1] in "=>=<=":
                return bool(eval(f"'{py_vers}' {con[1]} {con[2]}"))
            else:
                return False
    session.error("Constraints unclear: " + constraints)


@nox.session(reuse_venv=True)
def dev(session: nox.Session) -> None:
    """Creates the development environment."""
    if not VENV_DIR.is_dir():
        run(session, "virtualenv", str(VENV_DIR))
    install_deps(session, python)
    session.run(
        python, "-m", "pip", "install", "nox", external=True, silent=True
    )  # so mypy can typecheck this file
    session.notify("check")


@nox.session(reuse_venv=True)
def check(session: nox.Session) -> None:
    """Uses static code analysis and runs unittests."""
    run(session, "mypy")
    session.run(python, "-m", "unittest", external=True)


@nox.session(reuse_venv=True)
def tidy(session: nox.Session) -> None:
    run(session, "isort", "recipe2txt", "test")
    run(session, "black", "recipe2txt", "test", "noxfile.py")
    run(session, "autoflake", "recipe2txt", "test", "noxfile.py")
    session.notify("check")


@nox.session(reuse_venv=True)
def short(session: nox.Session) -> None:
    """System-testing: A short run of the entire program."""
    session.notify("check")
    session.notify("tidy")
    install_deps(session)
    session.run("python", "-m", "unittest", "discover", "-s", "test")
    session.run("python", "-m", "test.test4recipe2txt", env=root_env)


# TODO: parameterize test?
@nox.session(reuse_venv=True)
def medium(session: nox.Session) -> None:
    """System-testing: Test different CLI-configurations with short runs of the program."""
    session.notify("check")
    session.notify("tidy")
    install_deps(session)
    args = ["--delete-database", "--long-timeout"]
    args_md = args + ["--file-format", "md"]
    args_from_file = args + ["--input-format", "file"]
    args_serial = args + ["--connections", "1"]
    arg_permutations = [args_md, args_from_file, args_serial]
    for arg in arg_permutations:
        session.run("python", "-m", "test.test4recipe2txt", *arg, env=root_env)


@nox.session(reuse_venv=True)
def all(session: nox.Session) -> None:
    """System-testing: Scrape all URLs at once."""
    session.notify("check")
    session.notify("tidy")
    install_deps(session)
    session.run(
        "python",
        "-m",
        "test.test4recipe2txt",
        "--delete-database",
        "--long-timeout",
        "--number-of-urls",
        "-1",
        env=root_env,
    )


@nox.session(reuse_venv=True)
def release(session: nox.Session) -> None:
    """Release a new version of the program."""
    whl, tar = get_packages(session)
    run(session, "twine", "upload", str(whl), str(tar), use_root_env=True)


@nox.session(reuse_venv=True)
def install(session: nox.Session) -> None:
    """Installs the package locally."""
    whl, _ = get_packages(session)
    run(session, "pipx", "install", str(whl), use_root_env=True)


@nox.session(reuse_venv=True)
def clean(session: nox.Session) -> None:
    """Remove all temporary files occurring during program operation and testing."""
    to_remove = [
        root / "test" / "testfiles" / "debug-dirs",
        root / ".mypy_cache",
        root / "test" / "testfiles" / "tmp_testfiles_re2txt",
        root / "test" / "reports_test4recipe2txt",
        root / "recipe2txt.egg-info",
    ]
    for p in to_remove:
        session.log(f"Removing{p}")
        rmtree(p, ignore_errors=True)
    session.log("Removing all '__pycache__'-instances")
    for p in root.rglob("__pycache__"):
        rmtree(p)


@nox.session(reuse_venv=True)
def uninstall(session: nox.Session) -> None:
    """Uses 'clean' and removes the dev-virtual-environment."""
    session.notify("clean")
    rmtree(VENV_DIR, ignore_errors=True)
