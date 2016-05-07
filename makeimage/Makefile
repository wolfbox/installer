MAKE_JOBS:=`sysctl -n hw.ncpufound`
VERSION=59
DESTDIR=/usr/dest
RELEASEDIR=/usr/rel
BASE_SETS=$(RELEASEDIR)/base$(VERSION).tgz \
          $(RELEASEDIR)/man$(VERSION).tgz \
          $(RELEASEDIR)/comp$(VERSION).tgz
XENOCARA_SETS=$(RELEASEDIR)/xbase$(VERSION).tgz \
              $(RELEASEDIR)/xfont$(VERSION).tgz \
              $(RELEASEDIR)/xserv$(VERSION).tgz \
              $(RELEASEDIR)/xshare$(VERSION).tgz

FONTCONFIG_CONFIGS=src/configs/20-hinting-slight.conf \
                   src/configs/20-monospace-lcd-filter.conf

.PHONY: clean

all: build/root.tar.xz

build/root.tar.xz: $(BASE_SETS) $(XENOCARA_SETS) $(FONTCONFIG_CONFIGS)
	doas rm -rf build/root
	mkdir build/root
	for tarball in $(RELEASEDIR)/*.tgz; do doas tar -C build/root -xzf "$$tarball"; done
	for kern in bsd.rd bsd.mp; do doas install -g wheel -m644 $(RELEASEDIR)/$$kern ./build/root/; done
	doas ln build/root/bsd.mp build/root/bsd
	doas install -m644 -g bin $(FONTCONFIG_CONFIGS) build/root/etc/fonts/conf.avail/
	for conf in $(FONTCONFIG_CONFIGS); do \
	    conf=`basename $$conf` \
	    doas ln -s ../conf.avail/$$conf build/root/etc/fonts/conf.d; done
	doas install -m644 -g wheel src/profile build/root/etc/

	doas tar -C build/root -cf - . | xz > $@

build/.system-built:
	rm -rf build
	mkdir build
	doas rm -rf /usr/obj/*
	cd /usr/src && git reset --hard && doas git clean -xfd && make obj
	cd /usr/src/etc && doas env DESTDIR=/ make distrib-dirs
	cd /usr/src && make build -j${MAKE_JOBS}
	touch $@

$(BASE_SETS): build/.system-built
	export DESTDIR="${DESTDIR}" RELEASEDIR="${RELEASEDIR}" && \
	    doas rm -rf "${DESTDIR}" "${RELEASEDIR}" && \
	    doas mkdir -p "${DESTDIR}" "${RELEASEDIR}" && \
	    cd /usr/src/etc && doas make release && \
	    cd /usr/src/distrib/sets && doas sh checkflist

build/.xenocara-built: build/.system-built
	doas rm -rf /usr/xobj/*
	cd /usr/xenocara && make bootstrap && make obj && make build -j${MAKE_JOBS}
	touch $@

$(XENOCARA_SETS): build/.xenocara-built
	export DESTDIR="${DESTDIR}" RELEASEDIR="${RELEASEDIR}" && \
	    cd /usr/xenocara && doas make release

clean:
	rm -fr build/* build/.*
