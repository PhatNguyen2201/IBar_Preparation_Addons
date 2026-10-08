bl_info = {
    "name": "Dental-Lib",
    "author": "Phat Nguyen",
    "version": (0, 1, 8),
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
   Screw, Scanbody (moi slot 1 file STL/PLY).
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
    dental_lib.connection_names() / get_connection(name)
    dental_lib.attachment_names() / get_attachment(name)
"""

import bpy
import os
import json
import re
import shutil
import hashlib

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
        write_index({"version": 1, "connections": [], "attachments": []})
    return root


def empty_index():
    return {"version": 1, "connections": [], "attachments": []}


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


def _file_digest(path):
    """SHA1 cua noi dung file (rong neu khong doc duoc)."""
    try:
        digest = hashlib.sha1()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return ""


def _asset_rel(kind, name, slot, ext, source):
    """Duong dan relative trong lib.

    Slug sinh tu ten entry; neu trung slug voi asset khac (khac noi dung) thi
    them hau to so de tranh ghi de. Cung noi dung -> tai dung (dedup).
    """
    base = slugify(name)
    for index in range(1, 1000):
        slug = base if index == 1 else "%s_%d" % (base, index)
        rel = "/".join((kind, slug, slot + ext))
        dest = os.path.join(library_dir(), *rel.split("/"))
        if not os.path.exists(dest):
            return rel
        src_sum, dst_sum = _file_digest(source), _file_digest(dest)
        if src_sum and dst_sum and src_sum == dst_sum:
            return rel
    digest = hashlib.sha1(os.path.abspath(source).encode("utf-8")).hexdigest()[:6]
    return "/".join((kind, "%s_%s" % (base, digest), slot + ext))


def store_asset(source, kind, name, slot):
    """Copy file mesh vao thu vien, tra ve duong dan tuong doi (relative)."""
    ensure_library_dir()
    ext = os.path.splitext(source)[1].lower()
    if ext not in MESH_EXTS:
        ext = ".stl"
    rel = _asset_rel(kind, name, slot, ext, source)
    dest = os.path.join(library_dir(), *rel.split("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(source, dest)
    return rel


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
# ---------------------------------------------------------------------------
def connection_names():
    return [c.get("name", "") for c in read_index()["connections"] if c.get("name")]


def get_connection(name):
    for entry in read_index()["connections"]:
        if entry.get("name") == name:
            return entry
    return None


def connection_asset(name, slot):
    entry = get_connection(name)
    if not entry:
        return ""
    return resolve_asset(entry.get(slot, ""))


def attachment_names():
    return [a.get("name", "") for a in read_index()["attachments"] if a.get("name")]


def get_attachment(name):
    for entry in read_index()["attachments"]:
        if entry.get("name") == name:
            return entry
    return None


def attachment_asset(name, slot):
    entry = get_attachment(name)
    if not entry:
        return ""
    return resolve_asset(entry.get(slot, ""))


def attachment_visuals(name):
    """[(label, abspath), ...] cac Visual Object cua Attachment."""
    entry = get_attachment(name)
    if not entry:
        return []
    out = []
    for visual in entry.get("visuals", []):
        out.append((visual.get("label") or "Visual",
                    resolve_asset(visual.get("asset", ""))))
    return out


def attachment_visuals_rgba(name):
    """[(label, abspath, (r, g, b, a)), ...] - Visual Object kem mau cua no."""
    entry = get_attachment(name)
    if not entry:
        return []
    out = []
    for visual in entry.get("visuals", []):
        out.append((visual.get("label") or "Visual",
                    resolve_asset(visual.get("asset", "")),
                    read_color(visual.get("color"), DEFAULT_VISUAL_COLOR)))
    return out


def attachment_slot_color(name, slot):
    """RGBA mac dinh/da luu cua Apply Part Bar | Apply Part Sleeve."""
    fallback = SLOT_DEFAULT_COLOR.get(slot, DEFAULT_VISUAL_COLOR)
    entry = get_attachment(name)
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
    ("scanbody", "Scanbody (STL/PLY)", 'MESH_PLANE'),
]

ATTACHMENT_SLOT_LABELS = [
    ("part_bar", "Apply Part Bar (STL/PLY)", 'MESH_CUBE'),
    ("part_sleeve", "Apply Part Sleeve (STL/PLY)", 'MESH_TORUS'),
]


class DLIB_PG_ConnectionEntry(PropertyGroup):
    entry_name: StringProperty(name="Library Name", default="New Connection")
    open: BoolProperty(name="Mo rong", default=True,
                       description="Thu/mo danh sach slot file cua entry nay")
    slot_base: StringProperty(name="Base", subtype='FILE_PATH', default="")
    slot_analog: StringProperty(name="Implant-Analog", subtype='FILE_PATH', default="")
    slot_screw: StringProperty(name="Screw", subtype='FILE_PATH', default="")
    slot_scanbody: StringProperty(name="Scanbody", subtype='FILE_PATH', default="")


class DLIB_PG_AttachmentEntry(PropertyGroup):
    entry_name: StringProperty(name="Attachment Name", default="New Attachment")
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
    attachments: CollectionProperty(type=DLIB_PG_AttachmentEntry)


# ---------------------------------------------------------------------------
# Dong bo JSON <-> Scene PropertyGroup
# ---------------------------------------------------------------------------
CONNECTION_SLOT_FIELD = {
    "base": "slot_base",
    "analog": "slot_analog",
    "screw": "slot_screw",
    "scanbody": "slot_scanbody",
}


def _lib_group(context):
    return context.scene.dental_lib


def index_from_scene(context):
    """Chuyen buffer tren scene ve dict JSON."""
    group = _lib_group(context)
    data = {"version": 1, "connections": [], "attachments": []}
    for entry in group.connections:
        item = {"name": entry.entry_name}
        for slot, field in CONNECTION_SLOT_FIELD.items():
            item[slot] = getattr(entry, field)
        data["connections"].append(item)
    for entry in group.attachments:
        item = {
            "name": entry.entry_name,
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
    group.attachments.clear()
    for item in data.get("connections", []):
        entry = group.connections.add()
        entry.entry_name = item.get("name", "Connection")
        for slot, field in CONNECTION_SLOT_FIELD.items():
            setattr(entry, field, item.get(slot, ""))
    for item in data.get("attachments", []):
        entry = group.attachments.add()
        entry.entry_name = item.get("name", "Attachment")
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
    if len(group.connections) or len(group.attachments):
        return group
    data = read_index()
    if data["connections"] or data["attachments"]:
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
        data = read_index()
        self.report({'INFO'}, "Da nap %d Connection, %d Attachment tu %s"
                    % (len(data["connections"]), len(data["attachments"]),
                       index_path()))
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
        _save_all(context)
        self.report({'INFO'}, "Da tao '%s' - chon file cho tung slot ben duoi"
                    % entry.entry_name)
        return {'FINISHED'}


class DLIB_OT_remove_connection(Operator):
    """Xoa Connection khoi thu vien (giu lai file asset)"""
    bl_idname = "dental_lib.remove_connection"
    bl_label = "Remove Connection"
    bl_options = set()

    index: IntProperty(default=-1)

    def execute(self, context):
        group = ensure_loaded(context)
        if 0 <= self.index < len(group.connections):
            name = group.connections[self.index].entry_name
            group.connections.remove(self.index)
            _save_all(context)
            self.report({'INFO'}, "Da xoa '%s'" % name)
            return {'FINISHED'}
        return {'CANCELLED'}


class DLIB_OT_add_attachment(Operator):
    """Them mot Attachment moi vao thu vien"""
    bl_idname = "dental_lib.add_attachment"
    bl_label = "Add Attachment"
    bl_options = set()

    def execute(self, context):
        group = ensure_loaded(context)
        entry = group.attachments.add()
        entry.entry_name = _unique_entry_name(group.attachments, "Attachment")
        _save_all(context)
        self.report({'INFO'}, "Da tao '%s'" % entry.entry_name)
        return {'FINISHED'}


class DLIB_OT_remove_attachment(Operator):
    """Xoa Attachment khoi thu vien (giu lai file asset)"""
    bl_idname = "dental_lib.remove_attachment"
    bl_label = "Remove Attachment"
    bl_options = set()

    index: IntProperty(default=-1)

    def execute(self, context):
        group = ensure_loaded(context)
        if 0 <= self.index < len(group.attachments):
            name = group.attachments[self.index].entry_name
            group.attachments.remove(self.index)
            _save_all(context)
            self.report({'INFO'}, "Da xoa '%s'" % name)
            return {'FINISHED'}
        return {'CANCELLED'}


# ---------------------------------------------------------------------------
# Operator: nap file STL/PLY vao mot slot cua entry
# ---------------------------------------------------------------------------
def _entry_by_index(context, kind, index):
    group = _lib_group(context)
    if kind == "connection":
        if 0 <= index < len(group.connections):
            return group.connections[index]
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
        ensure_loaded(context)
        entry = _entry_by_index(context, self.kind, self.index)
        if entry is None:
            self.report({'ERROR'}, "Khong tim thay entry trong thu vien")
            return {'CANCELLED'}
        source = bpy.path.abspath(self.filepath)
        if not source or not os.path.exists(source):
            self.report({'ERROR'}, "Khong tim thay file: %s" % source)
            return {'CANCELLED'}
        name = entry.entry_name
        try:
            if self.kind == "connection":
                rel = store_asset(source, "connections", name, self.slot)
                setattr(entry, CONNECTION_SLOT_FIELD[self.slot], rel)
            else:
                rel = store_asset(source, "attachments", name, self.slot)
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

    def execute(self, context):
        ensure_loaded(context)
        entry = _entry_by_index(context, self.kind, self.index)
        if entry is None:
            return {'CANCELLED'}
        if self.kind == "connection":
            setattr(entry, CONNECTION_SLOT_FIELD[self.slot], "")
        else:
            setattr(entry, self.slot, "")
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
        ensure_loaded(context)
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
            rel = store_asset(source, "attachments", entry.entry_name,
                              "visual_%02d" % self.visual_index)
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
            path = resolve_asset(getattr(entry, CONNECTION_SLOT_FIELD[slot]))
            if not path or not os.path.exists(path):
                continue
            try:
                import_mesh_file(path, "%s_%s" % (entry.entry_name, slot.capitalize()), coll)
                count += 1
            except Exception as exc:
                self.report({'WARNING'}, "%s: %s" % (label, exc))
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


def _slot_state(value):
    """(text, icon) trang thai file cua mot slot."""
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


def _draw_slot(layout, kind, index, slot, label, icon, value, toggle=None):
    """Ve mot slot file.

    toggle = (obj, ten_prop): Apply Part nam o hang tren, con tick Add/Remove
    nam cung hang voi nut 'Gan file' o hang duoi. Neu khong co toggle thi
    ve giong cu (label + trang thai + nut tren cung mot hang).
    """
    if toggle is None:
        row = layout.row(align=True)
        row.label(text=label, icon=_ic(icon))
        text, state_icon = _slot_state(value)
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
        box.operator(DLIB_OT_add_connection.bl_idname,
                     text="+ Add Connection Base", icon=_ic('ADD'))
        for i, entry in enumerate(group.connections):
            sub = box.box()
            row = sub.row(align=True)
            row.prop(entry, "open", text="",
                     icon=_ic('TRIA_DOWN' if entry.open else 'TRIA_RIGHT'))
            row.prop(entry, "entry_name", text="")
            op = row.operator(DLIB_OT_remove_connection.bl_idname,
                              text="", icon=_ic('TRASH'))
            op.index = i
            if not entry.open:
                continue
            for slot, label, icon in CONNECTION_SLOT_LABELS:
                _draw_slot(sub, "connection", i, slot, label, icon,
                           getattr(entry, CONNECTION_SLOT_FIELD[slot]))
            sub.operator(DLIB_OT_insert_connection.bl_idname,
                         text="Insert vao scene", icon=_ic('IMPORT')).index = i

        # ---- 2. Attachment ---------------------------------------------
        box = layout.box()
        head = box.row(align=True)
        head.label(text="2. Attachment", icon=_ic('MESH_CUBE'))
        head.label(text=str(len(group.attachments)))
        box.operator(DLIB_OT_add_attachment.bl_idname,
                     text="+ Add Attachment", icon=_ic('ADD'))
        for i, entry in enumerate(group.attachments):
            sub = box.box()
            row = sub.row(align=True)
            row.prop(entry, "open", text="",
                     icon=_ic('TRIA_DOWN' if entry.open else 'TRIA_RIGHT'))
            row.prop(entry, "entry_name", text="")
            op = row.operator(DLIB_OT_remove_attachment.bl_idname,
                              text="", icon=_ic('TRASH'))
            op.index = i
            if not entry.open:
                continue
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
    DLIB_PG_ConnectionEntry,
    DLIB_PG_AttachmentEntry,
    DLIB_PG_Library,
    DLIB_OT_load_library,
    DLIB_OT_save_library,
    DLIB_OT_open_folder,
    DLIB_OT_add_connection,
    DLIB_OT_remove_connection,
    DLIB_OT_add_attachment,
    DLIB_OT_remove_attachment,
    DLIB_OT_import_asset,
    DLIB_OT_clear_asset,
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
    except Exception as exc:
        print(f"[Dental-Lib] Auto-load that bai: {exc}")


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.dental_lib = PointerProperty(type=DLIB_PG_Library)
    if _load_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_handler)
    ensure_library_dir()


def unregister():
    if _load_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_handler)
    del bpy.types.Scene.dental_lib
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()

