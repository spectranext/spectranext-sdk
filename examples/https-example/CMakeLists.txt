cmake_minimum_required(VERSION 3.16)

# Import Spectranext SDK - MUST be before project()
include($ENV{SPECTRANEXT_SDK_PATH}/cmake/spectranext_sdk_import.cmake)
spectranext_sdk_init()

project(https_example C)

add_executable(https_example main.c)

target_compile_options(https_example PUBLIC -debug)
target_link_libraries(https_example PUBLIC 
    -lndos 
    -llibspectranet.lib 
    -llibsocket.lib 
    -llibhttp.lib
)
target_link_options(https_example PUBLIC -debug -create-app)

# Set boot BASIC program (optional)
# This creates a boot.zx file that will be uploaded before your program
spectranext_set_boot("
10 PRINT \"Hello!\"
20 %tapein \"https_example.tap\"
30 LOAD \"\"
")

# Add convenience targets (upload_bin, upload_tap, etc.)
spectranext_add_extra_outputs(https_example)
