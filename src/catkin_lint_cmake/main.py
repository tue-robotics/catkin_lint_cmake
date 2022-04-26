import sys

import argparse
import configparser
import os

from catkin_lint import __version__ as catkin_lint_version
from catkin_lint.environment import CatkinEnvironment
from catkin_lint.linter import CMakeLinter, ERROR, WARNING, NOTICE
from catkin_lint.main import add_linter_check, get_severity_overrides_from_args
from catkin_lint.output import Color
from catkin_lint.util import getcwd

# noinspection PyUnresolvedReferences
import catkin_lint.checks


USE_COLOR = {"never": Color.Never, "always": Color.Always, "auto": Color.Auto}


def prepare_arguments(parser: argparse.ArgumentParser):
    parser.epilog = "Options marked with [*] can be set in the [catkin_lint] section of a configuration file."
    parser.add_argument("--version", action="version", version=catkin_lint_version)
    parser.add_argument("path", metavar="PATH", nargs="*", default=[], help="path to catkin packages")
    m = parser.add_mutually_exclusive_group()
    m.add_argument("--quiet", "-q", action="store_true", default=None, help="suppress final summary [*]")
    m.add_argument(
        "--no-quiet", action="store_false", default=None, help="override quiet=yes option from configuration file"
    )
    parser.add_argument(
        "--severity-level", "-W", metavar="LEVEL", type=int, default=None, help="set severity level (0-2) [*]"
    )
    parser.add_argument("-c", "--check", metavar="MODULE.CHECK", action="append", default=[], help=argparse.SUPPRESS)
    parser.add_argument(
        "--config",
        action="append",
        metavar="FILE",
        default=[],
        help="read configuration from FILE (can be used multiple times)",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        metavar="ID",
        default=[],
        help="ignore diagnostic message ID (can be used multiple times)",
    )
    parser.add_argument(
        "--error",
        action="append",
        metavar="ID",
        default=[],
        help="treat diagnostic message ID as error (can be used multiple times)",
    )
    parser.add_argument(
        "--warning",
        action="append",
        metavar="ID",
        default=[],
        help="treat diagnostic message ID as warning (can be used multiple times)",
    )
    parser.add_argument(
        "--notice",
        action="append",
        metavar="ID",
        default=[],
        help="treat diagnostic message ID as notice (can be used multiple times)",
    )
    m = parser.add_mutually_exclusive_group()
    m.add_argument("--strict", action="store_true", default=None, help="treat everything reported as error [*]")
    m.add_argument(
        "--no-strict", action="store_false", dest="strict", help="override strict=yes option from configuration file"
    )
    parser.add_argument(
        "--show-ignored", action="store_true", help="show messages even if they have been ignored explicitly"
    )
    parser.add_argument(
        "--pkg", action="append", default=[], help="specify catkin package by name (can be used multiple times)"
    )
    parser.add_argument(
        "--skip-pkg",
        metavar="PKG",
        action="append",
        default=[],
        help="skip testing a catkin package (can be used multiple times)",
    )
    parser.add_argument(
        "--skip-path",
        metavar="PATH",
        action="append",
        default=[],
        help="skip testing any package in a path that contains PATH (can be used multiple times)",
    )
    parser.add_argument(
        "--package-path",
        metavar="PATH",
        help="additional package path (separate multiple locations with '%s') [*]" % os.pathsep,
    )
    parser.add_argument(
        "--rosdistro", metavar="DISTRO", help="override ROS distribution (default: ROS_DISTRO environment variable) [*]"
    )
    m = parser.add_mutually_exclusive_group()
    m.add_argument(
        "--resolve-env",
        action="store_true",
        default=None,
        help="resolve $ENV{} references from environment variables [*]",
    )
    m.add_argument(
        "--no-resolve-env", action="store_false", help="override resolve_env=yes option from configuration file"
    )
    parser.add_argument(
        "--color",
        metavar="MODE",
        choices=["never", "always", "auto"],
        default=None,
        help='colorize text output; valid values are "never", "always", and "auto" [*]',
    )
    m = parser.add_mutually_exclusive_group()
    m.add_argument(
        "--offline", action="store_true", default=None, help="do not download package index to look for packages [*]"
    )
    m.add_argument("--no-offline", action="store_false", help="override offline=yes option from configuration file")
    parser.add_argument(
        "--clear-cache", action="store_true", help="clear internal cache and invalidate all downloaded manifests"
    )
    parser.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--disable-cache", action="store_true", help=argparse.SUPPRESS)

    parser.add_argument(
        "--output-file", metavar="OUTPUT_XML", type=str, help="Filename where to write the test results"
    )

    return parser


