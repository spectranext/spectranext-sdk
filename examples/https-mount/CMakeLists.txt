cmake_minimum_required(VERSION 3.16)

# Import Spectranext SDK - MUST be before project()
include($ENV{SPECTRANEXT_SDK_PATH}/cmake/spectranext_sdk_import.cmake)
spectranext_sdk_init()

project(https_mount C)

add_executable(https_mount main.c)

target_compile_options(https_mount PUBLIC -debug)
target_link_libraries(https_mount PUBLIC
    -llibspdos
    -llibspectranet.lib
)
target_link_options(https_mount PUBLIC -debug -create-app)

# Set boot BASIC program (optional)
spectranext_set_boot("
10 %tapein \"https_mount.tap\"
20 LOAD \"\"
")

# Add convenience targets (upload_bin, upload_tap, etc.)
spectranext_add_extra_outputs(https_mount)
