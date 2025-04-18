############################################################################################################################
##
## SimCenterBackendApplications main cmake file
##
## Contents:
##   - Definition of build options
##   - Compiler variables ( c++ standard, warnings etc. )
##   - Finding of service libraries. Required: Intel MKL, Intel IPP
##     the include paths are set, and the libraries are added to variable SERVICE_LIBS
##   - Subdirectory cmake lists are called
##       -> createEDP/          Contains all modules for creating engineering demand parameters
##       -> createEVENT/        Contains all modules for creating natural hazard events
##       -> createSAM/          Contains all modules for creating structural analysis model
##       -> performDL/          Contains all modules for performing damage and loss assessment
##       -> performSIMULATION/  Contains all modules for performing structural simulation
##       -> performUQ/          Contains all modules for uncertainty quantification
##
############################################################################################################################


############################################################################################################################
##
## Project name, version, Custom CMake functions
##
############################################################################################################################

CMAKE_MINIMUM_REQUIRED(VERSION 3.1)
PROJECT(SimCenterBackendApplications)
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} ${PROJECT_SOURCE_DIR}/cmake)
set(CMAKE_VERBOSE_MAKEFILE ON)
set (CMAKE_OSX_ARCHITECTURES "x86_64" CACHE INTERNAL "" FORCE)
SET (CONAN_DISABLE_CHECK_COMPILER ON)
include(SimCenterFunctions)
include(CMakeParseArguments)

# set(CMAKE_CXX_STANDARD 11)
set(CMAKE_COLOR_MAKEFILE ON)
set(CMAKE_VERBOSE_MAKEFILE OF)

if (NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "Debug")
  set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -Wall -g")
endif (NOT CMAKE_BUILD_TYPE)

############################################################################################################################
##
## Definition of build options
##
############################################################################################################################
# Currently no tests to build, so turn this off
option(BUILD_TESTING "Enable testing for stochastic module" OFF)

# Every folder that is listed here can contain modules or tests
# this can be extended by applications to have own modules
list(APPEND SIMCENTER_MODULE_DIRS "${PROJECT_SOURCE_DIR}/modules")
list(REMOVE_DUPLICATES  SIMCENTER_MODULE_DIRS )
set(SIMCENTER_MODULE_DIRS  ${SIMCENTER_MODULE_DIRS} CACHE INTERNAL "All folders that contain modules or tests" )

# Bring in dependencies from Conan, only getting required libs for Intel MKL and IPP
include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup(TARGETS)

############################################################################################################################
##
## Subdirectories
##
############################################################################################################################

# All include paths are specified relative to ./ directory
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/modules)

# Sources
add_subdirectory(modules)
# Tests (CURRENT NO TESTS, SO COMMENTED OUT...)
# if(BUILD_TESTING)
#     add_subdirectory(tests)
# else()
#     add_subdirectory(tests EXCLUDE_FROM_ALL)
# endif()
