#!/usr/bin/env python3.4
import urllib.request
import re
import random
from typing import Dict, List, Tuple


class FtpList:
    host = 'http://129.128.5.191/cgi-bin/ftplist.cgi'

    def __init__(self, raw_text: str, ftp_servers: List[Tuple[str, str]], aux_data: Dict[str, str]) -> None:
        self._raw_text = raw_text
        self.ftp_servers = ftp_servers
        self.aux_data = aux_data

    @property
    def mirrors(self) -> str:
        """Return a colon-delimited list of a few appropriate mirrors."""
        return ':'.join(['{}/%c/packages/%a'.format(x[0]) for x in self.ftp_servers])

    @property
    def tz(self) -> str:
        """Return the current timezone as determined by the host. If no
           timezone was provided, then return an empty string."""
        try:
            return self['TZ']
        except KeyError:
            return ''

    @property
    def raw_text(self) -> str:
        """Return the raw text of the host's response."""
        return self._raw_text

    def __getitem__(self, key: str) -> str:
        """Return a given key's value from the host's response."""
        return self.aux_data[key]

    @classmethod
    def empty(cls) -> 'FtpList':
        """Return an empty FtpList data set, useful as a fallback."""
        return cls('', [('http://ftp5.usa.openbsd.org/pub/OpenBSD', 'Redwood City, CA, USA'),
                        ('http://mirrors.sonic.net/pub/OpenBSD', 'San Francisco, CA, USA')], {})

    @classmethod
    def load(cls):
        """Request ftplist information from the remote host."""
        raw_text = ''
        ftp_servers = []
        aux_data = {}

        with urllib.request.urlopen(cls.host) as f:
            raw_text = str(f.read(), 'utf-8')
            for field in re.finditer(r'^(https?://\S+)\s+([^\n]*)$', raw_text, re.MULTILINE):
                ftp_servers.append((field.group(1), field.group(2)))

            for field in re.finditer(r'^([A-Z_]+)=([^\n]+)$', raw_text, re.MULTILINE):
                aux_data[field.group(1)] = field.group(2)

        if len(ftp_servers) > 2:
            ftp_servers = ftp_servers[:2]

        return cls(raw_text, ftp_servers, aux_data)
