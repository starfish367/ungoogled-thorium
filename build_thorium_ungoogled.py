import argparse
import os
import subprocess
import sys
import shutil
import glob

def run_cmd(cmd, cwd=None, env=None, check=True, shell=False):
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    subprocess.run(cmd, cwd=cwd, env=env, check=check, shell=shell)

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

    env['DEPOT_TOOLS_UPDATE'] = '0'
    env['DEPOT_TOOLS_WIN_TOOLCHAIN'] = '0'

    # Download Thorium source
    thorium_dir = os.path.join(root_dir, 'Thorium')
    if not os.path.exists(thorium_dir):
        run_cmd(['git', 'clone', '--depth=1', 'https://github.com/Alex313031/Thorium.git', thorium_dir])

    # The actual chromium source ends up in src_dir/src
    actual_src_dir = os.path.join(src_dir, 'src')

    if not os.path.exists(actual_src_dir):
        print("Chromium source not found. Fetching...")
        os.makedirs(src_dir, exist_ok=True)
        # Fetch matching tag instead of latest trunk
        if chromium_version:
            run_cmd(f"cd {src_dir} && fetch --nohooks --no-history chromium && cd src && git fetch --tags && git checkout {chromium_version}", shell=True, env=env)
        else:
            print("Warning: chromium_version.txt not found. Fetching latest trunk...")
            run_cmd(f"cd {src_dir} && fetch --nohooks --no-history chromium", shell=True, env=env)

    # Use the actual chromium src dir for the rest of the script
    src_dir = actual_src_dir

    # Ensure gclient sync runs for this version
    run_cmd(['gclient', 'sync', '-D', '--with_branch_heads', '--with_tags'], cwd=os.path.dirname(src_dir), env=env)
    run_cmd(['gclient', 'runhooks'], cwd=os.path.dirname(src_dir), env=env)

    # For Linux arm64 cross compile we need sysroots
    if target_os == 'linux' and target_cpu == 'arm64':
        print("Installing arm64 sysroot...")
        sysroot_script = os.path.join(src_dir, 'build', 'linux', 'sysroot_scripts', 'install-sysroot.py')
        if os.path.exists(sysroot_script):
            run_cmd([sys.executable, sysroot_script, '--arch=arm64'], cwd=src_dir)

    # Apply ungoogled-chromium modifications
    print("Applying ungoogled-chromium modifications...")
    run_cmd([sys.executable, 'utils/prune_binaries.py', src_dir, 'pruning.list'], cwd=root_dir)
    run_cmd([sys.executable, 'utils/patches.py', 'apply', src_dir, 'patches'], cwd=root_dir)

    # Apply domain substitution. Do NOT pass chromium_version.txt to -c (cache).
    run_cmd([sys.executable, 'utils/domain_substitution.py', 'apply', '-r', 'domain_regex.list', '-f', 'domain_substitution.list', src_dir], cwd=root_dir)

    # Apply Thorium modifications
    print("Applying Thorium overlay and patches...")
    thorium_src_overlay = os.path.join(thorium_dir, 'src')
    if os.path.exists(thorium_src_overlay):
        if sys.platform == 'win32':
            run_cmd(f"xcopy /E /I /Y {thorium_src_overlay}\\* {src_dir}\\")
        else:
            run_cmd(f"cp -r {thorium_src_overlay}/* {src_dir}/", shell=True)

    thorium_patches_dir = os.path.join(thorium_dir, 'patches')
    if os.path.exists(thorium_patches_dir):
        for patch_file in sorted(os.listdir(thorium_patches_dir)):
            if patch_file.endswith('.patch'):
                patch_path = os.path.join(thorium_patches_dir, patch_file)
                print(f"Applying Thorium patch: {patch_file}")
                # Use patch command. On windows, we prepended Git/usr/bin to PATH.
                subprocess.run(['patch', '-p1', '--forward', '-i', patch_path], cwd=src_dir, env=env)

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
        gn_args.append('is_component_build=false')

    out_dir = f"out/Thorium_{target_cpu}"
    out_path = os.path.join(src_dir, out_dir)
    os.makedirs(out_path, exist_ok=True)

    with open(os.path.join(out_path, 'args.gn'), 'w') as f:
        f.write('\n'.join(gn_args))

    print("Running gn gen...")
    gn_cmd = 'gn.bat' if sys.platform == 'win32' else 'gn'
    run_cmd([gn_cmd, 'gen', out_dir], cwd=src_dir, env=env)

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
