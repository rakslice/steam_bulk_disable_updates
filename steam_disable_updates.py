import glob
import os

import _winreg

import subprocess

import sys


"""
This is a script to bulk set all installed steam games to update only on launch
"""


AUTO_UPDATE_ONLY_ON_LAUNCH = "1"

NAME_LINE_PREFIX = '\t"name"\t\t'

REGISTRY_HIVE_NAMES = {_winreg.HKEY_CURRENT_USER: "HKEY_CURRENT_USER"}


def read_reg_string(key, sub_key, value_name):
    print "Reading registry string: %s" % r"%s\%s\%s" % (REGISTRY_HIVE_NAMES[key], sub_key, value_name)
    handle = _winreg.OpenKey(key, sub_key)
    try:
        value, type_ = _winreg.QueryValueEx(handle, value_name)
        assert type_ == _winreg.REG_SZ
        return value
    finally:
        handle.Close()


def get_steam_path():
    return read_reg_string(_winreg.HKEY_CURRENT_USER, "SOFTWARE\Valve\Steam", "SteamPath")


def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def is_process_running(image_name):
    output = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq %s" % image_name])
    return image_name.lower() in output.lower()


def get_steamapps_dirs():
    steam_path = get_steam_path()

    print "Main Steam folder: %s" % steam_path

    steam_main_steamapps = os.path.join(steam_path, "steamapps")

    library_folders_file = os.path.join(steam_main_steamapps, "libraryfolders.vdf")
    print "Loading library folders file: %s" % library_folders_file
    assert os.path.exists(library_folders_file)
    lines = contents_lines(library_folders_file)

    assert len(lines) >= 3
    assert lines[0] == '"LibraryFolders"'
    assert lines[1] == '{'
    assert lines[-2] == '}'
    assert lines[-1] == ''

    steamapps_dirs = [steam_main_steamapps]

    for line in lines[2:-2]:
        assert line.startswith('\t"'), line
        key = line[2:].split('"', 1)[0]
        if is_int(key):
            start = '\t"' + key + '"\t\t"'
            assert line.startswith(start)
            assert line.endswith('"')
            path = line[len(start):-1]
            path = path.replace(r'\"', '"')
            path = path.replace("\\\\", "\\")

            print "Adding configured library folder: %s" % path

            steamapps_dirs.append(os.path.join(path, "SteamApps"))

    return steamapps_dirs


def contents_lines(manifest_filename):
    with open(manifest_filename, "rb") as handle:
        return handle.read().split("\n")


def write_lines(manifest_filename, new_lines):
    with open(manifest_filename, "wb") as handle:
        for line in new_lines:
            handle.write(line + "\n")


def show_message_box(message):
    script_name = os.path.basename(sys.argv[0])

    # From http://stackoverflow.com/questions/4485610/python-message-box-without-huge-library-dependancy
    import ctypes
    MessageBox = ctypes.windll.user32.MessageBoxW
    MessageBox(None, unicode(message), unicode(script_name), 0)


def main():
    if is_process_running("steam.exe"):
        message = "steam.exe is currently running. You'll need to exit Steam completely using the Steam icon right-click menu or Task Manager before running this script so it can make changes to files."
        show_message_box(message)
        sys.exit(1)

    for steamapps_dir in get_steamapps_dirs():
        print "Processing manifest files in %s:" % steamapps_dir
        for manifest_filename_proper in glob.glob1(steamapps_dir, "*.acf"):
            print "\t%s" % manifest_filename_proper
            manifest_filename = os.path.join(steamapps_dir, manifest_filename_proper)
            lines = contents_lines(manifest_filename)

            auto_update_line_found = False
            changed = False
            app_name = None

            assert len(lines) >= 3
            assert lines[0] == '"AppState"'
            assert lines[1] == '{'
            for i, line in enumerate(lines[2:], 2):
                # print i, line
                if line == "}":
                    break

                if line.startswith(NAME_LINE_PREFIX):
                    app_name = line[len(NAME_LINE_PREFIX):]
                    assert app_name.startswith('"') and app_name.endswith('"')
                    app_name = app_name[1:-1]

                if line.strip().startswith('"AutoUpdateBehavior"'):
                    # for now expect rigid formatting
                    pref = '\t"AutoUpdateBehavior"\t\t"'
                    suff = '"'
                    assert line.startswith(pref)
                    assert line.endswith(suff)
                    old_auto_update_setting = line[len(pref):-len(suff)]

                    auto_update_line_found = True

                    assert app_name is not None, "no app name in %s" % manifest_filename_proper

                    print "\t\t- %s" % app_name

                    if old_auto_update_setting != AUTO_UPDATE_ONLY_ON_LAUNCH:
                        new_auto_update_setting = AUTO_UPDATE_ONLY_ON_LAUNCH

                        print "\t\t     Changed auto update setting %s -> %s" % (old_auto_update_setting, new_auto_update_setting)
                        line = pref + new_auto_update_setting + suff
                        lines[i] = line
                        changed = True
            else:
                assert False, "no main object end"

            assert auto_update_line_found, "file %r didn't have auto update line" % manifest_filename_proper

            if changed:
                write_lines(manifest_filename, lines)


if __name__ == "__main__":
    main()
