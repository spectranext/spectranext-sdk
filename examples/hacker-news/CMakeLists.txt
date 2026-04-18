cmake_minimum_required(VERSION 3.16)

# Import Spectranext SDK - MUST be before project()
include($ENV{SPECTRANEXT_SDK_PATH}/cmake/spectranext_sdk_import.cmake)
spectranext_sdk_init()

project(hacker_news C ASM)

find_package(Python3 REQUIRED COMPONENTS Interpreter)

add_subdirectory(zxgui)
zxgui_generate_tiles(${CMAKE_CURRENT_SOURCE_DIR}/img/tiles.png)
zxgui_generate_image(${CMAKE_CURRENT_SOURCE_DIR}/img/splash.png splash)
zxgui_generate_scenes(${CMAKE_CURRENT_SOURCE_DIR}/scenes zxgui_scenes)

add_executable(hacker_news
    main.c
    app.c
    news_backend.c
    ui.c
)

add_dependencies(hacker_news splash_image_gen)
add_dependencies(hacker_news zxgui_scenes)

target_include_directories(hacker_news PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_BINARY_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/zxgui/include
)

add_dependencies(hacker_news zxgui)

target_link_libraries(hacker_news PUBLIC
    -llibspdos -llibterm -llibspectranet_np.lib ${ZXGUI_LIBRARIES}
)

target_link_options(hacker_news PUBLIC
    -create-app
    -pragma-redirect:fputc_cons=spectranext_fputc_cons
)

spectranext_set_boot("
10 %tapein \"hacker_news.tap\"
20 LOAD \"\"
")

spectranext_add_extra_outputs(hacker_news)
