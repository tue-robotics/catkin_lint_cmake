import sys; sys.path.append("/usr/share/catkin-lint")  # noqa: E702

import configparser
import os

from catkin_lint.environment import CatkinEnvironment
from catkin_lint.linter import CMakeLinter, ERROR, WARNING, NOTICE
from catkin_lint.main import add_linter_check, get_severity_overrides_from_args, show_help_with_problems
from catkin_lint.output import Color, TextOutput, ExplainedTextOutput, JsonOutput, XmlOutput
from catkin_lint.util import getcwd

# noinspection PyUnresolvedReferences
import catkin_lint.checks


def run_linter(args):
    if args.clear_cache:
        from catkin_lint.environment import _clear_cache
        _clear_cache()
        return 0
    if args.help_problem is not None:
        return show_help_with_problems(args.help_problem)
    if args.list_check_ids:
        from catkin_lint.diagnostics import message_list
        ids = [k.lower() for k in message_list.keys()]
        ids.sort()
        sys.stdout.write("\n".join(ids))
        sys.stdout.write("\n")
        return 0
    if args.dump_cache:
        from catkin_lint.environment import _dump_cache
        _dump_cache()
        return 0
    config = configparser.ConfigParser(strict=True)
    config.optionxform = lambda option: option.lower().replace("-", "_")
    # Initialize configuration from command line arguments
    config["*"] = {}
    config["catkin_lint"] = {}
    if args.rosdistro:
        config["catkin_lint"]["rosdistro"] = args.rosdistro
    if args.package_path:
        config["catkin_lint"]["package_path"] = args.package_path
    if args.color:
        config["catkin_lint"]["color"] = args.color
    if args.output:
        config["catkin_lint"]["output"] = args.output
    if args.disable_cache:
        config["catkin_lint"]["disable_cache"] = "yes"
    if args.offline is not None:
        config["catkin_lint"]["offline"] = "yes" if args.offline else "no"
    if args.quiet is not None:
        config["catkin_lint"]["quiet"] = "yes" if args.quiet else "no"
    if args.strict is not None:
        config["catkin_lint"]["strict"] = "yes" if args.strict else "no"
    if args.severity_level is not None:
        config["catkin_lint"]["severity_level"] = str(args.severity_level)
    if args.resolve_env is not None:
        config["catkin_lint"]["resolve_env"] = "yes" if args.resolve_env else "no"

    for config_file in args.config:
        try:
            with open(config_file, "r") as f:
                config.read_file(f)
        except IOError as err:
            sys.stderr.write("catkin_lint: cannot read '%s': %s\n" % (config_file, err))
            return 1
    if "ROS_PACKAGE_PATH" in os.environ:
        config.read([os.path.join(d, ".catkin_lint") for d in os.environ["ROS_PACKAGE_PATH"].split(os.pathsep)])
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "") or os.path.expanduser("~/.config")
    config.read(
        [
            os.path.join(xdg_config_home, "catkin_lint"),
            os.path.expanduser("~/.catkin_lint")
        ]
    )

    # Override severity settings from command line
    severity_overrides = get_severity_overrides_from_args(args, config.optionxform)
    for section in config.sections():
        if section != "catkin_lint":
            config[section].update(severity_overrides)

    nothing_to_do = 0
    pkgs_to_check = []
    if "rosdistro" in config["catkin_lint"]:
        os.environ["ROS_DISTRO"] = config["catkin_lint"]["rosdistro"]
    quiet = config["catkin_lint"].getboolean("quiet", False)
    env = CatkinEnvironment(
        os_env=os.environ if config["catkin_lint"].getboolean("resolve_env", False) else None,
        use_rosdistro=not config["catkin_lint"].getboolean("offline", False),
        use_cache=not config["catkin_lint"].getboolean("disable_cache", False),
        quiet=quiet
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
            nothing_to_do = 1
            continue
        pkgs_to_check += env.add_path(path)
    for name in args.pkg:
        try:
            path, manifest = env.find_local_pkg(name)
            pkgs_to_check.append((path, manifest))
        except KeyError:
            sys.stderr.write("catkin_lint: no such package: %s\n" % name)
            nothing_to_do = 1
    pkgs_to_check = [(p, m) for p, m in pkgs_to_check if m.name not in args.skip_pkg and all((sp not in p) for sp in args.skip_path)]
    if not pkgs_to_check:
        sys.stderr.write("catkin_lint: no packages to check\n")
        return nothing_to_do
    if "ROS_DISTRO" not in os.environ:
        if env.knows_everything and not quiet:
            sys.stderr.write("catkin_lint: neither ROS_DISTRO environment variable nor --rosdistro option set\n")
            sys.stderr.write("catkin_lint: unknown dependencies will be ignored\n")
        env.knows_everything = False
    use_color = {"never": Color.Never, "always": Color.Always, "auto": Color.Auto}
    color_choice = config["catkin_lint"].get("color", "auto").lower()
    output_format = config["catkin_lint"].get("output", "text").lower()
    if output_format == "xml":
        output = XmlOutput()  # this is never colored
    elif output_format == "json":
        output = JsonOutput()  # also never colored
    elif output_format == "explain":
        output = ExplainedTextOutput(use_color.get(color_choice, Color.Auto))
    elif output_format == "text":
        output = TextOutput(use_color.get(color_choice, Color.Auto))
    else:
        sys.stderr.write("catkin_lint: unknown output format '%s'\n" % output_format)
        return 1
    linter = CMakeLinter(env)
    import_checks = (args.check or ["all"]) + [check for check in config["catkin_lint"].get("extra_checks", "").split() if check]
    for check in import_checks:
        try:
            add_linter_check(linter, check)
        except Exception as err:
            sys.stderr.write("catkin_lint: cannot import '%s': %s\n" % (check, str(err)))
            if args.debug:
                raise
            return 1
    for path, manifest in pkgs_to_check:
        try:
            linter.lint(path, manifest, config=config)
        except Exception as err:  # pragma: no cover
            sys.stderr.write("catkin_lint: cannot lint %s: %s\n" % (manifest.name, str(err)))
            if args.debug:
                raise
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
                sys.stderr.write("catkin_lint: option -W%d will show %d additional %ss\n" % (level, extras[level], diagnostic_label[level]))
        if linter.ignored_messages:
            sys.stderr.write("catkin_lint: %d messages have been ignored. Use --show-ignored to see them\n" % len(linter.ignored_messages))
    return exit_code
