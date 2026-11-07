from dataclasses import dataclass
from pathlib import Path

EXTENSIONS = {
    "Images": "jpg jpeg png gif webp bmp svg heic heif tif tiff avif raw dng ico",
    "Documents": "pdf txt md doc docx xls xlsx ppt pptx csv tsv odt rtf epub ods odp",
    "Videos": "mp4 mov mkv avi wmv webm m4v mpg mpeg",
    "Audio": "mp3 wav flac m4a ogg aac aiff opus wma",
    "Archives": "zip 7z rar gz bz2 xz tar tgz",
    "Code": "py js ts jsx tsx java c h cpp hpp cs go rs rb php html css json xml yaml yml toml sql ps1 sh",
    "Installers": "exe msi msix appx msp msixbundle",
    "Other": "",
}
BY_SUFFIX = {ext: name for name, exts in EXTENSIONS.items() for ext in exts.split()}


def category(name):
    return BY_SUFFIX.get(Path(name).suffix.lower()[1:], "Other")


@dataclass(frozen=True)
class Entry:
    name: str
    size: int
    mtime: int
    device: int
    inode: int

    @classmethod
    def from_stat(cls, name, info):
        return cls(name, info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino)

    @property
    def group(self):
        return category(self.name)


@dataclass(frozen=True)
class Move:
    entry: Entry
    target: str


@dataclass
class Scan:
    root: Path
    root_id: tuple[int, int]
    files: list[Entry]
    issues: list[str]
    drive_free: int | None = None


def readable_size(value):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:,} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024

