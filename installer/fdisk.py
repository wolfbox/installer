#!/usr/bin/env python3.4
import os.path
import subprocess
import re
import tempfile
import math

from typing import Dict, List

# Allow installation on SCSI, virtual, and IDE/SATA devices.
DISK_PREFIXES = ('sd', 'vn', 'wd')

# Refuse to install on a disk with less than 2GB.
MIN_SIZE = 2 * 1024 * 1024 * 1024


def sysctl(name: str) -> str:
    return str(subprocess.check_output(['sysctl', '-n', name]), 'utf-8')


def disklabel(disk_name: str, options: List[str]) -> bytes:
    return subprocess.check_output(['/sbin/disklabel'] + options + [disk_name])


def mount_disk(label: 'Label', root: str) -> None:
    # Mount softdep to speed up install significantly. Should be safe;
    # the OpenBSD installer mounts *async* after all.
    subprocess.check_call(['/sbin/mount',
                           '-o', 'softdep',
                           label.block_path,
                           os.path.join(root, label.relmountpoint)])


def format_disk(label: 'Label') -> None:
    subprocess.call(['/sbin/umount', label.block_path])
    subprocess.check_call(['/sbin/newfs', label.device_path])
    label.filesystem = 'ffs'


class DiskInfo:
    def __init__(self, device_node: str, raw_data: Dict[str, str]) -> None:
        self.device_node = device_node
        self.data = raw_data

    @property
    def label(self) -> str:
        return self.data['label']

    @property
    def sectors(self) -> int:
        return int(self.data['total sectors'])

    @property
    def bytes_per_sector(self) -> int:
        return int(self.data['bytes/sector'])

    @property
    def size(self):
        return self.sectors * self.bytes_per_sector

    @property
    def duid(self) -> str:
        return self.data['duid']

    def refresh(self) -> None:
        new_info = self.load(self.device_node)
        self.device_node = new_info.device_node
        self.data = new_info.data

    @classmethod
    def load(cls, disk_name: str) -> 'DiskInfo':
        output = str(disklabel(disk_name, []), 'utf-8')
        parsed = re.finditer(r'^([\S ]+): ([^\n]+)$', output, re.MULTILINE)
        data = {}
        for group in parsed:
            data[group.group(1)] = group.group(2)

        return DiskInfo(disk_name, data)


class Label:
    def __init__(self,
                 mountpoint: str,
                 diskinfo: DiskInfo,
                 disk_name: str,
                 partition_letter: str,
                 options=None) -> None:
        self.mountpoint = mountpoint
        self.diskinfo = diskinfo
        self.disk_name = disk_name
        self.partition_letter = partition_letter
        self.filesystem = None
        self.options = set(options if options else [])

        if self.mountpoint == 'swap':
            # This is unfortunate black magic: treat "swap" as being a special
            # value creating a "none" mountpoint.
            self.mountpoint = 'none'
            self.filesystem = 'swap'
            self.add_option('sw')
        else:
            # If you really need atime, you can set that up yourself.
            self.add_option('noatime')

    def add_option(self, option: str) -> None:
        self.options.add(option)

    @property
    def passno(self) -> int:
        return 1 if self.mountpoint == '/' else 2

    @property
    def relmountpoint(self) -> str:
        return self.mountpoint.lstrip('/')

    @property
    def block_path(self) -> str:
        return '/dev/{}{}'.format(self.disk_name, self.partition_letter)

    @property
    def device_path(self) -> str:
        return '/dev/r{}{}'.format(self.disk_name, self.partition_letter)

    def to_fstab(self) -> str:
        if not self.filesystem:
            return ''

        stanza = '{}.{} {} {} {}'.format(self.diskinfo.duid,
                                         self.partition_letter,
                                         self.mountpoint,
                                         self.filesystem,
                                         ','.join(self.options))
        if self.mountpoint != 'swap':
            stanza += ' 1 {}'.format(self.passno)

        return stanza

    def __repr__(self) -> str:
        return '{}({}, {}, {}, {}, {})'.format(self.__class__.__name__,
                                               self.mountpoint,
                                               self.diskinfo.duid,
                                               self.disk_name,
                                               self.partition_letter,
                                               list(self.options))


class LabelDefinition:
    def __init__(self, mountpoint: str, size_range, size_percent=0, options=None) -> None:
        self.mountpoint = mountpoint
        self.size_range = size_range
        self.size_percent = size_percent
        self.options = options[:] if options else []

    def to_line(self):
        lower, upper = self.size_range
        range_field = upper if self.is_fixed_size() else '{}-{}'.format(lower, upper)
        percent_field = '{}%'.format(self.size_percent) \
                        if self.size_percent \
                        else ''
        return '{:15} {:15} {}'.format(self.mountpoint, range_field, percent_field).strip()

    @staticmethod
    def is_fixed_size():
        return False

    def __repr__(self):
        return '{}({}, {}, {}, {})'.format(self.__class__.__name__,
                                           self.mountpoint,
                                           self.size_range,
                                           self.size_percent,
                                           self.options)


class LabelEditor:
    def __init__(self, disk_name: str) -> None:
        if not disk_name:
            raise ValueError(disk_name)

        self.disk_name = disk_name
        self.diskinfo = DiskInfo.load(self.disk_name)

    def autolabel(self, template: List[LabelDefinition]):
        template_string = '\n'.join([x.to_line() for x in template])
        with tempfile.NamedTemporaryFile(mode='wb+') as template_file:
            template_file.write(bytes(template_string, 'utf-8'))
            template_file.flush()
            disklabel(self.disk_name, ['-A', '-w', '-T', template_file.name])

        letters = ['a', 'b', 'd', 'e', 'f', 'g', 'h']
        labels = [Label(l.mountpoint,
                        self.diskinfo,
                        self.disk_name,
                        letters[template.index(l)],
                        l.options)
                  for l in template]

        # Format mountpoints
        i = -1
        for label in labels:
            i += 1
            if not label.mountpoint.startswith('/'):
                continue

            format_disk(label)

        self.diskinfo.refresh()
        return labels


class PartitionEditor:
    def __init__(self, disk_name: str) -> None:
        if not disk_name:
            raise ValueError(disk_name)

        self.disk_name = disk_name

    def clear_disk(self):
        # The OpenBSD installer suggests the boot partition to be >960 blocks.
        # We choose twice that for safety.
        self._fdisk(['-y', '-b', '1920', '-ig'])

    def _fdisk(self, options: List[str]):
        return subprocess.check_output(['/sbin/fdisk', '-y'] + options + [self.disk_name])


def list_disks() -> List[str]:
    raw = sysctl('hw.disknames')
    disks = [disk.split(':')[0] for disk in raw.split(',')]
    return [disk for disk in disks if disk[0:2] in DISK_PREFIXES]


def main(disk: str):
    editor = PartitionEditor(disk)
    label_editor = LabelEditor(disk)
    if label_editor.diskinfo.size < MIN_SIZE:
        print('Disk too small!')
        return

    editor.clear_disk()

    ramsize = int(sysctl('hw.physmem'))
    label_definitions = [
        LabelDefinition('/', ('1G', '*'), 0, ['rw']),
        LabelDefinition('swap',
                        ('100M', '{}M'.format(math.ceil(ramsize / 1024 / 1024))),
                        10),
        LabelDefinition('/var', ('500M', '*'), 90, ['rw', 'nosuid', 'nodev'])]
    return label_editor.autolabel(label_definitions)
