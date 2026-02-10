cmake_minimum_required(VERSION 3.16)

# Import Spectranext SDK - MUST be before project()
include($ENV{SPECTRANEXT_SDK_PATH}/cmake/spectranext_sdk_import.cmake)
spectranext_sdk_init()

project(spdos_file_list C)

add_executable(spdos_file_list main.c)

target_compile_options(spdos_file_list PUBLIC -debug)
target_link_libraries(spdos_file_list PUBLIC
    -llibspdos
    -llibspectranet.lib
)
target_link_options(spdos_file_list PUBLIC -debug -create-app)

# Set boot BASIC program (optional)
spectranext_set_boot("
10 %tapein \"spdos_file_list.tap\"
20 LOAD \"\"
")

# Add convenience targets (upload_bin, upload_tap, etc.)
spectranext_add_extra_outputs(spdos_file_list)
