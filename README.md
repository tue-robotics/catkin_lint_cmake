# catkin_lint_cmake

Catkin macro to run `catkin_lint` as a catkin `run_test`.

The [`catkin_lint`](https://github.com/fkie/catkin_lint) library is wrapped to convert it's xml scheme to a JUnit scheme.

## Usage

Add `catkin_lint_cmake` to your `package.xml` as a test dependency.

```xml
<test_depend>catkin_lint_cmake</test_depend>
```

In your cmake file, find this package and call the macro to add the test.

```cmake
if(CATKIN_ENABLE_TESTING)
  find_package(catkin REQUIRED COMPONENTS catkin_lint_cmake)
  catkin_add_catkin_lint_test([ARGS])
endif()
```

By default, it runs in quiet mode with XML output. You can overrule the quiet mode, but not the XML output. No other default arguments have been overridden.
All arguments of the function are passed to `catkin_lint` ([`catkin_lint` command line arguments](https://fkie.github.io/catkin_lint/usage/)).
