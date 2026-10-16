"""Download only solar units, their EEG records and lookup tables from the official MaStR ZIP."""
import argparse
import gzip
import io
import json
import shutil
import time
import urllib.request
from pathlib import Path
from zipfile import ZipFile

if __package__ in (None, ''):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project_paths import RAW

DEFAULT_URL = 'https://download.marktstammdatenregister.de/Gesamtdatenexport_20261013_26.2.zip'


class RemoteZip(io.RawIOBase):
    """Seekable HTTP Range reader with one cached block; never loads the full ZIP."""
    def __init__(self, url):
        self.url = url
        self.position = 0
        self.start = -1
        self.block = b''
        response = self.request('bytes=-65536')
        self.size = int(response.headers['Content-Range'].split('/')[-1])
        self.block = response.read()
        self.start = self.size - len(self.block)

    def request(self, byte_range):
        for attempt in range(4):
            try:
                response = urllib.request.urlopen(urllib.request.Request(
                    self.url, headers={'Range': byte_range, 'Accept-Encoding': 'identity'}), timeout=90)
                if response.status != 206:
                    response.close()
                    raise RuntimeError('Server did not honor HTTP Range; refusing a full download')
                return response
            except (OSError, TimeoutError):
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        return self.position

    def read(self, size=-1):
        size = min(self.size-self.position, size if size >= 0 else self.size-self.position)
        pieces = []
        while size > 0:
            if not self.start <= self.position < self.start + len(self.block):
                self.start = self.position
                end = min(self.size-1, self.start + max(size, 4*1024*1024)-1)
                with self.request(f'bytes={self.start}-{end}') as response:
                    self.block = response.read()
                if len(self.block) != end-self.start+1:
                    raise IOError('Incomplete HTTP Range response')
            offset = self.position-self.start
            count = min(size, len(self.block)-offset)
            pieces.append(self.block[offset:offset+count])
            self.position += count
            size -= count
        return b''.join(pieces)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=DEFAULT_URL)
    parser.add_argument('--list-only', action='store_true')
    args = parser.parse_args()
    folder = RAW / 'mastr' / Path(args.url).stem
    with RemoteZip(args.url) as remote, ZipFile(remote) as archive:
        selected = [entry for entry in archive.infolist() if
                    Path(entry.filename).name.startswith(('EinheitenSolar', 'AnlagenEegSolar', 'Katalogwerte', 'Katalogkategorien'))
                    and entry.filename.lower().endswith('.xml')]
        if not selected:
            raise RuntimeError('No solar records found')
        print(f'{len(selected)} files; {sum(e.compress_size for e in selected)/1e6:.1f} MB compressed', flush=True)
        if args.list_only:
            for entry in selected:
                print(entry.filename, entry.compress_size, flush=True)
            return
        folder.mkdir(parents=True, exist_ok=True)
        manifest = {'source_url': args.url, 'archive_bytes': remote.size,
                    'files': [{'name': e.filename, 'crc32': e.CRC, 'bytes': e.file_size} for e in selected]}
        for index, entry in enumerate(selected, 1):
            target = folder / (Path(entry.filename).name + '.gz')
            if target.exists():
                print('Already downloaded:', target.name, flush=True)
                continue
            temporary = target.with_suffix('.part')
            print(f'[{index}/{len(selected)}] {entry.filename}', flush=True)
            with archive.open(entry) as source, gzip.open(temporary, 'wb', compresslevel=1) as destination:
                shutil.copyfileobj(source, destination, length=1024*1024)
            temporary.replace(target)
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print('Download complete:', folder, flush=True)


if __name__ == '__main__':
    main()
