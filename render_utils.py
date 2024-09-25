import os


def collect_test_files(directory):
    # List to store all the filenames
    test_files = []
    subdirs = []

    # Walk through the directory
    for root, dirs, files in os.walk(directory):
        if root.endswith("/"):
            root = root[:-1]
        # Check if 'test' is part of the folder name
        if 'test' in os.path.basename(root).lower() or os.path.basename(root) in subdirs:
            for file in files:
                # Process only Python files
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    test_files.append(file_path)
            for d in dirs:
                subdirs.append(d)

    return test_files


def collect_python_files(directory):
    # List to store all the .py filenames
    python_files = []

    # Walk through the directory recursively
    for root, _, files in os.walk(directory):
        for file in files:
            # Check if the file ends with '.py'
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                python_files.append(file_path)

    return python_files


def _find_files_to_edit(base_dir: str, src_dir: str, test_dir: str) -> list[str]:
    """Identify files to remove content by heuristics.
    We assume source code is under [lib]/[lib] or [lib]/src.
    We exclude test code. This function would not work
    if test code doesn't have its own directory.

    Args:
    ----
        base_dir (str): the path to local library.

    Return:
    ------
        files (list[str]): a list of files to be edited.

    """
    files = collect_python_files(os.path.join(base_dir, src_dir))
    test_files = collect_test_files(os.path.join(base_dir, test_dir))
    files = list(set(files) - set(test_files))

    # don't edit __init__ files
    files = [f for f in files if "__init__" not in f]
    # don't edit __main__ files
    files = [f for f in files if "__main__" not in f]
    # don't edit confest.py files
    files = [f for f in files if "conftest.py" not in f]
    return files