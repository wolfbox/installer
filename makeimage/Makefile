MIRROR=ftp://ftp5.usa.openbsd.org/pub/OpenBSD/snapshots/amd64
ARCHIVES=base59.tgz man59.tgz xbase59.tgz xfont59.tgz xserv59.tgz xshare59.tgz comp59.tgz

FONTCONFIG_CONFIGS=configs/20-hinting-slight.conf \
                   configs/20-monospace-lcd-filter.conf

.PHONY: clean

image.tar.gz: root
	cd root && tar -czf ../$@ .

root: $(ARCHIVES) bsd.mp bsd.rd SHA256.sig
	signify -C -p /etc/signify/openbsd-59-base.pub -x SHA256.sig -q || true

	if [ `id -u` != 0 ]; then echo "Must extract as root"; false; fi
	rm -rf root
	mkdir root
	cd root && for a in $(ARCHIVES); do tar xpzf ../$$a; done

	# Install our kernels
	install -m644 -o root -g wheel bsd.rd root/
	install -m644 -o root -g wheel bsd.mp root/bsd

	# Put in our own config files
	install -m644 -g bin $(FONTCONFIG_CONFIGS) root/etc/fonts/conf.avail/
	install -m644 -g bin $(FONTCONFIG_CONFIGS) root/etc/fonts/conf.d/
	install -m644 -g wheel profile root/etc/

	# Set up for our read-only root
	cd root && mv home var/ && ln -s var/home home
	cd root/usr && mkdir ../var/usr && mv local ../var/usr && ln -s ../var/usr/local local
	cd root && rm var/tmp && mv tmp var/ && ln -s var/tmp tmp

$(ARCHIVES) bsd.mp bsd.rd SHA256.sig:
	if [ `id -u` = 0 ]; then echo "Don't download as root"; false; fi
	ftp $(MIRROR)/$@

clean:
	rm -rf root
