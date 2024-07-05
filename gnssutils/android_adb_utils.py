import subprocess
import os

def run_adb_command(command):
    """
    Runs an ADB command and returns the output.

    Args:
        command (list): List of command arguments.

    Returns:
        str: Output of the ADB command.

    Raises:
        Exception: If the command fails.
    """
    result = subprocess.run(['android_platform_tools/adb'] + command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise Exception(f"Command failed with error: {result.stderr}")
    return result.stdout

def get_files_in_directory(directory):
    """
    Gets a list of files in a directory on an Android device.

    Args:
        directory (str): Directory path.

    Returns:
        list: List of files in the directory.
    """
    list_command = ['shell', 'ls', directory]
    try:
        files = run_adb_command(list_command).splitlines()
        return files
    except Exception as e:
        print(f"Error getting files in directory: {e}")
        return []

def append_new_data(file_path, new_data):
    """
    Appends new data to a file.

    Args:
        file_path (str): Path to the file.
        new_data (str): Data to append.
    """
    try:
        with open(file_path, 'a') as file:
            file.write(new_data)
    except Exception as e:
        print(f"Error appending new data: {e}")

def read_existing_file(file_path):
    """
    Reads the content of an existing file.

    Args:
        file_path (str): Path to the file.

    Returns:
        str: Content of the file.
    """
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except Exception as e:
            print(f"Error reading existing file: {e}")
            return ""
    return ""

def delete_files_in_directory(directory):
    """
    Deletes all files in a directory on an Android device.

    Args:
        directory (str): Directory path.
    """
    try:
        files = get_files_in_directory(directory)
        for file in files:
            file_to_delete = f'{directory}/{file}'
            delete_command = ['shell', 'rm', file_to_delete]
            run_adb_command(delete_command)
            print(f"Deleted {file_to_delete}")
    except Exception as e:
        print(f"Error deleting files in directory: {e}")

def pull_file(file_to_pull):
    """
    Pulls a file from an Android device.

    Args:
        file_to_pull (str): Path to the file on the device.

    Returns:
        str: Content of the file.
    """
    pull_command = ['shell', 'cat', file_to_pull]
    new_data = run_adb_command(pull_command)
    return new_data
