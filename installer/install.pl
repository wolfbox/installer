#!/usr/bin/perl
use strict;
use warnings;

require File::Temp;
use File::Temp ();
use HTTP::Tiny;
use Fcntl;

sub run {
    my ($cmd) = @_;
    my $output = `$cmd`;
    my $status = $? >> 8;
    if($status) { die "Failed: '$cmd' with exit code $status"; }
    return $output;
}

sub get_ftplist {
    my ($url) = @_;
    my $response = HTTP::Tiny->new->get($url, {timeout => 12});
    die "Failed!\n" unless $response->{success};

    my $text = $response->{content};
    my @links = ($text =~ /^(https?:\/\/\S+)/mg);
    my %parts = ($text =~ /^([A-Z_]+)=(.*)/mg);
    @links = @links[0..2];
    @parts{'MIRRORS'} = \@links;

    return %parts;
}

sub list_disks {
    my $raw = `sysctl -n hw.disknames`;
    my @parts = ($raw =~ /([a-z]+[0-9]):[a-z0-9]+/g);
    return @parts;
}

sub list_ifaces {
    return;
}

sub umount_disk {
    `umount /mnt/var /mnt 2>&1`;
    return;
}

sub setup_disk {
    my ($disk) = @_;

    $disk =~ /(sd|vn|wd)[0-9]/ or die "Invalid diskname";
    run("mount") =~ "/dev/$disk" and die "Refusing to format mounted disk";

    my $ramsize = int(int(`sysctl -n hw.physmem`) / 1024 / 1024);
    if($ramsize <= 0) { die "Illegal ramsize $ramsize"; }

    run("/sbin/fdisk -y -b 1920 -ig '$disk'") or die "Failed to format disk";

    my $template = File::Temp->new(TEMPLATE => "/tmp/install.XXXXXX");
    print $template "/ 1G-* 0 rw\n";
    print $template "swap 100M-${ramsize}M 10\n";
    print $template "/var 500M-* 90 rw,nosuid,nodev\n";
    print $template "/nextimage 1G-* 0 ro\n";
    $template->flush();

    run("/sbin/disklabel -wAT '$template' '$disk'");

    my $disk_info = run("/sbin/disklabel '$disk'") or die "Failed to get disk info";
    my @duids = ($disk_info =~ /^duid: (\S+)/m);
    my $duid = $duids[0];

    my @fstab = ("$duid.a / ffs rw 1 1",
                 "$duid.b none swap sw",
                 "$duid.d /var ffs rw,nodev,nosuid 1 2",
                 "$duid.e /altroot ffs ro 1 2\n");

    foreach my $part ("a", "d", "e") {
        run("/sbin/newfs '$duid.$part'") or die "Failed to format $duid.$part";
    }

    return ($duid, @fstab);
}

sub mount_disk {
    my ($duid) = @_;

    run("mount -o async '$duid.a' /mnt");
    mkdir "/mnt/var" or die;
    run("mount -o async '$duid.d' /mnt/var");
    return;
}

# extract_image(image_path)
# Extract a given root image file into the given directory, and perform
# post-processing setup steps.
sub extract_image {
    my ($image_path) = @_;
    run("xzcat '$image_path' | tar -C /mnt -xhpf -");

    # Set up config files
    foreach my $tarball(glob "/mnt/var/sysmerge/*etc.tgz") {
        run("/bin/tar -C /mnt -zxphf '$tarball'");
    }

    # Make devices
    run("cd /mnt/dev && ./MAKEDEV all");

    # Make master password database
    run("/usr/sbin/pwd_mkdb -p -d /mnt/etc /etc/master.passwd");

    # Set up initial doas rule
    run("echo 'permit keepenv :wheel as root' > /mnt/etc/doas.conf");
    return;
}

sub configure_hostname {
    my ($hostname) = @_;
    my $fh = IO::File->new('/mnt/etc/myname', 'w')
        or die "Failed to open '/mnt/etc/myname': $!";
    print $fh "$hostname\n";
    close $fh;
    return;
}

sub configure_timezone {
    my ($tz) = @_;
    unlink('/mnt/etc/localtime');
    symlink("/usr/share/zoneinfo/$tz", '/mnt/etc/localtime') or die "Failed to set timezone: $!";
    return;
}

sub configure_mirrors {
    my (@mirrors) = @_;

    my @stanzas = map { "installpath+=$_" } @mirrors;
    my $fh = IO::File->new('/mnt/etc/pkg.conf', 'w')
        or die "Failed to open '/mnt/etc/pkg.conf': $!";
    print $fh join('\n', @stanzas);
    print $fh '\n';
    return;
}

sub configure {
    my ($duid, @fstab) = @_;

    run("dd status=none if=/dev/random of=/mnt/etc/random.seed bs=512 count=1");
    run("dd status=none if=/dev/random of=/mnt/var/db/host.random bs=65536 count=1");

    run("echo 'machdep.allowaperture=1' > /mnt/etc/sysctl.conf");
    run("printf '127.0.0.1\tlocalhost\n::1\t\tlocalhost\n' > /mnt/etc/hosts");

    my $fstab_fh = IO::File->new('/mnt/etc/fstab', 'w')
        or die "Failed to open '/mnt/etc/fstab': $!";
    print $fstab_fh join('\n', @fstab);
    print $fstab_fh '\n';

    run("/usr/sbin/installboot -r /mnt '$duid'");
    return;
}

sub create_user {
    my ($username, $fullname) = @_;

    if($fullname =~ ',') {
        die "Illegal name: $fullname";
    }

    my $gecos = "$fullname,,,";
    run("/usr/sbin/chroot /mnt /usr/sbin/useradd -m -k /etc/skel -c gecos -s /bin/ksh -G wheel '$username'");
    run("/usr/sbin/chroot /mnt /usr/bin/passwd '$username'");
    return;
}

sub main {
    my @disks = list_disks();
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

    my %ftplist = get_ftplist('http://129.128.5.191/cgi-bin/ftplist.cgi');

    umount_disk();
    my ($duid, @fstab) = setup_disk($disk);
    mount_disk $duid;
    extract_image('./root.tar.xz');
    configure($duid, @fstab);
    configure_hostname($hostname);
    configure_timezone($ftplist{'TZ'});
    configure_mirrors($ftplist{'MIRRORS'});
    create_user($username, $fullname);

    umount_disk();
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
$SIG{TERM} = sub { unlock_installer(); die "Caught sigterm"; };

lock_installer();
eval { main(); }; warn $@ if $@;
unlock_installer();
