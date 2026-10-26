import os
import shutil
import subprocess

from conan import ConanFile
from conan.errors import ConanException, ConanInvalidConfiguration
from conan.tools.files import copy, download

required_conan_version = ">=2.0"


class PwaosSdkConan(ConanFile):
    name = "pwaos_sdk"
    description = (
        "pwaOS runtime client SDK: stable C ABI header, client import "
        "library (libpwaos_runtime_api), and the pwaos_server runtime bundle"
    )
    # LICENSE.md in the SDK tree is the standard MIT permission notice; the
    # upstream GitHub repository is likewise detected as MIT.
    license = "MIT"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://github.com/daqingzd/pwaos"
    topics = ("pwa", "runtime", "chromium", "webview", "pwaos", "browser")
    package_type = "shared-library"
    settings = "os", "arch", "compiler", "build_type"
    # The SDK ships prebuilt binaries downloaded from the official release
    # (same scheme as the openjdk recipe: build_policy missing + upload skip;
    # no compilation happens in this recipe).
    build_policy = "missing"
    upload_policy = "skip"

    options = {
        # Bundle the pwaos_server runtime/ directory (~110 MB). Consumers who
        # only compile against the ABI can disable it.
        "with_runtime": [True, False],
        # Ship the Node.js addon binary (pwaos_runtime.node).
        "with_node_addon": [True, False],
    }
    default_options = {
        "with_runtime": True,
        "with_node_addon": False,
    }

    def package_id(self):
        # Prebuilt binaries: identical artifact regardless of the consumer's
        # compiler or build type (openjdk recipe pattern).
        del self.info.settings.compiler
        del self.info.settings.build_type

    def validate(self):
        key = self._artifact_key
        if key not in self.conan_data["sources"][self.version]:
            raise ConanInvalidConfiguration(
                f"pwaos_sdk/{self.version} has no release artifact for "
                f"{self.settings.os}/{self.settings.arch}"
            )

    @property
    def _artifact_key(self):
        # conandata.yml keys: Linux_x86_64 today; extend when upstream
        # publishes windows/android SDK archives.
        return f"{self.settings.os}_{self.settings.arch}"

    def layout(self):
        # Non-buildable package: give local flows a sane layout.
        self.folders.source = "."
        self.folders.build = "build"
        self.folders.generators = "build/generators"

    def source(self):
        # Prebuilt binary recipe (openjdk pattern): no settings access here
        # (source() is settings-independent); the artifact is downloaded in
        # build() with the os/arch key.
        pass

    def build(self):
        # Download the official release artifact and unpack it. download()
        # accepts a list of URL strings: first URL wins, the rest are mirrors
        # for the failure case. Every entry carries the same mandatory sha256,
        # so the artifact is verified regardless of which mirror served it.
        key = self._artifact_key
        entry = self.conan_data["sources"][self.version][key]
        entries = entry if isinstance(entry, list) else [entry]
        urls = [e["url"] for e in entries]
        filename = os.path.join(self.build_folder, "sdk.7z")
        download(self, urls, filename, sha256=entries[0]["sha256"])
        # conan.tools.files.get()/unzip() cannot extract .7z, and the archive
        # uses the BCJ2 filter which py7zr does not support either, so
        # extraction is delegated to the p7zip binary.
        exe = shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
        if not exe:
            raise ConanException(
                "extracting the pwaos_sdk release archive requires the "
                "p7zip binary (apt-get install p7zip-full); py7zr cannot "
                "handle its BCJ2 filter"
            )
        subprocess.run([exe, "x", "-y", f"-o{self.build_folder}", filename],
                       check=True, capture_output=True)
        os.remove(filename)
        # The archive contains a single v0.2.a/ root (upstream tags carry the
        # v prefix); flatten it so package() can address include/, lib/,
        # runtime/ directly.
        root = os.path.join(self.build_folder, f"v{self.version}")
        if os.path.isdir(root):
            for entry_dir in os.listdir(root):
                os.rename(os.path.join(root, entry_dir),
                          os.path.join(self.build_folder, entry_dir))
            os.rmdir(root)

    def package(self):
        src = self.build_folder
        # C ABI header.
        copy(self, "*.h", src=os.path.join(src, "include"),
             dst=os.path.join(self.package_folder, "include"))
        # Client import library (Linux x64).
        copy(self, "libpwaos_runtime_api.so",
             src=os.path.join(src, "lib", "linux"),
             dst=os.path.join(self.package_folder, "lib"))
        # Docs + licensing metadata.
        for f in ("README.md", "RELEASE_NOTES.md", "LICENSE.md"):
            if os.path.isfile(os.path.join(src, f)):
                copy(self, f, src=src,
                     dst=os.path.join(self.package_folder, "licenses"))
        # Optional heavy artifacts.
        if self.options.with_runtime:
            copy(self, "*", src=os.path.join(src, "runtime"),
                 dst=os.path.join(self.package_folder, "runtime"))
        if self.options.with_node_addon:
            copy(self, "pwaos_runtime.node",
                 src=os.path.join(src, "lib", "linux"),
                 dst=os.path.join(self.package_folder, "lib"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "pwaos_sdk")
        self.cpp_info.set_property("cmake_target_name", "pwaos::sdk")
        self.cpp_info.set_property("pkg_config_name", "pwaos_runtime_api")
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libdirs = ["lib"]
        self.cpp_info.libs = ["pwaos_runtime_api"]
        # pwaos_server is spawned by the client library; tell consumers where
        # the bundled runtime lives (unset when with_runtime=False).
        if self.options.with_runtime:
            runtime_dir = os.path.join(self.package_folder, "runtime")
            self.cpp_info.set_property("pwaos:runtime_dir", runtime_dir)
            self.buildenv_info.define_path("PWAOS_RUNTIME_DIR", runtime_dir)
            self.runenv_info.define_path("PWAOS_RUNTIME_DIR", runtime_dir)
        else:
            # with_runtime=False: define_path would still bake the (missing)
            # package runtime path into the env; keep it unset instead.
            self.buildenv_info.define("PWAOS_RUNTIME_DIR", "")
            self.runenv_info.define("PWAOS_RUNTIME_DIR", "")
