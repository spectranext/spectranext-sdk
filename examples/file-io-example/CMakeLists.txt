cmake_minimum_required(VERSION 3.16)

# Import Spectranext SDK - MUST be before project()
include($ENV{SPECTRANEXT_SDK_PATH}/cmake/spectranext_sdk_import.cmake)
spectranext_sdk_init()

project(file_io_example C)

add_executable(file_io_example main.c)

add_custom_target(upload_data_txt
    COMMAND ${SPX_PYTHON_PATH} ${SPX_SCRIPT} put ${CMAKE_CURRENT_SOURCE_DIR}/data.txt data.txt
    COMMENT "Upload data.txt"
)

target_compile_options(file_io_example PUBLIC -debug)
target_link_libraries(file_io_example PUBLIC 
    -llibspdos 
    -llibspectranet.lib 
)
target_link_options(file_io_example PUBLIC -debug -create-app)
add_dependencies(file_io_example upload_data_txt)

# Set boot BASIC program (optional)
# This creates a boot.zx file that will be uploaded before your program
spectranext_set_boot("
10 %tapein \"file_io_example.tap\"
20 LOAD \"\"
")

spectranext_add_extra_outputs(file_io_example)
