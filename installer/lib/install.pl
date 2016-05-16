#!/usr/bin/perl
use strict;
use warnings;

use Fcntl;
use Installer;

sub main {
    my @disks = Installer::list_disks();
    my $str_disks = join(', ', @disks);
    my $disk = '';

    until(grep {$_ eq $disk} @disks) {
        print "Disks: $str_disks\n";
        print 'Disk: ';
        $disk = <>;
        chomp $disk;
    }

    print 'Hostname: ';
    my $hostname = <>;
    chomp $hostname;

    print 'Username: ';
    my $username = <>;
    chomp $username;

    print 'Full Name: ';
    my $fullname = <>;
    chomp $fullname;

    my %ftplist = Installer::get_ftplist('http://129.128.5.191/cgi-bin/ftplist.cgi');

    Installer::umount_disk();
    my ($duid, @fstab) = Installer::setup_disk($disk);
    Installer::mount_disk $duid;
    Installer::extract_image('./root.tar.xz');
    Installer::configure($duid, @fstab);
    Installer::configure_hostname($hostname);
    Installer::configure_timezone($ftplist{'TZ'});
    Installer::configure_mirrors($ftplist{'MIRRORS'});
    Installer::create_user($username, $fullname);

    Installer::umount_disk();
    return;
}

sub lock_installer {
    IO::File->new("/tmp/installer.lock", O_CREAT|O_EXCL) or die "Failed to lock";
    return;
}

sub unlock_installer {
    unlink("/tmp/installer.lock");
    return;
}

local $SIG{INT} = sub { unlock_installer(); die "Caught sigint"; };
local $SIG{TERM} = sub { unlock_installer(); die "Caught sigterm"; };

lock_installer();
eval { main(); }; warn $@ if $@;
unlock_installer();
