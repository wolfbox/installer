#!/usr/bin/env python3.4

import os
import os.path
from typing import List

zoneinfo_path = '/usr/share/zoneinfo/'
timezones = []  # type: List[str]


def list_timezones() -> List[str]:
    available = []
    for root, _, files in os.walk(zoneinfo_path):
        root = root.replace(zoneinfo_path, '')
        for file in files:
            available.append(os.path.join(root, file))

    available.sort()
    return available


def search(prefix: str) -> List[str]:
    global timezones
    if not timezones:
        timezones = list_timezones()

    matches = []
    for tz in timezones:
        if tz.startswith(prefix):
            matches.append(tz)

    return matches


def is_tz(name: str) -> bool:
    path = os.path.join(zoneinfo_path, name)
    return os.path.isfile(path)


def cmdline_ask_for_tz(suggested_tz: str) -> str:
    if is_tz(suggested_tz):
        print('Detected the following timezone: {}'.format(suggested_tz))
        if input('Is this correct? (y/n) ') != 'n':
            return suggested_tz

    while True:
        tz = input('Timezone: ')
        if not is_tz(tz):
            print('\n'.join(search(tz)))
            continue

        return tz


def set_timezone(root: str, tz: str) -> None:
    if not is_tz(tz):
        raise ValueError(tz)

    path = os.path.join(zoneinfo_path, tz)
    srcpath = os.path.join(root, 'etc/localtime')
    try:
        os.unlink(srcpath)
    except FileNotFoundError:
        pass

    os.symlink(path, srcpath)


def cmdline(root: str, suggested_tz: str) -> None:
    tz = cmdline_ask_for_tz(suggested_tz)
    set_timezone(root, tz)
