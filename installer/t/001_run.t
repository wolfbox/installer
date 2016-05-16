#!/usr/bin/perl
use strict;
use warnings;

use Test::More tests => 2;
use Test::Exception;
use Installer;

my $var = 'foo bar';
dies_ok { Installer::run('false'); } 'Expected to die';
is(Installer::run("echo '$var'"), "$var\n");
