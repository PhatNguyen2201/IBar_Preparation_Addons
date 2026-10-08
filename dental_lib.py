bl_info = {
    "name": "Dental-Lib",
    "author": "Phat Nguyen",
    "version": (0, 4, 0),
    "blender": (4, 5, 3),
    "location": "View3D > Sidebar > Dental-Lib",
    "description": "Thu vien Connection Base (Implant Connection) va Attachment cho Rmvb-Bar",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}

"""Dental-Lib
============
Quan ly thu vien dung chung cho cac add-on nha khoa:

1. Implant Connection (Connection Base): Library Name, Base, Implant-Analog,
   Screw (moi slot 1 file STL/PLY), Scanbody (NHIEU file STL/PLY, ke ca
   cua nhom lan cua tung Connection).
2. Attachment: Attachment Name, Apply Part Bar (hang tren) + toggle
   Add/Remove on Bar cung hang voi nut 'Gan file', tuong tu cho Apply Part
   Sleeve (Add = Union, Remove = Difference khi Rmvb-Bar ap vao Bar / Sleeve),
   Visual Object (khong gioi han so luong, dat ten va CHON MAU tung
   object).
   Mac dinh khi dat vao scene:
     - Apply Part Bar   : do, alpha 0.5
     - Apply Part Sleeve: hong, alpha 0.5
     - Visual Object    : mau chon trong panel (mac dinh xam nhat)
   Color cua Part Bar/Sleeve duoc luu trong library.json (khong hien o chon
   mau tren panel), color cua Visual Object luu theo tung object.

Du luu ben vung trong <lib_dir>/library.json; asset duoc copy vao
<lib_dir>/connections/<Name>/ va <lib_dir>/attachments/<Name>/ de thu vien
chuyen duoc giua may. Add-on khac (Rmvb-Bar) truy cap qua API module:
    import dental_lib
    dental_lib.connection_names() / connection_list() / get_connection(name, group)
    dental_lib.attachment_names() / attachment_list() / get_attachment(name, group)
Ten muc KHONG duoc dam bao duy nhat (hai Connection / Attachment o hai nhom khac
nhau co the trung ten), nen moi ham tra cuu deu nhan them `group`:
    group=None  : khong loc nhom -> muc dau tien co ten trung (thu vien cu)
    group=""    : muc chua nhom
    group="X"   : muc thuoc nhom X; khong thay thi quay ve theo ten
"""

import bpy
import os
import json
import re
import shutil

from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatVectorProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup
from bpy_extras.io_utils import ImportHelper

LIB_DIR_DEFAULT = os.path.join(os.path.expanduser("~"), "Documents", "Dental-Lib")
INDEX_NAME = "library.json"
MESH_EXTS = (".stl", ".ply")

# ---------------------------------------------------------------------------
# Mau mac dinh (RGBA 0..1) - luu ben vung trong library.json
# ---------------------------------------------------------------------------
DEFAULT_VISUAL_COLOR = (0.75, 0.75, 0.80, 1.00)      # xam nhat (nhu cu)
DEFAULT_PART_BAR_COLOR = (1.00, 0.00, 0.00, 0.50)    # do, alpha 0.5
DEFAULT_PART_SLEEVE_COLOR = (1.00, 0.45, 0.72, 0.50)  # hong, alpha 0.5

SLOT_DEFAULT_COLOR = {
    "part_bar": DEFAULT_PART_BAR_COLOR,
    "part_sleeve": DEFAULT_PART_SLEEVE_COLOR,
}
# Ten truong mau cua AttachmentEntry theo tung slot
SLOT_COLOR_FIELD = {
    "part_bar": "part_bar_color",
    "part_sleeve": "part_sleeve_color",
}

_INDEX_CACHE = {"path": None, "mtime": None, "data": None}

_ICON_NAMES = None
_ICON_WARNED = set()


def _ic(name):
    """Tra ve ten icon hop le dung cho UILayout.

    Blender abort TOAN BO draw() callback neu gap icon khong ton tai
    (TypeError: enum "..." not found) -> moi widget phia sau bi mat hang
    loat. Ham nay kiem tra enum that va thay bang 'NONE' cho an toan.
    """
    global _ICON_NAMES
    if _ICON_NAMES is None:
        items = set()
        try:
            for func in bpy.types.UILayout.bl_rna.functions.values():
                for pname, prop in func.parameters.items():
                    if pname == "icon" and hasattr(prop, "enum_items"):
                        items.update(i.identifier for i in prop.enum_items)
        except Exception as exc:
            print(f"[Dental-Lib] Khong doc duoc danh sach icon: {exc}")
        _ICON_NAMES = items
    if not name:
        return "NONE"
    if not _ICON_NAMES or name in _ICON_NAMES:
        return name
    if name not in _ICON_WARNED:
        _ICON_WARNED.add(name)
        print(f"[Dental-Lib] Icon khong ton tai: {name} -> dung NONE")
    return "NONE"


# ---------------------------------------------------------------------------
# Layer luu tru (JSON + thu muc asset)
# ---------------------------------------------------------------------------
def _prefs():
    try:
        return bpy.context.preferences.addons[__name__].preferences
    except Exception:
        return None


def library_dir():
    pref = _prefs()
    folder = ""
    if pref is not None and getattr(pref, "lib_dir", ""):
        folder = bpy.path.abspath(pref.lib_dir)
    return folder or LIB_DIR_DEFAULT


def index_path():
    return os.path.join(library_dir(), INDEX_NAME)


def ensure_library_dir():
    root = library_dir()
    for sub in ("connections", "attachments"):
        try:
            os.makedirs(os.path.join(root, sub), exist_ok=True)
        except Exception as exc:
            print(f"[Dental-Lib] Khong tao duoc {sub}: {exc}")
    if not os.path.exists(index_path()):
        write_index(empty_index())
    return root


def empty_index():
    return {"version": 1, "connections": [], "connection_groups": [], "attachments": [],
            "attachment_groups": []}


def invalidate_cache():
    """Xoa bo nho dem library.json (dung khi doi thu muc thu vien hoac khi test).

    read_index() da tu kiem tra theo duong dan + mtime nen chi can goi ham nay
    khi muon buoc doc lai du lieu tu dia.
    """
    _INDEX_CACHE.update(path=None, mtime=None, data=None)


def read_index(use_cache=True):
    path = index_path()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return empty_index()
    data = _INDEX_CACHE["data"]
    if (use_cache and data is not None and _INDEX_CACHE["path"] == path
            and _INDEX_CACHE["mtime"] == mtime):
        return data
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        print(f"[Dental-Lib] Khong doc duoc library.json: {exc}")
        return empty_index()
    if not isinstance(data, dict):
        return empty_index()
    data.setdefault("version", 1)
    data.setdefault("connections", [])
    data.setdefault("connection_groups", [])
    data.setdefault("attachment_groups", [])
    data.setdefault("attachments", [])
    _INDEX_CACHE.update(path=path, mtime=mtime, data=data)
    return data


def write_index(data):
    """Ghi dict ra <lib_dir>/library.json (atomic + giu 1 ban .bak) va lam moi cache."""
    root = library_dir()
    os.makedirs(root, exist_ok=True)
    path = index_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    try:
        if os.path.exists(path):
            shutil.copy2(path, path + ".bak")
    except OSError as exc:
        print(f"[Dental-Lib] Khong tao duoc backup library.json.bak: {exc}")
    os.replace(tmp, path)
    _INDEX_CACHE.update(path=path, mtime=os.path.getmtime(path), data=data)
    return data


