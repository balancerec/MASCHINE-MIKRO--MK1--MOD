cmake_minimum_required(VERSION 3.20)
project(mk1_core VERSION 0.1.0 LANGUAGES C)
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
add_library(mk1_core STATIC core/src/mk1_core.c core/src/mk1_pad.c core/src/mk1_stream.c core/src/mk1_midi.c)
target_include_directories(mk1_core PUBLIC core/include)
add_library(mk1_core_shared SHARED core/src/mk1_core.c core/src/mk1_pad.c core/src/mk1_stream.c core/src/mk1_midi.c)
target_include_directories(mk1_core_shared PUBLIC core/include)
target_compile_definitions(mk1_core_shared PRIVATE MK1_CORE_SHARED)
foreach(target mk1_core mk1_core_shared)
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4 /WX)
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
include(CTest)
if(BUILD_TESTING)
  add_executable(mk1_core_test core/tests/test_core.c)
  target_link_libraries(mk1_core_test PRIVATE mk1_core)
  add_test(NAME core_contracts COMMAND mk1_core_test)
  add_executable(mk1_pad_test core/tests/test_pad.c)
  target_link_libraries(mk1_pad_test PRIVATE mk1_core)
  add_test(NAME pad_detector_contracts COMMAND mk1_pad_test)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME python_model_equivalence COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/core/tests/compare_models.py
    --library $<TARGET_FILE:mk1_core_shared>)
  add_test(NAME pad_detector_behavior COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/core/tests/test_pad_detector.py
    --library $<TARGET_FILE:mk1_core_shared>)
  add_test(NAME pad_stream_faults COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/core/tests/test_pad_stream.py
    --library $<TARGET_FILE:mk1_core_shared>)
  add_test(NAME midi_output_faults COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/core/tests/test_midi_output.py
    --library $<TARGET_FILE:mk1_core_shared>)
endif()
