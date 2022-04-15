if (_CATKIN_LINT_CMAKE_EXTRAS_INCLUDED_)
  return()
endif()
set(_CATKIN_LINT_CMAKE_EXTRAS_INCLUDED_ TRUE)

@[if INSTALLSPACE]@
# bin and template dir variables in installspace
set(CATKIN_LINT_CMAKE_SCRIPTS_DIR "${catkin_lint_cmake_DIR}/../../../@(CATKIN_PACKAGE_BIN_DESTINATION)")
@[else]@
# bin and template dir variables in develspace
set(CATKIN_LINT_CMAKE_SCRIPTS_DIR "@(CMAKE_CURRENT_SOURCE_DIR)/scripts")
@[end if]@

# Run catkin_lint for this package as a test.
#
# :param argn: linter options
# :type string
#
function(catkin_add_catkin_lint_test)
  _warn_if_skip_testing("catkin_add_catkin_lint_test")

  if(CATKIN_LINT_NOT_FOUND)
    message(STATUS "skipping catkin_lint in project '${PROJECT_NAME}'")
    return()
  endif()

  set(output_file_name "${CATKIN_TEST_RESULTS_DIR}/${PROJECT_NAME}/catkin_lint.xml")
  set(cmd "${CATKIN_LINT_CMAKE_SCRIPTS_DIR}/catkin_lint_wrapper ${ARGN} --xml ${CMAKE_SOURCE_DIR} --output-file ${output_file_name}")
  catkin_run_tests_target("catkin_lint" "lint" "catkin_lint.xml"
    WORKING_DIRECTORY ${PROJECT_SOURCE_DIR}
    COMMAND ${cmd})
endfunction()

find_package (Python COMPONENTS Interpreter)
execute_process(
    COMMAND ${Python_EXECUTABLE} -c "import catkin_lint; print(catkin_lint.__version__)"
    RESULT_VARIABLE CATKIN_LINT_NOT_FOUND
    OUTPUT_VARIABLE CATKIN_LINT_VERSION
    ERROR_QUIET
)
if(NOT CATKIN_LINT_NOT_FOUND)
  message(STATUS "Using catkin_lint: ${CATKIN_LINT_VERSION}")
else()
  message(STATUS "catkin_lint not found, linting can not be run (try installing package 'python3-catkin-lint')")
endif()
