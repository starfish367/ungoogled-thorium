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
    for rel_path in ['BUILD.gn', 'build/vs_toolchain.py', 'build/config/BUILDCONFIG.gn', 'build/config/arm.gni', 'content/test/BUILD.gn', 'components/BUILD.gn', 'v8/BUILD.gn']:
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
                content += '\ndeclare_args() {\n  enable_strict_deps = false\n  default_modulemap_mode = "none"\n}\n'
            if 'thorium_simd_optimization' not in content:
                content += '\n# Thorium SIMD optimization config\ndefault_compiler_configs += [ "//build/config/compiler:thorium_simd_optimization" ]\n'
        elif rel_path == 'BUILD.gn':
            if 'group("thorium")' not in content:
                content += '\n# Thorium target group\ngroup("thorium") {\n  public_deps = [ "//chrome" ]\n}\n'
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
        'build/config/nacl/config.gni': 'declare_args() {\n  enable_nacl = false\n}\n',
        'chrome/enterprise_companion/buildflags.gni': 'declare_args() {\n  enable_chrome_enterprise_companion = false\n}\n',
        'chromeos/ash/components/assistant/assistant.gni': 'declare_args() {\n  enable_cros_libassistant = false\n}\n',
        'components/nacl/features.gni': 'declare_args() {\n  enable_nacl = false\n}\n',
    }
    for stub_rel, stub_code in stubs.items():
        stub_full = os.path.join(src_dir, stub_rel)
        if not os.path.exists(stub_full):
            os.makedirs(os.path.dirname(stub_full), exist_ok=True)
            with open(stub_full, 'w', encoding='utf-8') as f:
                f.write(stub_code)

    # Ensure media/media_options.gni defines system_loopback_as_aec_reference_supported
    media_options_path = os.path.join(src_dir, 'media', 'media_options.gni')
    if os.path.exists(media_options_path):
        with open(media_options_path, 'r', encoding='utf-8') as f:
            media_content = f.read()
        if 'system_loopback_as_aec_reference_supported' not in media_content:
            media_content += '''
declare_args() {
  system_loopback_as_aec_reference_supported =
      (is_win || is_mac) && chrome_wide_echo_cancellation_supported
}
'''
            with open(media_options_path, 'w', encoding='utf-8') as f:
                f.write(media_content)

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
        os.makedirs(appdir)

        run_cmd(f"cp -r {appimage_dir}/AppDir/* {appdir}/", shell=True)

        for item in ['chrome', 'chrome_crashpad_handler', 'icudtl.dat', 'locales', 'MEIPreload']:
            src_item = os.path.join(src_dir, out_dir, item)
            if os.path.exists(src_item):
                run_cmd(f"cp -r {src_item} {appdir}/", shell=True)

        for file in glob.glob(os.path.join(src_dir, out_dir, '*.bin')) + glob.glob(os.path.join(src_dir, out_dir, '*.pak')):
            if os.path.exists(file):
                run_cmd(f"cp -r {file} {appdir}/", shell=True)

        run_cmd([appimagetool_path, appdir], cwd=os.path.join(src_dir, out_dir), env=appimage_env)
        print(f"Build complete. Binary is at {os.path.join(src_dir, out_dir, 'chrome')} and AppImage created.")
    elif target_os == 'win':
        print(f"Build complete. Installer is at {os.path.join(src_dir, out_dir, 'mini_installer.exe')}")

if __name__ == '__main__':
    main()
