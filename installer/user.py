#!/usr/bin/env python3.4

import os.path
import subprocess
from typing import Set


class User:
    def __init__(self, username: str) -> None:
        if not username:
            raise ValueError(username)

        self.username = username
        self.groups = set()  # type: Set[str]
        self.password = ''
        self.shell = '/bin/ksh'

        self.full_name = ''

    def add_group(self, group: str) -> None:
        """Add this user to a group."""
        self.groups.add(group)

    @property
    def gecos(self) -> str:
        """Return a GECOS string containing user information."""
        return ','.join((self.full_name, '', '', ''))


def install_user_database(root: str) -> None:
    subprocess.check_call(['/usr/sbin/pwd_mkdb',
                           '-p',
                           '-d',
                           os.path.join(root, 'etc'),
                           '/etc/master.passwd'])


def create_user(root: str, user: User) -> None:
    args = ['/usr/sbin/useradd']
    args.append('-m')
    args.extend(('-k', '/etc/skel'))
    args.extend(('-c', user.gecos))
    args.extend(('-s', user.shell))
    args.extend(('-G', ','.join(user.groups)))
    args.append(user.username)

    # Run in a chroot
    subprocess.check_call(['/usr/sbin/chroot', root] + args)


def cmdline(root: str) -> None:
    username = ''
    while not username:
        username = input('username> ').strip()

    user = User(username)
    user.add_group('wheel')

    install_user_database(root)
    create_user(root, user)
    subprocess.check_call(['/usr/sbin/chroot', root, '/usr/bin/passwd', username])