def run_linter(args: argparse.Namespace) -> int:
    """
    Run the linter

    :param args: Parsed arguments
    :return: exit_code
    """
    if args.clear_cache:
        from catkin_lint.environment import _clear_cache

        _clear_cache()

    config = configparser.ConfigParser(strict=True)
    config.optionxform = lambda option: option.lower().replace("-", "_")
    # Initialize configuration from command line arguments
    config["*"] = {}
    config["catkin_lint"] = {}

    for config_file in args.config:
        try:
            with open(config_file, "r") as f:
                config.read_file(f)
        except IOError as err:
            sys.stderr.write("catkin_lint: cannot read '%s': %s\n" % (config_file, err))
            return 1
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "") or os.path.expanduser("~/.config")
    config.read([os.path.join(xdg_config_home, "catkin_lint"), os.path.expanduser("~/.catkin_lint")])

    if args.rosdistro:
        config["catkin_lint"]["rosdistro"] = args.rosdistro
    if args.package_path:
        config["catkin_lint"]["package_path"] = args.package_path
    if args.color:
        config["catkin_lint"]["color"] = args.color
    if args.disable_cache:
        config["catkin_lint"]["disable_cache"] = "yes"
    if args.offline is not None:
        config["catkin_lint"]["offline"] = "yes" if args.offline else "no"
    if args.strict is not None:
        config["catkin_lint"]["strict"] = "yes" if args.strict else "no"
    if args.severity_level is not None:
        config["catkin_lint"]["severity_level"] = str(args.severity_level)
    if args.resolve_env is not None:
        config["catkin_lint"]["resolve_env"] = "yes" if args.resolve_env else "no"

    # Override output
    config["catkin_lint"]["output"] = "catkin_lint_cmake"

    # Override severity settings from command line
    severity_overrides = get_severity_overrides_from_args(args, config.optionxform)
    for section in config.sections():
        if section != "catkin_lint":
            config[section].update(severity_overrides)

    nothing_to_do = False
    pkgs_to_check = []
    if "rosdistro" in config["catkin_lint"]:
        os.environ["ROS_DISTRO"] = config["catkin_lint"]["rosdistro"]

    quiet = config["catkin_lint"].getboolean("quiet", False)
    env = CatkinEnvironment(
        os_env=os.environ if config["catkin_lint"].getboolean("resolve_env", False) else None,
        use_rosdistro=not config["catkin_lint"].getboolean("offline", False),
        use_cache=not config["catkin_lint"].getboolean("disable_cache", False),
        quiet=quiet,
    )
    if not args.path and not args.pkg:
        if os.path.isfile("package.xml"):
            pkgs_to_check += env.add_path(getcwd())
        else:
            sys.stderr.write("catkin_lint: no path given and no package.xml in current directory\n")
            return os.EX_NOINPUT
    if "package_path" in config["catkin_lint"]:
        for path in config["catkin_lint"]["package_path"].split(os.pathsep):
            env.add_path(path)
    if "ROS_PACKAGE_PATH" in os.environ:
        for path in os.environ["ROS_PACKAGE_PATH"].split(os.pathsep):
            env.add_path(path)
    for path in args.path:
        if not os.path.isdir(path):
            sys.stderr.write("catkin_lint: not a directory: %s\n" % path)
            nothing_to_do = True
            continue
        pkgs_to_check += env.add_path(path)
    for name in args.pkg:
        try:
            path, manifest = env.find_local_pkg(name)
            pkgs_to_check.append((path, manifest))
        except KeyError:
            sys.stderr.write("catkin_lint: no such package: %s\n" % name)
            # nothing_to_do = True
    # pkgs_to_check = [
    #     (p, m) for p, m in pkgs_to_check if m.name not in args.skip_pkg and all((sp not in p) for sp in args.skip_path)
    # ]
    # if not pkgs_to_check:
    #     sys.stderr.write("catkin_lint: no packages to check\n")
    #     return int(nothing_to_do)
    if "ROS_DISTRO" not in os.environ:
        if env.knows_everything and not quiet:
            sys.stderr.write("catkin_lint: neither ROS_DISTRO environment variable nor --rosdistro option set\n")
            sys.stderr.write("catkin_lint: unknown dependencies will be ignored\n")
        env.knows_everything = False

    # color_choice = config["catkin_lint"].get("color", "auto").lower()
    # use_color.get(color_choice, Color.Auto)

    linter = CMakeLinter(env)
    import_checks = (args.check or ["all"]) + [
        check for check in config["catkin_lint"].get("extra_checks", "").split() if check
    ]
    for check in import_checks:
        try:
            add_linter_check(linter, check)
        except Exception as err:
            sys.stderr.write("catkin_lint: cannot import '%s': %s\n" % (check, str(err)))
            if args.debug:
                raise
            return 1
    path = ""
    manifest = ""
    try:
        linter.lint(path, manifest, config=config)
    except Exception as err:  # pragma: no cover
        sys.stderr.write("catkin_lint: cannot lint %s: %s\n" % (manifest.name, str(err)))
        if args.debug:
            raise

    dirname = os.path.dirname(args.output_file)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    return 0

    extras = {ERROR: 0, WARNING: 0, NOTICE: 0}
    problems = 0
    exit_code = 0
    diagnostic_label = {ERROR: "error", WARNING: "warning", NOTICE: "notice"}
    output.prolog(fd=sys.stdout)
    severity_level = config["catkin_lint"].getint("severity_level", 1)
    be_strict = config["catkin_lint"].getboolean("strict", False)
    if args.show_ignored:
        linter.messages += linter.ignored_messages
        linter.ignored_messages = []
    for msg in sorted(linter.messages):
        if severity_level < msg.level:
            extras[msg.level] += 1
            continue
        if be_strict:
            msg.level = ERROR
        if msg.level == ERROR:
            exit_code = 1
        output.message(msg, fd=sys.stdout)
        problems += 1
    output.epilog(fd=sys.stdout)
    if not quiet:
        sys.stderr.write("catkin_lint: checked %d packages and found %d problems\n" % (len(pkgs_to_check), problems))
        for level in [ERROR, WARNING, NOTICE]:
            if extras[level] > 0:
                sys.stderr.write(
                    "catkin_lint: option -W%d will show %d additional %ss\n"
                    % (level, extras[level], diagnostic_label[level])
                )
        if linter.ignored_messages:
            sys.stderr.write(
                "catkin_lint: %d messages have been ignored. Use --show-ignored to see them\n"
                % len(linter.ignored_messages)
            )
    return exit_code
