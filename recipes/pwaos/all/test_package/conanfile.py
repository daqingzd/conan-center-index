import os

from conan import ConanFile
from conan.tools.build import can_run
from conan.tools.cmake import CMake, cmake_layout


class PwaosSdkTestPackageConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    test_type = "explicit"
    generators = "CMakeToolchain", "CMakeDeps", "VirtualRunEnv"

    def requirements(self):
        # Explicit traits: pwaos_sdk ships the C ABI header + client library;
        # consumers compile and link against them. Without this, application-
        # typed packages get headers=False/libs=False defaults and CMakeDeps
        # would generate a target without include dirs or libraries.
        self.requires(self.tested_reference_str, headers=True, libs=True, run=True)

    def layout(self):
        cmake_layout(self)

    def generate(self):
        # Tell the test build whether the server runtime is bundled, so the
        # test only exercises the full runtime flow when it can actually run.
        with_runtime = self.dependencies["pwaos_sdk"].options.with_runtime
        self.buildenv_info.define("PWAOS_WITH_RUNTIME", "1" if with_runtime else "0")

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if can_run(self):
            # Link/ABI smoke: version macros + resultToString, no server
            # needed. The full hello runtime flow (spawn pwaos_server) runs
            # with PWAOS_TEST_RUNTIME=1; it needs a working server
            # environment (display etc.). Extra client args are forwarded by
            # the client lib to the spawned pwaos_server (e.g. --no-sandbox
            # on root/CI boxes) via PWAOS_TEST_ARGS.
            bin_path = os.path.join(self.cpp.build.bindirs[0], "test_package")
            extra = os.environ.get("PWAOS_TEST_ARGS", "")
            self.run((bin_path + " " + extra).strip(), env="conanrun")
