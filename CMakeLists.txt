cmake_minimum_required(VERSION 3.0.2)
project(catkin_lint_cmake)

find_package(catkin REQUIRED)

catkin_package(CFG_EXTRAS ${PROJECT_NAME}-extras.cmake)

install(PROGRAMS scripts/catkin_lint_wrapper
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY resources
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})

# Lint itself. This also serves as a smoke check of the cmake extras file.
# Please note that this complexity is due to self-checking.
# To lint your package, just use catkin_add_catkin_lint_test(ARGS)
if(CATKIN_ENABLE_TESTING)
  set(extra "cmake/${PROJECT_NAME}-extras.cmake")
  em_expand(${catkin_EXTRAS_DIR}/templates/cfg-extras.context.py.in
    ${CMAKE_CURRENT_BINARY_DIR}/${extra}.develspace.context.cmake.py
    ${CMAKE_CURRENT_SOURCE_DIR}/${extra}.em
    ${CMAKE_CURRENT_BINARY_DIR}/${extra})
  find_file(BINARY_EXTRA_FILE
    DOC "Expanded extra cmake file in the CMAKE_CURRENT_BINARY_DIR"
    NAMES ${extra}
    PATHS ${CMAKE_CURRENT_BINARY_DIR}
    NO_DEFAULT_PATH
    REQUIRED)
  include(${BINARY_EXTRA_FILE})

  catkin_add_catkin_lint_test(-W2)
endif()
