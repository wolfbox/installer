import subprocess


def cmdline(disk: str, root: str) -> None:
    subprocess.check_call(['/usr/sbin/installboot', '-r', root, disk])
