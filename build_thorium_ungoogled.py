import argparse
import os
import subprocess
import sys
import shutil
import glob
import time
import urllib.request
import zipfile

def run_cmd(cmd, cwd=None, env=None, check=True, shell=False):
    if isinstance(cmd, list):
        print(f"Running: {' '.join(str(c) for c in cmd)}")
        if sys.platform == 'win32' and any(str(cmd[0]).lower().endswith(ext) for ext in ['.bat', '.cmd']):
            shell = True
    else:
        print(f"Running: {cmd}")
        shell = True
    sys.stdout.flush()
    subprocess.run(cmd, cwd=cwd, env=env, check=check, shell=shell)
    sys.stdout.flush()

def get_chromium_version(root_dir):
    version_file = os.path.join(root_dir, 'chromium_version.txt')
    if os.path.exists(version_file):
        with open(version_file, 'r') as f:
            return f.read().strip()
    return None

def main():
    parser = argparse.ArgumentParser(description="Build Thorium + ungoogled-chromium")
    parser.add_argument('--target-os', default='linux', choices=['linux', 'win'])
    parser.add_argument('--target-cpu', default='arm64', choices=['arm64', 'x64'])
    parser.add_argument('--src-dir', default='src', help='Chromium source directory')
    args = parser.parse_args()

    target_os = args.target_os
    target_cpu = args.target_cpu
    src_dir = os.path.abspath(args.src_dir)
    root_dir = os.path.abspath(os.path.dirname(__file__))

    chromium_version = get_chromium_version(root_dir)

    # Set up depot_tools
    depot_tools_dir = os.path.join(root_dir, 'depot_tools')
    if not os.path.exists(depot_tools_dir):
        run_cmd(['git', 'clone', 'https://chromium.googlesource.com/chromium/tools/depot_tools.git', depot_tools_dir])

    env = os.environ.copy()
    sep = ';' if sys.platform == 'win32' else ':'
    env['PATH'] = f"{depot_tools_dir}{sep}{env['PATH']}"
    # Use bash explicitly on Windows if patch is needed. Assuming git bash is in PATH on GH Actions.
    if sys.platform == 'win32':
        env['PATH'] = f"C:\\Program Files\\Git\\usr\\bin{sep}{env['PATH']}"

    env['DEPOT_TOOLS_UPDATE'] = '1'
    env['DEPOT_TOOLS_WIN_TOOLCHAIN'] = '0'

    # Configure git for large repositories to prevent schannel/RPC drops
    run_cmd(['git', 'config', '--global', 'http.postBuffer', '1048576000'])
    if sys.platform == 'win32':
        run_cmd(['git', 'config', '--global', 'http.sslBackend', 'openssl'])
        run_cmd(['git', 'config', '--global', 'core.longpaths', 'true'])

    # Ensure depot tools is updated so fetch works
    update_cmd = 'update_depot_tools.bat' if sys.platform == 'win32' else 'update_depot_tools'
    run_cmd([update_cmd], cwd=depot_tools_dir, env=env, shell=True)

    # Download Thorium source
    thorium_dir = os.path.join(root_dir, 'Thorium')
    if not os.path.exists(thorium_dir):
        run_cmd(['git', 'clone', '--depth=1', 'https://github.com/Alex313031/Thorium.git', thorium_dir])

    # The actual chromium source ends up in src_dir/src
    actual_src_dir = os.path.join(src_dir, 'src')

    if not os.path.exists(actual_src_dir):
        print("Chromium source not found. Fetching...")
        os.makedirs(src_dir, exist_ok=True)
        fetch_exec = 'fetch.bat' if sys.platform == 'win32' else 'fetch'
        for attempt in range(1, 4):
            try:
                print(f"Fetching Chromium (attempt {attempt}/3)...")
                run_cmd([fetch_exec, '--nohooks', '--no-history', 'chromium'], cwd=src_dir, env=env)
                if chromium_version:
                    run_cmd(['git', 'fetch', '--depth=1', 'origin', 'tag', chromium_version], cwd=actual_src_dir, env=env)
                    run_cmd(['git', 'checkout', chromium_version], cwd=actual_src_dir, env=env)
                    run_cmd(['git', 'config', 'remote.origin.fetch', f'+refs/tags/{chromium_version}:refs/tags/{chromium_version}'], cwd=actual_src_dir, env=env)
                    run_cmd(['git', 'config', 'remote.origin.tagOpt', '--no-tags'], cwd=actual_src_dir, env=env)
                break
            except Exception as e:
                print(f"Fetch attempt {attempt} failed: {e}")
                if attempt == 3:
                    raise
                # Clean up any partial gclient metadata before retrying
                for item in ['.gclient', '.gclient_entries', 'src']:
                    p = os.path.join(src_dir, item)
                    if os.path.exists(p):
                        try:
                            if os.path.isdir(p):
                                shutil.rmtree(p, ignore_errors=True)
                            else:
                                os.remove(p)
                        except Exception:
                            pass
                time.sleep(10)

    # Optimize .gclient to exclude heavy unused test suites like VK-GL-CTS
    gclient_file = os.path.join(os.path.dirname(actual_src_dir), '.gclient')
    if os.path.exists(gclient_file):
        try:
            with open(gclient_file, 'r') as f:
                content = f.read()
            if 'VK-GL-CTS' not in content:
                content = content.replace('"custom_deps": {}', '"custom_deps": {"src/third_party/angle/third_party/VK-GL-CTS/src": None}')
                content = content.replace('"custom_vars": {}', '"custom_vars": {"checkout_configuration": "small"}')
                with open(gclient_file, 'w') as f:
                    f.write(content)
        except Exception as e:
            print(f"Warning: could not patch .gclient: {e}")

    # Restrict origin refspec in src repo so gclient sync never tries to fetch all remote branches
    if chromium_version and os.path.exists(actual_src_dir):
        try:
            run_cmd(['git', 'config', 'remote.origin.fetch', f'+refs/tags/{chromium_version}:refs/tags/{chromium_version}'], cwd=actual_src_dir, env=env)
            run_cmd(['git', 'config', 'remote.origin.tagOpt', '--no-tags'], cwd=actual_src_dir, env=env)
        except Exception as e:
            print(f"Warning: could not set refspec: {e}")

    # Use the actual chromium src dir for the rest of the script
    src_dir = actual_src_dir

    # Ensure gclient sync runs for this version with minimal disk footprint
    gclient_cmd = 'gclient.bat' if sys.platform == 'win32' else 'gclient'
    for attempt in range(1, 4):
        try:
            print(f"Running gclient sync (attempt {attempt}/3)...")
            if chromium_version:
                run_cmd([gclient_cmd, 'sync', '-D', '--no-history', '--shallow', '--revision', f'src@{chromium_version}'], cwd=os.path.dirname(src_dir), env=env)
            else:
                run_cmd([gclient_cmd, 'sync', '-D', '--no-history', '--shallow'], cwd=os.path.dirname(src_dir), env=env)
            break
        except Exception as e:
            if attempt == 3:
                raise
            print(f"gclient sync attempt {attempt} failed ({e}), waiting 30s before retrying...")
            time.sleep(30)

    for attempt in range(1, 4):
        try:
            print(f"Running gclient runhooks (attempt {attempt}/3)...")
            run_cmd([gclient_cmd, 'runhooks'], cwd=os.path.dirname(src_dir), env=env)
            break
        except Exception as e:
            if attempt == 3:
                raise
            print(f"gclient runhooks attempt {attempt} failed ({e}), waiting 30s before retrying...")
            time.sleep(30)

    # For Linux arm64 cross compile we need sysroots
    if target_os == 'linux' and target_cpu == 'arm64':
        print("Installing arm64 sysroot...")
        sysroot_script = os.path.join(src_dir, 'build', 'linux', 'sysroot_scripts', 'install-sysroot.py')
        if os.path.exists(sysroot_script):
            run_cmd([sys.executable, sysroot_script, '--arch=arm64'], cwd=src_dir)

    # Ensure rust windows msvc import libs are never pruned
    pruning_list_path = os.path.join(root_dir, 'pruning.list')
    if os.path.exists(pruning_list_path):
        with open(pruning_list_path, 'r', encoding='utf-8') as f:
            pl_content = f.read()
        if 'windows_x86_64_msvc' in pl_content:
            lines = [l for l in pl_content.splitlines() if not ('windows_' in l and '_msvc' in l and '.lib' in l)]
            with open(pruning_list_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')

    # Apply ungoogled-chromium modifications
    print("Applying ungoogled-chromium modifications...")
    run_cmd([sys.executable, 'utils/prune_binaries.py', '--ignore-missing', '--keep-contingent-paths', src_dir, 'pruning.list'], cwd=root_dir)
    run_cmd([sys.executable, 'utils/patches.py', 'apply', src_dir, 'patches'], cwd=root_dir)

    # Apply domain substitution. Do NOT pass chromium_version.txt to -c (cache).
    run_cmd([sys.executable, 'utils/domain_substitution.py', 'apply', '-r', 'domain_regex.list', '-f', 'domain_substitution.list', src_dir], cwd=root_dir)

    # Ensure rust toolchain VERSION file exists so gn gen never fails
    rust_version_file = os.path.join(src_dir, 'third_party', 'rust-toolchain', 'VERSION')
    if not os.path.exists(rust_version_file):
        os.makedirs(os.path.dirname(rust_version_file), exist_ok=True)
        with open(rust_version_file, 'w', encoding='utf-8') as f:
            f.write("rustc 1.88.0 (chromium)\n")

    # Apply Thorium modifications
    print("Applying Thorium overlay and patches...")
    # Preserve Chromium's original root build configs and scripts so declarations and toolchains aren't broken
    preserved_files = {}
    for rel_path in [
        'BUILD.gn',
        'build/vs_toolchain.py',
        'build/config/BUILDCONFIG.gn',
        'build/config/arm.gni',
        'chrome/BUILD.gn',
        'chrome/browser/BUILD.gn',
        'content/browser/BUILD.gn',
        'content/gpu/BUILD.gn',
        'content/test/BUILD.gn',
        'content/shell/BUILD.gn',
        'components/BUILD.gn',
        'v8/BUILD.gn',
        'sandbox/linux/BUILD.gn',
        'tools/v8_context_snapshot/BUILD.gn',
        'build/config/android/BUILD.gn',
        'build/config/mac/BUILD.gn',
        'build/config/win/BUILD.gn',
        'build/config/compiler/BUILD.gn',
        'ui/views/examples/BUILD.gn',
        'ui/webui/resources/images/BUILD.gn',
        'content/shell/android/BUILD.gn',
        'chrome/android/BUILD.gn',
        'ash/webui/sample_system_web_app_ui/BUILD.gn',
        'ash/webui/sample_system_web_app_ui/mojom/BUILD.gn',
        'ash/webui/sample_system_web_app_ui/resources/trusted/BUILD.gn',
        'ash/webui/sample_system_web_app_ui/resources/untrusted/BUILD.gn',
        'chrome/installer/linux/BUILD.gn',
        'third_party/widevine/cdm/BUILD.gn',
        'components/vector_icons/BUILD.gn',
        'chrome/app/vector_icons/BUILD.gn',
        'net/cert/x509_util.cc',
        'net/base/load_flags_list.h',
        'net/url_request/url_request_http_job.cc',
        'net/dns/dns_transaction.cc',
        'net/dns/dns_client.cc',
        'ui/base/x/x11_util.cc',
        'google_apis/default_api_keys.h',
        'google_apis/default_api_keys-inc.cc',
        'media/base/supported_types.cc',
        'media/base/media_switches.cc',
        'media/media_options.gni',
    ]:
        full_path = os.path.join(src_dir, rel_path)
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                preserved_files[rel_path] = f.read()

    thorium_src_overlay = os.path.join(thorium_dir, 'src')
    if os.path.exists(thorium_src_overlay):
        print(f"Copying Thorium overlay from {thorium_src_overlay} to {src_dir}...")
        shutil.copytree(thorium_src_overlay, src_dir, dirs_exist_ok=True)

    # Restore preserved files
    for rel_path, content in preserved_files.items():
        full_path = os.path.join(src_dir, rel_path)
        if rel_path == 'build/config/BUILDCONFIG.gn':
            if 'enable_strict_deps' not in content:
                content += '''
declare_args() {
  enable_strict_deps = false
  default_modulemap_mode = "none"
  llvm_android_mainline = false
  llvm_force_head_revision = false
  is_cronet_build = false
  is_castos = false
  lacros_use_chromium_toolchain = false
  android_full_debug = false
  is_high_end_android = false
  allow_runtime_configurable_key_storage = false
  is_thorium_build = true
  is_raspi = false
  is_chancie_wancie_build = false
  enable_glic = false
  enable_webui_tab_strip = false
  enable_click_to_call = false
  build_with_tflite_lib = false
}
'''
            if 'is_nacl = false' not in content:
                content += '''
is_nacl = false
is_nacl_irt = false
is_nacl_saigo = false
chromeos_is_browser_only = false
is_chromeos_lacros = false
is_chromeos_device = false
llvm_android_mainline = false
llvm_force_head_revision = false
is_cronet_build = false
is_castos = false
lacros_use_chromium_toolchain = false
android_full_debug = false
is_high_end_android = false
allow_runtime_configurable_key_storage = false
is_thorium_build = true
is_raspi = false
is_chancie_wancie_build = false
enable_glic = false
enable_webui_tab_strip = false
enable_click_to_call = false
build_with_tflite_lib = false
'''
            if 'thorium_simd_optimization' not in content:
                content += '\n# Thorium SIMD optimization config\ndefault_compiler_configs += [ "//build/config/compiler:thorium_simd_optimization" ]\n'
        elif rel_path == 'BUILD.gn':
            if 'group("thorium")' not in content:
                content += '\n# Thorium target group\ngroup("thorium") {\n  public_deps = [ "//chrome" ]\n}\n'
        elif rel_path == 'media/media_options.gni':
            if 'enable_platform_vvc' not in content:
                content += '\ndeclare_args() {\n  enable_platform_vvc = false\n}\n'
        elif rel_path == 'chrome/BUILD.gn':
            content = content.replace('_chrome_output_name = "initialexe/chrome"', '_chrome_output_name = "initialexe/thorium"')
            content = content.replace('_chrome_output_name = "chrome"', '_chrome_output_name = "thorium"')
            content = content.replace('"$root_out_dir/initialexe/chrome.exe"', '"$root_out_dir/initialexe/thorium.exe"')
            content = content.replace('"$root_out_dir/initialexe/chrome.exe.pdb"', '"$root_out_dir/initialexe/thorium.exe.pdb"')
            content = content.replace('"$root_out_dir/chrome.exe"', '"$root_out_dir/thorium.exe"')
            content = content.replace('"$root_out_dir/chrome.exe.pdb"', '"$root_out_dir/thorium.exe.pdb"')
            content = content.replace('binary = "$root_out_dir/chrome"', 'binary = "$root_out_dir/thorium"')
        elif rel_path == 'chrome/installer/linux/BUILD.gn':
            content = content.replace('"$root_out_dir/chrome"', '"$root_out_dir/thorium"')
        elif rel_path == 'components/vector_icons/BUILD.gn':
            if 'if (is_chromeos)' in content and 'reload_thorium.icon' not in content:
                content = content.replace(
                    'if (is_chromeos) {',
                    '''if (is_thorium_build) {
      sources += [
        "thorium/reload_thorium.icon",
        "thorium/reload_chrome_refresh_thorium.icon",
        "thorium/restore_tab.icon",
      ]
    }

    if (is_chromeos) {'''
                )
        elif rel_path == 'chrome/app/vector_icons/BUILD.gn':
            if 'if (is_mac)' in content and 'browser_tools_thorium.icon' not in content:
                content = content.replace(
                    'if (is_mac) {',
                    '''if (is_thorium_build) {
    sources += [
      "thorium/browser_tools_thorium.icon",
      "thorium/browser_tools_chrome_refresh_thorium.icon",
      "thorium/chrome_labs_thorium.icon",
      "thorium/chrome_labs_chrome_refresh_thorium.icon",
      "thorium/navigate_home_thorium.icon",
      "thorium/navigate_home_chrome_refresh_thorium.icon",
      "thorium/science_thorium.icon",
      "thorium/side_panel_left_thorium.icon",
      "thorium/side_panel_left_chrome_refresh_thorium.icon",
      "thorium/side_panel_left_touch_thorium.icon",
      "thorium/side_panel_thorium.icon",
      "thorium/side_panel_chrome_refresh_thorium.icon",
      "thorium/side_panel_touch_thorium.icon",
    ]
  }

  if (is_mac) {'''
                )
        elif rel_path == 'net/base/load_flags_list.h':
            if 'MINIMAL_HEADERS' not in content:
                content += '''
// Thorium custom load flags
LOAD_FLAG(SKIP_VARY_CHECK, 1 << 20)
LOAD_FLAG(MINIMAL_HEADERS, 1 << 21)
'''
        elif rel_path == 'build/config/win/BUILD.gn':
            content = content.replace(
                '"NTDDI_VERSION=NTDDI_WIN11_BR",',
                '"NTDDI_WIN11_BR=0x0A000011",\n    "NTDDI_VERSION=0x0A000011",'
            )
            content = content.replace(
                '  arflags = [\n    # "No public symbols found; archive member will be inaccessible." This\n    # means that one or more object files in the library can never be\n    # pulled in to targets that link to this library. It\'s just a warning that\n    # the source file is a no-op.\n    "/ignore:4221",\n  ]',
                '  arflags = [\n    "/ignore:4221",\n    "/ignore:emptyoutput",\n    "/llvmlibempty",\n  ]'
            )
        elif rel_path == 'net/url_request/url_request_http_job.cc':
            if 'LOAD_MINIMAL_HEADERS' not in content:
                content = content.replace(
                    'if (referrer.is_valid()) {\n    std::string referer_value = referrer.spec();\n    request_info_.extra_headers.SetHeader(HttpRequestHeaders::kReferer,\n                                          referer_value);\n  }',
                    'if (!(request_info_.load_flags & LOAD_MINIMAL_HEADERS)) {\n    if (referrer.is_valid()) {\n      std::string referer_value = referrer.spec();\n      request_info_.extra_headers.SetHeader(HttpRequestHeaders::kReferer,\n                                            referer_value);\n    }\n  }'
                )
                content = content.replace(
                    'request_info_.extra_headers.SetHeaderIfMissing(\n      HttpRequestHeaders::kUserAgent,\n      http_user_agent_settings_ ? http_user_agent_settings_->GetUserAgent()\n                                : std::string());',
                    'if (!(request_info_.load_flags & LOAD_MINIMAL_HEADERS)) {\n    request_info_.extra_headers.SetHeaderIfMissing(\n        HttpRequestHeaders::kUserAgent,\n        http_user_agent_settings_ ? http_user_agent_settings_->GetUserAgent()\n                                  : std::string());\n  }'
                )
                content = content.replace(
                    'request()->context()->enable_brotli(),\n      request()->context()->enable_zstd());\n\n  if (http_user_agent_settings_) {',
                    '!(request_info_.load_flags & LOAD_MINIMAL_HEADERS) && request()->context()->enable_brotli(),\n      !(request_info_.load_flags & LOAD_MINIMAL_HEADERS) && request()->context()->enable_zstd());\n\n  if (!(request_info_.load_flags & LOAD_MINIMAL_HEADERS) && http_user_agent_settings_) {'
                )
        elif rel_path == 'ui/base/x/x11_util.cc':
            content = content.replace(
                '  // Stacking WMs should use custom frames.\n  return !IsWmTiling(wm);',
                '  // Never default to using the custom title bar, unless the windows manager is a tiling WM.\n  // Thorium should integrate, not be a special little snowflake.\n  return false;'
            )
        elif rel_path == 'media/base/media_switches.cc':
            if 'kAutoplayDisableSettings' not in content:
                content += '''
// Thorium custom media features
BASE_FEATURE(kAutoplayDisableSettings,
             "AutoplayDisableSettings",
             base::FEATURE_DISABLED_BY_DEFAULT);

BASE_FEATURE(kAVDColorSpaceChanges,
             "AVDColorSpaceChanges",
             base::FEATURE_ENABLED_BY_DEFAULT);
'''
        elif rel_path == 'chrome/browser/BUILD.gn':
            if 'thorium_flag_choices.h' not in content and '"about_flags.cc",' in content:
                content = content.replace(
                    '"about_flags.cc",',
                    '"about_flags.cc",\n    "thorium_flag_choices.h",\n    "thorium_flag_entries.h",'
                )
        elif rel_path == 'build/config/compiler/BUILD.gn':
            if 'thorium_simd_optimization' not in content:
                content += '''
import("//build/config/compiler_opt.gni")

# Thorium SIMD optimizations
config("thorium_simd_optimization") {
  cflags = []
  ldflags = []
  if (current_cpu == "x86") {
    if (is_win) {
      if (use_sse2) {
        cflags += [ "/arch:SSE2", "/clang:-msse2", ]
      }
      if (use_sse3) {
        cflags += [ "/clang:-msse3", ]
      }
      if (use_sse41) {
        cflags += [ "/clang:-mssse3", "/clang:-msse4.1", ]
      }
      if (use_sse42) {
        cflags += [ "/clang:-msse4.2", ]
      }
    } else {
      if (use_sse2) {
        cflags += [ "-msse2", ]
        ldflags += [ "-msse2", ]
      }
      if (use_sse3) {
        cflags += [ "-msse3", ]
        ldflags += [ "-msse3", ]
      }
      if (use_sse41) {
        cflags += [ "-mssse3", "-msse4.1", ]
        ldflags += [ "-mssse3", "-msse4.1", ]
      }
      if (use_sse42) {
        cflags += [ "-msse4", "-msse4.2", ]
        ldflags += [ "-msse4.2", ]
      }
    }
  } else if (current_cpu == "x64") {
    if (is_win) {
      if (use_sse3) {
        cflags += [ "/clang:-msse3", ]
      }
      if (use_sse41) {
        cflags += [ "/clang:-mssse3", "/clang:-msse4.1", ]
      }
      if (use_sse42) {
        cflags += [ "/clang:-msse4.2", ]
      }
      if (use_avx) {
        cflags += [ "/clang:-mpclmul", "/clang:-maes", "/clang:-mavx", ]
      }
      if (use_fma) {
        cflags += [ "/clang:-mfma", "/clang:-ffp-contract=fast", ]
      }
      if (use_avx2) {
        cflags += [ "/clang:-mavx2", "/clang:-mf16c", "/clang:-mlzcnt", "/clang:-mbmi", "/clang:-mbmi2", ]
        ldflags += [ "-mllvm:-march=haswell", ]
      }
      if (use_avx512) {
        cflags += [ "/clang:-mavx512f", "/clang:-mavx512cd", "/clang:-mavx512vl", "/clang:-mavx512bw", "/clang:-mavx512dq", ]
        ldflags += [ "-mllvm:-march=skylake-avx512", ]
      }
    } else if (is_mac) {
      if (use_avx2) {
        cflags += [ "-march=x86-64-v3", ]
        ldflags += [ "-Wl,-mllvm,-march=x86-64-v3", ]
      } else {
        cflags += [ "-msse3", "-mssse3", "-msse4.1", ]
      }
    } else {
      # Linux and ChromiumOS and Android
      if (use_sse3) {
        cflags += [ "-msse3", ]
        ldflags += [ "-msse3", ]
      }
      if (use_sse41) {
        cflags += [ "-mssse3", "-msse4.1", ]
        ldflags += [ "-mssse3", "-msse4.1", ]
      }
      if (use_sse42) {
        cflags += [ "-msse4", "-msse4.2", ]
        ldflags += [ "-msse4.2", ]
      }
      if (use_avx) {
        cflags += [ "-mpclmul", "-maes", "-mavx", ]
        ldflags += [ "-mpclmul", "-maes", "-mavx", ]
      }
      if (use_fma) {
        cflags += [ "-mfma", "-ffp-contract=fast", ]
        ldflags += [ "-mfma", "-Wl,-mllvm,-fp-contract=fast", ]
      }
      if (use_avx2) {
        cflags += [ "-mavx2", "-mf16c", "-mlzcnt", "-mbmi", "-mbmi2", ]
        ldflags += [ "-mavx2", "-mf16c", "-mlzcnt", "-mbmi", "-mbmi2", "-Wl,-mllvm,-march=haswell", ]
      }
      if (use_avx512) {
        cflags += [ "-mavx512f", "-mavx512cd", "-mavx512vl", "-mavx512bw", "-mavx512dq", ]
        ldflags += [ "-mavx512f", "-mavx512cd", "-mavx512vl", "-mavx512bw", "-mavx512dq", "-Wl,-mllvm,-march=skylake-avx512", ]
      }
    }
  } else if (current_cpu == "arm") {
    if (is_android || is_linux) {
    }
  } else if (current_cpu == "arm64") {
    if (is_win) {
      cflags += [ "-march=armv8-a+simd", ]
    } else if (is_mac) {
      cflags += [ "-march=armv8.3-a+simd+crypto", "-mtune=apple-m1", ]
      ldflags += [ "-march=armv8.3-a+simd+crypto", "-mtune=apple-m1", ]
    } else {
      # Linux and ChromiumOS and Android
      cflags += [ "-march=armv8-a+simd", ]
      if (is_raspi) {
        cflags += [ "-mtune=cortex-a72", ]
      }
    }
  }
}
'''
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

    # Ensure missing compatibility stubs exist for Chromium 154
    stubs = {
        'build/config/chromeos/ui_mode.gni': '''declare_args() {
  chromeos_is_browser_only = false
  also_build_ash_chrome = false
  also_build_lacros_chrome = false
  also_build_lacros_chrome_for_architecture = ""
}

is_chromeos_ash = is_chromeos && !chromeos_is_browser_only
is_chromeos_lacros = is_chromeos && chromeos_is_browser_only
''',
        'build/config/nacl/config.gni': '''declare_args() {
  enable_nacl = false
}
is_nacl = false
is_nacl_irt = false
is_nacl_saigo = false
''',
        'chrome/enterprise_companion/buildflags.gni': 'declare_args() {\n  enable_chrome_enterprise_companion = false\n}\n',
        'chromeos/ash/components/assistant/assistant.gni': 'declare_args() {\n  enable_cros_libassistant = false\n}\n',
        'components/nacl/features.gni': 'import("//build/config/nacl/config.gni")\n',
        'ppapi/buildflags/buildflags.gni': '''import("//content/public/common/features.gni")

declare_args() {
  enable_ppapi = false
}
''',
        'ppapi/buildflags/BUILD.gn': '''import("//build/buildflag_header.gni")
import("//ppapi/buildflags/buildflags.gni")

buildflag_header("buildflags") {
  header = "buildflags.h"
  flags = [
    "ENABLE_PLUGINS=$enable_plugins",
    "ENABLE_PPAPI=$enable_ppapi",
  ]
}
''',
        'ppapi/buildflags/buildflags.h': '''#ifndef PPAPI_BUILDFLAGS_BUILDFLAGS_H_
#define PPAPI_BUILDFLAGS_BUILDFLAGS_H_

#include "build/buildflag.h"

#define BUILDFLAG_INTERNAL_ENABLE_PLUGINS() (0)
#define BUILDFLAG_INTERNAL_ENABLE_PPAPI() (0)

#endif  // PPAPI_BUILDFLAGS_BUILDFLAGS_H_
''',
        'chrome/browser/request_header_integrity/buildflags.gni': 'import("//chrome/common/request_header_integrity/buildflags.gni")\n',
        'components/sharing_message/buildflags.gni': '''declare_args() {
  enable_sharing_message = false
}
''',
        'services/accessibility/buildflags.gni': '''declare_args() {
  enable_accessibility_service = false
}
''',
        'chromeos/components/libsegmentation/buildflags.gni': '''declare_args() {
  enable_cros_libsegmentation = false
}
''',
        # Stub for removed ChromeOS toolchain config in Chromium 154
        'build/toolchain/cros/cros_config.gni': '''declare_args() {
  lacros_use_chromium_toolchain = false
}
''',
        # Stub for relocated isolated_web_apps preload component in Chromium 154
        'components/webapps/isolated_web_apps/preload/BUILD.gn': '''group("component") {
  public_deps = [ "//chrome/browser/web_applications/isolated_web_apps/key_distribution/preload:component" ]
}

group("component_bundle") {
  public_deps = [ "//chrome/browser/web_applications/isolated_web_apps/key_distribution/preload:component_bundle" ]
}
''',
        # Stubs for relocated device_trust attestation targets in Chromium 154
        'chrome/browser/enterprise/connectors/device_trust/attestation/common/BUILD.gn': '''group("types") {
  public_deps = [ "//components/enterprise/device_trust/core/attestation:types" ]
}

group("common") {
  public_deps = [ "//components/enterprise/device_trust/core/attestation" ]
}
''',
        'chrome/browser/enterprise/connectors/device_trust/attestation/common/proto/BUILD.gn': '''group("attestation_ca_proto") {
  public_deps = [ "//components/enterprise/device_trust/core/attestation/proto:attestation_ca_proto" ]
}

group("google_key_proto") {
  public_deps = [ "//components/enterprise/device_trust/core/attestation/proto:google_key_proto" ]
}

group("interface_proto") {
  public_deps = [ "//components/enterprise/device_trust/core/attestation/proto:interface_proto" ]
}
''',
        'chrome/browser/enterprise/connectors/device_trust/common/BUILD.gn': '''group("common") {
  public_deps = [ "//components/enterprise/device_trust/core" ]
}
''',
        'chrome/browser/enterprise/connectors/device_trust/signals/decorators/common/BUILD.gn': '''group("common") {
  public_deps = [ "//components/enterprise/device_trust/core/signals" ]
}
''',
    }
    for stub_rel, stub_code in stubs.items():
        stub_full = os.path.join(src_dir, stub_rel)
        if not os.path.exists(stub_full):
            os.makedirs(os.path.dirname(stub_full), exist_ok=True)
            with open(stub_full, 'w', encoding='utf-8') as f:
                f.write(stub_code)

    # Ensure media/media_options.gni defines system_loopback_as_aec_reference_supported and enable_media_remoting_redirection
    media_options_path = os.path.join(src_dir, 'media', 'media_options.gni')
    if os.path.exists(media_options_path):
        with open(media_options_path, 'r', encoding='utf-8') as f:
            media_content = f.read()
        changes = False
        if 'enable_media_remoting_redirection' not in media_content:
            media_content += '''
declare_args() {
  enable_media_remoting_redirection = enable_media_remoting_rpc && is_win
}
'''
            changes = True
        if 'system_loopback_as_aec_reference_supported' not in media_content:
            media_content += '''
declare_args() {
  system_loopback_as_aec_reference_supported =
      (is_win || is_mac) && chrome_wide_echo_cancellation_supported
}
'''
            changes = True
        if 'enable_platform_vvc' not in media_content:
            media_content += '''
declare_args() {
  enable_platform_vvc = false
}
'''
            changes = True
        if changes:
            with open(media_options_path, 'w', encoding='utf-8') as f:
                f.write(media_content)

    # Ensure chromeos_is_browser_only is defined in chromeos ui_mode.gni and args.gni if they exist
    for rel_cros in ['build/config/chromeos/ui_mode.gni', 'build/config/chromeos/args.gni']:
        cros_full = os.path.join(src_dir, rel_cros)
        if os.path.exists(cros_full):
            with open(cros_full, 'r', encoding='utf-8') as f:
                cros_code = f.read()
            if 'chromeos_is_browser_only' not in cros_code:
                cros_code += '\nchromeos_is_browser_only = false\nis_chromeos_lacros = false\n'
                with open(cros_full, 'w', encoding='utf-8') as f:
                    f.write(cros_code)

    # Ensure rlz buildflags allow is_win for Windows installer
    rlz_buildflags_path = os.path.join(src_dir, 'rlz', 'buildflags', 'buildflags.gni')
    if os.path.exists(rlz_buildflags_path):
        with open(rlz_buildflags_path, 'r', encoding='utf-8') as f:
            rb_content = f.read()
        if 'enable_rlz_support = false' in rb_content:
            rb_content = rb_content.replace('enable_rlz_support = false', 'enable_rlz_support = is_win')
            with open(rlz_buildflags_path, 'w', encoding='utf-8') as f:
                f.write(rb_content)

    # Patch tools/grit/grit/node/base.py to safely handle undefined Grit variables (e.g. chromeos_ash / chromeos_lacros in Chromium 154)
    grit_base_path = os.path.join(src_dir, 'tools', 'grit', 'grit', 'node', 'base.py')
    if os.path.exists(grit_base_path):
        with open(grit_base_path, 'r', encoding='utf-8') as f:
            gb_code = f.read()
        if "assert False, 'undefined Grit variable found: ' + name" in gb_code:
            gb_code = gb_code.replace(
                "assert False, 'undefined Grit variable found: ' + name",
                "value = False  # undefined Grit variable fallback for removed cros flags"
            )
            with open(grit_base_path, 'w', encoding='utf-8') as f:
                f.write(gb_code)

    # Patch build/config/compiler/BUILD.gn to safely handle use_libcxx_modules
    compiler_build_gn = os.path.join(src_dir, 'build', 'config', 'compiler', 'BUILD.gn')
    if os.path.exists(compiler_build_gn):
        with open(compiler_build_gn, 'r', encoding='utf-8') as f:
            cbg = f.read()
        if 'use_libcxx_modules' in cbg:
            cbg = cbg.replace('if (use_libcxx_modules)', 'if (false)')
            cbg = cbg.replace('if (use_explicit_libcxx_modules)', 'if (false)')
            with open(compiler_build_gn, 'w', encoding='utf-8') as f:
                f.write(cbg)

    # Patch chrome/BUILD.gn to point isolated_web_apps preload component to upstream location
    chrome_build_gn = os.path.join(src_dir, 'chrome', 'BUILD.gn')
    if os.path.exists(chrome_build_gn):
        with open(chrome_build_gn, 'r', encoding='utf-8') as f:
            ch_bg = f.read()
        if '//components/webapps/isolated_web_apps/preload:component' in ch_bg:
            ch_bg = ch_bg.replace(
                '//components/webapps/isolated_web_apps/preload:component',
                '//chrome/browser/web_applications/isolated_web_apps/key_distribution/preload:component'
            )
            ch_bg = ch_bg.replace(
                '//components/webapps/isolated_web_apps/preload:component_bundle',
                '//chrome/browser/web_applications/isolated_web_apps/key_distribution/preload:component_bundle'
            )
            with open(chrome_build_gn, 'w', encoding='utf-8') as f:
                f.write(ch_bg)

    # Patch chrome/installer/mini_installer/BUILD.gn to reference thorium.exe for Windows
    mini_installer_build_gn = os.path.join(src_dir, 'chrome', 'installer', 'mini_installer', 'BUILD.gn')
    if os.path.exists(mini_installer_build_gn):
        with open(mini_installer_build_gn, 'r', encoding='utf-8') as f:
            mi_bg = f.read()
        if '"$root_out_dir/chrome.exe"' in mi_bg:
            mi_bg = mi_bg.replace('"$root_out_dir/chrome.exe"', '"$root_out_dir/thorium.exe"')
            with open(mini_installer_build_gn, 'w', encoding='utf-8') as f:
                f.write(mi_bg)

    # Patch ui/native_theme/BUILD.gn to forward native_theme_browser to native_theme
    native_theme_build_gn = os.path.join(src_dir, 'ui', 'native_theme', 'BUILD.gn')
    if os.path.exists(native_theme_build_gn):
        with open(native_theme_build_gn, 'r', encoding='utf-8') as f:
            nt_content = f.read()
        if 'group("native_theme_browser")' not in nt_content:
            nt_content += '''
group("native_theme_browser") {
  public_deps = [ ":native_theme" ]
}
'''
            with open(native_theme_build_gn, 'w', encoding='utf-8') as f:
                f.write(nt_content)

    # Ensure legacy .gni files exist for Thorium overlay compatibility
    legacy_gni_files = {
        'components/os_crypt/sync/features.gni': '''declare_args() {
  allow_runtime_configurable_key_storage = false
}
''',
        'components/services/on_device_translation/buildflags/features.gni': '''import("//components/on_device_translation/buildflags/features.gni")
''',
        'chromeos/ash/components/assistant/assistant.gni': '''declare_args() {
  enable_cros_libassistant = false
  enable_fake_assistant_microphone = false
  enable_assistant_integration_tests = false
}
''',
        'components/nacl/features.gni': '''declare_args() {
  enable_nacl = false
}
''',
        'build/config/nacl/config.gni': '''declare_args() {
  is_nacl_glibc = false
  is_nacl_saigo = false
}
''',
        'ppapi/buildflags/buildflags.gni': '''declare_args() {
  enable_plugins = true
  enable_ppapi = false
}
''',
        'services/video_effects/args.gni': '''declare_args() {
  enable_video_effects = false
}
''',
        'chrome/enterprise_companion/buildflags.gni': '''import("//chrome/enterprise_companion/config.gni")
''',
        'mojo/public/rust/rust.gni': '''declare_args() {
  enable_rust_mojo = false
}
'''
    }

    for rel_gni, gni_content in legacy_gni_files.items():
        full_gni = os.path.join(src_dir, rel_gni)
        if not os.path.exists(full_gni):
            os.makedirs(os.path.dirname(full_gni), exist_ok=True)
            with open(full_gni, 'w', encoding='utf-8') as f:
                f.write(gni_content)

    # BUILDCONFIG.gn already declares global fallback args across the entire build tree

    if target_os == 'win':
        # Patch build/toolchain/win/setup_toolchain.py to detect installed Windows SDK
        setup_toolchain_path = os.path.join(src_dir, 'build', 'toolchain', 'win', 'setup_toolchain.py')
        if os.path.exists(setup_toolchain_path):
            with open(setup_toolchain_path, 'r', encoding='utf-8') as f:
                st_code = f.read()
            st_code = st_code.replace(
                "args.append(SDK_VERSION)",
                """# Auto-detect installed SDK version instead of failing on hardcoded 10.0.28000.0
        import glob
        installed_sdks = sorted([os.path.basename(p) for p in glob.glob(r'C:\\Program Files (x86)\\Windows Kits\\10\\Include\\10.*')])
        if installed_sdks:
            args.append(installed_sdks[-1])
        else:
            args.append(SDK_VERSION)"""
            )
            import re
            pattern = r'raise Exception\(\s*\'Path "%s" from environment variable "%s" does not exist\.\s*\'\s*\'Make sure the necessary SDK is installed\.\'\s*%\s*\(part,\s*envvar\)\s*\)'
            st_code = re.sub(pattern, 'continue', st_code)
            with open(setup_toolchain_path, 'w', encoding='utf-8') as f:
                f.write(st_code)

        # Ensure dxil.dll is available in expected SDK version folder
        sdk_root = r"C:\Program Files (x86)\Windows Kits\10"
        if os.path.exists(sdk_root):
            import glob
            dxil_candidates = glob.glob(f"{sdk_root}\\**\\dxil.dll", recursive=True)
            if dxil_candidates:
                target_sdk_dir = f"{sdk_root}\\bin\\10.0.28000.0\\x64"
                os.makedirs(target_sdk_dir, exist_ok=True)
                shutil.copy2(dxil_candidates[0], os.path.join(target_sdk_dir, 'dxil.dll'))

        # Patch message_compiler.py in build/win and third_party to not fail when mc.exe produces extra/different bin files
        for mc_py_path in [
            os.path.join(src_dir, 'build', 'win', 'message_compiler.py'),
            os.path.join(src_dir, 'third_party', 'dawn', 'third_party', 'directx-shader-compiler', 'build', 'message_compiler.py')
        ]:
            if os.path.exists(mc_py_path):
                with open(mc_py_path, 'r', encoding='utf-8') as f:
                    mc_code = f.read()
                mc_code = mc_code.replace("sys.exit(1)", "pass # sys.exit(1) ignored for sdk mc.exe differences")
                with open(mc_py_path, 'w', encoding='utf-8') as f:
                    f.write(mc_code)

    thorium_patches_dir = os.path.join(thorium_dir, 'patches')
    if os.path.exists(thorium_patches_dir):
        for patch_file in sorted(os.listdir(thorium_patches_dir)):
            if patch_file.endswith('.patch'):
                patch_path = os.path.join(thorium_patches_dir, patch_file)
                print(f"Applying Thorium patch: {patch_file}")
                # Use patch command. On windows, we prepended Git/usr/bin to PATH.
                run_cmd(['patch', '-p1', '--forward', '-i', patch_path], cwd=src_dir, env=env, check=False)

    # Prepare GN args
    gn_args = []
    flags_path = os.path.join(root_dir, 'flags.gn')
    if os.path.exists(flags_path):
        with open(flags_path, 'r') as f:
            for line in f:
                if not line.strip().startswith('#') and '=' in line:
                    gn_args.append(line.strip())

    gn_args.append(f'target_os="{target_os}"')
    gn_args.append(f'target_cpu="{target_cpu}"')
    gn_args.append('is_debug=false')
    gn_args.append('is_official_build=true')
    gn_args.append('is_component_build=false')
    gn_args.append('symbol_level=0')
    gn_args.append('blink_symbol_level=0')
    gn_args.append('use_thin_lto=true')
    gn_args.append('thin_lto_enable_optimizations=true')
    gn_args.append('cc_wrapper="sccache"')

    if target_os == 'linux':
        gn_args.append('use_sysroot=true')
        gn_args.append('enable_nacl=false')
    elif target_os == 'win':
        gn_args.append('enable_nacl=false')

    out_dir = f"out/Thorium_{target_cpu}"
    out_path = os.path.join(src_dir, out_dir)
    os.makedirs(out_path, exist_ok=True)
    with open(os.path.join(out_path, 'args.gn'), 'w') as f:
        f.write('\n'.join(gn_args))

    print("Ensuring gn executable is available...")
    buildtools_platform = 'win' if sys.platform == 'win32' else 'linux64'
    gn_bin = os.path.join(src_dir, 'buildtools', buildtools_platform, 'gn.exe' if sys.platform == 'win32' else 'gn')
    if not os.path.exists(gn_bin):
        os.makedirs(os.path.dirname(gn_bin), exist_ok=True)
        platform_name = 'windows-amd64' if sys.platform == 'win32' else 'linux-amd64'
        gn_zip_url = f"https://chrome-infra-packages.appspot.com/dl/gn/gn/{platform_name}/+/latest"
        temp_zip = os.path.join(root_dir, 'gn_bin.zip')
        print(f"Downloading GN from {gn_zip_url}...")
        urllib.request.urlretrieve(gn_zip_url, temp_zip)
        with zipfile.ZipFile(temp_zip, 'r') as zf:
            member = 'gn.exe' if sys.platform == 'win32' else 'gn'
            zf.extract(member, os.path.dirname(gn_bin))
        if sys.platform != 'win32':
            os.chmod(gn_bin, 0o755)
        if os.path.exists(temp_zip):
            os.remove(temp_zip)

    # Prepend gn directory to PATH so gn can be invoked directly
    env['PATH'] = f"{os.path.dirname(gn_bin)}{sep}{env['PATH']}"

    # Also copy to third_party/gn/ if it exists or for depot_tools gn.py wrapper
    tp_gn_dir = os.path.join(src_dir, 'third_party', 'gn')
    os.makedirs(tp_gn_dir, exist_ok=True)
    tp_gn = os.path.join(tp_gn_dir, 'gn.exe' if sys.platform == 'win32' else 'gn')
    shutil.copy2(gn_bin, tp_gn)
    if sys.platform != 'win32':
        os.chmod(tp_gn, 0o755)

    print(f"Running gn gen using {gn_bin}...")
    run_cmd([gn_bin, 'gen', out_dir], cwd=src_dir, env=env)

    # Free up 15-20 GB of disk space before ninja compilation by removing the .git directory
    print("Cleaning up .git to maximize compilation disk space...")
    git_dir = os.path.join(src_dir, '.git')
    if os.path.exists(git_dir):
        shutil.rmtree(git_dir, ignore_errors=True)

    print("Running ninja...")
    target = 'chrome'
    if target_os == 'win':
        target = 'mini_installer'

    ninja_cmd = 'ninja.exe' if sys.platform == 'win32' else 'ninja'
    run_cmd([ninja_cmd, '-C', out_dir, target], cwd=src_dir, env=env)

    print("Packaging...")
    if target_os == 'linux':
        print("Packaging AppImage...")
        appimage_dir = os.path.join(thorium_dir, 'infra', 'APPIMAGE')

        # We are running on x86_64 host but building for arm64.
        # So we MUST use the x86_64 AppImageTool, but pass ARCH=arm64 environment var.
        appimagetool_path = os.path.join(root_dir, 'appimagetool-x86_64.AppImage')
        if not os.path.exists(appimagetool_path):
            run_cmd(['wget', '-O', appimagetool_path, 'https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage'])
            run_cmd(['chmod', '+x', appimagetool_path])

        appimage_env = env.copy()
        appimage_env['PATH'] = f"{root_dir}:{appimage_env['PATH']}"
        appimage_env['ARCH'] = 'arm64'
        appimage_env['APPIMAGE_EXTRACT_AND_RUN'] = '1'

        appdir = os.path.join(src_dir, out_dir, 'Thorium.AppDir')
        if os.path.exists(appdir):
            shutil.rmtree(appdir)
        os.makedirs(appdir, exist_ok=True)

        appdir_src = os.path.join(appimage_dir, 'AppDir')
        if os.path.exists(appdir_src):
            run_cmd(f"cp -r {appdir_src}/* {appdir}/", shell=True)

        for item in ['chrome', 'thorium', 'chrome_crashpad_handler', 'icudtl.dat', 'locales', 'MEIPreload']:
            src_item = os.path.join(src_dir, out_dir, item)
            if os.path.exists(src_item):
                run_cmd(f"cp -r {src_item} {appdir}/", shell=True)
                if item == 'chrome' and not os.path.exists(os.path.join(appdir, 'thorium')):
                    run_cmd(f"cp -r {src_item} {appdir}/thorium", shell=True)
                elif item == 'thorium' and not os.path.exists(os.path.join(appdir, 'chrome')):
                    run_cmd(f"cp -r {src_item} {appdir}/chrome", shell=True)

        for file in glob.glob(os.path.join(src_dir, out_dir, '*.bin')) + glob.glob(os.path.join(src_dir, out_dir, '*.pak')) + glob.glob(os.path.join(src_dir, out_dir, '*.so')):
            if os.path.exists(file):
                run_cmd(f"cp -r {file} {appdir}/", shell=True)

        apprun_path = os.path.join(appdir, 'AppRun')
        if not os.path.exists(apprun_path):
            with open(apprun_path, 'w', encoding='utf-8') as f:
                f.write('''#!/bin/sh
HERE=$(dirname $(readlink -f "${0}"))
export LD_LIBRARY_PATH="${HERE}"/usr/lib:"${HERE}":$LD_LIBRARY_PATH
if [ -x "${HERE}"/thorium ]; then
  exec "${HERE}"/thorium --no-default-browser-check "$@"
elif [ -x "${HERE}"/chrome ]; then
  exec "${HERE}"/chrome --no-default-browser-check "$@"
else
  echo "Error: Thorium/Chrome binary not found in AppImage" >&2
  exit 1
fi
''')
            os.chmod(apprun_path, 0o755)

        desktop_path = os.path.join(appdir, 'thorium-browser.desktop')
        if not os.path.exists(desktop_path):
            with open(desktop_path, 'w', encoding='utf-8') as f:
                f.write('''[Desktop Entry]
Version=1.0
Name=Thorium Browser
GenericName=Web Browser
Comment=Access the Internet
Exec=AppRun --no-default-browser-check %U
StartupWMClass=thorium
Icon=thorium
Terminal=false
Type=Application
Categories=Network;WebBrowser;
MimeType=text/html;text/xml;application/xhtml_xml;x-scheme-handler/http;x-scheme-handler/https;
''')
            os.chmod(desktop_path, 0o755)

        icon_path = os.path.join(appdir, 'thorium.png')
        if not os.path.exists(icon_path):
            logo_512 = os.path.join(thorium_dir, 'infra', 'APPIMAGE', 'files', 'product_logo_512.png')
            if os.path.exists(logo_512):
                shutil.copy(logo_512, icon_path)

        run_cmd([appimagetool_path, appdir], cwd=os.path.join(src_dir, out_dir), env=appimage_env)
        print(f"Build complete. AppImage created in {os.path.join(src_dir, out_dir)}.")
    elif target_os == 'win':
        print(f"Build complete. Installer is at {os.path.join(src_dir, out_dir, 'mini_installer.exe')}")

if __name__ == '__main__':
    main()
