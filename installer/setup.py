#!/usr/bin/env python3.4

import subprocess
import contextlib
import glob
import os
import os.path
import urllib.error
import logging

import bootloader
import fdisk
import ftplist
import timezone
import user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
ROOT = '/mnt'


@contextlib.contextmanager
def in_dir(path: str):
    orig_path = os.getcwd()
    os.chdir(path)
    yield orig_path
    os.chdir(orig_path)


def dd(inpath: str, outpath: str, count: int, bs: int) -> None:
    subprocess.check_call(['/bin/dd',
                           'if={0}'.format(inpath),
                           'of={0}'.format(outpath),
                           'bs={0}'.format(bs),
                           'count={0}'.format(count)])


def main() -> None:
    subprocess.call(['/sbin/umount', '-af'])

    disks = fdisk.list_disks()
    disk = ''
    while disk not in disks:
        print(', '.join(disks))
        disk = input('> ')

    logger.info('Setting up partition')
    labels = fdisk.main(disk)
    mount_list = [l for l in labels if l.mountpoint.startswith('/')]
    mount_list.sort(key=lambda l: len(l.mountpoint))
    for label in mount_list:
        if label.relmountpoint:
            os.makedirs(os.path.join(ROOT, label.relmountpoint))
        fdisk.mount_disk(label, ROOT)

    logger.info('Extracting image')
    subprocess.check_call(['/bin/tar',
                           '-C', ROOT,
                           '-xhpzf',
                           'image.tar.gz'])

    logger.info('Merging config files')
    for etc in glob.glob(os.path.join(ROOT, '/var/sysmerge/*etc.tgz')):
        subprocess.check_call(['/bin/tar',
                               '-C', ROOT,
                               '-zxphf', etc])

    logger.info('Creating devices')
    with in_dir(os.path.join(ROOT, 'dev')):
        subprocess.check_call(['./MAKEDEV', 'all'])

    logger.info('Creating fstab')
    with open(os.path.join(ROOT, 'etc', 'fstab'), 'w') as fstab:
        fstab.write('\n'.join([f.to_fstab() for f in labels]) + '\n')

    logger.info('Getting ftplist information')
    ftplist_info = ftplist.FtpList.empty()
    try:
        ftplist_info = ftplist.FtpList.load()
    except urllib.error.URLError:
        pass

    logger.info('Setting up timezones')
    timezone.cmdline(ROOT, ftplist_info.tz)

    logger.info('Setting up user')
    user.cmdline(ROOT)

    logger.info('Finishing up')
    with open(os.path.join(ROOT, 'etc/sysctl.conf'), 'a') as f:
        f.write('machdep.allowaperture=1\n')
    with open(os.path.join(ROOT, 'etc/hosts'), 'a') as f:
        f.write('127.0.0.1\tlocalhost\n')
        f.write('::1\t\tlocalhost\n')

    dd(inpath='/dev/random',
       outpath=os.path.join(ROOT, 'etc/random.seed'),
       bs=512,
       count=1)
    dd(inpath='/dev/random',
       outpath=os.path.join(ROOT, 'var/db/host.random'),
       bs=65536,
       count=1)

    logger.info('Writing bootloader')
    bootloader.cmdline(disk, ROOT)

if __name__ == '__main__':
    main()