def slugify(text):
    text = (text or "").strip()
    text = re.sub(r"[^\w\-. ]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text)
    return text or "entry"


KIND_DIRS = ("connections", "attachments")


def _norm(path):
    return os.path.normcase(os.path.normpath(path))


def _library_path(rel):
    return os.path.join(library_dir(), *rel.replace("\\", "/").split("/"))


def _rel_folder(rel):
    """(loai, thu muc) neu `rel` la duong dan tuong doi nam trong thu vien (connections|attachments/<thu muc>/...),
    nguoc lai None (duong dan tuyet doi tro ra ngoai, rong...)."""
    if not rel or os.path.isabs(rel):
        return None
    parts = rel.replace("\\", "/").split("/")
    if len(parts) >= 3 and parts[0] in KIND_DIRS and parts[1]:
        return parts[0], parts[1]
    return None


def _same_entry(a, b):
    return a is not None and b is not None and a.as_pointer() == b.as_pointer()


# Stem cua file danh so tu dong (nhieu file cung loai): '<ten>_NN' - Visual Object cua Attachment, Scanbody cua Connection
AUTO_VISUAL = "visual#"
AUTO_SCANBODY = "scanbody#"


def _auto_family(stem):
    """'visual' | 'scanbody' neu `stem` la stem danh so tu dong, nguoc lai None (slot co ten co dinh)."""
    return stem[:-1] if stem and stem.endswith("#") else None


def _entry_asset_refs(kind, entry):
    """[(stem, rel hien tai, setter)] moi file 3D cua entry. stem AUTO_* = file danh so tu dong (ten tu cap)."""
    refs = []
    if kind == "connections":
        for slot, field in CONNECTION_SLOT_FIELD.items():
            refs.append((slot, getattr(entry, field), lambda v, f=field: setattr(entry, f, v)))
        for row in entry.scanbodies:
            refs.append((AUTO_SCANBODY, row.asset, lambda v, r=row: setattr(r, "asset", v)))
    else:
        for field in ("part_bar", "part_sleeve"):
            refs.append((field, getattr(entry, field), lambda v, f=field: setattr(entry, f, v)))
        for row in entry.visuals:
            refs.append((AUTO_VISUAL, row.asset, lambda v, r=row: setattr(r, "asset", v)))
    return refs


def _folder_in_use(kind, folder, entries, exclude=None):
    key = _norm(folder)
    for other in entries:
        if not _same_entry(other, exclude) and other.folder and _norm(other.folder) == key:
            return True
    return os.path.exists(os.path.join(library_dir(), kind, folder))


def unique_folder(kind, name, entries, exclude=None):
    """Ten thu muc rieng cua mot entry: slug cua ten, them _2, _3... neu da co entry khac dung hoac da co
    thu muc cung ten tren dia (khong bao gio dung chung / lan voi file cua entry khac)."""
    base = slugify(name)
    for index in range(1, 10000):
        folder = base if index == 1 else "%s_%d" % (base, index)
        if not _folder_in_use(kind, folder, entries, exclude):
            return folder
    raise RuntimeError("Khong tao duoc ten thu muc cho '%s'" % name)


def _free_auto_stem(folder_abs, entry, family, prefix="", taken=()):
    """'<family>_NN' (visual | scanbody) chua dung trong thu muc (ten file co tien to `prefix`) va chua nam
    trong `taken`."""
    used = set(taken)
    try:
        for name in os.listdir(folder_abs):
            base = os.path.splitext(name)[0]
            if base.startswith(prefix):
                used.add(base[len(prefix):])
    except OSError:
        pass
    for row in (entry.visuals if family == "visual" else entry.scanbodies):
        if row.asset:
            base = os.path.splitext(os.path.basename(row.asset.replace("\\", "/")))[0]
            if base.startswith(prefix):
                used.add(base[len(prefix):])
    index = 0
    while "%s_%02d" % (family, index) in used:
        index += 1
    return "%s_%02d" % (family, index)


def _group_def_of(entry, library):
    """Nhom chua `entry` (Connection -> nhom Implant Connection, Attachment -> nhom Attachment); None neu
    chua nhom. Moi nhom co thu muc chung trong thu vien, file cua cac thanh vien nam phang trong do."""
    if library is None or not hasattr(entry, "group"):
        return None
    name = entry.group.strip()
    if not name:
        return None
    if hasattr(entry, "slot_base"):
        return _find_connection_group(library, name)
    if hasattr(entry, "visuals"):
        return _find_attachment_group(library, name)
    return None


def _location(kind, entry, library=None):
    """(thu muc, tien to ten file) noi chua file RIENG cua entry.

    Entry thuoc nhom -> thu muc cua nhom (phang), ten file co tien to '<thu muc cua entry>_';
    nguoc lai thu muc rieng cua entry, khong tien to."""
    gdef = _group_def_of(entry, library)
    if gdef is not None and gdef.folder and entry.folder:
        return gdef.folder, entry.folder + "_"
    return entry.folder, ""


def _is_own_file(kind, entry, stem, rel):
    """`rel` la file RIENG cua entry: nam trong thu muc rieng cua entry, hoac la file '<thu muc entry>_<stem>'
    (Visual Object / Scanbody: '<thu muc entry>_visual_NN' / '_scanbody_NN') trong thu muc nhom."""
    found = _rel_folder(rel)
    if not found or found[0] != kind or not entry.folder:
        return False
    if _norm(found[1]) == _norm(entry.folder):
        return True
    base = os.path.splitext(os.path.basename(rel.replace("\\", "/")))[0]
    family = _auto_family(stem)
    if family:
        return re.fullmatch(re.escape(entry.folder) + "_" + family + r"_\d+", base) is not None
    return base == entry.folder + "_" + stem


def _place_file(kind, entry, folder, source, stem, current_rel, prefix=""):
    """Copy `source` vao <lib>/<kind>/<folder>/<prefix><stem><ext> (ghi de neu da co) va tra ve rel.

    stem AUTO_* (Visual Object / Scanbody): dung lai ten file hien tai neu no da nam trong thu muc cua entry,
    khong thi lay '<visual|scanbody>_NN' chua dung. File cu cua cung slot (khac duoi file) cua entry bi xoa."""
    folder_abs = os.path.join(library_dir(), kind, folder)
    os.makedirs(folder_abs, exist_ok=True)
    ext = os.path.splitext(source)[1].lower()
    if ext not in MESH_EXTS:
        ext = ".stl"
    current = _rel_folder(current_rel)
    inside = bool(current) and current[0] == kind and _norm(current[1]) == _norm(folder)
    if inside and prefix:
        inside = os.path.basename(current_rel.replace("\\", "/")).startswith(prefix)
    family = _auto_family(stem)
    if family:
        if inside:
            stem = os.path.splitext(os.path.basename(current_rel.replace("\\", "/")))[0][len(prefix):]
        else:
            stem = _free_auto_stem(folder_abs, entry, family, prefix)
    name = prefix + stem
    dest = os.path.join(folder_abs, name + ext)
    if not (os.path.exists(dest) and os.path.samefile(source, dest)):
        shutil.copy2(source, dest)
    if inside:
        old = _library_path(current_rel)
        if os.path.exists(old) and _norm(old) != _norm(dest):
            try:
                os.remove(old)
            except OSError as exc:
                print(f"[Dental-Lib] Khong xoa duoc file cu {old}: {exc}")
    return "/".join((kind, folder, name + ext))


def ensure_entry_folder(kind, entry, entries, skip_rel="", library=None):
    """Ten thu muc rieng cua entry (chua co thi chon ten; chua tao thu muc tren dia cho den khi co file).
    Connection thuoc nhom thi `folder` chi la ten dinh danh / tien to ten file (file nam trong thu muc nhom).

    Entry cu (khong co folder): neu moi file da nam chung 1 thu muc trong thu vien va chua entry nao
    nhan thu muc do thi nhan luon (khong copy; khong ap dung cho entry thuoc nhom); nguoc lai chon ten
    moi va COPY cac file con lai vao do (file cu giu nguyen). `skip_rel` = file sap bi thay nen khong can copy."""
    if entry.folder:
        return entry.folder
    refs = [(stem, rel, setter) for stem, rel, setter in _entry_asset_refs(kind, entry) if rel]
    grouped = _group_def_of(entry, library) is not None
    found = {_rel_folder(rel) for _stem, rel, _set in refs}
    if not grouped and len(found) == 1:
        only = next(iter(found))
        if only and only[0] == kind and not any(
                other.folder and _norm(other.folder) == _norm(only[1])
                for other in entries if not _same_entry(other, entry)):
            entry.folder = only[1]
            return entry.folder
    entry.folder = unique_folder(kind, entry.entry_name, entries, exclude=entry)
    folder, prefix = _location(kind, entry, library)
    for stem, rel, setter in refs:
        if rel == skip_rel:
            continue
        current = _rel_folder(rel)
        if _is_own_file(kind, entry, stem, rel) or (
                current and current[0] == kind and _norm(current[1]) == _norm(folder) and not prefix):
            continue
        source = resolve_asset(rel)
        if source and os.path.isfile(source):
            setter(_place_file(kind, entry, folder, source, stem, "", prefix))
    return entry.folder


def store_entry_asset(kind, entry, entries, source, stem, get_current, library=None):
    """Gan file mesh `source` vao slot cua entry: file luon nam trong thu muc rieng cua entry (hoac thu muc nhom
    neu Connection thuoc nhom), tra ve rel. stem = ten slot (vd. 'base', 'part_bar') hoac None cho Visual
    Object; get_current() = rel dang gan."""
    ensure_library_dir()
    ensure_entry_folder(kind, entry, entries, skip_rel=get_current(), library=library)
    folder, prefix = _location(kind, entry, library)
    return _place_file(kind, entry, folder, source, stem, get_current(), prefix)


def _rewrite_folder_refs(kind, owner, old, new):
    """Sua moi duong dan cua `owner` dang tro vao <kind>/<old>/... thanh <kind>/<new>/..."""
    for _stem, rel, setter in _entry_asset_refs(kind, owner):
        found = _rel_folder(rel)
        if found and found[0] == kind and _norm(found[1]) == _norm(old):
            rest = rel.replace("\\", "/").split("/")[2:]
            setter("/".join([kind, new] + rest))


def rename_entry_folder(kind, entry, entries, library=None, extra=()):
    """Entry doi ten -> doi ten thu muc theo va sua moi duong dan file (ke ca cua cac owner trong `extra`, vd.
    cac Connection trong nhom khi nhom doi ten). Connection thuoc nhom khong co thu muc rieng: doi tien to ten
    file trong thu muc nhom. That bai thi giu nguyen (file van cung mot cho)."""
    old = entry.folder
    if not old:
        return False
    base = slugify(entry.entry_name)
    if base == old:
        return False
    if _norm(base) == _norm(old):                         # chi doi hoa / thuong
        new = base
    else:
        new = unique_folder(kind, entry.entry_name, entries, exclude=entry)
    folder, prefix = _location(kind, entry, library)
    if prefix:
        plan = []
        for stem, rel, setter in _entry_asset_refs(kind, entry):
            if rel and _is_own_file(kind, entry, stem, rel):
                src = _library_path(rel)
                if os.path.isfile(src):
                    base = os.path.splitext(os.path.basename(src))[0]
                    tail = base[len(old) + 1:] if _auto_family(stem) else stem
                    dest_rel = "/".join((kind, folder, new + "_" + tail + os.path.splitext(src)[1]))
                    plan.append((src, _library_path(dest_rel), dest_rel, setter))
        try:
            for src, dest, _rel, _set in plan:
                os.replace(src, dest)
        except OSError as exc:
            print(f"[Dental-Lib] Khong doi ten file cua '{old}' -> '{new}': {exc}")
            return False
        entry.folder = new
        for _src, _dest, dest_rel, setter in plan:
            setter(dest_rel)
        return True
    old_abs, new_abs = (os.path.join(library_dir(), kind, f) for f in (old, new))
    try:
        if os.path.isdir(old_abs):
            os.rename(old_abs, new_abs)
    except OSError as exc:
        print(f"[Dental-Lib] Khong doi ten thu muc '{old}' -> '{new}': {exc}")
        return False
    entry.folder = new
    for owner in (entry,) + tuple(extra):
        _rewrite_folder_refs(kind, owner, old, new)
    return True


def relocate_entry_files(kind, entry, library):
    """Dua file RIENG cua entry (ke ca Visual Object / Scanbody) ve dung cho theo nhom hien tai: entry thuoc nhom -> thu muc cua
    nhom (ten file co tien to '<thu muc entry>_'), khong thuoc nhom -> thu muc rieng. File cua chinh entry thi DI
    CHUYEN (thu muc cu rong thi go), file tu noi khac (cu / ngoai thu vien) thi COPY. Tra ve so file da dua ve cho."""
    refs = [(stem, rel, setter) for stem, rel, setter in _entry_asset_refs(kind, entry) if rel]
    if not refs:
        return 0
    if not entry.folder:
        entries = _connection_entries(library) if kind == "connections" else _attachment_entries(library)
        entry.folder = unique_folder(kind, entry.entry_name, entries, exclude=entry)
    folder, prefix = _location(kind, entry, library)
    folder_abs = os.path.join(library_dir(), kind, folder)
    done = 0
    old_dirs = set()
    taken = set()                                # ten (khong duoi file) da dung cho Visual Object / Scanbody trong luot nay
    for stem, rel, setter in refs:
        source = resolve_asset(rel)
        if not source or not os.path.isfile(source):
            continue
        ext = os.path.splitext(source)[1].lower() or ".stl"
        family = _auto_family(stem)
        if family:
            found = re.search(r"(%s_\d+)$" % family, os.path.splitext(os.path.basename(source))[0])
            use = found.group(1) if found else None
            if use is None or use in taken:
                use = _free_auto_stem(folder_abs, entry, family, prefix, taken)
            taken.add(use)
        else:
            use = stem
        dest_rel = "/".join((kind, folder, prefix + use + ext))
        dest = _library_path(dest_rel)
        if _norm(dest) == _norm(source):
            continue
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if _is_own_file(kind, entry, stem, rel):
                try:
                    os.replace(source, dest)
                except OSError:
                    shutil.copy2(source, dest)
                    os.remove(source)
                old_dirs.add(os.path.dirname(source))
            else:
                shutil.copy2(source, dest)
        except OSError as exc:
            print(f"[Dental-Lib] Khong dua duoc file '{rel}' ve '{dest_rel}': {exc}")
            continue
        setter(dest_rel)
        done += 1
    for directory in old_dirs:
        try:
            os.rmdir(directory)              # chi go duoc khi da rong
        except OSError:
            pass
    return done


def gather_connection_group_files(context):
    """Gom file rieng cua moi Connection thuoc nhom vao thu muc cua nhom (di chuyen, sua duong dan, ghi
    library.json). Chay lai nhieu lan khong doi gi them. Tra ve so file da gom."""
    library = _lib_group(context)
    moved = 0
    for entry in library.connections:
        if entry.group.strip():
            moved += relocate_entry_files("connections", entry, library)
    if moved:
        _save_all(context)
    return moved


def gather_attachment_group_files(context):
    """Nhu gather_connection_group_files nhung cho Attachment (ke ca Visual Object); bo nhom Attachment khong con
    thanh vien. Tra ve so file da gom."""
    library = _lib_group(context)
    moved = 0
    for entry in library.attachments:
        if entry.group.strip():
            moved += relocate_entry_files("attachments", entry, library)
    pruned = prune_attachment_groups(library)
    if moved or pruned:
        _save_all(context)
    return moved


def gather_group_files(context):
    """Gom file cua Connection va Attachment thuoc nhom vao thu muc cua nhom. Tra ve tong so file da gom."""
    return gather_connection_group_files(context) + gather_attachment_group_files(context)


def resolve_asset(ref):
    """Duong dan tuyet doi cua asset (tuong doi trong lib hoac tuyet doi)."""
    if not ref:
        return ""
    path = bpy.path.abspath(ref)
    if os.path.isabs(path) and os.path.exists(path):
        return path
    candidate = os.path.normpath(os.path.join(library_dir(), ref))
    if os.path.exists(candidate):
        return candidate
    return path


# ---------------------------------------------------------------------------
# API cho add-on khac (Rmvb-Bar)
#   Moi muc duoc nhan dien bang cap (ten nhom, ten muc): thu vien cho phep hai
#   muc o hai nhom khac nhau trung ten, nen loc theo ten khong thi du.
# ---------------------------------------------------------------------------
def _entry_group(entry):
    return str(entry.get("group", "") or "").strip()


def _find_entry(entries, name, group=None):
    """Muc co ten `name`; `group` = loc theo ten nhom (None: bo qua nhom).

    Dat `group` thi uu tien khop dung (nhom, ten); neu khong thay (nhom bi doi
    ten / xoa, file .blend luu nhom cu) thi quay ve khop theo ten."""
    if group is not None:
        for entry in entries:
            if entry.get("name") == name and _entry_group(entry) == group:
                return entry
    for entry in entries:
        if entry.get("name") == name:
            return entry
    return None


def connection_names():
    return [c.get("name", "") for c in read_index()["connections"] if c.get("name")]


def connection_list():
    """[(ten nhom, ten Connection), ...] theo thu tu thu vien; vi tri trong danh
    sach la chi so dung chung voi menus cua add-on khac (Rmvb-Bar)."""
    return [(_entry_group(c), c.get("name", ""))
            for c in read_index()["connections"] if c.get("name")]


def get_connection(name, group=None):
    """Muc Connection theo ten; `group` duoc cung cap thi khop dung nhom truoc,
    de ten trung o nhom khac khong bi resolve ve muc dau tien."""
    return _find_entry(read_index()["connections"], name, group)


def connection_group(name):
    """Ten nhom cua Connection ("" = chua nhom)."""
    entry = get_connection(name)
    return _entry_group(entry) if entry else ""


def _scanbody_refs(item):
    """Danh sach duong dan Scanbody luu trong 1 muc JSON (Connection / nhom). Thu vien cu chi co khoa
    'scanbody' (1 file) thi coi la danh sach 1 phan tu."""
    refs = item.get("scanbodies")
    if not isinstance(refs, list):
        refs = [item.get("scanbody", "")]
    return [str(ref) for ref in refs if ref]


def connection_scanbodies(name, group=None):
    """[duong dan tuyet doi, ...] cac file Scanbody cua Connection: danh sach rieng neu co, khong thi danh sach
    chung cua nhom (ke thua). Phan tu co the tro toi file khong con tren dia."""
    entry = get_connection(name, group)
    if not entry:
        return []
    refs = _scanbody_refs(entry)
    group = _entry_group(entry)
    if not refs and group:
        for item in read_index().get("connection_groups", []):
            if item.get("name") == group:
                refs = _scanbody_refs(item)
    return [resolve_asset(ref) for ref in refs]


def connection_asset(name, slot, group=None):
    """File mesh cua mot thanh phan (base|analog|screw|scanbody): file rieng cua Connection neu co, khong
    thi file chung cua nhom ma Connection thuoc ve (ke thua). Scanbody co nhieu file: slot "scanbody" tra ve
    file dau tien, day du xem connection_scanbodies(). `group` chon dung muc khi thu vien co ten trung."""
    if slot == "scanbody":
        found = connection_scanbodies(name, group)
        return found[0] if found else ""
    entry = get_connection(name, group)
    if not entry:
        return ""
    own = entry.get(slot, "")
    if own:
        return resolve_asset(own)
    group = _entry_group(entry)
    if group:
        for item in read_index().get("connection_groups", []):
            if item.get("name") == group:
                return resolve_asset(item.get(slot, ""))
    return ""


def connection_groups():
    """[(ten nhom, [ten Connection, ...]), ...]: nhom dat ten theo ABC, "" (chua nhom) o cuoi; trong moi nhom
    giu thu tu thu vien. Chua co Connection nao thuoc nhom -> [("", tat ca)]."""
    return _grouped_names(read_index()["connections"])


def attachment_names():
    return [a.get("name", "") for a in read_index()["attachments"] if a.get("name")]


def attachment_list():
    """[(ten nhom, ten Attachment), ...] theo thu tu thu vien (chi so nhu attachment_names())."""
    return [(_entry_group(a), a.get("name", ""))
            for a in read_index()["attachments"] if a.get("name")]


def attachment_group(name):
    """Ten nhom cua Attachment ("" = chua nhom)."""
    entry = get_attachment(name)
    return _entry_group(entry) if entry else ""


def _grouped_names(entries):
    buckets = {}
    for entry in entries:
        if entry.get("name"):
            buckets.setdefault(str(entry.get("group", "") or "").strip(), []).append(entry["name"])
    out = [(key, buckets[key]) for key in sorted((k for k in buckets if k), key=str.casefold)]
    if "" in buckets:
        out.append(("", buckets[""]))
    return out


def attachment_groups():
    """[(ten nhom, [ten Attachment, ...]), ...]: nhom dat ten theo thu tu ABC, nhom "" (chua nhom)
    o cuoi; trong moi nhom giu thu tu trong thu vien. Chua co nhom nao -> [("", tat ca)]."""
    return _grouped_names(read_index()["attachments"])


def get_attachment(name, group=None):
    """Muc Attachment theo ten; `group` duoc cung cap thi khop dung nhom truoc."""
    return _find_entry(read_index()["attachments"], name, group)


def attachment_asset(name, slot, group=None):
    entry = get_attachment(name, group)
    if not entry:
        return ""
    return resolve_asset(entry.get(slot, ""))


def attachment_visuals(name, group=None):
    """[(label, abspath), ...] cac Visual Object cua Attachment."""
    entry = get_attachment(name, group)
    if not entry:
        return []
    out = []
    for visual in entry.get("visuals", []):
        out.append((visual.get("label") or "Visual",
                    resolve_asset(visual.get("asset", ""))))
    return out


def attachment_visuals_rgba(name, group=None):
    """[(label, abspath, (r, g, b, a)), ...] - Visual Object kem mau cua no."""
    entry = get_attachment(name, group)
    if not entry:
        return []
    out = []
    for visual in entry.get("visuals", []):
        out.append((visual.get("label") or "Visual",
                    resolve_asset(visual.get("asset", "")),
                    read_color(visual.get("color"), DEFAULT_VISUAL_COLOR)))
    return out


def attachment_slot_color(name, slot, group=None):
    """RGBA mac dinh/da luu cua Apply Part Bar | Apply Part Sleeve."""
    fallback = SLOT_DEFAULT_COLOR.get(slot, DEFAULT_VISUAL_COLOR)
    entry = get_attachment(name, group)
    if not entry:
        return tuple(fallback)
    return read_color(entry.get(SLOT_COLOR_FIELD.get(slot, ""), None), fallback)


def read_color(value, fallback=DEFAULT_VISUAL_COLOR):
    """Chuyen gia tri mau (list/tuple trong JSON, Vector/Color cua property)
    ve tuple RGBA (clip 0..1); tra ve fallback neu khong doc duoc 3 hoac 4 kenh.
    """
    if isinstance(value, str) or value is None:
        return tuple(fallback)
    try:
        comps = [float(c) for c in value]
    except (TypeError, ValueError):
        return tuple(fallback)
    if len(comps) == 3:
        comps.append(1.0)
    if len(comps) != 4:
        return tuple(fallback)
    return tuple(min(1.0, max(0.0, c)) for c in comps)


def write_color(value):
    """Chuyen property RGBA (Vector/Color/list) ve list 4 so nguyen mau JSON."""
    return [round(c, 4) for c in read_color(value)]


def mesh_slots_connection():
    return ("base", "analog", "screw", "scanbody")


def mesh_slots_attachment():
    return ("part_bar", "part_sleeve")


# ---------------------------------------------------------------------------
# PropertyGroup (buffer chinh sua noi bo - source of truth la library.json)
# ---------------------------------------------------------------------------
_SUPPRESS_AUTOSAVE = [False]


def _autosave(context):
    """Ghi library.json ngay khi gia tri property doi tren UI (o chon mau).

    Cac operator khac van goi _save_all(); rieng color picker khong qua
    operator nao nen can update callback de khong mat mau khi dong Blender.
    """
    if _SUPPRESS_AUTOSAVE[0]:
        return
    try:
        ctx = context if getattr(context, "scene", None) is not None else bpy.context
        if getattr(ctx, "scene", None) is None:
            return
        write_index(index_from_scene(ctx))
    except Exception as exc:
        print(f"[Dental-Lib] Khong luu duoc mau vao library.json: {exc}")


def _update_color(self, context):
    _autosave(context)


_GROUP_BUSY = [False]       # True: dang tu sua nhom bang code, bo qua update callback


def _connection_entries(library):
    """Moi muc co thu muc rieng trong connections/: Connection + nhom (de ten thu muc khong trung nhau)."""
    return list(library.connections) + list(library.connection_groups)


def _find_connection_group(library, name):
    for item in library.connection_groups:
        if item.entry_name == name:
            return item
    return None


def new_connection_group(library, name):
    """Them nhom Connection (bo file chung); chon san ten thu muc, chua tao tren dia."""
    item = library.connection_groups.add()
    item.entry_name = name          # update: prev_name rong -> chi ghi nho ten
    item.prev_name = name
    item.folder = unique_folder("connections", name, _connection_entries(library), exclude=item)
    return item


def _attachment_entries(library):
    """Moi muc co thu muc trong attachments/: Attachment + nhom Attachment (de ten thu muc khong trung nhau)."""
    return list(library.attachments) + list(library.attachment_groups)


def _find_attachment_group(library, name):
    for item in library.attachment_groups:
        if item.entry_name == name:
            return item
    return None


def new_attachment_group(library, name):
    """Them nhom Attachment (chi giu ten thu muc chung); chon san ten thu muc, chua tao tren dia."""
    item = library.attachment_groups.add()
    item.entry_name = name
    item.folder = unique_folder("attachments", name, _attachment_entries(library), exclude=item)
    return item


def prune_attachment_groups(library):
    """Bo nhom Attachment khong con thanh vien (go thu muc nhom neu da rong). Tra ve so nhom da bo."""
    used = {e.group.strip() for e in library.attachments if e.group.strip()}
    removed = 0
    for index in reversed(range(len(library.attachment_groups))):
        item = library.attachment_groups[index]
        if item.entry_name not in used:
            try:
                os.rmdir(os.path.join(library_dir(), "attachments", item.folder))
            except OSError:
                pass
            library.attachment_groups.remove(index)
            removed += 1
    return removed


def _att_member_group_update(self, context):
    """Doi nhom cua mot Attachment: go ten nhom chua co thi tu tao nhom (thu muc chung), file di chuyen theo."""
    if _SUPPRESS_AUTOSAVE[0] or _GROUP_BUSY[0]:
        return
    name = self.group.strip()
    if name != self.group:
        self.group = name
        return
    library = bpy.context.scene.dental_lib
    if name and _find_attachment_group(library, name) is None:
        new_attachment_group(library, name)
    try:
        relocate_entry_files("attachments", self, library)
    except Exception as exc:
        print(f"[Dental-Lib] Khong gom file cua '{self.entry_name}' theo nhom: {exc}")
    prune_attachment_groups(library)
    _autosave(context)


def _conn_member_group_update(self, context):
    """Doi nhom cua mot Connection: go ten nhom chua co thi tu tao nhom (de gan bo file chung)."""
    if _SUPPRESS_AUTOSAVE[0] or _GROUP_BUSY[0]:
        return
    name = self.group.strip()
    if name != self.group:
        self.group = name           # goi lai update voi ten da cat khoang trang
        return
    library = bpy.context.scene.dental_lib
    if name and _find_connection_group(library, name) is None:
        new_connection_group(library, name)
    try:
        relocate_entry_files("connections", self, library)       # vao / ra khoi nhom: file di chuyen theo
    except Exception as exc:
        print(f"[Dental-Lib] Khong gom file cua '{self.entry_name}' theo nhom: {exc}")
    _autosave(context)


def _conn_group_name_update(self, context):
    """Doi ten nhom: cac Connection trong nhom theo ten moi, thu muc chung doi ten theo; ten rong / trung
    nhom khac thi tra ve ten cu."""
    if _SUPPRESS_AUTOSAVE[0] or _GROUP_BUSY[0]:
        return
    library = bpy.context.scene.dental_lib
    old, new = self.prev_name, self.entry_name.strip()
    if not old:
        self.prev_name = new
        return
    if new == old and self.entry_name == new:
        return
    clash = any(item.entry_name == new and not _same_entry(item, self) for item in library.connection_groups)
    _GROUP_BUSY[0] = True
    try:
        if not new or clash:
            self.entry_name = old
            return
        self.entry_name = new
        for entry in library.connections:
            if entry.group == old:
                entry.group = new
        self.prev_name = new
        try:
            members = [e for e in library.connections if e.group == new]
            rename_entry_folder("connections", self, _connection_entries(library), library, extra=members)
        except Exception as exc:
            print(f"[Dental-Lib] Khong doi ten thu muc nhom: {exc}")
    finally:
        _GROUP_BUSY[0] = False
    _autosave(context)


def _entry_name_updater(kind):
    """Update cua o ten Connection / Attachment: doi ten thu muc rieng theo ten moi roi ghi thu vien."""
    def update(self, context):
        if _SUPPRESS_AUTOSAVE[0]:
            return
        try:
            library = bpy.context.scene.dental_lib
            entries = _connection_entries(library) if kind == "connections" else _attachment_entries(library)
            if self.folder:
                rename_entry_folder(kind, self, entries, library)
        except Exception as exc:
            print(f"[Dental-Lib] Khong doi ten thu muc theo ten moi: {exc}")
        _autosave(context)
    return update


class DLIB_PG_VisualObject(PropertyGroup):
    label: StringProperty(name="Ten", default="Visual")
    asset: StringProperty(name="File", subtype='FILE_PATH', default="")
    color: FloatVectorProperty(
        name="Mau",
        description="Mau hien thi cua Visual Object khi dat vao scene "
                    "(kenh A dieu chinh do trong suot)",
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=DEFAULT_VISUAL_COLOR,
        update=_update_color)


CONNECTION_SLOT_LABELS = [
    ("base", "Base (STL/PLY)", 'MESH_CYLINDER'),
    ("analog", "Implant-Analog (STL/PLY)", 'MESH_CONE'),
    ("screw", "Screw (STL/PLY)", 'MESH_UVSPHERE'),
]

ATTACHMENT_SLOT_LABELS = [
    ("part_bar", "Apply Part Bar (STL/PLY)", 'MESH_CUBE'),
    ("part_sleeve", "Apply Part Sleeve (STL/PLY)", 'MESH_TORUS'),
]


class DLIB_PG_ScanbodyFile(PropertyGroup):
    """Mot file Scanbody (STL/PLY) cua Connection hoac nhom Connection."""
    asset: StringProperty(name="File", subtype='FILE_PATH', default="")


class DLIB_PG_AttachmentGroup(PropertyGroup):
    """Nhom Attachment: chi giu ten thu muc chung (attachments/<thu muc>/) chua file cua cac Attachment trong nhom."""
    entry_name: StringProperty(name="Ten nhom", default="Group")
    folder: StringProperty(
        name="Thu muc", default="",
        description="Thu muc chung cua nhom trong thu vien (attachments/<thu muc>)")


class DLIB_PG_ConnectionGroup(PropertyGroup):
    """Nhom Implant Connection: bo file chung (Base / Analog / Screw + danh sach Scanbody) cho cac Connection trong
    nhom ke thua; file nam trong thu muc rieng cua nhom (connections/<thu muc>/)."""
    entry_name: StringProperty(name="Ten nhom", default="Group", update=_conn_group_name_update)
    prev_name: StringProperty(default="")
    folder: StringProperty(
        name="Thu muc", default="",
        description="Thu muc rieng cua nhom trong thu vien (connections/<thu muc>): chua cac file chung")
    slot_base: StringProperty(name="Base", subtype='FILE_PATH', default="")
    slot_analog: StringProperty(name="Implant-Analog", subtype='FILE_PATH', default="")
    slot_screw: StringProperty(name="Screw", subtype='FILE_PATH', default="")
    scanbodies: CollectionProperty(type=DLIB_PG_ScanbodyFile)


class DLIB_PG_ConnectionEntry(PropertyGroup):
    entry_name: StringProperty(name="Library Name", default="New Connection",
                               update=_entry_name_updater("connections"))
    folder: StringProperty(
        name="Thu muc", default="",
        description="Thu muc rieng cua muc nay trong thu vien (connections/<thu muc>): moi file 3D cua muc luon nam "
                    "trong do va thu muc doi ten theo khi doi ten muc")
    group: StringProperty(
        name="Nhom", default="", update=_conn_member_group_update,
        description="Nhom Implant Connection chua muc nay. De trong = chua nhom. Thanh phan nao khong co "
                    "file rieng thi dung file chung cua nhom (ke thua); gan file rieng de ghi de. Scanbody: "
                    "Connection co file Scanbody rieng thi dung danh sach cua minh, khong thi dung danh sach cua nhom")
    open: BoolProperty(name="Mo rong", default=True,
                       description="Thu/mo danh sach slot file cua entry nay")
    slot_base: StringProperty(name="Base", subtype='FILE_PATH', default="")
    slot_analog: StringProperty(name="Implant-Analog", subtype='FILE_PATH', default="")
    slot_screw: StringProperty(name="Screw", subtype='FILE_PATH', default="")
    scanbodies: CollectionProperty(type=DLIB_PG_ScanbodyFile)


class DLIB_PG_AttachmentEntry(PropertyGroup):
    entry_name: StringProperty(name="Attachment Name", default="New Attachment",
                               update=_entry_name_updater("attachments"))
    folder: StringProperty(
        name="Thu muc", default="",
        description="Thu muc rieng cua muc nay trong thu vien (attachments/<thu muc>): moi file 3D cua muc luon nam "
                    "trong do va thu muc doi ten theo khi doi ten muc")
    group: StringProperty(
        name="Nhom", default="",
        description="Ten nhom (thu muc) chua Attachment nay. De trong = chua nhom. Panel Dental-Lib "
                    "va menu Select Attachment ben Rmvb-Bar gom cac Attachment theo nhom; file cua cac "
                    "Attachment trong nhom nam chung trong thu muc cua nhom",
        update=_att_member_group_update)
    open: BoolProperty(name="Mo rong", default=True,
                       description="Thu/mo danh sach slot file cua entry nay")
    on_bar: BoolProperty(
        name="Add/Remove on Bar", default=True,
        description="Tick = ADD (Boolean Union Part Bar vao Bar), bo tick = REMOVE "
                    "(Boolean Difference khoet Part Bar khoi Bar). Duoc ap dung khi "
                    "Add Attachment ben Rmvb-Bar (them san modifier, mac dinh Disable Preview; Enable / "
                    "Disable Preview chi bat / tat Realtime Display in Viewport cua modifier do)")
    bar_in_sleeve: BoolProperty(
        name="Attachment on Bar khi tao Sleeve", default=False,
        description="Tick = khi bam 'Create Sleeve Design' ben Rmvb-Bar, Part Bar cua Attachment nay "
                    "VAN duoc ap len Bar (Union / Difference theo Add/Remove on Bar) truoc khi tao "
                    "Sleeve. Bo tick = Attachment bi bo qua, Sleeve chi theo be mat Bar goc",
        update=_update_color)       # ghi library.json ngay: Rmvb-Bar doc tu dia khi Add Attachment
    part_bar: StringProperty(name="Apply Part Bar", subtype='FILE_PATH', default="")
    part_bar_color: FloatVectorProperty(
        name="Mau Apply Part Bar",
        description="Mau mac dinh cua Apply Part Bar khi dat vao scene "
                    "(do, alpha 0.5 - luu trong library.json, khong hien tren panel)",
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=DEFAULT_PART_BAR_COLOR)
    on_sleeve: BoolProperty(
        name="Add/Remove on Sleeve", default=False,
        description="Tick = ADD (Boolean Union Part Sleeve vao Sleeve), bo tick = "
                    "REMOVE (Boolean Difference khoet Part Sleeve khoi Sleeve). Duoc "
                    "ap dung khi bam 'Create Sleeve Design' ben Rmvb-Bar")
    part_sleeve: StringProperty(name="Apply Part Sleeve", subtype='FILE_PATH', default="")
    part_sleeve_color: FloatVectorProperty(
        name="Mau Apply Part Sleeve",
        description="Mau mac dinh cua Apply Part Sleeve khi dat vao scene "
                    "(hong, alpha 0.5 - luu trong library.json, khong hien tren panel)",
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=DEFAULT_PART_SLEEVE_COLOR)
    visuals: CollectionProperty(type=DLIB_PG_VisualObject)


class DLIB_PG_Library(PropertyGroup):
    """Buffer hien thi thu vien tren panel (source of truth: library.json)."""
    connections: CollectionProperty(type=DLIB_PG_ConnectionEntry)
    connection_groups: CollectionProperty(type=DLIB_PG_ConnectionGroup)
    attachments: CollectionProperty(type=DLIB_PG_AttachmentEntry)
    attachment_groups: CollectionProperty(type=DLIB_PG_AttachmentGroup)


# ---------------------------------------------------------------------------
# Dong bo JSON <-> Scene PropertyGroup
# ---------------------------------------------------------------------------
CONNECTION_SLOT_FIELD = {
    "base": "slot_base",
    "analog": "slot_analog",
    "screw": "slot_screw",
}


def _lib_group(context):
    return context.scene.dental_lib


def index_from_scene(context):
    """Chuyen buffer tren scene ve dict JSON."""
    group = _lib_group(context)
    data = {"version": 1, "connections": [], "connection_groups": [], "attachments": [],
            "attachment_groups": []}
    for entry in group.attachment_groups:
        data["attachment_groups"].append({"name": entry.entry_name, "folder": entry.folder})
    for entry in group.connection_groups:
        item = {"name": entry.entry_name, "folder": entry.folder}
        for slot, field in CONNECTION_SLOT_FIELD.items():
            item[slot] = getattr(entry, field)
        item["scanbodies"] = [row.asset for row in entry.scanbodies]
        data["connection_groups"].append(item)
    for entry in group.connections:
        item = {"name": entry.entry_name, "folder": entry.folder, "group": entry.group.strip()}
        for slot, field in CONNECTION_SLOT_FIELD.items():
            item[slot] = getattr(entry, field)
        item["scanbodies"] = [row.asset for row in entry.scanbodies]
        data["connections"].append(item)
    for entry in group.attachments:
        item = {
            "name": entry.entry_name,
            "folder": entry.folder,
            "group": entry.group.strip(),
            "on_bar": bool(entry.on_bar),
            "bar_in_sleeve": bool(entry.bar_in_sleeve),
            "part_bar": entry.part_bar,
            "part_bar_color": write_color(entry.part_bar_color),
            "on_sleeve": bool(entry.on_sleeve),
            "part_sleeve": entry.part_sleeve,
            "part_sleeve_color": write_color(entry.part_sleeve_color),
            "visuals": [{"label": v.label, "asset": v.asset,
                         "color": write_color(v.color)} for v in entry.visuals],
        }
        data["attachments"].append(item)
    return data


def scene_from_index(context, data):
    """Nap dict JSON vao buffer tren scene (khong tu luu lai)."""
    group = _lib_group(context)
    _SUPPRESS_AUTOSAVE[0] = True
    try:
        _fill_group(group, data)
    finally:
        _SUPPRESS_AUTOSAVE[0] = False
    return group


def _fill_group(group, data):
    group.connections.clear()
    group.connection_groups.clear()
    group.attachments.clear()
    group.attachment_groups.clear()
    for item in data.get("attachment_groups", []):
        adef = group.attachment_groups.add()
        adef.entry_name = item.get("name", "Group")
        adef.folder = str(item.get("folder", "") or "")
    for item in data.get("connection_groups", []):
        gdef = group.connection_groups.add()
        gdef.entry_name = item.get("name", "Group")
        gdef.prev_name = gdef.entry_name
        gdef.folder = str(item.get("folder", "") or "")
        for slot, field in CONNECTION_SLOT_FIELD.items():
            setattr(gdef, field, item.get(slot, ""))
        for ref in _scanbody_refs(item):
            gdef.scanbodies.add().asset = ref
    for item in data.get("connections", []):
        entry = group.connections.add()
        entry.entry_name = item.get("name", "Connection")
        entry.folder = str(item.get("folder", "") or "")
        entry.group = str(item.get("group", "") or "").strip()
        for slot, field in CONNECTION_SLOT_FIELD.items():
            setattr(entry, field, item.get(slot, ""))
        for ref in _scanbody_refs(item):
            entry.scanbodies.add().asset = ref
    for entry in group.connections:         # nhom duoc tham chieu nhung chua co dinh nghia (json sua tay)
        if entry.group and _find_connection_group(group, entry.group) is None:
            new_connection_group(group, entry.group)
    for gdef in group.connection_groups:
        if not gdef.folder:
            gdef.folder = unique_folder("connections", gdef.entry_name, _connection_entries(group), exclude=gdef)
    for item in data.get("attachments", []):
        entry = group.attachments.add()
        entry.entry_name = item.get("name", "Attachment")
        entry.folder = str(item.get("folder", "") or "")
        entry.group = str(item.get("group", "") or "").strip()
        entry.on_bar = bool(item.get("on_bar", True))
        entry.bar_in_sleeve = bool(item.get("bar_in_sleeve", False))
        entry.part_bar = item.get("part_bar", "")
        entry.part_bar_color = read_color(item.get("part_bar_color"),
                                          DEFAULT_PART_BAR_COLOR)
        entry.on_sleeve = bool(item.get("on_sleeve", False))
        entry.part_sleeve = item.get("part_sleeve", "")
        entry.part_sleeve_color = read_color(item.get("part_sleeve_color"),
                                             DEFAULT_PART_SLEEVE_COLOR)
        for visual in item.get("visuals", []):
            row = entry.visuals.add()
            row.label = visual.get("label", "Visual")
            row.asset = visual.get("asset", "")
            row.color = read_color(visual.get("color"), DEFAULT_VISUAL_COLOR)
    for entry in group.attachments:         # nhom Attachment chua co dinh nghia (thu vien cu / json sua tay)
        if entry.group and _find_attachment_group(group, entry.group) is None:
            new_attachment_group(group, entry.group)
    for adef in group.attachment_groups:
        if not adef.folder:
            adef.folder = unique_folder("attachments", adef.entry_name, _attachment_entries(group), exclude=adef)
    return group


def sync_scene(context):
    """Dam bao buffer scene trung khop voi library.json tren dia."""
    return scene_from_index(context, read_index())


# ---------------------------------------------------------------------------
# Operator: dong bo thu vien
# ---------------------------------------------------------------------------
def _save_all(context):
    write_index(index_from_scene(context))
    return {"FINISHED"}


def ensure_loaded(context):
    """Nap thu vien tu dia neu buffer rong trong khi library.json da co data.

    Ne cham ham nay truoc khi sua thi mot file .blend moi (chua sync) se bi
    _save_all() ghi de len library.json va xoa mem toan bo thu vien cu.
    """
    group = _lib_group(context)
    if len(group.connections) or len(group.connection_groups) or len(group.attachments):
        return group
    data = read_index()
    if data["connections"] or data.get("connection_groups") or data["attachments"]:
        scene_from_index(context, data)
    return group


class DLIB_OT_load_library(Operator):
    """Nap lai thu vien tu file library.json tren dia"""
    bl_idname = "dental_lib.load_library"
    bl_label = "Nap thu vien"
    bl_options = set()

    def execute(self, context):
        ensure_library_dir()
        sync_scene(context)
        moved = gather_group_files(context)
        data = read_index()
        self.report({'INFO'}, "Da nap %d Connection, %d Attachment tu %s%s"
                    % (len(data["connections"]), len(data["attachments"]),
                       index_path(),
                       " (gom %d file vao thu muc nhom)" % moved if moved else ""))
        return {'FINISHED'}


class DLIB_OT_save_library(Operator):
    """Luu toan bo thu vien vao file library.json"""
    bl_idname = "dental_lib.save_library"
    bl_label = "Luu thu vien"
    bl_options = set()

    def execute(self, context):
        try:
            _save_all(context)
        except Exception as exc:
            self.report({'ERROR'}, "Khong luu duoc thu vien: %s" % exc)
            return {'CANCELLED'}
        self.report({'INFO'}, "Da luu thu vien vao %s" % index_path())
        return {'FINISHED'}


class DLIB_OT_open_folder(Operator):
    """Mo thu muc thu vien trong trinh duyet file"""
    bl_idname = "dental_lib.open_folder"
    bl_label = "Mo thu muc"

    def execute(self, context):
        root = ensure_library_dir()
        try:
            bpy.ops.file.browse_directory(target=str(root))
        except Exception:
            try:
                import subprocess, sys
                if sys.platform.startswith("win"):
                    os.startfile(root)  # noqa
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", root])
                else:
                    subprocess.Popen(["xdg-open", root])
            except Exception as exc:
                self.report({'WARNING'}, "Thu vien nam tai: %s (%s)" % (root, exc))
                return {'CANCELLED'}
        self.report({'INFO'}, "Thu vien: %s" % root)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: them / xoa entry
# ---------------------------------------------------------------------------
def _unique_name(entries, prefix, attr="entry_name"):
    """Ten '<prefix> N' dau tien chua ton tai (dung len() sau khi xoa la sai)."""
    used = {getattr(entry, attr) for entry in entries}
    index = 1
    while ("%s %d" % (prefix, index)) in used:
        index += 1
    return "%s %d" % (prefix, index)


def _unique_entry_name(entries, prefix):
    return _unique_name(entries, prefix, "entry_name")


class DLIB_OT_add_connection(Operator):
    """Them mot Implant Connection moi vao thu vien"""
    bl_idname = "dental_lib.add_connection"
    bl_label = "Add Connection Base"
    bl_options = set()

    def execute(self, context):
        group = ensure_loaded(context)
        entry = group.connections.add()
        entry.entry_name = _unique_entry_name(group.connections, "Connection")
        entry.folder = unique_folder("connections", entry.entry_name, _connection_entries(group), exclude=entry)
        _save_all(context)
        self.report({'INFO'}, "Da tao '%s' - chon file cho tung slot ben duoi"
                    % entry.entry_name)
        return {'FINISHED'}


def _confirm_delete(operator, context, event, title, message, confirm_text="Xóa"):
    """Hop thoai xac nhan truoc khi xoa (nhan nham nut thung rac / X khong mat du lieu ngay).
    Goi bang script (bpy.ops.dental_lib.xxx(...)) thi khong qua invoke nen van xoa thang."""
    return context.window_manager.invoke_confirm(
        operator, event, title=title, message=message, confirm_text=confirm_text, icon='WARNING')


class DLIB_OT_remove_connection(Operator):
    """Xoa Connection khoi thu vien (giu lai file asset)"""
    bl_idname = "dental_lib.remove_connection"
    bl_label = "Remove Connection"
    bl_options = set()

    index: IntProperty(default=-1)

    def invoke(self, context, event):
        group = ensure_loaded(context)
        if not 0 <= self.index < len(group.connections):
            return {'CANCELLED'}
        name = group.connections[self.index].entry_name
        return _confirm_delete(self, context, event, "Xóa Connection '%s'?" % name,
                               "Xóa Connection '%s' khỏi thư viện Dental-Lib. File mesh gốc vẫn được giữ "
                               "trong thư mục thư viện." % name)

    def execute(self, context):
        group = ensure_loaded(context)
        if 0 <= self.index < len(group.connections):
            name = group.connections[self.index].entry_name
            group.connections.remove(self.index)
            _save_all(context)
            self.report({'INFO'}, "Da xoa '%s'" % name)
            return {'FINISHED'}
        return {'CANCELLED'}


class DLIB_OT_add_connection_group(Operator):
    """Them nhom Implant Connection: bo file chung cho cac Connection trong nhom"""
    bl_idname = "dental_lib.add_connection_group"
    bl_label = "Add Connection Group"
    bl_options = set()

    def execute(self, context):
        library = ensure_loaded(context)
        item = new_connection_group(library, _unique_name(library.connection_groups, "Group"))
        _save_all(context)
        self.report({'INFO'}, "Da tao nhom '%s' - gan file chung cho nhom roi dat Connection vao nhom" % item.entry_name)
        return {'FINISHED'}


class DLIB_OT_remove_connection_group(Operator):
    """Xoa nhom Implant Connection (cac Connection trong nhom thanh chua nhom, giu lai file)"""
    bl_idname = "dental_lib.remove_connection_group"
    bl_label = "Remove Connection Group"
    bl_options = set()

    index: IntProperty(default=-1)

    def invoke(self, context, event):
        library = ensure_loaded(context)
        if not 0 <= self.index < len(library.connection_groups):
            return {'CANCELLED'}
        name = library.connection_groups[self.index].entry_name
        count = sum(1 for e in library.connections if e.group == name)
        return _confirm_delete(self, context, event, "Xóa nhóm '%s'?" % name,
                               "Xóa nhóm '%s'. %d Connection trong nhóm thành chưa nhóm: file riêng của chúng được "
                               "chuyển ra thư mục riêng, còn phần kế thừa từ nhóm mất (thành phần nào chưa có file "
                               "riêng sẽ trống). File chung của nhóm vẫn được giữ trong thư mục nhóm."
                               % (name, count))

    def execute(self, context):
        library = ensure_loaded(context)
        if not 0 <= self.index < len(library.connection_groups):
            return {'CANCELLED'}
        name = library.connection_groups[self.index].entry_name
        _GROUP_BUSY[0] = True
        try:
            for entry in library.connections:
                if entry.group == name:
                    entry.group = ""
                    try:
                        relocate_entry_files("connections", entry, library)      # file ve lai thu muc rieng
                    except Exception as exc:
                        print(f"[Dental-Lib] Khong dua file cua '{entry.entry_name}' ra khoi nhom: {exc}")
            library.connection_groups.remove(self.index)
        finally:
            _GROUP_BUSY[0] = False
        _save_all(context)
        self.report({'INFO'}, "Da xoa nhom '%s'" % name)
        return {'FINISHED'}


class DLIB_OT_gather_groups(Operator):
    """Gom file cua cac muc trong nhom (Implant Connection va Attachment) vao thu muc cua nhom"""
    bl_idname = "dental_lib.gather_groups"
    bl_label = "Gom file nhom"
    bl_options = set()

    def execute(self, context):
        ensure_loaded(context)
        moved = gather_group_files(context)
        self.report({'INFO'}, "Da gom %d file vao thu muc nhom" % moved if moved else
                    "Moi file cua cac nhom da nam trong thu muc nhom")
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class DLIB_OT_set_connection_group(Operator):
    """Dat nhom cho Implant Connection"""
    bl_idname = "dental_lib.set_connection_group"
    bl_label = "Dat nhom"
    bl_options = set()

    index: IntProperty(default=-1)
    group: StringProperty(default="")

    def execute(self, context):
        library = ensure_loaded(context)
        if not 0 <= self.index < len(library.connections):
            return {'CANCELLED'}
        library.connections[self.index].group = self.group.strip()      # update -> tao nhom neu chua co + autosave
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


def draw_connection_group_choices(layout, library, index):
    """Danh sach nhom Connection hien co de gan nhanh cho Connection `index` (+ bo nhom)."""
    names = sorted((g.entry_name for g in library.connection_groups), key=str.casefold)
    current = library.connections[index].group.strip() if 0 <= index < len(library.connections) else ""
    for name in names:
        op = layout.operator(DLIB_OT_set_connection_group.bl_idname, text=name,
                             icon=_ic('CHECKMARK' if name == current else 'FILE_FOLDER'))
        op.index = index
        op.group = name
    if names:
        layout.separator()
    op = layout.operator(DLIB_OT_set_connection_group.bl_idname, text="(Chưa nhóm)",
                         icon=_ic('X' if current else 'CHECKMARK'))
    op.index = index
    op.group = ""
    if not names:
        layout.label(text="Bấm '+ Group' hoặc gõ tên vào ô Nhóm để tạo nhóm", icon=_ic('INFO'))


class DLIB_OT_pick_connection_group(Operator):
    """Chon mot nhom da co cho Connection nay (hoac go ten nhom moi vao o Nhom)"""
    bl_idname = "dental_lib.pick_connection_group"
    bl_label = "Chon nhom"
    bl_options = {'INTERNAL'}

    index: IntProperty(default=-1)

    def invoke(self, context, event):
        if not 0 <= self.index < len(context.scene.dental_lib.connections):
            return {'CANCELLED'}
        index = self.index

        def draw(menu, menu_context):
            draw_connection_group_choices(menu.layout, menu_context.scene.dental_lib, index)

        context.window_manager.popup_menu(draw, title="Nhóm Implant Connection", icon='FILE_FOLDER')
        return {'INTERFACE'}


class DLIB_OT_add_attachment(Operator):
    """Them mot Attachment moi vao thu vien"""
    bl_idname = "dental_lib.add_attachment"
    bl_label = "Add Attachment"
    bl_options = set()

    def execute(self, context):
        group = ensure_loaded(context)
        entry = group.attachments.add()
        entry.entry_name = _unique_entry_name(group.attachments, "Attachment")
        entry.folder = unique_folder("attachments", entry.entry_name, _attachment_entries(group), exclude=entry)
        _save_all(context)
        self.report({'INFO'}, "Da tao '%s'" % entry.entry_name)
        return {'FINISHED'}


class DLIB_OT_remove_attachment(Operator):
    """Xoa Attachment khoi thu vien (giu lai file asset)"""
    bl_idname = "dental_lib.remove_attachment"
    bl_label = "Remove Attachment"
    bl_options = set()

    index: IntProperty(default=-1)

    def invoke(self, context, event):
        group = ensure_loaded(context)
        if not 0 <= self.index < len(group.attachments):
            return {'CANCELLED'}
        entry = group.attachments[self.index]
        extra = " cùng %d Visual Object" % len(entry.visuals) if len(entry.visuals) else ""
        return _confirm_delete(self, context, event, "Xóa Attachment '%s'?" % entry.entry_name,
                               "Xóa Attachment '%s'%s khỏi thư viện Dental-Lib. File mesh gốc vẫn được giữ "
                               "trong thư mục thư viện." % (entry.entry_name, extra))

    def execute(self, context):
        group = ensure_loaded(context)
        if 0 <= self.index < len(group.attachments):
            name = group.attachments[self.index].entry_name
            group.attachments.remove(self.index)
            _save_all(context)
            self.report({'INFO'}, "Da xoa '%s'" % name)
            return {'FINISHED'}
        return {'CANCELLED'}


# Trang thai thu/mo cua tung nhom Attachment tren panel (chi la UI, khong luu vao thu vien)
_GROUP_CLOSED = set()


def grouped_indices(entries):
    """[(ten nhom, [chi so entry, ...]), ...] cung quy tac thu tu voi attachment_groups()."""
    buckets = {}
    for index, entry in enumerate(entries):
        buckets.setdefault(entry.group.strip(), []).append(index)
    out = [(key, buckets[key]) for key in sorted((k for k in buckets if k), key=str.casefold)]
    if "" in buckets:
        out.append(("", buckets[""]))
    return out


class DLIB_OT_toggle_attachment_group(Operator):
    """Thu / mo mot nhom Attachment tren panel"""
    bl_idname = "dental_lib.toggle_attachment_group"
    bl_label = "Thu / mo nhom"
    bl_options = {'INTERNAL'}

    group: StringProperty(default="")

    def execute(self, context):
        if self.group in _GROUP_CLOSED:
            _GROUP_CLOSED.discard(self.group)
        else:
            _GROUP_CLOSED.add(self.group)
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class DLIB_OT_set_attachment_group(Operator):
    """Dat nhom cho Attachment"""
    bl_idname = "dental_lib.set_attachment_group"
    bl_label = "Dat nhom"
    bl_options = set()

    index: IntProperty(default=-1)
    group: StringProperty(default="")

    def execute(self, context):
        library = ensure_loaded(context)
        if not 0 <= self.index < len(library.attachments):
            return {'CANCELLED'}
        library.attachments[self.index].group = self.group.strip()      # update -> autosave
        _GROUP_CLOSED.discard(self.group.strip())                        # mo nhom vua chuyen vao
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


def draw_group_choices(layout, library, index):
    """Danh sach nhom hien co de gan nhanh cho Attachment `index` (+ bo nhom)."""
    names = sorted({e.group.strip() for e in library.attachments if e.group.strip()}, key=str.casefold)
    current = library.attachments[index].group.strip() if 0 <= index < len(library.attachments) else ""
    for name in names:
        op = layout.operator(DLIB_OT_set_attachment_group.bl_idname, text=name,
                             icon=_ic('CHECKMARK' if name == current else 'FILE_FOLDER'))
        op.index = index
        op.group = name
    if names:
        layout.separator()
    op = layout.operator(DLIB_OT_set_attachment_group.bl_idname, text="(Chưa nhóm)",
                         icon=_ic('X' if current else 'CHECKMARK'))
    op.index = index
    op.group = ""
    if not names:
        layout.label(text="Gõ tên vào ô Nhóm để tạo nhóm mới", icon=_ic('INFO'))


class DLIB_OT_pick_attachment_group(Operator):
    """Chon mot nhom da co cho Attachment nay (hoac go ten nhom moi vao o Nhom)"""
    bl_idname = "dental_lib.pick_attachment_group"
    bl_label = "Chon nhom"
    bl_options = {'INTERNAL'}

    index: IntProperty(default=-1)

    def invoke(self, context, event):
        if not 0 <= self.index < len(context.scene.dental_lib.attachments):
            return {'CANCELLED'}
        index = self.index

        def draw(menu, menu_context):
            draw_group_choices(menu.layout, menu_context.scene.dental_lib, index)

        context.window_manager.popup_menu(draw, title="Nhóm Attachment", icon='FILE_FOLDER')
        return {'INTERFACE'}


# ---------------------------------------------------------------------------
# Operator: nap file STL/PLY vao mot slot cua entry
# ---------------------------------------------------------------------------
def _entry_by_index(context, kind, index):
    group = _lib_group(context)
    if kind == "connection":
        if 0 <= index < len(group.connections):
            return group.connections[index]
    elif kind == "connection_group":
        if 0 <= index < len(group.connection_groups):
            return group.connection_groups[index]
    else:
        if 0 <= index < len(group.attachments):
            return group.attachments[index]
    return None


class DLIB_OT_import_asset(Operator, ImportHelper):
    """Chon file STL/PLY va copy vao thu vien cho slot duoc chon"""
    bl_idname = "dental_lib.import_asset"
    bl_label = "Import STL/PLY"

    filepath: StringProperty(subtype='FILE_PATH', default="")
    filter_glob: StringProperty(default="*.stl;*.ply;*.STL;*.PLY", options={'HIDDEN'})

    kind: StringProperty(default="connection")
    index: IntProperty(default=-1)
    slot: StringProperty(default="base")

    def execute(self, context):
        library = ensure_loaded(context)
        entry = _entry_by_index(context, self.kind, self.index)
        if entry is None:
            self.report({'ERROR'}, "Khong tim thay entry trong thu vien")
            return {'CANCELLED'}
        source = bpy.path.abspath(self.filepath)
        if not source or not os.path.exists(source):
            self.report({'ERROR'}, "Khong tim thay file: %s" % source)
            return {'CANCELLED'}
        try:
            if self.kind in ("connection", "connection_group"):
                field = CONNECTION_SLOT_FIELD[self.slot]
                rel = store_entry_asset("connections", entry, _connection_entries(library), source, self.slot,
                                        lambda: getattr(entry, field), library)
                setattr(entry, field, rel)
            else:
                rel = store_entry_asset("attachments", entry, _attachment_entries(library), source, self.slot,
                                        lambda: getattr(entry, self.slot), library)
                setattr(entry, self.slot, rel)
        except Exception as exc:
            self.report({'ERROR'}, "Khong copy duoc file vao thu vien: %s" % exc)
            return {'CANCELLED'}
        _save_all(context)
        self.report({'INFO'}, "%s -> %s" % (self.slot, rel))
        return {'FINISHED'}


class DLIB_OT_clear_asset(Operator):
    """Xoa lien ket file cua slot (khong xoa file trong thu vien)"""
    bl_idname = "dental_lib.clear_asset"
    bl_label = "Clear"
    bl_options = set()

    kind: StringProperty(default="connection")
    index: IntProperty(default=-1)
    slot: StringProperty(default="base")

    def invoke(self, context, event):
        ensure_loaded(context)
        entry = _entry_by_index(context, self.kind, self.index)
        if entry is None:
            return {'CANCELLED'}
        slot = ("%s" % self.slot)
        return _confirm_delete(self, context, event, "Bỏ liên kết file '%s'?" % slot,
                               "Bỏ liên kết file của slot '%s' trong '%s'. File mesh trong thư mục thư viện "
                               "không bị xóa, nhưng phải bấm 'Gan file' lại để dùng tiếp."
                               % (slot, entry.entry_name), confirm_text="Bỏ liên kết")

    def execute(self, context):
        ensure_loaded(context)
        entry = _entry_by_index(context, self.kind, self.index)
        if entry is None:
            return {'CANCELLED'}
        if self.kind in ("connection", "connection_group"):
            setattr(entry, CONNECTION_SLOT_FIELD[self.slot], "")
        else:
            setattr(entry, self.slot, "")
        _save_all(context)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: Scanbody (nhieu file cho moi Connection / nhom Connection)
# ---------------------------------------------------------------------------
class DLIB_OT_add_scanbody(Operator, ImportHelper):
    """Chon mot hoac nhieu file STL/PLY Scanbody va them vao Connection / nhom Connection"""
    bl_idname = "dental_lib.add_scanbody"
    bl_label = "Add Scanbody (STL/PLY)"

    filepath: StringProperty(subtype='FILE_PATH', default="")
    filter_glob: StringProperty(default="*.stl;*.ply;*.STL;*.PLY", options={'HIDDEN'})
    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'})

    kind: StringProperty(default="connection")
    index: IntProperty(default=-1)

    def execute(self, context):
        library = ensure_loaded(context)
        entry = _entry_by_index(context, self.kind, self.index)
        if entry is None:
            self.report({'ERROR'}, "Khong tim thay entry trong thu vien")
            return {'CANCELLED'}
        names = [item.name for item in self.files] or [os.path.basename(self.filepath)]
        folder = bpy.path.abspath(self.directory) if self.directory else os.path.dirname(bpy.path.abspath(self.filepath))
        added = 0
        for name in names:
            source = os.path.join(folder, name)
            if not name or not os.path.isfile(source):
                self.report({'WARNING'}, "Khong tim thay file: %s" % source)
                continue
            try:
                rel = store_entry_asset("connections", entry, _connection_entries(library), source, AUTO_SCANBODY,
                                        lambda: "", library)
            except Exception as exc:
                self.report({'ERROR'}, "Khong copy duoc '%s' vao thu vien: %s" % (name, exc))
                continue
            entry.scanbodies.add().asset = rel
            added += 1
        if not added:
            return {'CANCELLED'}
        _save_all(context)
        self.report({'INFO'}, "Da them %d Scanbody vao '%s'" % (added, entry.entry_name))
        return {'FINISHED'}


class DLIB_OT_remove_scanbody(Operator):
    """Bo mot file Scanbody khoi Connection / nhom Connection (file trong thu vien duoc giu lai)"""
    bl_idname = "dental_lib.remove_scanbody"
    bl_label = "Remove Scanbody"
    bl_options = set()

    kind: StringProperty(default="connection")
    index: IntProperty(default=-1)
    scan_index: IntProperty(default=-1)

    def invoke(self, context, event):
        ensure_loaded(context)
        entry = _entry_by_index(context, self.kind, self.index)
        if entry is None or not 0 <= self.scan_index < len(entry.scanbodies):
            return {'CANCELLED'}
        name = _short(entry.scanbodies[self.scan_index].asset, 40) or "Scanbody %d" % (self.scan_index + 1)
        return _confirm_delete(self, context, event, "Bỏ Scanbody '%s'?" % name,
                               "Bỏ Scanbody '%s' khỏi '%s'. File mesh gốc vẫn được giữ trong thư mục thư viện."
                               % (name, entry.entry_name), confirm_text="Bỏ")

    def execute(self, context):
        ensure_loaded(context)
        entry = _entry_by_index(context, self.kind, self.index)
        if entry is None or not 0 <= self.scan_index < len(entry.scanbodies):
            return {'CANCELLED'}
        entry.scanbodies.remove(self.scan_index)
        _save_all(context)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: Visual Object (khong gioi han so luong, dat duoc ten)
# ---------------------------------------------------------------------------
class DLIB_OT_add_visual(Operator):
    """Them mot Visual Object vao Attachment"""
    bl_idname = "dental_lib.add_visual"
    bl_label = "Add Visual Object"
    bl_options = set()

    index: IntProperty(default=-1)

    def execute(self, context):
        ensure_loaded(context)
        entry = _entry_by_index(context, "attachment", self.index)
        if entry is None:
            return {'CANCELLED'}
        row = entry.visuals.add()
        row.label = _unique_name(entry.visuals, "Visual", "label")
        _save_all(context)
        return {'FINISHED'}


class DLIB_OT_remove_visual(Operator):
    """Xoa Visual Object khoi Attachment"""
    bl_idname = "dental_lib.remove_visual"
    bl_label = "Remove Visual"
    bl_options = set()

    index: IntProperty(default=-1)
    visual_index: IntProperty(default=-1)

    def invoke(self, context, event):
        ensure_loaded(context)
        entry = _entry_by_index(context, "attachment", self.index)
        if entry is None or not 0 <= self.visual_index < len(entry.visuals):
            return {'CANCELLED'}
        label = entry.visuals[self.visual_index].label
        return _confirm_delete(self, context, event, "Xóa Visual Object '%s'?" % label,
                               "Xóa Visual Object '%s' khỏi Attachment '%s'. File mesh gốc vẫn được giữ "
                               "trong thư mục thư viện." % (label, entry.entry_name))

    def execute(self, context):
        ensure_loaded(context)
        entry = _entry_by_index(context, "attachment", self.index)
        if entry is None:
            return {'CANCELLED'}
        if 0 <= self.visual_index < len(entry.visuals):
            entry.visuals.remove(self.visual_index)
            _save_all(context)
            return {'FINISHED'}
        return {'CANCELLED'}


class DLIB_OT_import_visual(Operator, ImportHelper):
    """Chon file STL/PLY cho Visual Object"""
    bl_idname = "dental_lib.import_visual"
    bl_label = "Import Visual (STL/PLY)"

    filepath: StringProperty(subtype='FILE_PATH', default="")
    filter_glob: StringProperty(default="*.stl;*.ply;*.STL;*.PLY", options={'HIDDEN'})

    index: IntProperty(default=-1)
    visual_index: IntProperty(default=-1)

    def execute(self, context):
        library = ensure_loaded(context)
        entry = _entry_by_index(context, "attachment", self.index)
        if entry is None or not (0 <= self.visual_index < len(entry.visuals)):
            self.report({'ERROR'}, "Khong tim thay Visual Object")
            return {'CANCELLED'}
        source = bpy.path.abspath(self.filepath)
        if not source or not os.path.exists(source):
            self.report({'ERROR'}, "Khong tim thay file: %s" % source)
            return {'CANCELLED'}
        row = entry.visuals[self.visual_index]
        try:
            rel = store_entry_asset("attachments", entry, _attachment_entries(library), source, AUTO_VISUAL,
                                    lambda: row.asset, library)
        except Exception as exc:
            self.report({'ERROR'}, "Khong copy duoc file vao thu vien: %s" % exc)
            return {'CANCELLED'}
        row.asset = rel
        _save_all(context)
        self.report({'INFO'}, "Visual '%s' -> %s" % (row.label, rel))
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Import mesh (dung chung - Rmvb-Bar co the goi lai)
# ---------------------------------------------------------------------------
def import_mesh_file(filepath, name="Mesh", collection=None):
    """Import 1 file STL/PLY va tra ve object mesh dau tien (da doi ten)."""
    if not filepath or not os.path.exists(filepath):
        raise FileNotFoundError("Khong tim thay file mesh: %s" % filepath)
    ext = os.path.splitext(filepath)[1].lower()
    before = {ob.name for ob in bpy.data.objects}
    if ext == ".ply":
        bpy.ops.wm.ply_import(filepath=filepath)
    else:
        bpy.ops.wm.stl_import(filepath=filepath)
    created = [ob for ob in bpy.data.objects
               if ob.name not in before and ob.type in {'MESH', 'OTHER'}]
    meshes = [ob for ob in created if ob.type == 'MESH']
    if not meshes:
        raise RuntimeError("File khong chua mesh: %s" % filepath)
    if len(meshes) > 1:
        bpy.ops.object.select_all(action='DESELECT')
        for ob in meshes:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.join()
        meshes = [bpy.context.view_layer.objects.active]
    obj = meshes[0]
    obj.name = name
    obj.data.name = name
    if collection is not None and obj.name not in collection.objects:
        for parent in list(obj.users_collection):
            parent.objects.unlink(obj)
        collection.objects.link(obj)
    return obj


def ensure_collection(name, parent=None):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        host = parent if parent is not None else bpy.context.scene.collection
        host.children.link(coll)
    return coll


def color_material(rgba):
    """Material toi (Principled) dung chung cho mot mau RGBA.

    Alpha < 1 duoc bat trong suot (BLEND / BLENDED) de xem truoc trong viewport
    giong cach Gingiva_Teeth_Splitter dat mau hien thi.
    """
    r, g, b, a = read_color(rgba)
    name = "DLIB_Color_%g_%g_%g_%g" % (r, g, b, a)
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (r, g, b, a)
    bsdf = None
    for nd in getattr(mat.node_tree, "nodes", []):
        if nd.type == 'BSDF_PRINCIPLED':
            bsdf = nd
            break
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = a
    if a < 1.0:
        if hasattr(mat, "blend_method"):
            try:
                mat.blend_method = 'BLEND'
            except Exception:
                pass
        if hasattr(mat, "surface_render_method"):
            try:
                mat.surface_render_method = 'BLENDED'
            except Exception:
                pass
        if hasattr(mat, "show_transparent_back"):
            mat.show_transparent_back = False
    elif hasattr(mat, "blend_method"):
        try:
            mat.blend_method = 'OPAQUE'
        except Exception:
            pass
    return mat


def apply_display_color(obj, rgba):
    """Dat mau hien thi cho object: obj.color + material co ho tro alpha."""
    if obj is None:
        return obj
    r, g, b, a = read_color(rgba)
    try:
        obj.color = (r, g, b, a)
        obj.display_color = 'OBJECT'
    except Exception:
        pass
    if obj.type == 'MESH':
        try:
            mat = color_material((r, g, b, a))
            mesh = obj.data
            if mesh is not None and not mesh.materials and not obj.material_slots:
                mesh.materials.append(mat)
            if obj.material_slots:
                slot = obj.material_slots[-1]
                try:
                    slot.link = 'OBJECT'   # de mesh dung chung khong bi doi mau
                except Exception:
                    pass
                slot.material = mat
        except Exception as exc:
            print(f"[Dental-Lib] Khong gan duoc material mau: {exc}")
    return obj


def _effective_slot(library, entry, slot):
    """Duong dan (rel) cua thanh phan: file rieng cua Connection, khong thi file chung cua nhom."""
    own = getattr(entry, CONNECTION_SLOT_FIELD[slot])
    if own:
        return own
    name = entry.group.strip()
    gdef = _find_connection_group(library, name) if name else None
    return getattr(gdef, CONNECTION_SLOT_FIELD[slot]) if gdef is not None else ""


def _effective_scanbodies(library, entry):
    """Danh sach duong dan (rel) Scanbody cua Connection: danh sach rieng, khong co thi cua nhom."""
    own = [row.asset for row in entry.scanbodies if row.asset]
    if own:
        return own
    name = entry.group.strip()
    gdef = _find_connection_group(library, name) if name else None
    return [row.asset for row in gdef.scanbodies if row.asset] if gdef is not None else []


class DLIB_OT_insert_connection(Operator):
    """Dat toan bo mesh cua Connection vao scene (kiem tra thu vien)"""
    bl_idname = "dental_lib.insert_connection"
    bl_label = "Insert vao Scene"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        group = ensure_loaded(context)
        if not (0 <= self.index < len(group.connections)):
            return {'CANCELLED'}
        entry = group.connections[self.index]
        coll = ensure_collection("Dental-Lib Preview")
        count = 0
        for slot, label, _icon in CONNECTION_SLOT_LABELS:
            path = resolve_asset(_effective_slot(group, entry, slot))
            if not path or not os.path.exists(path):
                continue
            try:
                import_mesh_file(path, "%s_%s" % (entry.entry_name, slot.capitalize()), coll)
                count += 1
            except Exception as exc:
                self.report({'WARNING'}, "%s: %s" % (label, exc))
        for number, rel in enumerate(_effective_scanbodies(group, entry), 1):
            path = resolve_asset(rel)
            if not path or not os.path.exists(path):
                continue
            try:
                import_mesh_file(path, "%s_Scanbody_%d" % (entry.entry_name, number), coll)
                count += 1
            except Exception as exc:
                self.report({'WARNING'}, "Scanbody %d: %s" % (number, exc))
        self.report({'INFO'}, "Da insert %d mesh cua %s" % (count, entry.entry_name))
        return {'FINISHED'}


class DLIB_OT_insert_attachment(Operator):
    """Dat Part Bar / Part Sleeve / Visual Object vao scene"""
    bl_idname = "dental_lib.insert_attachment"
    bl_label = "Insert vao Scene"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        group = ensure_loaded(context)
        if not (0 <= self.index < len(group.attachments)):
            return {'CANCELLED'}
        entry = group.attachments[self.index]
        coll = ensure_collection("Dental-Lib Preview")
        count = 0
        for slot, label, _icon in ATTACHMENT_SLOT_LABELS:
            path = resolve_asset(getattr(entry, slot))
            if not path or not os.path.exists(path):
                continue
            try:
                obj = import_mesh_file(path, "%s_%s" % (entry.entry_name, slot.capitalize()), coll)
                apply_display_color(obj, getattr(entry, SLOT_COLOR_FIELD[slot]))
                count += 1
            except Exception as exc:
                self.report({'WARNING'}, "%s: %s" % (label, exc))
        for i, row in enumerate(entry.visuals):
            path = resolve_asset(row.asset)
            if not path or not os.path.exists(path):
                continue
            try:
                obj = import_mesh_file(path, "%s_%s" % (entry.entry_name, row.label), coll)
                apply_display_color(obj, row.color)
                count += 1
            except Exception as exc:
                self.report({'WARNING'}, "%s: %s" % (row.label, exc))
        self.report({'INFO'}, "Da insert %d mesh cua %s" % (count, entry.entry_name))
        return {'FINISHED'}



# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
def _short(path, width=26):
    """Tinh gon ten file hien thi trong sidebar hep."""
    name = os.path.basename(path) if path else ""
    if len(name) > width:
        name = name[:width - 3] + "..."
    return name


def _slot_state(value, inherited=""):
    """(text, icon) trang thai file cua mot slot. `inherited` = file cua nhom khi slot chua co file rieng."""
    if not value and inherited:
        path = resolve_asset(inherited)
        return "Nhóm: " + _short(path, 20), _ic('LINKED' if os.path.exists(path) else 'ERROR')
    if not value:
        return "(chua co file)", _ic('BLANK1')
    path = resolve_asset(value)
    return _short(path), _ic('CHECKMARK' if os.path.exists(path) else 'ERROR')


def _slot_buttons(row, kind, index, slot, value):
    """Nut 'Gan file' (+ nut xoa lien ket) cho mot slot."""
    op = row.operator(DLIB_OT_import_asset.bl_idname, text="Gan file",
                      icon=_ic('FILEBROWSER'))
    op.kind = kind
    op.index = index
    op.slot = slot
    if value:
        op = row.operator(DLIB_OT_clear_asset.bl_idname, text="", icon=_ic('X'))
        op.kind = kind
        op.index = index
        op.slot = slot


def _folder_text(kind, entry, library=None):
    if entry.folder:
        folder, prefix = _location(kind, entry, library)
        if prefix:
            return "Thư mục nhóm: %s/%s (file riêng: %s*)" % (kind, folder, prefix)
        return "Thư mục: %s/%s" % (kind, entry.folder)
    return "Thư mục: (mục cũ - tạo khi gắn file)"


def _draw_slot(layout, kind, index, slot, label, icon, value, toggle=None, inherited=""):
    """Ve mot slot file.

    toggle = (obj, ten_prop): Apply Part nam o hang tren, con tick Add/Remove
    nam cung hang voi nut 'Gan file' o hang duoi. Neu khong co toggle thi
    ve giong cu (label + trang thai + nut tren cung mot hang).
    """
    if toggle is None:
        row = layout.row(align=True)
        row.label(text=label, icon=_ic(icon))
        text, state_icon = _slot_state(value, inherited)
        row.label(text=text, icon=state_icon)
        _slot_buttons(row, kind, index, slot, value)
        return
    head = layout.row(align=True)
    head.label(text=label, icon=_ic(icon))
    text, state_icon = _slot_state(value)
    head.label(text=text, icon=state_icon)
    act = layout.row(align=True)
    act.prop(toggle[0], toggle[1])
    _slot_buttons(act, kind, index, slot, value)


def _draw_scanbodies(layout, kind, index, entry, inherited=()):
    """Danh sach file Scanbody (khong gioi han so luong) cua Connection / nhom + nut them. `inherited` = Scanbody cua
    nhom, chi hien (chi doc) khi Connection chua co file rieng."""
    layout.label(text="Scanbody (nhiều file):", icon=_ic('MESH_PLANE'))
    for j, row in enumerate(entry.scanbodies):
        srow = layout.row(align=True)
        text, state_icon = _slot_state(row.asset)
        srow.label(text=text, icon=state_icon)
        op = srow.operator(DLIB_OT_remove_scanbody.bl_idname, text="", icon=_ic('X'))
        op.kind = kind
        op.index = index
        op.scan_index = j
    if not len(entry.scanbodies):
        for ref in inherited:
            text, state_icon = _slot_state("", ref)
            layout.label(text=text, icon=state_icon)
        if not inherited:
            layout.label(text="(chua co file)", icon=_ic('BLANK1'))
    op = layout.operator(DLIB_OT_add_scanbody.bl_idname, text="+ Add Scanbody", icon=_ic('ADD'))
    op.kind = kind
    op.index = index


def _draw_connection_entry(box, i, entry, library):
    sub = box.box()
    row = sub.row(align=True)
    row.prop(entry, "open", text="",
             icon=_ic('TRIA_DOWN' if entry.open else 'TRIA_RIGHT'))
    row.prop(entry, "entry_name", text="")
    op = row.operator(DLIB_OT_remove_connection.bl_idname,
                      text="", icon=_ic('TRASH'))
    op.index = i
    if not entry.open:
        return
    sub.label(text=_folder_text("connections", entry, library), icon=_ic('FILE_FOLDER'))
    if len(library.connection_groups):
        grow = sub.row(align=True)
        grow.prop(entry, "group", text="Nhóm", icon=_ic('FILE_FOLDER'))
        grow.operator(DLIB_OT_pick_connection_group.bl_idname, text="",
                      icon=_ic('DOWNARROW_HLT')).index = i
    gdef = _find_connection_group(library, entry.group.strip()) if entry.group.strip() else None
    for slot, label, icon in CONNECTION_SLOT_LABELS:
        field = CONNECTION_SLOT_FIELD[slot]
        own = getattr(entry, field)
        inherited = getattr(gdef, field) if gdef is not None and not own else ""
        _draw_slot(sub, "connection", i, slot, label, icon, own, inherited=inherited)
    _draw_scanbodies(sub, "connection", i, entry,
                     [row.asset for row in gdef.scanbodies if row.asset] if gdef is not None else ())
    sub.operator(DLIB_OT_insert_connection.bl_idname,
                 text="Insert vao scene", icon=_ic('IMPORT')).index = i


def _draw_connection_list(box, library):
    """Danh sach Connection: chua co nhom nao thi phang; co nhom thi gom theo thu muc (bo file chung o dau)."""
    members = {}
    for i, entry in enumerate(library.connections):
        members.setdefault(entry.group.strip(), []).append(i)
    if not len(library.connection_groups):
        for i, entry in enumerate(library.connections):
            _draw_connection_entry(box, i, entry, library)
        return
    order = sorted(range(len(library.connection_groups)),
                   key=lambda k: library.connection_groups[k].entry_name.casefold())
    for gi in order:
        gdef = library.connection_groups[gi]
        key = "conn:" + gdef.entry_name
        closed = key in _GROUP_CLOSED
        folder = box.box()
        head = folder.row(align=True)
        toggle = head.operator(DLIB_OT_toggle_attachment_group.bl_idname, text="", emboss=False,
                               icon=_ic('TRIA_RIGHT' if closed else 'TRIA_DOWN'))
        toggle.group = key
        head.prop(gdef, "entry_name", text="", icon=_ic('FILE_FOLDER'))
        head.label(text=str(len(members.get(gdef.entry_name, []))))
        head.operator(DLIB_OT_remove_connection_group.bl_idname, text="", icon=_ic('TRASH')).index = gi
        if closed:
            continue
        folder.label(text=_folder_text("connections", gdef), icon=_ic('FILE_FOLDER'))
        folder.label(text="File chung của nhóm (Connection trong nhóm kế thừa, gắn file riêng để ghi đè):",
                     icon=_ic('LINKED'))
        folder.operator(DLIB_OT_gather_groups.bl_idname, text="Gom file nhóm", icon=_ic('FILE_FOLDER'))
        for slot, label, icon in CONNECTION_SLOT_LABELS:
            _draw_slot(folder, "connection_group", gi, slot, label, icon, getattr(gdef, CONNECTION_SLOT_FIELD[slot]))
        _draw_scanbodies(folder, "connection_group", gi, gdef)
        for i in members.get(gdef.entry_name, []):
            _draw_connection_entry(folder, i, library.connections[i], library)
    loose = members.get("", [])
    if loose:
        key = "conn:"
        closed = key in _GROUP_CLOSED
        folder = box.box()
        head = folder.row(align=True)
        toggle = head.operator(DLIB_OT_toggle_attachment_group.bl_idname, text="(Chưa nhóm)", emboss=False,
                               icon=_ic('TRIA_RIGHT' if closed else 'TRIA_DOWN'))
        toggle.group = key
        head.label(text=str(len(loose)), icon=_ic('FILE_FOLDER'))
        if not closed:
            for i in loose:
                _draw_connection_entry(folder, i, library.connections[i], library)


class DLIB_PT_panel(Panel):
    bl_label = "Dental-Lib"
    bl_idname = "VIEW3D_PT_dental_lib"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Dental-Lib"

    def draw(self, context):
        layout = self.layout
        group = ensure_loaded(context)

        row = layout.row(align=True)
        row.operator(DLIB_OT_load_library.bl_idname, text="Nap thu vien",
                     icon=_ic('FILE_REFRESH'))
        row.operator(DLIB_OT_save_library.bl_idname, text="Luu thu vien",
                     icon=_ic('FILE_TICK'))
        col = layout.column(align=True)
        col.operator(DLIB_OT_open_folder.bl_idname, text="Mo thu muc thu vien",
                     icon=_ic('FILE_FOLDER'))
        col.label(text=_short(library_dir(), 46))

        # ---- 1. Implant Connection -------------------------------------
        box = layout.box()
        head = box.row(align=True)
        head.label(text="1. Implant Connection", icon=_ic('MESH_CYLINDER'))
        head.label(text=str(len(group.connections)))
        add_row = box.row(align=True)
        add_row.operator(DLIB_OT_add_connection.bl_idname,
                         text="+ Add Connection Base", icon=_ic('ADD'))
        add_row.operator(DLIB_OT_add_connection_group.bl_idname,
                         text="+ Group", icon=_ic('FILE_FOLDER'))
        _draw_connection_list(box, group)

        # ---- 2. Attachment ---------------------------------------------
        box = layout.box()
        head = box.row(align=True)
        head.label(text="2. Attachment", icon=_ic('MESH_CUBE'))
        head.label(text=str(len(group.attachments)))
        box.operator(DLIB_OT_add_attachment.bl_idname,
                     text="+ Add Attachment", icon=_ic('ADD'))
        named = any(entry.group.strip() for entry in group.attachments)
        for group_name, indices in grouped_indices(group.attachments):
            holder = box
            if named:   # co it nhat 1 nhom: gom theo thu muc (thu / mo); chua co nhom nao thi giu danh sach phang
                folder = box.box()
                closed = group_name in _GROUP_CLOSED
                head = folder.row(align=True)
                toggle = head.operator(DLIB_OT_toggle_attachment_group.bl_idname,
                                       text=group_name or "(Chưa nhóm)", emboss=False,
                                       icon=_ic('TRIA_RIGHT' if closed else 'TRIA_DOWN'))
                toggle.group = group_name
                head.label(text=str(len(indices)), icon=_ic('FILE_FOLDER'))
                if closed:
                    continue
                if group_name:
                    adef = _find_attachment_group(group, group_name)
                    if adef is not None:
                        folder.label(text=_folder_text("attachments", adef), icon=_ic('FILE_FOLDER'))
                        folder.operator(DLIB_OT_gather_groups.bl_idname, text="Gom file nhóm",
                                        icon=_ic('FILE_FOLDER'))
                holder = folder
            for i in indices:
                _draw_attachment_entry(holder, i, group.attachments[i], group)


def _draw_attachment_entry(box, i, entry, library=None):
    sub = box.box()
    row = sub.row(align=True)
    row.prop(entry, "open", text="",
             icon=_ic('TRIA_DOWN' if entry.open else 'TRIA_RIGHT'))
    row.prop(entry, "entry_name", text="")
    op = row.operator(DLIB_OT_remove_attachment.bl_idname,
                      text="", icon=_ic('TRASH'))
    op.index = i
    if not entry.open:
        return
    sub.label(text=_folder_text("attachments", entry, library), icon=_ic('FILE_FOLDER'))
    grow = sub.row(align=True)
    grow.prop(entry, "group", text="Nhóm", icon=_ic('FILE_FOLDER'))
    grow.operator(DLIB_OT_pick_attachment_group.bl_idname, text="",
                  icon=_ic('DOWNARROW_HLT')).index = i
    _draw_slot(sub, "attachment", i, "part_bar", "Apply Part Bar",
               'MESH_CUBE', entry.part_bar, toggle=(entry, "on_bar"))
    sub.prop(entry, "bar_in_sleeve")
    _draw_slot(sub, "attachment", i, "part_sleeve", "Apply Part Sleeve",
               'MESH_TORUS', entry.part_sleeve,
               toggle=(entry, "on_sleeve"))
    sub.label(text="Visual Objects (khong gioi han so luong):",
              icon=_ic('OUTLINER_OB_MESH'))
    for j, visual in enumerate(entry.visuals):
        vrow = sub.row(align=True)
        vrow.prop(visual, "label", text="", icon=_ic('MESH_DATA'))
        vrow.prop(visual, "color", text="")
        state_text, state_icon = _slot_state(visual.asset)
        vrow.label(text=state_text, icon=state_icon)
        op = vrow.operator(DLIB_OT_import_visual.bl_idname,
                           text="Gan file", icon=_ic('FILEBROWSER'))
        op.index = i
        op.visual_index = j
        op = vrow.operator(DLIB_OT_remove_visual.bl_idname,
                           text="", icon=_ic('TRASH'))
        op.index = i
        op.visual_index = j
    sub.operator(DLIB_OT_add_visual.bl_idname,
                 text="+ Add Visual Object",
                 icon=_ic('ADD')).index = i
    sub.operator(DLIB_OT_insert_attachment.bl_idname,
                 text="Insert vao scene",
                 icon=_ic('IMPORT')).index = i


# ---------------------------------------------------------------------------
# Preferences + Register
# ---------------------------------------------------------------------------
class DLibPreferences(AddonPreferences):
    bl_idname = __name__

    lib_dir: StringProperty(
        name="Thu muc thu vien",
        description="Noi luu library.json va toan bo mesh asset",
        subtype='DIR_PATH',
        default=LIB_DIR_DEFAULT,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "lib_dir")
        layout.label(text="Index: %s" % index_path())


_classes = (
    DLIB_PG_VisualObject,
    DLIB_PG_ScanbodyFile,
    DLIB_PG_AttachmentGroup,
    DLIB_PG_ConnectionGroup,
    DLIB_PG_ConnectionEntry,
    DLIB_PG_AttachmentEntry,
    DLIB_PG_Library,
    DLIB_OT_load_library,
    DLIB_OT_save_library,
    DLIB_OT_open_folder,
    DLIB_OT_add_connection,
    DLIB_OT_remove_connection,
    DLIB_OT_add_connection_group,
    DLIB_OT_remove_connection_group,
    DLIB_OT_set_connection_group,
    DLIB_OT_pick_connection_group,
    DLIB_OT_gather_groups,
    DLIB_OT_add_attachment,
    DLIB_OT_remove_attachment,
    DLIB_OT_toggle_attachment_group,
    DLIB_OT_set_attachment_group,
    DLIB_OT_pick_attachment_group,
    DLIB_OT_import_asset,
    DLIB_OT_clear_asset,
    DLIB_OT_add_scanbody,
    DLIB_OT_remove_scanbody,
    DLIB_OT_add_visual,
    DLIB_OT_remove_visual,
    DLIB_OT_import_visual,
    DLIB_OT_insert_connection,
    DLIB_OT_insert_attachment,
    DLIB_PT_panel,
    DLibPreferences,
)


@bpy.app.handlers.persistent
def _load_handler(dummy):
    """library.json la source of truth -> nap lai buffer moi lan mo file.

    Bat buoc dung decorator persistent: Blender xoa toan bo load_post khi mo
    file moi, neu khong thi handler tu register() bi mat sau lan load dau tien
    va thu vien khong bao gio duoc nap lai (dan den ghi de mat du lieu).
    """
    try:
        if bpy.context.scene is None:
            return
        sync_scene(bpy.context)
        gather_group_files(bpy.context)
    except Exception as exc:
        print(f"[Dental-Lib] Auto-load that bai: {exc}")


def _startup_load():
    """Mot lan sau khi bat add-on: nap thu vien va gom file nhom (khong lam trong draw())."""
    try:
        if bpy.context.scene is not None:
            ensure_loaded(bpy.context)
            gather_group_files(bpy.context)
    except Exception as exc:
        print(f"[Dental-Lib] Nap thu vien luc khoi dong that bai: {exc}")
    return None


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.dental_lib = PointerProperty(type=DLIB_PG_Library)
    if _load_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_handler)
    ensure_library_dir()
    if not bpy.app.background and not bpy.app.timers.is_registered(_startup_load):
        bpy.app.timers.register(_startup_load, first_interval=1.0)


def unregister():
    if bpy.app.timers.is_registered(_startup_load):
        bpy.app.timers.unregister(_startup_load)
    if _load_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_handler)
    del bpy.types.Scene.dental_lib
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()

