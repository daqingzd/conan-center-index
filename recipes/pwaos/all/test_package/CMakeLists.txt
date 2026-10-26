cmake_minimum_required(VERSION 3.15)
project(test_package LANGUAGES C)

find_package(pwaos_sdk REQUIRED CONFIG)

add_executable(${PROJECT_NAME} test_package.c)
target_link_libraries(${PROJECT_NAME} PRIVATE pwaos::sdk)
if(WIN32)
    target_link_libraries(${PROJECT_NAME} PRIVATE winmm)
endif()

if(PWAOS_WITH_RUNTIME)
    target_compile_definitions(${PROJECT_NAME} PRIVATE PWAOS_WITH_RUNTIME=1)
endif()
