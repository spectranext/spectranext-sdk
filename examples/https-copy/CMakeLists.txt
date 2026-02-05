cmake_minimum_required(VERSION 3.16)

# Import Spectranext SDK - MUST be before project()
include($ENV{SPECTRANEXT_SDK_PATH}/cmake/spectranext_sdk_import.cmake)
spectranext_sdk_init()

project(https_copy C)

add_executable(https_copy main.c)

target_compile_options(https_copy PUBLIC -debug)
target_link_libraries(https_copy PUBLIC
    -llibspdos
    -llibspectranet.lib
)
target_link_options(https_copy PUBLIC -debug -create-app)

# Set boot BASIC program (optional)
spectranext_set_boot("
10 %tapein \"https_copy.tap\"
20 LOAD \"\"
")

# Add convenience targets (upload_bin, upload_tap, etc.)
spectranext_add_extra_outputs(https_copy)
