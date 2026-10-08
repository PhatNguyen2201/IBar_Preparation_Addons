bl_info = {
    "name": "Rmvb-Bar",
    "author": "Phat Nguyen",
    "version": (0, 7, 0),
    "blender": (4, 5, 3),
    "location": "View3D > Sidebar > Rmvb-Bar",
    "description": "Thiet ke bar implant: Set / Connection / Bar Pillar / Top Bar Plane + Bar Segment tu cap nhat / Attachment / Sleeve",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}

"""Rmvb-Bar
===========
Panel thiet ke khung bar implant. Lay Connection Base va Attachment tu add-on
Dental-Lib. Quy trinh:

    Set Gingiva / Denture / Antagonist (chon object san co trong scene; Set CHI doi mau +
    danh dau + doi ten mesh, khong chuan bi - khoi cat nuouu tao khi Create Top Bar Plane cho
    Bar ('GingivaCut') va khi Create Sleeve Design cho Sleeve ('GingivaCut.Sleeve'), moi loai
    mot Offset Gingiva rieng)
      -> Select Connection Base + Place Connection (doc .constructionInfo)
      -> Bar Pillar -> Create Top Bar Plane -> Draw Line Bar (snap Plane) -> Bar Segment
         tu cap nhat -> Enable / Disable Preview cat Top Bar (modifier them san)
      -> Attachment (moi lan Add = 1 group)
      -> Sleeve Design
      -> Apply / Delete Bar Design -> Save Bar & Sleeve Design (STL)

Chuan do luong: 1 Blender unit = 1 mm (dung chung cach lam voi add-on iBar).

Mau hien thi lay tu thu vien Dental-Lib:
    Apply Part Bar   -> do, alpha 0.5 (mac dinh trong library.json)
    Apply Part Sleeve-> hong, alpha 0.5
    Visual Object    -> mau chon theo tung object tren panel Dental-Lib
"""

import bpy
import bmesh
import contextlib
import math
import os
import re
import sys
import time

from mathutils import Vector, Matrix
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    FloatVectorProperty,
    EnumProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.types import Menu, Operator, Panel, PropertyGroup, UIList
from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper
from bpy_extras import view3d_utils
import xml.etree.ElementTree as ET

MESH_EXTS = (".stl", ".ply")
MM_TO_BU = 1.0

COL_IMPORT = "Rmvb Import"
COL_CONNECTION = "Rmvb Connections"
COL_BARDESIGN = "BarDesign"          # Bar Pillar + Bar Segment (+ line)
COL_PILLAR = COL_BARDESIGN
COL_SEGMENT = COL_BARDESIGN
COL_CUTPLANE = "CutPlane"            # PlaneVisual + PlaneCubeCut + InsertionArrow
COL_ATTACHMENT = "Rmvb Attachment"
COL_SLEEVE = "Rmvb Sleeve"
COL_PREVIEW = "Rmvb Preview"

OBJ_SEGMENT = "BarSegment"
OBJ_BACKUP = "BarSegmentBackup"
OBJ_LINE = "Rmvb_BarLine"
OBJ_CENTER = "Rmvb_BarCenter"
OBJ_ARROW = "InsertionArrow"
OBJ_PLANE = "PlaneVisual"
OBJ_CUTTER = "PlaneCubeCut"
OBJ_SLEEVE = "Rmvb_Sleeve"
OBJ_GINGIVA_CUT = "GingivaCut"        # khoi cat nuouu RIENG cho BAR: ban copy Gingiva da chuan bi kin + offset (an)
OBJ_GINGIVA_CUT_SLEEVE = "GingivaCut.Sleeve"   # khoi cat nuouu RIENG cho SLEEVE: offset doc lap, an
OBJ_GINGIVA_CUT_BASE = "GingivaCut.base"   # mesh cache da chuan bi kin (chua offset), DUNG CHUNG cho ca 2 khoi cat

# Tien to ten modifier do add-on tao (rebuild xoa theo tien to nay)
MOD_PREFIX = "RMVB_"

# Ngung dung (mm) khi xac dinh cac dinh nam cung mot cao do dinh mui extrude.
TOP_EPS = 1e-4

GROUP_AXES_SIZE = 1.0               # mm: size Plain Axes (Empty) cua nhom Implant / Attachment
CENTER_GUIDE_WIDTH = 0.001         # mm: be rong khoi dan huong "Can giua be mat Bar" (sai so ngang toi da 0.0005 mm)
CENTER_GUIDE_HALF_HEIGHT = 100.0    # mm: nua chieu dai khoi dan huong (doc HUONG MUI TEN, cung truc extrude Bar)
CENTER_GUIDE_VERSION = 4            # 1 = dai phang tren Plane (khoa luon Z), 2 = tuong dung ho (khong dung duoc voi
                                    # Snap Mode Inside), 3 = khoi hop mong KIN doc tam bar (dai doc phap tuyen Plane),
                                    # 4 = dai doc HUONG MUI TEN (cung truc extrude Bar Segment)

CST_ON_PLANE = "RMVB_on_plane"
CST_CENTER = "RMVB_center_bar"
CST_ROT_PLANE = "RMVB_lock_rot_topbar"
CST_ROT_LIMIT = "RMVB_lock_rot_xy"
CST_COPY_LOC = "RMVB_lock_location"
CST_COPY_ROT = "RMVB_lock_rotation"

# Thong so chuan bi mesh (mm, truc local cua mesh)
GINGIVA_BASE_DEPTH = 10.0       # Gingiva: extrude day xuong 10 mm roi fill
GINGIVA_OFFSET_EPS = 1e-6       # Nguong so sanh offset trong chu ky (dung lai) khoi cat nuouu
CONN_BOTTOM_LIFT = 0.1          # Base ho day, buoc 1: extrude +0.1 mm theo z local
CONN_BOTTOM_EXTRUDE = 1.0       # buoc 2: tu phan moi extrude them -1 mm theo z local
CONN_BOTTOM_SCALE = 1.5         # ... va scale local x1.5 (tam = tam vong ho goc)
CONN_TOP_EXTRUDE = 30.0         # Base ho dinh (Screw): extrude 30 mm
PLANE_SIZE = 100.0              # PlaneVisual / PlaneCubeCut: 100 x 100 mm
PLANE_CUBE_HEIGHT = 100.0       # PlaneCubeCut: extrude +z local 100 mm (hop lap phuong)

# Mau hien thi cua Implant Connection (RGBA)
COLOR_CONN_VISUAL = (0.5, 0.5, 0.5, 1.0)     # ConnectionVisual: xam (Value 0.5), opacity 1
COLOR_CONN_ANALOG = (0.10, 0.30, 1.00, 1.0)  # Analog: xanh lam, opacity 1
COLOR_CONN_SCREW = (0.3, 0.3, 0.3, 0.8)      # Screw: xam (Value 0.3), opacity 0.8
OBJ_CONN_VISUAL = "ConnectionVisual"
OBJ_IMPLANT_GROUP = "Implant"                 # Plain Axes chung cua 1 implant: Implant_<rang>

# Mau dung khi thu vien khong khai bao (trung voi mac dinh cua Dental-Lib)
FALLBACK_PART_BAR_COLOR = (1.0, 0.0, 0.0, 0.5)       # do, alpha 0.5
FALLBACK_PART_SLEEVE_COLOR = (1.0, 0.45, 0.72, 0.5)  # hong, alpha 0.5
SLEEVE_COLOR = (1.0, 0.93, 0.50, 0.5)                 # vang nhat, opacity 0.5 (mau duy nhat cua Sleeve)
FALLBACK_VISUAL_COLOR = (0.75, 0.75, 0.80, 1.0)      # xam nhat


# ---------------------------------------------------------------------------
# Tiep can add-on Dental-Lib
# ---------------------------------------------------------------------------
def dlib():
    """Tra ve module dental_lib (add-on thu vien) hoac None."""
    module = sys.modules.get("dental_lib")
    if module is not None:
        return module
    try:
        import dental_lib as module  # noqa
        return module
    except Exception:
        pass
    # Fallback: thu tim trong thu muc add-on dang dung
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.append(here)
        import dental_lib as module  # noqa
        return module
    except Exception as exc:
        print(f"[Rmvb-Bar] Khong tim thay add-on Dental-Lib: {exc}")
        return None


def lib_connection_names():
    lib = dlib()
    return lib.connection_names() if lib else []


def lib_attachment_names():
    lib = dlib()
    return lib.attachment_names() if lib else []


def lib_connection_asset(name, slot):
    lib = dlib()
    return lib.connection_asset(name, slot) if lib else ""


def lib_attachment(name):
    lib = dlib()
    return lib.get_attachment(name) if lib else None


def lib_visuals(name):
    """[(label, abspath, rgba), ...] Visual Object kem mau cua tung object."""
    lib = dlib()
    if lib is None:
        return []
    if hasattr(lib, "attachment_visuals_rgba"):
        return lib.attachment_visuals_rgba(name)
    gray = getattr(lib, "DEFAULT_VISUAL_COLOR", (0.75, 0.75, 0.80, 1.0))
    return [(label, path, tuple(gray))
            for label, path in lib.attachment_visuals(name)]


def lib_slot_color(name, slot):
    """Mau mac dinh cua Apply Part Bar / Apply Part Sleeve tu thu vien."""
    fallbacks = {"part_bar": FALLBACK_PART_BAR_COLOR,
                 "part_sleeve": FALLBACK_PART_SLEEVE_COLOR}
    lib = dlib()
    if lib is not None and hasattr(lib, "attachment_slot_color"):
        try:
            return lib.attachment_slot_color(name, slot)
        except Exception:
            pass
    return fallbacks.get(slot, FALLBACK_VISUAL_COLOR)


# ---------------------------------------------------------------------------
# Collection / object helpers
# ---------------------------------------------------------------------------
def ensure_collection(name, parent=None):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        host = parent if parent is not None else bpy.context.scene.collection
        host.children.link(coll)
    return coll


def link_to(obj, coll):
    for user in list(obj.users_collection):
        user.objects.unlink(obj)
    coll.objects.link(obj)
    return obj


def new_object(name, mesh, coll):
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def remove_object(obj):
    if obj is None:
        return
    try:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
    except (ReferenceError, RuntimeError):
        return
    if data is not None and data.users == 0:
        try:
            bpy.data.meshes.remove(data)
        except Exception:
            pass


def purge_collection(coll):
    """Xoa sach moi object trong collection (cho duoc goi nhieu lan)."""
    for name in [ob.name for ob in list(coll.objects)]:
        remove_object(bpy.data.objects.get(name))


def set_color(obj, rgba):
    """Dat mau hien thi trong viewport cho de phan biet cac thanh phan."""
    try:
        obj.color = rgba
        obj.display_color = 'OBJECT'
    except Exception:
        pass


def set_display_color(obj, rgba):
    """Dat mau co ho tro alpha (trong suot) cho object.

    Dung helper cua Dental-Lib neu co (gan them material trung voi obj.color);
    neu khong thi roi xuong set_color() de tuong thich ban cu.
    """
    lib = dlib()
    if lib is not None and hasattr(lib, "apply_display_color"):
        try:
            return lib.apply_display_color(obj, rgba)
        except Exception:
            pass
    set_color(obj, rgba)
    return obj


def set_single_material(obj, rgba):
    """Chi giu DUNG 1 material (mau rgba, co alpha) tren obj.

    Boolean cong don slot material cua moi operand (Bar, Part Sleeve, Gingiva...) nen Sleeve ra voi
    nhieu lop mau; xoa het slot cu, dua moi mat ve slot 0 roi gan 1 material duy nhat."""
    set_color(obj, rgba)
    mesh = obj.data
    mesh.materials.clear()
    mesh.polygons.foreach_set("material_index", [0] * len(mesh.polygons))
    mesh.update()
    mat = None
    lib = dlib()
    if lib is not None and hasattr(lib, "color_material"):
        try:
            mat = lib.color_material(rgba)
        except Exception:
            mat = None
    if mat is None:
        name = "RMVB_Color_%g_%g_%g_%g" % tuple(rgba)
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.diffuse_color = tuple(rgba)
        if rgba[3] < 1.0 and hasattr(mat, "blend_method"):
            try:
                mat.blend_method = 'BLEND'
            except Exception:
                pass
    mesh.materials.append(mat)
    return obj


def ensure_object_mode(context):
    """Thoat Edit Mode (vd. dang Edit Line Bar) ve Object Mode; Edit Mode ghi diem vao mesh khi thoat."""
    if context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except RuntimeError:
            pass


def activate(context, obj, select=True):
    ensure_object_mode(context)     # select_all poll fail neu dang o Edit Mode
    bpy.ops.object.select_all(action='DESELECT')
    try:
        obj.select_set(select)
    except Exception:
        pass
    context.view_layer.objects.active = obj
    return obj


def blend_dir():
    """Thu muc chua file .blend hien tai ("" neu chua luu)."""
    path = bpy.data.filepath
    return os.path.dirname(path) if path else ""


def timestamp():
    return time.strftime("%y%m%d-%H%M")


# ---------------------------------------------------------------------------
# Mesh cache: doc STL/PLY thanh bpy.data.meshes (khong de lai object roi)
# ---------------------------------------------------------------------------
_MESH_CACHE = {}           # key -> ten mesh (KHONG giu tham chieu Python)
_DEFERRED_MESHES = []      # mesh boolean sinh ra, duoc don o cuoi operator


def _cached_mesh(key):
    """Mesh da cache theo key, hoac None neu da bi xoa (undo / purge / file moi).

    Chi luu TEN mesh: giu tham chieu Python toi mesh da bi xoa se gay loi
    "StructRNA of type Mesh has been removed" khi truy cap.
    """
    name = _MESH_CACHE.get(key)
    if not name:
        return None
    mesh = bpy.data.meshes.get(name)
    if mesh is None or mesh.get("rmvb_cache_key") != repr(key):
        _MESH_CACHE.pop(key, None)
        return None
    return mesh


def mesh_from_file(filepath, scale=1.0):
    """Import STL/PLY va tra ve Mesh datablock duoc dung lai nhieu lan."""
    if not filepath or not os.path.exists(filepath):
        raise FileNotFoundError("Khong tim thay file mesh: %s" % filepath)
    key = (os.path.abspath(filepath), os.path.getmtime(filepath), round(scale, 6))
    cached = _cached_mesh(key)
    if cached is not None:
        return cached

    ext = os.path.splitext(filepath)[1].lower()
    before = {ob.name for ob in bpy.data.objects}
    if ext == ".ply":
        bpy.ops.wm.ply_import(filepath=filepath, global_scale=scale)
    else:
        bpy.ops.wm.stl_import(filepath=filepath, global_scale=scale)
    created = [ob for ob in bpy.data.objects
               if ob.name not in before and ob.type == 'MESH']
    if not created:
        raise RuntimeError("File khong chua mesh: %s" % filepath)

    bm = bmesh.new()
    for ob in created:
        temp = bmesh.new()
        temp.from_mesh(ob.data)
        temp.transform(ob.matrix_world)
        merge_map = {}
        for vert in temp.verts:
            merge_map[vert.index] = bm.verts.new(vert.co)
        for face in temp.faces:
            try:
                bm.faces.new([merge_map[v.index] for v in face.verts])
            except ValueError:
                pass
        temp.free()
    mesh = bpy.data.meshes.new(os.path.basename(filepath))
    bm.to_mesh(mesh)
    bm.free()
    for ob in created:
        if ob.name in bpy.data.objects:
            bpy.data.objects.remove(ob, do_unlink=True)
    mesh.use_fake_user = True          # thu vien STL khong bi purge khi khong con object
    mesh["rmvb_cache_key"] = repr(key)
    _MESH_CACHE[key] = mesh.name
    return mesh


def object_from_mesh(name, mesh, coll, matrix=None):
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    if matrix is not None:
        obj.matrix_world = matrix
    return obj


# ---------------------------------------------------------------------------
# Boundary loop: phat hien cac vung mo cua mesh
# ---------------------------------------------------------------------------
def boundary_loops(bm):
    """Danh sach cac vong bien cua mesh mo.

    Tra ve list[dict]: {"edges": [BMEdge...], "verts": [BMVert theo thu tu vong],
    "z": gia tri Z trung binh trong toa do local}
    """
    bm.verts.index_update()
    bm.edges.index_update()
    bm.edges.ensure_lookup_table()
    seen = set()
    loops = []
    for edge in bm.edges:
        if not edge.is_boundary or edge.index in seen:
            continue
        stack = [edge]
        comp = []
        while stack:
            cur = stack.pop()
            if cur.index in seen:
                continue
            seen.add(cur.index)
            comp.append(cur)
            for vert in cur.verts:
                for link in vert.link_edges:
                    if link.is_boundary and link.index not in seen:
                        stack.append(link)
        verts = ordered_loop_verts(comp)
        z_mean = sum(v.co.z for v in verts) / max(1, len(verts))
        loops.append({"edges": comp, "verts": verts, "z": z_mean})
    return loops


def ordered_loop_verts(loop):
    """Thu tu dinh cua mot vong bien lien ket kin."""
    if not loop:
        return []
    edge_ids = {edge.index for edge in loop}
    ordered = []
    current = loop[0]
    prev_vert = None
    used_edges = set()
    guard = 0
    while current is not None and guard <= len(loop) * 2 + 4:
        guard += 1
        used_edges.add(current.index)
        vert_a, vert_b = current.verts
        if prev_vert is None:
            ordered.append(vert_a)
            nxt_vert = vert_b
        else:
            nxt_vert = vert_b if prev_vert is vert_a else vert_a
        ordered.append(nxt_vert)
        prev_vert = nxt_vert
        following = None
        for edge in nxt_vert.link_edges:
            if edge.index in edge_ids and edge.index not in used_edges:
                following = edge
                break
        current = following
    return ordered


# ---------------------------------------------------------------------------
# Boolean / modifier khong dung ops (an toan trong background va modal)
# ---------------------------------------------------------------------------
def evaluated_mesh_object(obj, name=None, coll=None):
    """Copy da apply toan bo modifier (mesh tinh theo toa do local cua obj)."""
    context = bpy.context
    context.view_layer.update()
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    mesh = _mesh_from_evaluated(obj.evaluated_get(depsgraph))
    mesh.name = (name or obj.name) + "_eval"
    new = bpy.data.objects.new(name or obj.name + ".eval", mesh)
    host = coll if coll is not None else context.scene.collection
    host.objects.link(new)
    new.matrix_world = obj.matrix_world.copy()
    return new


def _mesh_from_evaluated(evaluated):
    """new_from_object co fallback (preserve_all_data_layers lam mat mesh)."""
    mesh = bpy.data.meshes.new_from_object(evaluated)
    if len(mesh.polygons) == 0:
        try:
            alt = bpy.data.meshes.new_from_object(
                evaluated, preserve_all_data_layers=True)
            if len(alt.polygons) > 0:
                bpy.data.meshes.remove(mesh)
                return alt
            bpy.data.meshes.remove(alt)
        except Exception:
            pass
    return mesh


def add_boolean(target, operand, operation, keep_source=True,
                solver='EXACT', use_self=False):
    mod = target.modifiers.new(name="RMVB_Boolean", type='BOOLEAN')
    mod.operation = operation            # 'DIFFERENCE' | 'UNION' | 'INTERSECT'
    mod.object = operand
    mod.solver = solver
    for prop, value in (("use_self", use_self), ("use_hole_tolerant", False)):
        if hasattr(mod, prop):
            try:
                setattr(mod, prop, value)
            except Exception:
                pass
    return mod


def _mesh_quality(obj):
    """(polys, boundary_edges, non_manifold_edges) - dung quyet dinh solver."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    polys = len(bm.faces)
    bnd = sum(1 for edge in bm.edges if edge.is_boundary)
    nonmani = sum(1 for edge in bm.edges if len(edge.link_faces) != 2)
    bm.free()
    return polys, bnd, nonmani


def apply_modifiers_in_place(obj):
    """Apply kieu khong ops: lay mesh evaluated roi thay vao data cu."""
    context = bpy.context
    context.view_layer.update()
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    mesh = _mesh_from_evaluated(obj.evaluated_get(depsgraph))
    old = obj.data
    obj.data = mesh
    mesh.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return obj


def boolean_objects(target, operands, operation, solvers=None):
    """target = target <operation> cac operand; thu lan luot cac solver.

    Solver MANIFOLD cho ket qua kin dao nhat; EXACT (va EXACT + use_self) duoc
    dung lam bo phan khi dau vao co dinh ky khong manifold.
    """
    operands = [o for o in operands if o is not None]
    if not operands:
        return target
    if solvers is None:
        solvers = ('MANIFOLD', 'EXACT')
    source = target.data
    original = source.copy()
    original.name = target.name + ".src"
    best = None
    closed = False
    candidates = []            # ban copy chua tung gan vao object -> don duoc
    for index, solver in enumerate(solvers):
        for flag in ((False, True) if solver == 'EXACT' else (False,)):
            target.data = original.copy()
            for mod in [m for m in target.modifiers
                        if m.name.startswith("RMVB_Boolean")]:
                target.modifiers.remove(mod)
            for operand in operands:
                add_boolean(target, operand, operation, solver=solver,
                            use_self=(solver == 'EXACT' and flag))
            bpy.context.view_layer.update()
            apply_modifiers_in_place(target)
            for mod in [m for m in target.modifiers
                        if m.name.startswith("RMVB_Boolean")]:
                target.modifiers.remove(mod)
            polys, bnd, nonmani = _mesh_quality(target)
            if polys == 0:
                continue
            score = bnd * 1000 + nonmani
            if best is None or score < best[0]:
                best = (score, target.data.copy(), solver, flag)
                candidates.append(best[1])
            if bnd == 0:
                closed = True          # khong con canh ho: du dung, khong thu solver cham hon
                break
        if closed:
            break
    if best is not None:
        old = target.data
        target.data = best[1]
        target.data.name = old.name
        if old.users == 0:
            bpy.data.meshes.remove(old)
        else:
            _defer_mesh(old)
    if original.users == 0:
        bpy.data.meshes.remove(original)
    else:
        _defer_mesh(original)
    for mesh in candidates:
        try:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
            else:
                _defer_mesh(mesh)
        except ReferenceError:
            pass
    _defer_mesh(source)
    return target


def solvers_for(obj):
    """Solver cho object co dau ruan de: tranh Manifold crash native."""
    try:
        if obj is not None and obj.get("rmvb_degenerate"):
            return ('EXACT',)
    except Exception:
        pass
    return None


def _defer_mesh(mesh):
    """Ghi nho mesh do boolean sinh ra de don o lan purge gan nhat."""
    try:
        if mesh is not None and mesh.name in bpy.data.meshes:
            _DEFERRED_MESHES.append(mesh)
            if len(_DEFERRED_MESHES) > 4096:
                del _DEFERRED_MESHES[:2048]
    except ReferenceError:
        pass


def purge_unused_meshes():
    """Xoa mesh cua Rmvb-Bar khong con object nao dung (goi cuoi operator).

    Chi cham vao danh sach mesh do chinh boolean sinh ra; bo qua mesh co
    use_fake_user (thu vien STL trong _MESH_CACHE) va mesh con duoc dung.
    """
    context = bpy.context
    try:
        context.view_layer.update()
    except Exception:
        pass
    left = []
    for mesh in _DEFERRED_MESHES:
        try:
            if mesh.users > 0 or mesh.use_fake_user:
                left.append(mesh)
                continue
            bpy.data.meshes.remove(mesh)
        except ReferenceError:
            pass
        except Exception:
            pass
    _DEFERRED_MESHES[:] = left


# ---------------------------------------------------------------------------
# Xuat STL (tuong thich Blender 4.x / 5.x)
# ---------------------------------------------------------------------------
def export_stl(objects, filepath, context):
    """Xuat danh sach object ra STL binary."""
    objs = [o for o in objects if o is not None and o.name in bpy.data.objects]
    if not objs:
        raise RuntimeError("Khong co object de xuat STL")
    folder = os.path.dirname(filepath)
    if folder:
        os.makedirs(folder, exist_ok=True)
    unhidden = []
    for obj in objs:
        if obj.hide_get():
            obj.hide_set(False)
            unhidden.append(obj)
    activate(context, objs[0])
    for obj in objs:
        try:
            obj.select_set(True)
        except Exception:
            pass
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=filepath, export_selected_objects=True,
                              apply_modifiers=True, global_scale=1.0)
    elif hasattr(bpy.ops.export_mesh, "stl"):
        bpy.ops.export_mesh.stl(filepath=filepath, use_selection=True)
    else:
        raise RuntimeError("Blender khong co exporter STL")
    for obj in unhidden:
        obj.hide_set(True)
    return filepath


# ---------------------------------------------------------------------------
# View / transform orientation
# ---------------------------------------------------------------------------
def use_local_orientation(context):
    """Dat transform orientation = Local (dung khi sua dinh Bar Pillar / Segment).

    Blender 4.x: tool_settings.transform_orientation
    Blender 5.x: scene.transform_orientation_slots[0].type
    """
    done = False
    try:
        context.tool_settings.transform_orientation = 'LOCAL'
        done = True
    except Exception:
        pass
    if not done:
        try:
            slots = context.scene.transform_orientation_slots
            if slots:
                slots[0].type = 'LOCAL'
                done = True
        except Exception:
            pass
    try:
        context.tool_settings.transform_pivot_point = 'INDIVIDUAL_ORIGINS'
    except Exception:
        pass
    return done


def view_3d_area(context):
    if context.area is not None and context.area.type == 'VIEW_3D':
        return context.area
    if context.screen is None:
        return None
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            return area
    return None


# ---------------------------------------------------------------------------
# Doc file .constructionInfo / ImplantDirectionPosition.xml
# ---------------------------------------------------------------------------
def matrix_from_element(element):
    """Chuyen <MatrixImplantGeometry> (_00.._33) thanh mathutils.Matrix."""
    values = {child.tag: child.text for child in element}

    def num(key):
        try:
            return float(values.get(key, 0.0))
        except (TypeError, ValueError):
            return 0.0

    return Matrix((
        (num("_00"), num("_10"), num("_20"), num("_30")),
        (num("_01"), num("_11"), num("_21"), num("_31")),
        (num("_02"), num("_12"), num("_22"), num("_32")),
        (num("_03"), num("_13"), num("_23"), num("_33")),
    ))


def parse_construction_info(filepath):
    """Lay danh sach implant: [{'tooth','type','matrix','axis'}]."""
    root = ET.parse(filepath).getroot()
    implants = []
    for tooth in root.findall(".//Tooth"):
        implant_type = tooth.findtext("ImplantType", default="None")
        geometry = tooth.find("MatrixImplantGeometry")
        if implant_type in (None, "None") or geometry is None:
            continue
        axis = None
        axis_element = tooth.find("AxisImplant")
        if axis_element is not None:
            try:
                axis = Vector((float(axis_element.findtext("x", 0.0)),
                               float(axis_element.findtext("y", 0.0)),
                               float(axis_element.findtext("z", 0.0))))
            except (TypeError, ValueError):
                axis = None
        implants.append({
            "tooth": tooth.findtext("Number", default="?"),
            "type": implant_type,
            "matrix": matrix_from_element(geometry),
            "axis": axis,
        })
    return implants


# ---------------------------------------------------------------------------
# Combobox lay danh sach tu thu vien Dental-Lib
#   Dung Menu (ve lai moi lan mo) + operator gan gia tri thang, KHONG dung
#   EnumProperty dong: callback items tra ve chuoi tao moi nen Blender co the
#   doc chuoi da bi giai phong -> chon muc trong dropdown khong an.
# ---------------------------------------------------------------------------
def get_connection_items():
    return lib_connection_names()


def get_attachment_items():
    return lib_attachment_names()


def _clamp_index(value, count):
    return max(0, min(int(value), max(0, count - 1)))


class RMVB_OT_pick_library_item(Operator):
    """Chon Connection Base / Attachment trong thu vien Dental-Lib"""
    bl_idname = "rmvb.pick_library_item"
    bl_label = "Chon muc thu vien"
    bl_options = {'INTERNAL'}

    kind: EnumProperty(
        name="Kind",
        items=[('CONNECTION', "Connection", ""), ('ATTACHMENT', "Attachment", "")],
        default='CONNECTION')
    index: IntProperty(name="Index", default=0, min=0)

    def execute(self, context):
        props = context.scene.rmvb
        if self.kind == 'CONNECTION':
            names = get_connection_items()
            props.connection_index = _clamp_index(self.index, len(names))
            props.connection_name = names[props.connection_index] if names else ""
        else:
            names = get_attachment_items()
            props.attachment_index = _clamp_index(self.index, len(names))
            props.active_attachment = names[props.attachment_index] if names else ""
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


def _draw_library_menu(layout, kind, names, icon):
    if not names:
        layout.label(text="(Trống - thêm mục trong Dental-Lib)", icon='ERROR')
        return
    for index, name in enumerate(names):
        op = layout.operator(RMVB_OT_pick_library_item.bl_idname, text=name, icon=icon)
        op.kind = kind
        op.index = index


def lib_connection_groups(names):
    """[(ten nhom, [ten Connection, ...]), ...] theo Dental-Lib; thu vien cu khong co nhom -> 1 nhom ""."""
    lib = dlib()
    if lib is not None and hasattr(lib, "connection_groups"):
        groups = lib.connection_groups()
        if groups:
            return groups
    return [("", list(names))]


def _draw_grouped_pick(layout, kind, names, groups, icon):
    """Menu chon muc thu vien gom theo nhom (tieu de thu muc + cac muc); chua co nhom nao thi danh sach phang.
    Chi so gui cho operator la vi tri trong danh sach thu vien."""
    if not any(group for group, _members in groups):
        _draw_library_menu(layout, kind, names, icon)
        return
    index_of = {name: index for index, name in enumerate(names)}
    for position, (group, members) in enumerate(groups):
        if position:
            layout.separator()
        layout.label(text=group or "(Chưa nhóm)", icon='FILE_FOLDER')
        for name in members:
            if name not in index_of:
                continue
            op = layout.operator(RMVB_OT_pick_library_item.bl_idname, text=name, icon=icon)
            op.kind = kind
            op.index = index_of[name]


class RMVB_MT_pick_connection(Menu):
    bl_label = "Select Connection Base"

    def draw(self, context):
        names = get_connection_items()
        _draw_grouped_pick(self.layout, 'CONNECTION', names, lib_connection_groups(names), 'MESH_CYLINDER')


def lib_attachment_groups(names):
    """[(ten nhom, [ten Attachment, ...]), ...] theo Dental-Lib; thu vien cu khong co nhom -> 1 nhom ""."""
    lib = dlib()
    if lib is not None and hasattr(lib, "attachment_groups"):
        groups = lib.attachment_groups()
        if groups:
            return groups
    return [("", list(names))]


class RMVB_MT_pick_attachment(Menu):
    bl_label = "Select Attachment"

    def draw(self, context):
        names = get_attachment_items()
        _draw_grouped_pick(self.layout, 'ATTACHMENT', names, lib_attachment_groups(names), 'MESH_CUBE')


def _save_dir_get(self):
    """Thu muc luu: gia tri nguoi dung chon, neu trong thi lay thu muc file .blend."""
    stored = self.get("save_dir_value", "")
    return stored if stored else blend_dir()


def _save_dir_set(self, value):
    self["save_dir_value"] = value


# ---------------------------------------------------------------------------
# Property group
# ---------------------------------------------------------------------------
def _group_name_update(self, context):
    """Doi ten group: doi ten Empty cua group va cap nhat Lock dang tro toi ten cu."""
    props = context.scene.rmvb
    old = self.get("prev_name", "")
    self["prev_name"] = self.name
    if old and old != self.name:
        for other in props.groups:
            if other.lock_target == old:
                other.lock_target = self.name
    if self.empty is not None:
        try:
            self.empty.name = "Att_" + self.name
        except Exception:
            pass


def _group_lock_update(self, context):
    apply_group_locks(self, context.scene.rmvb)


def _group_align_update(self, context):
    """Doi trang thai Dao 180 do: xoay lai group ngay (handler depsgraph chi chay khi co thay doi khac)."""
    if self.align_x_bar and valid_obj(self.empty):
        align_group_x(self, context.scene.rmvb)


def _bar_param_update(self, context):
    """Doi Be rong / Chieu cao bar: Bar Segment cap nhat ngay."""
    try:
        sync_bar_segment(context.scene, force=True)
    except Exception as exc:
        print("[Rmvb-Bar] Khong cap nhat duoc Bar Segment: %s" % exc)


_GROUP_SELECT_LOCK = [False]    # True: group_index doi do code, khong tu chon Empty


def _group_index_update(self, context):
    """Bam vao muc trong danh sach Attachment: chon Plain Axes cua group + cong cu Move."""
    if _GROUP_SELECT_LOCK[0]:
        return
    if 0 <= self.group_index < len(self.groups):
        select_group_for_move(context, self.groups[self.group_index])


def set_group_index(props, index):
    """Dat group_index bang code ma KHONG kich hoat chon Empty."""
    _GROUP_SELECT_LOCK[0] = True
    try:
        props.group_index = max(0, index)
    finally:
        _GROUP_SELECT_LOCK[0] = False


def _gingiva_offset_update(self, context):
    """Doi Offset Gingiva Bar: ap dung lai khoi cat nuouu CUA BAR (neu da tao) va cap nhat stack
    modifier cua Bar Segment ngay; chua Create Top Bar Plane thi chi luu gia tri, khong tao som.
    Khoi cat cua Sleeve (GingivaCut.Sleeve) khong bi anh huong."""
    try:
        props = context.scene.rmvb
        if valid_obj(props.gingiva_cutter) or valid_obj(props.bar_segment):
            ensure_gingiva_cutter(props)
        if valid_obj(props.bar_segment):
            rebuild_segment_modifiers(context)
    except Exception as exc:
        print("[Rmvb-Bar] Khong cap nhat duoc khoi cat Gingiva (Bar): %s" % exc)


_GCUT_QUIET = [False]     # True: dang di du offset tu file cu -> khong dung lai khoi cat


def _gingiva_offset_sleeve_update(self, context):
    """Doi Offset Gingiva Sleeve: chi dung lai khoi cat nuouu RIENG CUA SLEEVE (neu no da ton tai
    tu lan Create Sleeve Design dau tien). Bar Segment va khoi cat cua Bar khong doi."""
    if _GCUT_QUIET[0]:
        return                      # luc mo file: chi di du gia tri, Create Sleeve Design moi dung
    try:
        props = context.scene.rmvb
        if valid_obj(props.gingiva_cutter_sleeve) or valid_obj(props.sleeve_object):
            ensure_gingiva_cutter(props, sleeve=True)
    except Exception as exc:
        print("[Rmvb-Bar] Khong cap nhat duoc khoi cat Gingiva (Sleeve): %s" % exc)


class RMVB_PG_PlacedConnection(PropertyGroup):
    tooth: StringProperty(name="Tooth", default="?")
    lib_name: StringProperty(name="Library", default="")
    group_object: PointerProperty(name="Implant group", type=bpy.types.Object)
    base_object: PointerProperty(name="Base", type=bpy.types.Object)
    visual_object: PointerProperty(name="ConnectionVisual", type=bpy.types.Object)
    analog_object: PointerProperty(name="Analog", type=bpy.types.Object)
    screw_object: PointerProperty(name="Screw", type=bpy.types.Object)
    scanbody_object: PointerProperty(name="Scanbody (file cu)", type=bpy.types.Object)   # chi de don file .blend cu


class RMVB_PG_PartRef(PropertyGroup):
    object: PointerProperty(name="Object", type=bpy.types.Object)
    tooth: StringProperty(name="Tooth", default="")


class RMVB_PG_AttachmentGroup(PropertyGroup):
    """Mot lan Add Attachment = mot group: Empty cha + Part Bar + Part Sleeve + Visual."""
    name: StringProperty(
        name="Tên Attachment",
        description="Ten group Attachment (mac dinh lay theo ten Attachment trong "
                    "thu vien). Doi ten se doi ten Empty cua group",
        default="", update=_group_name_update)
    lib_name: StringProperty(name="Library", default="")
    empty: PointerProperty(name="Group", type=bpy.types.Object)
    part_bar: PointerProperty(name="Part Bar", type=bpy.types.Object)
    part_sleeve: PointerProperty(name="Part Sleeve", type=bpy.types.Object)
    visuals: CollectionProperty(type=RMVB_PG_PartRef)
    on_bar: BoolProperty(
        name="Add/Remove on Bar", default=True,
        description="Lay tu Dental-Lib: True = Union len Bar, False = Difference")
    bar_in_sleeve: BoolProperty(
        name="Attachment on Bar khi tạo Sleeve", default=False,
        description="Lay tu Dental-Lib: tick = Part Bar cua Attachment nay VAN duoc ap len Bar "
                    "(Union / Difference theo Add/Remove on Bar) khi bam Create Sleeve Design, "
                    "khong bi bo qua")
    on_sleeve: BoolProperty(
        name="Add/Remove on Sleeve", default=False,
        description="Lay tu Dental-Lib: True = Union len Sleeve, False = Difference")
    center_bar: BoolProperty(
        name="Căn giữa bề mặt Bar",
        description="Tam group luon nam NGAY GIUA be mat Bar Segment theo be rong bar (tren duong "
                    "tam line): keo group doc theo Bar thi group truot theo tam, khong lech sang hai "
                    "ben. CHI doi vi tri ngang - chieu cao so voi Plane van tu do (tick Lock Z de giu "
                    "group tren Plane). Khong anh huong huong xoay",
        default=False, update=_group_lock_update)
    align_x_bar: BoolProperty(
        name="Trục X theo dọc Bar",
        description="Truc X cua group luon chay doc theo tam Bar Segment tai vi tri group (theo chieu "
                    "ve line, tren mat Plane): doi vi tri doc Bar thi group xoay theo cho cong cua "
                    "bar. Tu giu truc Z vuong goc Plane nhu Lock Rotation; xoay tay quanh Z bi ghi de",
        default=False, update=_group_lock_update)
    align_x_flip: BoolProperty(
        name="Đảo 180°",
        description="Xoay group them 180 do quanh Z (quanh phap tuyen Plane) de huong Attachment di "
                    "nguoc chieu ve line. Chi co tac dung khi tick 'Truc X theo doc Bar'",
        default=False, update=_group_align_update)
    lock_topbar: BoolProperty(
        name="Lock Z với Top Bar",
        description="Tam group luon nam tren mat phang PlaneVisual (chi khoa Z local "
                    "cua Plane, X/Y tu do). Khong anh huong huong xoay",
        default=False, update=_group_lock_update)
    lock_rot_topbar: BoolProperty(
        name="Lock Rotation với Top Bar",
        description="Khoa xoay X va Y theo PlaneVisual: truc Z cua group luon vuong goc "
                    "Plane (nghieng Plane thi group nghieng theo). KHONG khoa xoay Z: van "
                    "xoay duoc quanh phap tuyen Plane. Khong anh huong vi tri",
        default=False, update=_group_lock_update)
    lock_attachment: BoolProperty(
        name="Lock Location & Rotation với Attachment",
        description="Group luon cung vi tri va huong xoay voi mot group Attachment khac",
        default=False, update=_group_lock_update)
    lock_target: StringProperty(
        name="Attachment", description="Group Attachment dung lam goc",
        default="", update=_group_lock_update)


class RMVB_PG_props(PropertyGroup):
    # Set: doi tuong da co trong scene
    gingiva_object: PointerProperty(name="Gingiva", type=bpy.types.Object)
    denture_object: PointerProperty(name="Denture", type=bpy.types.Object)
    antagonist_object: PointerProperty(name="Antagonist", type=bpy.types.Object)

    # Offset cua khoi cat nuouu DUNG CHO BAR (Boolean Difference cua Bar Segment voi Gingiva)
    gingiva_offset: FloatProperty(
        name="Offset Gingiva Bar (mm)", default=0.0, soft_min=-2.0, soft_max=2.0, unit='LENGTH',
        update=_gingiva_offset_update,
        description="CHỈ ÁP DỤNG CHO BAR: nới / thu hẹp khối cắt nướu 'GingivaCut' trước khi "
                    "Boolean Difference với Bar Segment: + = phình khối cắt ra ngoài, Bar bị cắt "
                    "HỞ, cách mặt nướu đúng số mm này; − = thu khối cắt lại, Bar ăn SÂU vào nướu; "
                    "0 = cắt sát mặt nướu (không dời đỉnh). Khối cắt (ẩn) được tạo khi Create Top "
                    "Bar Plane và luôn cập nhật theo thông số này. Sleeve có khối cắt "
                    "'GingivaCut.Sleeve' và thông số Offset Gingiva Sleeve riêng (mục 6). "
                    "Mesh offset dựng bằng cách dời toàn bộ đỉnh của bản copy đã đóng kín của "
                    "Gingiva dọc pháp tuyến của nó (không Remesh nên biên dạng scan giữ nguyên)")
    gingiva_cutter: PointerProperty(name="Gingiva Cutter Bar (ẩn)", type=bpy.types.Object)
    gingiva_cutter_sleeve: PointerProperty(name="Gingiva Cutter Sleeve (ẩn)", type=bpy.types.Object)

    # Connection Base + constructionInfo
    connection_index: IntProperty(name="Connection Index", default=0, min=0)
    connection_name: StringProperty(name="Connection Name", default="")
    construction_file: StringProperty(name="constructionInfo",
                                      subtype='FILE_PATH', default="")
    placed: CollectionProperty(type=RMVB_PG_PlacedConnection)
    use_org_txt: BoolProperty(
        name="Transform theo before/transform.txt",
        description="Khi Place Connection, doc before.txt + transform.txt (do add-on iBar ghi) o thu "
                    "muc constructionInfo (hoac thu muc file .blend) va dua implant tu toa do file "
                    "ve toa do lam viec: transform x before^-1. Save Bar & Sleeve se dua nguoc ve "
                    "toa do file. Tat neu Gingiva dang o toa do file",
        default=True)
    org_active: BoolProperty(
        name="Da transform theo txt", default=False,
        description="Place Connection gan nhat da dung before/transform.txt")
    org_matrix: FloatVectorProperty(
        name="Toa do file -> lam viec", size=16,
        default=(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),
        description="transform x before^-1 (4x4, theo hang)")
    org_folder: StringProperty(name="Thu muc txt", default="")
    # Bar Pillar
    pillars: CollectionProperty(type=RMVB_PG_PartRef)
    pillar_lift: FloatProperty(
        name="Extrude lên (mm)",
        description="Extrude vung ho ket noi (day Base) thang len theo local Z "
                    "(mac dinh 7 li)",
        default=7.0, min=0.1, unit='LENGTH')

    # Bar Segment + Top Bar
    bar_line: PointerProperty(name="Bar Line", type=bpy.types.Object)
    bar_center: PointerProperty(name="Bar Center (dai tam bar)", type=bpy.types.Object)
    bar_arrow: PointerProperty(name="Mũi tên hướng lắp", type=bpy.types.Object)
    bar_segment: PointerProperty(name="Bar Segment", type=bpy.types.Object)
    bar_backup: PointerProperty(name="Bar Segment Backup", type=bpy.types.Object)
    bar_width: FloatProperty(name="Bề rộng bar (mm)", default=4.0, min=0.1,
                             unit='LENGTH', update=_bar_param_update)
    bar_height: FloatProperty(name="Chiều cao bar (mm)", default=3.0, min=0.1,
                              unit='LENGTH', update=_bar_param_update)
    top_plane: PointerProperty(name="PlaneVisual", type=bpy.types.Object)
    top_cutter: PointerProperty(name="PlaneCubeCut", type=bpy.types.Object)

    # Attachment
    attachment_index: IntProperty(name="Attachment Index", default=0, min=0)
    active_attachment: StringProperty(name="Attachment", default="")
    groups: CollectionProperty(type=RMVB_PG_AttachmentGroup)
    group_index: IntProperty(name="Group Index", default=0, min=0,
                             update=_group_index_update)

    # Sleeve Design
    sleeve_offset: FloatProperty(name="Offset bar (mm)", default=0.1, min=0.0,
                                 unit='LENGTH')
    sleeve_thickness: FloatProperty(name="Sleeve thickness (mm)", default=0.5,
                                    min=0.01, unit='LENGTH')
    sleeve_voxel: FloatProperty(
        name="Remesh voxel (mm)", default=0.15, min=0.0, soft_min=0.05, soft_max=0.5, unit='LENGTH',
        description="Cỡ voxel của lớp Remesh dùng RIÊNG để tạo Sleeve (không đổi Bar Segment): mặt Sleeve "
                    "đều và mịn, hết tam giác dài mỏng / giao cắt. Nhỏ = chính xác hơn nhưng nặng hơn. "
                    "0 = tắt Remesh (cách cũ)")
    # Offset cua khoi cat nuouu DUNG CHO SLEEVE (khoi cat GingivaCut.Sleeve, ap luc cat Sleeve)
    gingiva_offset_sleeve: FloatProperty(
        name="Offset Gingiva Sleeve (mm)", default=0.0, soft_min=-2.0, soft_max=2.0, unit='LENGTH',
        update=_gingiva_offset_sleeve_update,
        description="CHỈ ÁP DỤNG CHO SLEEVE: nới / thu hẹp khối cắt nướu riêng 'GingivaCut.Sleeve' "
                    "trước khi cắt Sleeve ở bước cuối: + = phình khối cắt ra ngoài, Sleeve bị cắt "
                    "HỞ, cách mặt nướu đúng số mm này; − = thu khối cắt lại, Sleeve ăn SÂU vào "
                    "nướu; 0 = cắt sát mặt nướu. Độc lập với Offset Gingiva Bar: đổi thông số này "
                    "không làm đổi Bar Segment. Khối cắt (ẩn) được tạo khi bấm Create Sleeve "
                    "Design và luôn cập nhật theo thông số này")
    apply_attachment_sleeve: BoolProperty(
        name="Apply attachment on Sleeve",
        description="Cong don cac Attachment (toggle Add/Remove on Sleeve cua "
                    "Dental-Lib: Add = Union, Remove = Difference) vao khoi Sleeve",
        default=True)
    sleeve_object: PointerProperty(name="Sleeve", type=bpy.types.Object)

    # Save
    save_dir: StringProperty(
        name="Thư mục lưu", subtype='DIR_PATH', default="",
        description="De trong = thu muc chua file .blend hien tai",
        get=_save_dir_get, set=_save_dir_set)


# ---------------------------------------------------------------------------
# Chuan bi mesh: loop bien, fill, extrude
# ---------------------------------------------------------------------------
def unique_loop_verts(loop):
    """Dinh cua vong bien theo thu tu, khong lap diem dau o cuoi."""
    verts = list(loop["verts"])
    if len(verts) > 1 and verts[0] is verts[-1]:
        verts = verts[:-1]
    return verts


def loop_perimeter(loop):
    return sum(edge.calc_length() for edge in loop["edges"])


def cap_loop(bm, loop):
    """Nap kin mot vong bien bang mat n-gon (fallback: holes_fill / triangle_fill)."""
    verts = unique_loop_verts(loop)
    if len(verts) >= 3:
        try:
            bm.faces.new(verts)
            return True
        except ValueError:
            pass
    edges = [e for e in loop["edges"] if e.is_valid and e.is_boundary]
    if not edges:
        return True
    try:
        bmesh.ops.holes_fill(bm, edges=edges, sides=len(edges) + 2)
    except Exception:
        pass
    edges = [e for e in edges if e.is_valid and e.is_boundary]
    if edges:
        try:
            bmesh.ops.triangle_fill(bm, use_beauty=True, edges=edges)
        except Exception:
            pass
    return not any(e.is_valid and e.is_boundary for e in loop["edges"])


def _extrude_loop(bm, loop):
    """Extrude vong bien ra them 1 vong dinh moi, tra ve list BMVert moi."""
    result = bmesh.ops.extrude_edge_only(bm, edges=loop["edges"])
    return [g for g in result['geom'] if isinstance(g, bmesh.types.BMVert)]


def _loops_within(bm, verts):
    """Cac vong bien nam hoan toan tren tap dinh `verts`."""
    keep = set(verts)
    return [lp for lp in boundary_loops(bm)
            if all(v in keep for v in lp["verts"])]


def outward_solid(bm):
    """Normal huong ra ngoai; neu the tich am thi dao lai. Tra ve the tich."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    volume = 0.0
    try:
        volume = bm.calc_volume(signed=True)
        if volume < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
            volume = -volume
    except Exception:
        pass
    return volume


def face_components(bm):
    """Cac thanh phan lien thong (list BMFace), lon nhat truoc."""
    bm.faces.index_update()
    bm.faces.ensure_lookup_table()
    seen = set()
    comps = []
    for face in bm.faces:
        if face.index in seen:
            continue
        stack = [face]
        comp = []
        seen.add(face.index)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for edge in cur.edges:
                for other in edge.link_faces:
                    if other.index not in seen:
                        seen.add(other.index)
                        stack.append(other)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    return comps


def repair_manifold(bm, rounds=8):
    """Xoa canh > 2 mat va dinh KHONG-manifold (that nut o vanh, dinh roi) cho den khi sach.

    Moi diem bi xoa de lai 1 lo nho (vong canh mot dinh) duoc fill lai o buoc sau, nen
    be mat chi doi o ban kinh 1 vong tam giac quanh diem loi."""
    removed = 0
    for _ in range(rounds):
        bad_faces = {f for e in bm.edges if len(e.link_faces) > 2 for f in e.link_faces}
        if bad_faces:
            bmesh.ops.delete(bm, geom=list(bad_faces), context='FACES')
            removed += len(bad_faces)
        bad_verts = [v for v in bm.verts if not v.is_manifold]
        if bad_verts:
            bmesh.ops.delete(bm, geom=bad_verts, context='VERTS')
            removed += len(bad_verts)
        if not bad_faces and not bad_verts:
            break
    return removed


def count_self_intersections(bm, limit=100000):
    """So cap tam giac giao nhau (khong tinh cap chung dinh) - chi de bao cao."""
    from mathutils.bvhtree import BVHTree
    bm.verts.index_update()
    bm.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm, epsilon=1e-6)
    count = 0
    for a, b in tree.overlap(tree):
        if a >= b:
            continue
        if {v.index for v in bm.faces[a].verts} & {v.index for v in bm.faces[b].verts}:
            continue
        count += 1
        if count >= limit:
            break
    return count


def prepare_gingiva(obj, depth=GINGIVA_BASE_DEPTH):
    """Chuan bi tren CHINH obj (sua mesh cua obj) - giu API cu."""
    return prepare_gingiva_mesh(obj.data, obj.matrix_world, depth)


def prepare_gingiva_mesh(mesh, world, depth=GINGIVA_BASE_DEPTH):
    """Bien mesh (toa do local, `world` = matrix world cua object so huu) thanh KHOI kin +
    manifold - dung cho BAN COPY cua Gingiva (mesh goac giu nguyen):

    0. Lam sach: hop nhat dinh trung, xoa dinh that nut / canh > 2 mat (nguyen nhan mesh
       sau extrude van hong va Boolean tu choi), bo manh roi rac nho.
    1. Moi manh lon: cac vong ho nho (mat tren) fill de khong bi lung.
    2. Vong ho lon nhat (mat duoi): extrude xuong de MOI diem da extrude cung nam tren
       1 MAT PHANG song song Oxy (world), cach diem thap nhat cua cac vanh ho do `depth` mm
       (z_de = Z world nho nhat cua vanh - depth; XY giu nguyen). Roi fill tao de phang
       -> toan bo Gingiva thanh khoi. Khong phu thuoc xoay / scale cua object.

    info: loops, filled, extruded, closed (khong con canh ho), manifold (kin + khong canh
    > 2 mat + khong dinh that nut), repaired (so dinh/mat da xoa), islands (manh roi bi bo),
    intersections (cap tam giac tu giao con lai), floor_z, open_side_up (than mesh nam DUOI
    vanh: de keo xuong se di xuyen vao than mesh nen Create Top Bar Plane canh bao).
    """
    info = {"loops": 0, "filled": 0, "extruded": False, "closed": False, "manifold": False,
            "repaired": 0, "islands": 0, "intersections": 0,
            "open_side_up": False, "floor_z": None}
    bm = bmesh.new()
    bm.from_mesh(mesh)
    # 1e-5 mm: chi gop dinh trung toa do (Blender 4.5 gop khong het neu nguong qua nho)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    info["repaired"] = repair_manifold(bm)

    comps = face_components(bm)
    if len(comps) > 1:
        # giu cac manh lon (>= 1% manh lon nhat); manh nho hon la rac cua scan -> bo
        threshold = max(4, int(len(comps[0]) * 0.01) + 1)
        trash = [f for comp in comps if len(comp) < threshold for f in comp]
        if trash:
            info["islands"] = sum(1 for comp in comps if len(comp) < threshold)
            bmesh.ops.delete(bm, geom=trash, context='FACES')
            info["repaired"] += repair_manifold(bm)
    comps = face_components(bm)
    comp_of = {f.index: ci for ci, comp in enumerate(comps) for f in comp}

    bm.verts.index_update()
    bm.edges.index_update()
    loops = boundary_loops(bm)
    info["loops"] = len(loops)
    if loops:
        by_comp = {}
        for loop in loops:
            face = loop["edges"][0].link_faces[0]
            by_comp.setdefault(comp_of.get(face.index, 0), []).append(loop)
        bases = []
        for ci in sorted(by_comp):
            lps = by_comp[ci]
            base = max(lps, key=loop_perimeter)
            bases.append(base)
            for loop in lps:
                if loop is not base and cap_loop(bm, loop):
                    info["filled"] += 1

        try:
            inverse = world.inverted()
        except ValueError:
            world = inverse = Matrix.Identity(4)
        rim_world = [world @ v.co for base in bases for v in unique_loop_verts(base)]
        main = unique_loop_verts(bases[0])
        main_center = world @ (sum((v.co for v in main), Vector()) / max(1, len(main)))
        body = world @ (sum((v.co for v in bm.verts), Vector()) / max(1, len(bm.verts)))
        info["open_side_up"] = body.z < main_center.z - 1e-6
        floor_z = min(p.z for p in rim_world) - depth
        info["floor_z"] = floor_z
        for base in bases:
            new_verts = _extrude_loop(bm, base)
            for vert in new_verts:
                point = world @ vert.co
                point.z = floor_z                  # cung 1 mat phang Oxy
                vert.co = inverse @ point
            for loop in _loops_within(bm, new_verts):
                cap_loop(bm, loop)
        info["extruded"] = True
        rest = [e for e in bm.edges if e.is_boundary]
        if rest:                                   # du phong: lap not cac lo con sot
            try:
                bmesh.ops.holes_fill(bm, edges=rest, sides=len(rest) + 2)
            except Exception:
                pass
            rest = [e for e in bm.edges if e.is_valid and e.is_boundary]
            if rest:
                try:
                    bmesh.ops.triangle_fill(bm, use_beauty=True, edges=rest)
                except Exception:
                    pass
        outward_solid(bm)
        bm.to_mesh(mesh)
        mesh.update()
    info["closed"] = not any(e.is_boundary for e in bm.edges)
    info["manifold"] = (info["closed"] and not any(len(e.link_faces) > 2 for e in bm.edges)
                        and all(v.is_manifold for v in bm.verts))
    try:
        info["intersections"] = count_self_intersections(bm)
    except Exception:
        info["intersections"] = 0
    bm.free()
    return info


ROLE_COLOR = {
    'GINGIVA': (1.0, 0.55, 0.70, 0.5),      # hong, opacity 0.5
    'DENTURE': (0.25, 0.80, 0.35, 0.5),     # xanh la, opacity 0.5
    'ANTAGONIST': (0.55, 0.33, 0.15, 1.0),  # nau, opacity 1
}
ROLE_OBJECT_NAME = {
    'GINGIVA': "Gingiva",
    'DENTURE': "Denture",
    'ANTAGONIST': "Antagonist",
}
ROLE_PROPERTY = {
    'GINGIVA': "gingiva_object",
    'DENTURE': "denture_object",
    'ANTAGONIST': "antagonist_object",
}


def pick_mesh_object(context):
    """Object mesh dang chon (uu tien active)."""
    active = context.active_object
    if active is not None and active.type == 'MESH' and active.select_get():
        return active
    for obj in context.selected_objects:
        if obj.type == 'MESH':
            return obj
    if active is not None and active.type == 'MESH':
        return active
    return None


class RMVB_OT_set_role(Operator):
    """Gan object mesh dang chon vao vai tro Gingiva / Denture / Antagonist:
    CHI doi ten + danh dau (rmvb_role) + doi mau hien thi, mesh giu nguyen.
    Khoi cat nuouu (ban copy da chuan bi kin + offset) chi duoc tao khi
    Create Top Bar Plane"""
    bl_idname = "rmvb.set_role"
    bl_label = "Set"
    bl_options = {'REGISTER', 'UNDO'}

    role: EnumProperty(
        name="Role",
        items=[('GINGIVA', "Gingiva", ""),
               ('DENTURE', "Denture", ""),
               ('ANTAGONIST', "Antagonist", "")],
        default='GINGIVA')

    def execute(self, context):
        props = context.scene.rmvb
        obj = pick_mesh_object(context)
        if obj is None:
            self.report({'ERROR'}, "Chon mot object mesh trong scene truoc")
            return {'CANCELLED'}
        for role, field in ROLE_PROPERTY.items():
            if role != self.role and getattr(props, field) == obj:
                self.report({'ERROR'}, "'%s' dang la %s" % (obj.name, role.title()))
                return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        message = ""
        if self.role == 'GINGIVA':
            # Thuat toan moi: Set Gingiva KHONG chuan bi / sua mesh nua - chi doi mau +
            # danh dau + doi ten, mesh goac giu nguyen nguyen ven. Khoi cat nuouu (toi uu
            # mesh / dong mesh ho / offset de toi uu cho Boolean) duoc tao khi Create Top
            # Bar Plane
            message = " (mesh giữ nguyên - khối cắt nướu được tạo khi Create Top Bar Plane)"
        obj.name = ROLE_OBJECT_NAME[self.role]
        obj["rmvb_role"] = self.role
        set_display_color(obj, ROLE_COLOR[self.role])
        setattr(props, ROLE_PROPERTY[self.role], obj)
        if self.role == 'GINGIVA':
            try:
                # Chi dung lai khoi cat NEU no da ton tai (Create Top Bar Plane / Create Sleeve
                # Design da chay, hoac file cu): doi sang Gingiva khac thi moi khoi cat dung lai
                # theo mesh moi; chua tao thi khong tao som
                if valid_obj(props.gingiva_cutter) or valid_obj(props.bar_segment):
                    ensure_gingiva_cutter(props)
                    if valid_obj(props.bar_segment):
                        rebuild_segment_modifiers(context)   # CutGingiva tro lai dung operand
                if valid_obj(props.gingiva_cutter_sleeve) or valid_obj(props.sleeve_object):
                    ensure_gingiva_cutter(props, sleeve=True)
            except Exception as exc:
                self.report({'WARNING'}, "Không dựng được khối cắt nướu: %s" % exc)
        activate(context, obj)
        self.report({'INFO'}, "Set %s: %s%s" % (self.role.title(), obj.name, message))
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Place Connection - doc .constructionInfo va dat theo toa do XML
# ---------------------------------------------------------------------------
def clear_placed_connections(context, remove_pillars=False):
    props = context.scene.rmvb
    for item in list(props.placed):
        for field in ("base_object", "visual_object", "analog_object",
                      "screw_object", "scanbody_object", "group_object"):
            remove_object(getattr(item, field))
    props.placed.clear()
    if remove_pillars:
        for ref in list(props.pillars):
            remove_object(ref.object)
        props.pillars.clear()


def current_connection_name(props):
    name = props.connection_name
    names = get_connection_items()
    if name in names:
        return name
    if names:
        return names[min(props.connection_index, len(names) - 1)]
    return ""


def prepare_connection_mesh(source):
    """Chuan bi Base de dung lam khoi Boolean (mesh moi, khong sua `source`):

    1. Base ho day (Connection): extrude +0.1 mm theo local Z; roi tu phan moi extrude tiep
       -1 mm theo local Z va scale local x1.5.
    2. Base ho dinh (Screw): extrude +30 mm theo local Z.
    3. Nap kin 2 dau + Flip Normal (normal huong ra ngoai) de thanh solid.
    Vong ho day GOC duoc luu trong mesh["rmvb_ring"] (x,y,z... local) de tao Pillar.
    """
    mesh = source.copy()
    mesh.name = "Rmvb_ConnBase"
    info = {"loops": 0, "closed": False}
    bm = bmesh.new()
    bm.from_mesh(mesh)
    loops = boundary_loops(bm)
    info["loops"] = len(loops)
    if loops:
        ordered = sorted(loops, key=lambda item: item["z"])
        bottom = ordered[0]
        top = ordered[-1] if len(ordered) > 1 else None
        ring = unique_loop_verts(bottom)
        center = sum((v.co for v in ring), Vector()) / len(ring)
        mesh["rmvb_ring"] = [c for v in ring for c in (v.co.x, v.co.y, v.co.z)]

        lifted = _extrude_loop(bm, bottom)
        for vert in lifted:
            vert.co.z += CONN_BOTTOM_LIFT
        lift_loops = _loops_within(bm, lifted)
        new_bottom = _extrude_loop(bm, lift_loops[0]) if lift_loops else lifted
        new_top = _extrude_loop(bm, top) if top is not None else []
        for vert in new_bottom:
            vert.co.x = center.x + (vert.co.x - center.x) * CONN_BOTTOM_SCALE
            vert.co.y = center.y + (vert.co.y - center.y) * CONN_BOTTOM_SCALE
            vert.co.z -= CONN_BOTTOM_EXTRUDE
        for vert in new_top:
            vert.co.z += CONN_TOP_EXTRUDE
        for loop in _loops_within(bm, new_bottom + new_top):
            cap_loop(bm, loop)
        outward_solid(bm)
    info["closed"] = not any(e.is_boundary for e in bm.edges)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh, info


ORG_BEFORE = "before.txt"
ORG_TRANSFORM = "transform.txt"


def read_matrix_txt(filepath):
    """Doc file ma tran 4x4 do add-on iBar ghi: 4 dong, moi dong 4 so cach nhau bang dau phay."""
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                rows.append([float(value) for value in line.split(",")])
    if len(rows) != 4 or any(len(row) != 4 for row in rows):
        raise ValueError("%s can 4 dong x 4 so" % os.path.basename(filepath))
    return Matrix(rows)


def _find_file_ci(folder, name):
    """Duong dan file `name` trong `folder` (khong phan biet hoa thuong), hoac ""."""
    try:
        for entry in os.listdir(folder):
            full = os.path.join(folder, entry)
            if entry.lower() == name and os.path.isfile(full):
                return full
    except OSError:
        pass
    return ""


def load_org_transform(construction_path):
    """Tim before.txt + transform.txt (thu muc constructionInfo truoc, roi thu muc .blend).

    Tra ve (work_from_org, folder). work_from_org = transform x before^-1 chuyen toa do
    file (ORG) sang toa do lam viec, giong 'Create Tubes' / 'Offset from ORG to current'
    cua add-on iBar. Khong tim thay du 2 file -> (None, thu_muc_co_1_file_hoac_"").
    Raise ValueError/OSError neu file hong.
    """
    folders = []
    for folder in (os.path.dirname(os.path.abspath(construction_path)), blend_dir()):
        if folder and folder not in folders:
            folders.append(folder)
    partial = ""
    for folder in folders:
        before = _find_file_ci(folder, ORG_BEFORE)
        transform = _find_file_ci(folder, ORG_TRANSFORM)
        if before and transform:
            before_matrix = read_matrix_txt(before)
            transform_matrix = read_matrix_txt(transform)
            try:
                inverse = before_matrix.inverted()
            except ValueError:
                raise ValueError("before.txt khong kha nghich")
            return transform_matrix @ inverse, folder
        if before or transform:
            partial = folder
    return None, partial


def org_matrix_from_props(props):
    flat = list(props.org_matrix)
    return Matrix([flat[i * 4:(i + 1) * 4] for i in range(4)])


# Mau / an-hien cua tung phan Connection (analog, screw). Scanbody (nhieu file trong Dental-Lib) KHONG duoc dat vao scene.
CONN_PART_STYLE = {
    "analog": (COLOR_CONN_ANALOG, False),
    "screw": (COLOR_CONN_SCREW, False),
}
CONN_PART_FIELD = (("analog", "analog_object"), ("screw", "screw_object"))


def make_connection_kit(lib_name):
    """Bo mesh cua 1 Connection Base trong thu vien (dung chung cho nhieu implant):
    Base da extrude (khoi Boolean), hinh hien thi cua Base goc, Analog / Screw.
    Raise FileNotFoundError neu thu vien chua co mesh Base."""
    base_path = lib_connection_asset(lib_name, "base")
    if not base_path or not os.path.exists(base_path):
        raise FileNotFoundError("Connection '%s' chua co mesh Base" % lib_name)
    source_mesh = mesh_from_file(base_path)
    base_mesh, base_info = prepare_connection_mesh(source_mesh)

    # Hinh hien thi cua Base GOC (chua extrude/nap kin), normal huong ra ngoai
    visual_mesh = source_mesh.copy()
    visual_mesh.name = "Rmvb_ConnVisual"
    bm = bmesh.new()
    bm.from_mesh(visual_mesh)
    outward_solid(bm)
    bm.to_mesh(visual_mesh)
    bm.free()
    visual_mesh.update()

    # Analog / Screw: luon dat vao scene (moi loai 1 ban copy dung chung)
    parts = {}
    warnings = []
    for slot, _field in CONN_PART_FIELD:
        asset = lib_connection_asset(lib_name, slot)
        if asset and os.path.exists(asset):
            try:
                parts[slot] = mesh_from_file(asset).copy()
                parts[slot].name = "Rmvb_Conn_" + slot
            except Exception as exc:
                warnings.append("%s: %s" % (slot, exc))
    return {"lib_name": lib_name, "base": base_mesh, "info": base_info,
            "visual": visual_mesh, "parts": parts, "warnings": warnings}


def populate_implant(item, group, kit, coll):
    """Tao Base / ConnectionVisual / Analog / Screw cua `kit` lam con cua Empty `group`
    va ghi vao `item` (RMVB_PG_PlacedConnection)."""
    tooth = item.tooth
    item.lib_name = kit["lib_name"]
    # Base da xu ly (extrude) chi dung lam khoi Boolean -> an
    obj = object_from_mesh("Conn_%s_Base" % tooth, kit["base"], coll)
    attach_to(obj, group)
    set_color(obj, (0.72, 0.74, 0.78, 1.0))
    obj.hide_set(True)
    item.base_object = obj
    visual = object_from_mesh("%s_%s" % (OBJ_CONN_VISUAL, tooth), kit["visual"], coll)
    attach_to(visual, group)
    set_display_color(visual, COLOR_CONN_VISUAL)
    visual["rmvb_role"] = "CONNECTION_VISUAL"
    item.visual_object = visual
    for slot, field in CONN_PART_FIELD:
        mesh = kit["parts"].get(slot)
        if mesh is None:
            continue
        part = object_from_mesh("Conn_%s_%s" % (tooth, slot.capitalize()), mesh, coll)
        attach_to(part, group)
        rgba, hidden = CONN_PART_STYLE[slot]
        set_display_color(part, rgba)
        if hidden:
            part.hide_set(True)
        setattr(item, field, part)


def remove_implant_parts(item):
    """Xoa cac phan Connection cua 1 implant (giu Empty nhom, Bar Pillar va toa do)."""
    for field in ("base_object", "visual_object", "analog_object", "screw_object", "scanbody_object"):
        remove_object(getattr(item, field))


class RMVB_OT_place_connection(Operator, ImportHelper):
    """Doc file constructionInfo va dat Implant Connection theo dung toa do XML"""
    bl_idname = "rmvb.place_connection"
    bl_label = "Place Connection"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH', default="")
    filter_glob: StringProperty(default="*.constructionInfo;*.xml",
                                options={'HIDDEN'})

    def execute(self, context):
        props = context.scene.rmvb
        path = bpy.path.abspath(self.filepath)
        if not path or not os.path.exists(path):
            self.report({'ERROR'}, "Khong tim thay file constructionInfo")
            return {'CANCELLED'}

        lib_name = current_connection_name(props)
        if not lib_name:
            self.report({'ERROR'},
                        "Chua chon Connection Base trong thu vien Dental-Lib")
            return {'CANCELLED'}

        base_path = lib_connection_asset(lib_name, "base")
        if not base_path or not os.path.exists(base_path):
            self.report({'ERROR'}, "Connection '%s' chua co mesh Base" % lib_name)
            return {'CANCELLED'}

        try:
            implants = parse_construction_info(path)
        except Exception as exc:
            self.report({'ERROR'}, "Loi doc XML: %s" % exc)
            return {'CANCELLED'}
        if not implants:
            self.report({'ERROR'},
                        "File khong chua implant nao (ImplantType + MatrixImplantGeometry)")
            return {'CANCELLED'}

        try:
            kit = make_connection_kit(lib_name)
        except Exception as exc:
            self.report({'ERROR'}, "Loi doc mesh Base: %s" % exc)
            return {'CANCELLED'}
        for warning in kit["warnings"]:
            self.report({'WARNING'}, warning)
        base_info = kit["info"]

        org = None
        org_folder = ""
        if props.use_org_txt:
            try:
                org, org_folder = load_org_transform(path)
            except (OSError, ValueError) as exc:
                self.report({'WARNING'}, "Khong doc duoc before/transform.txt (%s) - dat "
                            "theo toa do file" % exc)
            else:
                if org is None:
                    where = os.path.dirname(os.path.abspath(path))
                    self.report({'WARNING'}, "Khong thay du before.txt + transform.txt%s trong '%s' "
                                "(va thu muc .blend) - dat theo toa do file"
                                % (" (moi co 1 file)" if org_folder else "", where))

        clear_placed_connections(context, remove_pillars=True)
        coll = ensure_collection(COL_CONNECTION)
        for implant in implants:
            tooth = str(implant["tooth"])
            matrix = org @ implant["matrix"] if org is not None else implant["matrix"]
            # Moi implant = 1 nhom Plain Axes (giong cach Attachment duoc add): Base, ConnectionVisual,
            # Analog, Screw la con cua Empty nay; keo Empty la di chuyen ca nhom
            group = bpy.data.objects.new("%s_%s" % (OBJ_IMPLANT_GROUP, tooth), None)
            group.empty_display_type = 'PLAIN_AXES'
            group.empty_display_size = GROUP_AXES_SIZE
            group.show_in_front = True
            coll.objects.link(group)
            group.matrix_world = matrix
            group["rmvb_role"] = "IMPLANT_GROUP"
            group["rmvb_tooth"] = tooth
            item = props.placed.add()
            item.tooth = tooth
            item.group_object = group
            populate_implant(item, group, kit, coll)

        props.construction_file = path
        props.connection_name = lib_name
        props.org_active = org is not None
        props.org_folder = org_folder if org is not None else ""
        if org is not None:
            props.org_matrix = [org[i][j] for i in range(4) for j in range(4)]
        rebuild_segment_modifiers(context)
        if base_info["loops"] != 2:
            self.report({'WARNING'}, "Base co %d vung ho (can 2: day + dinh)"
                        % base_info["loops"])
        self.report({'INFO'}, "Da dat %d Connection (%s) tu %s%s%s"
                    % (len(implants), lib_name, os.path.basename(path),
                       " + transform theo before/transform.txt" if org is not None else "",
                       "" if base_info["closed"] else " (Base chua kin)"))
        return {'FINISHED'}


def draw_implant_connection_choices(layout, props, index):
    """Danh sach Connection Base trong thu vien de doi cho implant `index` (muc dang dung co dau tick);
    gom theo nhom Implant Connection cua Dental-Lib neu co."""
    names = get_connection_items()
    if not names:
        layout.label(text="(Trống - thêm mục trong Dental-Lib)", icon='ERROR')
        return
    current = props.placed[index].lib_name if 0 <= index < len(props.placed) else ""
    groups = lib_connection_groups(names)
    named = any(group for group, _members in groups)
    for position, (group, members) in enumerate(groups):
        if named:
            if position:
                layout.separator()
            layout.label(text=group or "(Chưa nhóm)", icon='FILE_FOLDER')
        for name in members:
            op = layout.operator(RMVB_OT_set_implant_connection.bl_idname, text=name,
                                 icon='CHECKMARK' if name == current else 'MESH_CYLINDER')
            op.index = index
            op.connection = name


class RMVB_OT_choose_implant_connection(Operator):
    """Mo danh sach chon Connection Base rieng cho mot implant"""
    bl_idname = "rmvb.choose_implant_connection"
    bl_label = "Chon Connection Base cho implant"
    bl_options = {'INTERNAL'}

    index: IntProperty(default=0, min=0)

    def invoke(self, context, event):
        props = context.scene.rmvb
        if not 0 <= self.index < len(props.placed):
            return {'CANCELLED'}
        index = self.index

        def draw(menu, menu_context):
            draw_implant_connection_choices(menu.layout, menu_context.scene.rmvb, index)

        context.window_manager.popup_menu(
            draw, title="Connection Base - răng %s" % props.placed[index].tooth, icon='MESH_CYLINDER')
        return {'INTERFACE'}


class RMVB_OT_set_implant_connection(Operator):
    """Doi Connection Base cua MOT implant: thay Base / ConnectionVisual / Analog / Screw
    bang bo mesh cua Connection da chon (giu nguyen vi tri implant va cac implant khac)"""
    bl_idname = "rmvb.set_implant_connection"
    bl_label = "Doi Connection Base cua implant"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=0, min=0)
    connection: StringProperty(default="")

    def execute(self, context):
        props = context.scene.rmvb
        if not 0 <= self.index < len(props.placed):
            self.report({'ERROR'}, "Khong co implant nao ung voi muc nay")
            return {'CANCELLED'}
        item = props.placed[self.index]
        seg = props.bar_segment
        if valid_obj(seg) and seg.get("rmvb_applied"):
            self.report({'ERROR'}, "Bar Segment da Apply - bam Delete Bar Design de sua tiep")
            return {'CANCELLED'}
        if not valid_obj(item.group_object):
            self.report({'ERROR'}, "Implant %s mat nhom Plain Axes - bam Place Connection lai" % item.tooth)
            return {'CANCELLED'}
        if self.connection not in get_connection_items():
            self.report({'ERROR'}, "Connection '%s' khong co trong thu vien Dental-Lib" % self.connection)
            return {'CANCELLED'}
        if item.lib_name == self.connection and valid_obj(item.base_object):
            self.report({'INFO'}, "Rang %s da dung Connection '%s'" % (item.tooth, self.connection))
            return {'CANCELLED'}
        try:
            kit = make_connection_kit(self.connection)
        except Exception as exc:
            self.report({'ERROR'}, "Loi doc mesh Base cua '%s': %s" % (self.connection, exc))
            return {'CANCELLED'}
        for warning in kit["warnings"]:
            self.report({'WARNING'}, warning)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        old_name = item.lib_name
        remove_implant_parts(item)
        populate_implant(item, item.group_object, kit, ensure_collection(COL_CONNECTION))
        if valid_obj(seg) and cut_preview_enabled(seg):
            item.visual_object.hide_set(True)       # Preview cat Top Bar dang an ConnectionVisual cua cac implant
        rebuild_segment_modifiers(context)           # CutBase tro vao Base moi
        purge_unused_meshes()
        stale = any(ref.tooth == item.tooth for ref in props.pillars)
        self.report({'INFO'}, "Rang %s: Connection '%s' -> '%s'" % (item.tooth, old_name, self.connection))
        if stale:
            self.report({'WARNING'}, "Bar Pillar rang %s dang tao tu Base cu - chon implant (Plain Axes) hoac "
                        "Pillar cua rang nay roi bam Create/Reset bar pillar de dung lai theo Base moi" % item.tooth)
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class RMVB_OT_clear_connection(Operator):
    """Xoa cac Connection da dat (va Bar Pillar) de chon lai constructionInfo"""
    bl_idname = "rmvb.clear_connection"
    bl_label = "Clear Connection"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        props = context.scene.rmvb
        if not props.placed and not props.pillars:
            self.report({'INFO'}, "Chua co Connection nao")
            return {'CANCELLED'}
        clear_placed_connections(context, remove_pillars=True)
        props.construction_file = ""
        rebuild_segment_modifiers(context)
        purge_unused_meshes()
        self.report({'INFO'}, "Da xoa Connection va Bar Pillar - chon lai "
                    "constructionInfo roi bam Place Connection")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Bar Pillar
# ---------------------------------------------------------------------------
def connection_ring(base_obj):
    """Vong ho day (Connection) goc cua Base: list Vector theo toa do local."""
    stored = base_obj.data.get("rmvb_ring")
    if stored:
        flat = list(stored)
        return [Vector(flat[i:i + 3]) for i in range(0, len(flat) - 2, 3)]
    # Base chua duoc chuan bi (scene cu): lay vong ho thap nhat cua mesh
    bm = bmesh.new()
    bm.from_mesh(base_obj.data)
    loops = boundary_loops(bm)
    ring = []
    if loops:
        lowest = min(loops, key=lambda item: item["z"])
        ring = [v.co.copy() for v in unique_loop_verts(lowest)]
    bm.free()
    return ring


def build_pillar_mesh(base_obj, lift):
    """Bar Pillar = sao chep cac diem vung ho day (Connection) cua Base, extrude len
    `lift` mm theo local Z, fill kin ca day lan dinh -> solid manifold.

    Tra ve (mesh, info). info["top_z"] = cao do dinh mui extrude (local).
    """
    ring = connection_ring(base_obj)
    info = {"closed": False, "top_z": None, "volume": 0.0, "points": len(ring)}
    if len(ring) < 3:
        return None, info
    bm = bmesh.new()
    bottom = [bm.verts.new(co) for co in ring]
    top = [bm.verts.new((co.x, co.y, co.z + lift)) for co in ring]
    count = len(ring)
    for i in range(count):
        j = (i + 1) % count
        try:
            bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
        except ValueError:
            pass
    for cap in (bottom, top):
        try:
            bm.faces.new(cap)
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    info["volume"] = outward_solid(bm)
    info["closed"] = not any(e.is_boundary for e in bm.edges)
    info["top_z"] = max(co.z for co in ring) + lift
    mesh = bpy.data.meshes.new("%s.pillar" % base_obj.name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.validate()
    mesh.update()
    return mesh, info


def selected_teeth(context):
    """So rang (chuoi) cua cac object dang chon thuoc ve mot implant: Bar Pillar, Plain Axes Implant_<rang>,
    hoac bat ky phan nao cua implant (ConnectionVisual, Base...)."""
    teeth = set()
    for obj in context.selected_objects:
        role = obj.get("rmvb_role")
        if role in ("PILLAR", "IMPLANT_GROUP") and obj.get("rmvb_tooth") is not None:
            teeth.add(str(obj["rmvb_tooth"]))
        elif obj.parent is not None and obj.parent.get("rmvb_role") == "IMPLANT_GROUP":
            teeth.add(str(obj.parent.get("rmvb_tooth")))
    return teeth


def pillar_targets(context):
    """(cac implant can tao / reset Bar Pillar, cac rang da co Pillar trong do).

    Co chon Pillar / implant trong viewport -> chi cac rang do (Reset neu da co Pillar, tao moi neu chua);
    khong chon gi -> chi tao cac rang CHUA co Pillar."""
    props = context.scene.rmvb
    have = {ref.tooth for ref in props.pillars if valid_obj(ref.object)}
    chosen = selected_teeth(context)
    if chosen:
        items = [item for item in props.placed if item.tooth in chosen]
    else:
        items = [item for item in props.placed if item.tooth not in have]
    return items, [item.tooth for item in items if item.tooth in have]


class RMVB_OT_create_bar_pillar(Operator):
    """Tao / Reset Bar Pillar tu vung ho day (Connection) cua Base, extrude len theo local Z va fill kin.
    Chua chon gi: tao Pillar cho cac rang chua co. Chon Pillar hoac implant (Plain Axes) trong viewport:
    chi dung lai (Reset) cac rang do, rang khac giu nguyen; rang da co Pillar thi hoi xac nhan"""
    bl_idname = "rmvb.create_bar_pillar"
    bl_label = "Create/Reset bar pillar"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        _items, replaced = pillar_targets(context)
        if replaced:
            return context.window_manager.invoke_confirm(
                self, event, title="Reset Bar Pillar?",
                message="Dựng lại Bar Pillar răng %s theo Base hiện tại. Mọi chỉnh sửa trên các Pillar này "
                        "(sửa đỉnh, di chuyển...) sẽ mất; các răng khác giữ nguyên." % ", ".join(replaced),
                confirm_text="Reset", icon='WARNING')
        return self.execute(context)

    def execute(self, context):
        props = context.scene.rmvb
        if not props.placed:
            self.report({'ERROR'}, "Chua dat Connection nao (bam Place Connection)")
            return {'CANCELLED'}
        items, _replaced = pillar_targets(context)
        if not items:
            self.report({'ERROR'}, "Moi rang deu da co Bar Pillar - chon Pillar (hoac implant Plain Axes) can "
                        "Reset trong viewport roi bam lai")
            return {'CANCELLED'}
        coll = ensure_collection(COL_PILLAR)
        refs = {ref.tooth: ref for ref in props.pillars}

        created = []
        reset = []
        notes = []
        for item in items:
            base = item.base_object
            if base is None or base.type != 'MESH':
                continue
            try:
                mesh, info = build_pillar_mesh(base, props.pillar_lift)
            except Exception as exc:
                self.report({'WARNING'}, "Rang %s: %s" % (item.tooth, exc))
                continue
            if mesh is None:
                notes.append("rang %s khong co vung ho day" % item.tooth)
                continue
            ref = refs.get(item.tooth)
            if ref is not None and valid_obj(ref.object):
                remove_object(ref.object)               # chi xoa Pillar cu sau khi Pillar moi dung thanh cong
                reset.append(item.tooth)
            else:
                created.append(item.tooth)
            obj = bpy.data.objects.new("BarPillar_%s" % item.tooth, mesh)
            coll.objects.link(obj)
            if valid_obj(item.group_object):
                attach_to(obj, item.group_object)       # di chuyen implant thi Pillar di theo
            else:
                obj.matrix_world = base.matrix_world.copy()
            obj["rmvb_role"] = "PILLAR"
            obj["rmvb_tooth"] = item.tooth
            obj["rmvb_top_z"] = float(info["top_z"])
            set_color(obj, (0.85, 0.65, 0.25, 1.0))
            if ref is None:
                ref = props.pillars.add()
                ref.tooth = item.tooth
            ref.object = obj
            if valid_obj(props.bar_segment) and cut_preview_enabled(props.bar_segment):
                obj.hide_set(True)                      # Preview cat Top Bar dang bat: Pillar nam gon trong ket qua
            if not info["closed"]:
                notes.append("rang %s pillar chua kin" % item.tooth)
        if not (created or reset):
            self.report({'ERROR'}, "Khong tao duoc Bar Pillar nao")
            return {'CANCELLED'}
        rebuild_segment_modifiers(context)
        purge_unused_meshes()
        if notes:
            self.report({'WARNING'}, "; ".join(notes))
        parts = []
        if created:
            parts.append("tao moi %d (rang %s)" % (len(created), ", ".join(created)))
        if reset:
            parts.append("reset %d (rang %s)" % (len(reset), ", ".join(reset)))
        self.report({'INFO'}, "Bar Pillar: %s - extrude len %g mm, solid kin" % ("; ".join(parts), props.pillar_lift))
        return {'FINISHED'}


def selected_pillars(context):
    """Cac object Bar Pillar dang duoc chon (hoac dang o Edit Mode) trong viewport."""
    objs = []
    for obj in context.selected_objects:
        if obj.type == 'MESH' and obj.get("rmvb_role") == "PILLAR" and obj not in objs:
            objs.append(obj)
    return objs


class RMVB_OT_select_pillar_top(Operator):
    """Sua dinh tru bar: chon object Bar Pillar trong viewport roi bam - vao Edit Mode va CHI chon cac dinh
    o dinh mui extrude cua (cac) Bar Pillar dang chon"""
    bl_idname = "rmvb.select_pillar_top"
    bl_label = "Sửa đỉnh trụ bar"

    def execute(self, context):
        pillars = selected_pillars(context)
        if not pillars:
            self.report({'ERROR'}, "Chon object Bar Pillar trong viewport truoc roi bam Sua dinh tru bar "
                        "(Pillar dang an thi bam Disable Preview cat Top Bar de hien lai)")
            return {'CANCELLED'}
        active = context.active_object if context.active_object in pillars else pillars[0]
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        for obj in pillars:
            obj.select_set(True)
        # Pillar khong duoc chon: xoa dinh con chon tu lan truoc de ket qua dut khoat
        for ref in context.scene.rmvb.pillars:
            other = ref.object
            if valid_obj(other) and other not in pillars:
                for coll in (other.data.vertices, other.data.edges, other.data.polygons):
                    coll.foreach_set("select", [False] * len(coll))
                other.data.update()
        context.view_layer.objects.active = active
        bpy.ops.object.mode_set(mode='EDIT')
        use_local_orientation(context)
        try:
            context.tool_settings.mesh_select_mode = (True, False, False)
        except Exception:
            pass
        total = 0
        for obj in pillars:
            bm = bmesh.from_edit_mesh(obj.data)
            for elem in list(bm.verts) + list(bm.edges) + list(bm.faces):
                elem.select_set(False)
            top_z = obj.get("rmvb_top_z")
            if not isinstance(top_z, (int, float)):
                top_z = max(v.co.z for v in bm.verts)
            for vert in bm.verts:
                if vert.co.z >= top_z - TOP_EPS:
                    vert.select_set(True)
                    total += 1
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, destructive=False)
        self.report({'INFO'}, "Da chon %d dinh o dinh mui extrude cua %d Bar Pillar (%s)"
                    % (total, len(pillars), ", ".join(str(o.get("rmvb_tooth", o.name)) for o in pillars)))
        return {'FINISHED'}


class RMVB_OT_exit_edit(Operator):
    """Thoat Edit Mode ve Object Mode"""
    bl_idname = "rmvb.exit_edit"
    bl_label = "Exit Edit"

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, "Da ve Object Mode")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Quy trinh Bar Segment + Top Bar:
#   1. Create Top Bar Plane  -> PlaneVisual + PlaneCubeCut (an) + Mui ten huong lap
#   2. Draw Line Bar         -> line ve tren PlaneVisual (1 modifier Shrinkwrap)
#   3. Bar Segment TU CAP NHAT khi sua line / Plane / mui ten / thong so
# ---------------------------------------------------------------------------
def valid_obj(obj):
    try:
        return obj is not None and obj.name in bpy.data.objects
    except ReferenceError:
        return False


def ensure_arrow(context, location):
    """Mui ten huong lap: Empty SINGLE_ARROW huong len Z+ (xoay duoc de doi huong
    lap = huong canh ben cua Bar)."""
    props = context.scene.rmvb
    arrow = props.bar_arrow
    if valid_obj(arrow):
        place_arrow(arrow)
    else:
        arrow = bpy.data.objects.new(OBJ_ARROW, None)
        arrow.empty_display_type = 'SINGLE_ARROW'
        arrow.empty_display_size = 12.0
        arrow.show_in_front = True
        arrow.color = (0.1, 0.9, 0.2, 1.0)
        arrow.location = location
        arrow["rmvb_role"] = "ARROW"
        ensure_collection(COL_CUTPLANE).objects.link(arrow)
        props.bar_arrow = arrow
    return arrow


def place_arrow(arrow):
    """InsertionArrow nam cung collection voi PlaneVisual (CutPlane); file cu de no o BarDesign."""
    coll = ensure_collection(COL_CUTPLANE)
    if list(arrow.users_collection) != [coll]:
        link_to(arrow, coll)


def arrow_object(props):
    """Mui ten huong lap hien co: pointer tren panel; pointer bi mat (file cu, undo, xoa
    nham) -> tim lai InsertionArrow trong scene. None khi chua co mui ten nao."""
    arrow = props.bar_arrow
    if valid_obj(arrow):
        return arrow
    found = bpy.data.objects.get(OBJ_ARROW)
    if valid_obj(found) and found.type == 'EMPTY':
        return found
    return None


def arrow_direction(arrow, depsgraph=None):
    """Huong lap (world, don vi) = truc Z cua mui ten. Chi khi THAT SU khong co mui ten
    moi mac dinh Z+ - neu co mui ten dang nghieng thi luc nao cung doc theo no."""
    if not valid_obj(arrow):
        return Vector((0.0, 0.0, 1.0))
    obj = arrow.evaluated_get(depsgraph) if depsgraph is not None else arrow
    direction = obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
    if direction.length < 1e-9:
        return Vector((0.0, 0.0, 1.0))
    return direction.normalized()


def project_to_plane(point, origin, normal):
    return point - normal * (point - origin).dot(normal)


# ---------------------------------------------------------------------------
# Line: Edit Mode + 1 modifier Shrinkwrap (Nearest Surface Point, Above Surface)
# ---------------------------------------------------------------------------
def add_line_modifier(obj, plane):
    """Chi 1 modifier RMVB_Shrinkwrap bam line vao PlaneVisual; hien ket qua ngay
    trong Edit Mode va On Cage de diem dieu khien nam dung tren Plane."""
    obj.modifiers.clear()
    mod = obj.modifiers.new(name=MOD_PREFIX + "Shrinkwrap", type='SHRINKWRAP')
    mod.target = plane
    mod.wrap_method = 'NEAREST_SURFACEPOINT'
    mod.wrap_mode = 'ABOVE_SURFACE'
    mod.offset = 0.0
    mod.show_in_editmode = True
    if hasattr(mod, "show_on_cage"):
        try:
            mod.show_on_cage = True
        except Exception:
            pass
    return mod


def walk_ordered_path(mesh, matrix):
    """Doc chuoi dinh theo thu tu noi canh. Tra ve (points_world, closed)."""
    count = len(mesh.vertices)
    adj = {i: [] for i in range(count)}
    for edge in mesh.edges:
        a, b = edge.vertices
        adj[a].append(b)
        adj[b].append(a)
    endpoints = [i for i, nb in adj.items() if len(nb) == 1]
    closed = (count >= 3 and not endpoints
              and all(len(nb) == 2 for nb in adj.values()))
    start = endpoints[0] if endpoints else 0
    order = []
    visited = set()
    cur = start
    prev = None
    while cur is not None and cur not in visited:
        visited.add(cur)
        order.append(cur)
        nxts = [v for v in adj[cur] if v != prev and v not in visited]
        prev = cur
        cur = nxts[0] if nxts else None
    return [matrix @ mesh.vertices[i].co for i in order], closed


def line_world_points(line, depsgraph):
    """Cac diem line sau modifier Shrinkwrap (ke ca khi line dang o Edit Mode)."""
    evaluated = line.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        points, _closed = walk_ordered_path(mesh, evaluated.matrix_world)
    finally:
        evaluated.to_mesh_clear()
    return points


def clean_points(points, eps=1e-4):
    """Bo cac diem trung lien tiep (do dai canh = 0 lam hong tiet dien)."""
    out = []
    for point in points:
        if not out or (point - out[-1]).length > eps:
            out.append(point)
    return out


# ---------------------------------------------------------------------------
# Khoi bar tiet dien hinh binh hanh
# ---------------------------------------------------------------------------
def bmesh_from_rings(rings):
    """Noi cac vong 4 dinh thanh khoi bar mo (nap kin 2 dau)."""
    bm = bmesh.new()
    verts = [[bm.verts.new(co) for co in ring] for ring in rings]

    def bridge(a, b):
        for i in range(4):
            j = (i + 1) % 4
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass

    for i in range(len(verts) - 1):
        bridge(verts[i], verts[i + 1])
    for cap in (tuple(reversed(verts[0])), tuple(verts[-1])):
        try:
            bm.faces.new(cap)
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    outward_solid(bm)
    return bm


def parallelogram_rings(points, normal, drop, width):
    """Cac vong 4 dinh: mat tren nam tren Plane (rong `width`, can giua line), canh
    ben di them vector `drop` (song song mui ten huong lap). Goc line duoc vat
    mep (mitre) de be rong khong bi hep lai."""
    count = len(points)
    if count < 2:
        return None
    dirs = [(points[i + 1] - points[i]).normalized() for i in range(count - 1)]
    half = width * 0.5
    rings = []
    for i, point in enumerate(points):
        t_prev = dirs[i - 1] if i > 0 else dirs[0]
        t_next = dirs[i] if i < count - 1 else dirs[-1]
        tangent = t_prev + t_next
        if tangent.length < 1e-6:
            tangent = t_next
        tangent.normalize()
        side = normal.cross(tangent)
        if side.length < 1e-9:
            side = Vector((1.0, 0.0, 0.0))
        side.normalize()
        offset = side * (half / max(0.5, tangent.dot(t_next)))
        left = point - offset
        right = point + offset
        rings.append([left, right, right + drop, left + drop])
    return rings


# ---------------------------------------------------------------------------
# Khoi dan huong "Can giua be mat Bar": Shrinkwrap constraint KHONG bam duoc vao line chi co canh
# (khong co mat) nen tao 1 khoi hop mong (an) doc tam bar lam muc tieu. Phai DUNG (khong phai dai
# phang tren Plane: diem gan nhat tren dai phang se khoa luon chieu Z) va phai KIN (Snap Mode
# Inside chi bam dung voi khoi kin; mat ho chi snap duoc cac diem o mot phia). Tru dai cua khoi
# THEO HUONG MUI TEN - cung truc extrude cua Bar Segment - chu khong thang theo phap tuyen Plane:
# mui ten nghieng (doi huong lap) thi khoi nghieng theo, mat ben khoi luon song song mat ben bar.
# ---------------------------------------------------------------------------
def update_center_guide(props, flat, normal, direction=None):
    """Dung lai khoi dan huong (mesh toa do world): hop mong KIN doc tam bar, rong CENTER_GUIDE_WIDTH,
    dai +-CENTER_GUIDE_HALF_HEIGHT DOC HUONG MUI TEN (`direction`, cung truc extrude cua Bar Segment -
    khong con thang theo phap tuyen Plane). Constraint Shrinkwrap dung Snap Mode Inside nen muc tieu
    phai la khoi kin, phap tuyen huong ra ngoai. Diem gan nhat tren khoi chi doi vi tri NGANG (vao
    tam bar), con vi tri doc huong mui ten giu nguyen - muon group nam tren Plane thi tick them Lock Z."""
    if direction is None or direction.length < 1e-6:
        direction = arrow_direction(arrow_object(props))       # Z+ neu chua co mui ten
    direction = direction.normalized()
    _CENTERLINE["flat"], _CENTERLINE["normal"] = list(flat), normal.copy()
    lift = direction * CENTER_GUIDE_HALF_HEIGHT           # truc dai THEO HUONG MUI TEN, giong Bar Segment
    rings = parallelogram_rings([point - lift for point in flat], normal, lift * 2.0, CENTER_GUIDE_WIDTH)
    if rings is None:
        return None
    bm = bmesh_from_rings(rings)
    guide = props.bar_center
    if not valid_obj(guide):
        guide = bpy.data.objects.new(OBJ_CENTER, bpy.data.meshes.new(OBJ_CENTER))
        ensure_collection(COL_SEGMENT).objects.link(guide)
        guide["rmvb_role"] = "BAR_CENTER"
        guide.hide_render = True
        guide.hide_select = True
        try:
            guide.hide_set(True)        # an khoi Viewport; Shrinkwrap van dung duoc lam muc tieu
        except RuntimeError:
            pass
        props.bar_center = guide
    bm.to_mesh(guide.data)
    bm.free()
    guide.data.update()
    guide["rmvb_guide_ver"] = CENTER_GUIDE_VERSION
    guide["rmvb_guide_dir"] = tuple(round(c, 6) for c in direction)
    return guide


def flat_centerline(props, depsgraph=None):
    """(cac diem tam bar da chieu len Plane, phap tuyen Plane) tinh tu line + Plane; None neu line
    < 2 diem hoac chua co Plane."""
    line, plane = props.bar_line, props.top_plane
    if not (valid_obj(line) and valid_obj(plane)):
        return None
    if depsgraph is None:
        depsgraph = bpy.context.evaluated_depsgraph_get()
    points = clean_points(line_world_points(line, depsgraph))
    if len(points) < 2:
        return None
    matrix = plane.evaluated_get(depsgraph).matrix_world
    normal = (matrix.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    return [project_to_plane(p, matrix.translation, normal) for p in points], normal


def guide_is_stale(props):
    """Khoi dan huong can dung lai: file kieu cu (dai doc phap tuyen Plane) hoac khoi bi dung
    luc chua biet huong mui ten that (truc luu tren object lech huong mui ten hien tai > ~0.57 do)."""
    guide = props.bar_center
    if not valid_obj(guide) or not len(guide.data.polygons):
        return False
    if guide.get("rmvb_guide_ver") != CENTER_GUIDE_VERSION:
        return True
    stored = guide.get("rmvb_guide_dir")
    if stored is None:
        return False
    try:
        return Vector(stored).angle(arrow_direction(arrow_object(props))) > 0.01
    except (TypeError, ValueError):
        return False


def ensure_center_guide(props):
    """Dai tam bar hien co, hoac dung tu line + Plane + mui ten neu chua co (None neu line < 2 diem).
    Khoi dung roi nhung sai huong mui ten (file kieu cu, mui ten moi tim lai duoc) -> dung lai."""
    guide = props.bar_center
    if valid_obj(guide) and len(guide.data.polygons) and not guide_is_stale(props):
        return guide
    data = flat_centerline(props)
    if data:
        return update_center_guide(props, data[0], data[1],
                                   arrow_direction(arrow_object(props)))
    return guide if valid_obj(guide) and len(guide.data.polygons) else None


# Tam bar (cac diem da chieu len Plane) lan cuoi Bar Segment cap nhat - "Truc X theo doc Bar" doc o
# day thay vi dung lai line moi lan Empty dich chuyen. Mat khi mo file -> dung lai tu line.
_CENTERLINE = {"flat": None, "normal": None}


def centerline(props):
    if _CENTERLINE["flat"] is None:
        data = flat_centerline(props)
        if data is None:
            return None
        _CENTERLINE["flat"], _CENTERLINE["normal"] = list(data[0]), data[1].copy()
    return _CENTERLINE["flat"]


def polyline_tangent(flat, point):
    """Huong (don vi) cua doan tam bar gan `point` nhat, theo chieu ve line (diem dau -> diem cuoi)."""
    best = None
    for index in range(len(flat) - 1):
        a, b = flat[index], flat[index + 1]
        edge = b - a
        length2 = edge.length_squared
        if length2 < 1e-12:
            continue
        t = max(0.0, min(1.0, (point - a).dot(edge) / length2))
        dist2 = (a + edge * t - point).length_squared
        if best is None or dist2 < best[0] - 1e-12:
            best = (dist2, edge)
    return best[1].normalized() if best else None


def align_group_x(group, props, depsgraph=None):
    """Xoay Empty cua group quanh phap tuyen Plane de truc X trung huong tam bar tai vi tri group
    (them 180 do neu group.align_x_flip).

    Lock Rotation (COPY_ROTATION BEFORE Plane) coi rotation_euler.z la goc quanh phap tuyen Plane, do
    tu truc X cua Plane -> chi can dat z = goc cua huong bar trong he truc Plane. Tra ve True neu doi."""
    empty, plane = group.empty, props.top_plane
    if not (valid_obj(empty) and valid_obj(plane)) or centerline(props) is None:
        return False
    if depsgraph is None:
        depsgraph = bpy.context.evaluated_depsgraph_get()
    tangent = polyline_tangent(_CENTERLINE["flat"], empty.evaluated_get(depsgraph).matrix_world.translation)
    if tangent is None:
        return False
    plane_rot = plane.evaluated_get(depsgraph).matrix_world.to_3x3().normalized()
    local = plane_rot.inverted() @ tangent
    if math.hypot(local.x, local.y) < 1e-6:
        return False                      # huong bar vuong goc Plane (khong xay ra khi line nam tren Plane)
    angle = math.atan2(local.y, local.x) + (math.pi if group.align_x_flip else 0.0)
    if empty.rotation_mode != 'XYZ':
        empty.rotation_mode = 'XYZ'
    current = empty.rotation_euler.z
    delta = (angle - current + math.pi) % (2.0 * math.pi) - math.pi
    if abs(delta) < 1e-5:
        return False
    empty.rotation_euler.z = current + delta
    return True


def add_center_constraint(empty, guide):
    """Shrinkwrap (Nearest Surface Point, Snap Mode Inside) cua Empty vao khoi tam bar: vi tri ngang
    luon nam tren tam bar."""
    constraint = empty.constraints.get(CST_CENTER)
    if constraint is None:
        constraint = empty.constraints.new('SHRINKWRAP')
        constraint.name = CST_CENTER
    constraint.target = guide
    constraint.shrinkwrap_type = 'NEAREST_SURFACE'
    constraint.wrap_mode = 'INSIDE'        # Snap Mode: Inside (muc tieu la khoi kin; ben trong khoi thi giu nguyen)
    constraint.distance = 0.0
    return constraint


# ---------------------------------------------------------------------------
# Bar Segment tu cap nhat (handler depsgraph + update cua thong so)
# ---------------------------------------------------------------------------
_SYNC = {"sig": None, "busy": False, "error": ""}


def sync_bar_segment(scene, depsgraph=None, force=False):
    """Dung lai mesh Bar Segment tu line + PlaneVisual + mui ten + thong so.

    Line nam tren Plane (Shrinkwrap) -> extrude theo huong NGUOC mui ten
    `Chieu cao bar` (do vuong goc Plane), canh ben song song mui ten. Chi ghi
    lai khi dau vao thay doi. Tra ve True neu da cap nhat.
    """
    props = scene.rmvb
    line, plane = props.bar_line, props.top_plane
    if _SYNC["busy"] or not valid_obj(line) or not valid_obj(plane):
        return False
    seg = props.bar_segment
    if valid_obj(props.bar_backup) or (valid_obj(seg) and seg.get("rmvb_applied")):
        return False                      # da Apply Bar Design: khong dung lai
    if depsgraph is None:
        depsgraph = bpy.context.evaluated_depsgraph_get()
    points = clean_points(line_world_points(line, depsgraph))
    if len(points) < 2:
        return False

    matrix = plane.evaluated_get(depsgraph).matrix_world
    direction = arrow_direction(arrow_object(props), depsgraph)
    normal = (matrix.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    if normal.dot(direction) < 0:
        normal = -normal
    cosine = normal.dot(direction)
    if cosine < 0.1:
        _SYNC["error"] = "PlaneVisual gan song song voi mui ten huong lap"
        return False
    origin = matrix.translation
    signature = (
        tuple(round(c, 4) for p in points for c in p),
        tuple(round(c, 4) for row in matrix for c in row),
        tuple(round(c, 5) for c in direction),
        round(props.bar_width, 5), round(props.bar_height, 5),
    )
    if not force and signature == _SYNC["sig"] and valid_obj(seg):
        return False

    _SYNC["busy"] = True
    try:
        flat = [project_to_plane(p, origin, normal) for p in points]
        drop = -direction * (props.bar_height / cosine)
        rings = parallelogram_rings(flat, normal, drop, props.bar_width)
        if rings is None:
            return False
        bm = bmesh_from_rings(rings)
        if not valid_obj(seg):
            mesh = bpy.data.meshes.new(OBJ_SEGMENT)
            seg = bpy.data.objects.new(OBJ_SEGMENT, mesh)
            ensure_collection(COL_SEGMENT).objects.link(seg)
            set_color(seg, (0.20, 0.65, 0.95, 1.0))
            seg["rmvb_role"] = "SEGMENT"
            props.bar_segment = seg
            created = True
        else:
            created = False
        bm.to_mesh(seg.data)
        bm.free()
        seg.data.update()
        seg["rmvb_topbar"] = True
        try:
            guide = update_center_guide(props, flat, normal, direction)
            if guide is not None:        # group da tick "Can giua be mat Bar" truoc khi co line
                for group in props.groups:
                    if group.center_bar and valid_obj(group.empty):
                        add_center_constraint(group.empty, guide)
        except Exception as exc:
            print("[Rmvb-Bar] Khong cap nhat duoc dai tam bar: %s" % exc)
        if created:
            rebuild_segment_modifiers(bpy.context)
        _SYNC["sig"] = signature
        _SYNC["error"] = ""
    finally:
        _SYNC["busy"] = False
    return True


@persistent
def rmvb_load_post(_dummy=None):
    """Mo file: group da bat Lock Rotation tu ban cu (copy ca 3 truc) duoc dung lai
    constraint kieu moi (chi khoa X/Y). Xoa cache tam bar cua file truoc."""
    _CENTERLINE["flat"] = _CENTERLINE["normal"] = None
    for obj in bpy.data.objects:        # file cu: Plain Axes cua nhom Implant / Attachment to 4 mm -> 1 mm
        if (obj.type == 'EMPTY' and obj.empty_display_type == 'PLAIN_AXES'
                and obj.get("rmvb_role") in ("IMPLANT_GROUP", "ATTACHMENT_GROUP")
                and obj.empty_display_size != GROUP_AXES_SIZE):
            obj.empty_display_size = GROUP_AXES_SIZE
    for scene in bpy.data.scenes:
        props = getattr(scene, "rmvb", None)
        if props is None:
            continue
        if not props.get("rmvb_gcut_split"):
            # File cu (truoc v0.7.0): Bar va Sleeve dung CHUNG mot khoi cat + mot offset. Lan mo
            # dau tien voi add-on moi thi lay Offset Gingiva Bar lam Offset Gingiva Sleeve de
            # Sleeve duoc cat giong nhu truoc day; khong dung lai mesh ngay luc mo file
            # (_GCUT_QUIET) - lan Create Sleeve Design tiep theo moi dung lai
            props["rmvb_gcut_split"] = True
            if (valid_obj(props.sleeve_object) and not valid_obj(props.gingiva_cutter_sleeve)
                    and abs(props.gingiva_offset) >= GINGIVA_OFFSET_EPS):
                _GCUT_QUIET[0] = True
                try:
                    props.gingiva_offset_sleeve = props.gingiva_offset
                finally:
                    _GCUT_QUIET[0] = False
        arrow = arrow_object(props)
        if arrow is not None:
            if not valid_obj(props.bar_arrow):
                props.bar_arrow = arrow        # pointer bi mat -> gan lai de dung dung huong lap
            place_arrow(arrow)
        if guide_is_stale(props) and not (
                valid_obj(props.bar_backup)
                or (valid_obj(props.bar_segment) and props.bar_segment.get("rmvb_applied"))):
            # Bar Segment va dai tam bar phai cung HUONG MUI TEN -> dung lai ca hai. Bar da
            # Apply / co backup thi giu dai cu cho khop voi khoi bar da dong bang.
            try:
                if valid_obj(props.bar_segment):
                    sync_bar_segment(scene, force=True)      # dung bar + dai tam bar cung luc
                if guide_is_stale(props):
                    ensure_center_guide(props)               # chi moi truong hop dung lai dai
                guide = props.bar_center
                if valid_obj(guide):
                    for group in props.groups:
                        if group.center_bar and valid_obj(group.empty):
                            add_center_constraint(group.empty, guide)   # dat lai Snap Mode Inside
            except Exception as exc:
                print("[Rmvb-Bar] Khong nang cap duoc dai tam bar: %s" % exc)
        for group in props.groups:
            if (group.lock_rot_topbar and valid_obj(group.empty)
                    and CST_ROT_LIMIT not in group.empty.constraints):
                try:
                    apply_group_locks(group, props)
                except Exception as exc:
                    print("[Rmvb-Bar] Khong nang cap duoc Lock Rotation: %s" % exc)


@persistent
def rmvb_depsgraph_handler(scene, depsgraph):
    """Line / PlaneVisual / mui ten duoc sua (ke ca trong Edit Mode) -> cap nhat Bar Segment; group
    tick "Truc X theo doc Bar" duoc xoay lai theo huong bar tai vi tri moi."""
    if _SYNC["busy"]:
        return
    try:
        props = scene.rmvb
    except AttributeError:
        return
    updated = {update.id.name for update in depsgraph.updates}
    line, plane = props.bar_line, props.top_plane
    bar_moved = False
    if valid_obj(line) and valid_obj(plane):
        watched = {line.name, line.data.name, plane.name, plane.data.name}
        arrow = arrow_object(props)
        if valid_obj(arrow):
            watched.add(arrow.name)
        bar_moved = bool(updated & watched)
        if bar_moved:
            try:
                sync_bar_segment(scene, depsgraph)
            except Exception as exc:
                message = str(exc)
                if message != _SYNC["error"]:
                    _SYNC["error"] = message
                    print("[Rmvb-Bar] Khong cap nhat duoc Bar Segment: %s" % message)
    gingiva = props.gingiva_object
    if valid_obj(gingiva) and {gingiva.name, gingiva.data.name} & updated:
        # Sua mesh / doi scale Gingiva: MOI khoi cat nuouu DA DUOC TAO (Bar va Sleeve, du offset
        # 0 hay khong) dung lai theo; keo xoay thi con cua Gingiva di theo nen _cutter_current
        # bao qua, khong dung lai mesh
        for sleeve_kind in (False, True):
            if not valid_obj(get_gingiva_cutter(props, sleeve_kind)):
                continue
            try:
                ensure_gingiva_cutter(props, sleeve=sleeve_kind)
            except Exception as exc:
                print("[Rmvb-Bar] Khong dung duoc khoi cat Gingiva (%s): %s"
                      % ("Sleeve" if sleeve_kind else "Bar", exc))
    for group in props.groups:
        if group.align_x_bar and valid_obj(group.empty) and (bar_moved or group.empty.name in updated):
            try:
                align_group_x(group, props, depsgraph)
            except Exception as exc:
                print("[Rmvb-Bar] Khong canh duoc truc X cua '%s': %s" % (group.name, exc))


class RMVB_OT_update_bar_segment(Operator):
    """Dung lai Bar Segment ngay (du phong neu tu cap nhat khong chay)"""
    bl_idname = "rmvb.update_bar_segment"
    bl_label = "Cập nhật Bar Segment"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        if not valid_obj(props.top_plane):
            self.report({'ERROR'}, "Bam Create Top Bar Plane truoc")
            return {'CANCELLED'}
        if not valid_obj(props.bar_line):
            self.report({'ERROR'}, "Chua co line. Bam Draw Line Bar truoc")
            return {'CANCELLED'}
        if context.mode != 'OBJECT' and context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        if not sync_bar_segment(context.scene, force=True):
            self.report({'WARNING'}, _SYNC["error"] or
                        "Khong dung lai duoc Bar Segment (line can it nhat 2 diem, "
                        "hoac Bar Design da Apply)")
            return {'CANCELLED'}
        self.report({'INFO'}, "Da cap nhat Bar Segment")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Draw Line Bar (snap PlaneVisual): modal ve theo con tro, line o Edit Mode
# ---------------------------------------------------------------------------
class RMVB_OT_create_bar_line(Operator):
    """Tao line bat dau tu 3D Cursor (chieu len PlaneVisual) va vao che do ve theo
    con tro (E hoac click de them diem NGAY tai vi tri con tro tren Plane)"""
    bl_idname = "rmvb.create_bar_line"
    bl_label = "Draw Line Bar"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        plane = props.top_plane
        if not valid_obj(plane):
            self.report({'ERROR'}, "Bam Create Top Bar Plane truoc khi ve line")
            return {'CANCELLED'}
        if valid_obj(props.bar_backup):
            self.report({'ERROR'}, "Dang co Bar Design da Apply - bam Delete Bar Design truoc")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if valid_obj(props.bar_line):
            remove_object(props.bar_line)
        context.view_layer.update()
        matrix = plane.matrix_world
        normal = (matrix.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
        start = project_to_plane(context.scene.cursor.location.copy(),
                                 matrix.translation, normal)
        mesh = bpy.data.meshes.new(OBJ_LINE)
        mesh.from_pydata([start], [], [])
        mesh.update()
        line = bpy.data.objects.new(OBJ_LINE, mesh)
        ensure_collection(COL_SEGMENT).objects.link(line)
        props.bar_line = line
        _SYNC["sig"] = None
        add_line_modifier(line, plane)
        set_color(line, (1.0, 0.35, 0.05, 1.0))

        bpy.ops.object.select_all(action='DESELECT')
        line.select_set(True)
        context.view_layer.objects.active = line
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        self.report({'INFO'}, "Di chuot tren PlaneVisual, nhan E (hoac click) de them diem")
        try:
            bpy.ops.rmvb.draw_bar_line('INVOKE_DEFAULT')
        except Exception as exc:
            self.report({'WARNING'}, "Khong mo duoc che do ve: %s" % exc)
        return {'FINISHED'}


class RMVB_OT_draw_bar_line(Operator):
    """Ve line theo con tro: di chuot tren PlaneVisual roi nhan E (hoac click trai) de
    them diem NGAY TAI con tro. Backspace xoa diem cuoi, Enter/Esc/chuot phai ket thuc"""
    bl_idname = "rmvb.draw_bar_line"
    bl_label = "Ve duong bar (theo con tro)"
    bl_options = {'REGISTER', 'UNDO'}

    def _find_view(self, context):
        area = view_3d_area(context)
        if area is None:
            return None, None, None
        region = None
        for reg in area.regions:
            if reg.type == 'WINDOW':
                region = reg
        return area, region, area.spaces.active.region_3d

    def _raycast(self, context, mouse_x, mouse_y):
        """Vi tri world tren PlaneVisual duoi con tro (hoac None)."""
        if self.region is None or self.rv3d is None:
            return None
        coord = (mouse_x - self.region.x, mouse_y - self.region.y)
        if (coord[0] < 0 or coord[1] < 0 or coord[0] > self.region.width
                or coord[1] > self.region.height):
            return None
        direction = view3d_utils.region_2d_to_vector_3d(self.region, self.rv3d, coord)
        origin = view3d_utils.region_2d_to_origin_3d(self.region, self.rv3d, coord)
        plane = self.plane
        inverse = plane.matrix_world.inverted()
        try:
            done, local, _n, _i = plane.ray_cast(
                inverse @ origin, (inverse.to_3x3() @ direction).normalized())
        except Exception:
            done = False
        if not done:
            return None
        return plane.matrix_world @ local

    def _pick_tip(self):
        """Dinh dau line dang ho (de noi diem moi vao)."""
        bm = self.bm
        bm.verts.ensure_lookup_table()
        tip = None
        if bm.select_history:
            last = bm.select_history[-1]
            if isinstance(last, bmesh.types.BMVert) and last.is_valid:
                tip = last
        if tip is None:
            open_ends = [v for v in bm.verts if len(v.link_edges) <= 1]
            sel = [v for v in open_ends if v.select]
            if sel:
                tip = sel[-1]
            elif open_ends:
                tip = open_ends[-1]
            elif bm.verts:
                tip = bm.verts[-1]
        return tip

    def _select_only(self, vert):
        bm = self.bm
        for v in bm.verts:
            v.select_set(False)
        for e in bm.edges:
            e.select_set(False)
        bm.select_history.clear()
        if vert is not None and vert.is_valid:
            vert.select_set(True)
            bm.select_history.add(vert)

    def _add_point(self, context, event):
        world = self._raycast(context, event.mouse_x, event.mouse_y)
        if world is None:
            self.report({'WARNING'}, "Khong cham vao PlaneVisual")
            return
        local = self.line.matrix_world.inverted() @ world
        new = self.bm.verts.new(local)
        if self.tip is not None and self.tip.is_valid:
            try:
                self.bm.edges.new((self.tip, new))
            except ValueError:
                pass
        self._select_only(new)
        self.tip = new
        self.bm.verts.ensure_lookup_table()
        bmesh.update_edit_mesh(self.line.data, destructive=False)
        if self.area:
            self.area.tag_redraw()

    def _remove_last(self, context):
        bm = self.bm
        if self.tip is None or not self.tip.is_valid or len(bm.verts) <= 1:
            return
        neighbor = None
        for edge in self.tip.link_edges:
            neighbor = edge.other_vert(self.tip)
            break
        try:
            bm.verts.remove(self.tip)
        except Exception:
            pass
        bm.verts.ensure_lookup_table()
        if neighbor is None or not neighbor.is_valid:
            neighbor = self._pick_tip()
        self.tip = neighbor
        self._select_only(neighbor)
        bmesh.update_edit_mesh(self.line.data, destructive=True)
        if self.area:
            self.area.tag_redraw()

    def _status(self, context, on=True):
        try:
            if on:
                context.workspace.status_text_set(
                    "Ve line bar tren PlaneVisual | E hoac Click trai: them diem tai con tro | "
                    "Backspace: xoa diem cuoi | Cuon/Giua chuot: zoom-xoay | "
                    "Enter/Esc/Chuot phai: xong")
            else:
                context.workspace.status_text_set(None)
        except Exception:
            pass

    def _draw_cb(self):
        """Duong 'cao su' tu dinh dau toi vi tri con tro (preview)."""
        if self.hit_world is None or self.tip is None or not self.tip.is_valid:
            return
        try:
            import gpu
            from gpu_extras.batch import batch_for_shader
        except Exception:
            return
        tip_world = self.line.matrix_world @ self.tip.co
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')
        gpu.state.line_width_set(2.0)
        gpu.state.point_size_set(9.0)
        try:
            batch = batch_for_shader(shader, 'LINES',
                                     {"pos": [tip_world, self.hit_world]})
            shader.bind()
            shader.uniform_float("color", (1.0, 0.8, 0.1, 0.9))
            batch.draw(shader)
            point = batch_for_shader(shader, 'POINTS', {"pos": [self.hit_world]})
            shader.bind()
            shader.uniform_float("color", (1.0, 0.3, 0.1, 1.0))
            point.draw(shader)
        except Exception:
            pass
        finally:
            gpu.state.line_width_set(1.0)
            gpu.state.point_size_set(1.0)
            gpu.state.depth_test_set('LESS_EQUAL')
            gpu.state.blend_set('NONE')

    def invoke(self, context, event):
        props = context.scene.rmvb
        plane = props.top_plane
        line = props.bar_line
        if not valid_obj(plane):
            self.report({'ERROR'}, "Bam Create Top Bar Plane truoc khi ve line")
            return {'CANCELLED'}
        if not valid_obj(line):
            self.report({'ERROR'}, "Chua co line. Bam Draw Line Bar truoc")
            return {'CANCELLED'}
        self.plane = plane
        self.line = line
        self.hit_world = None
        self.handle = None
        self.area, self.region, self.rv3d = self._find_view(context)
        if self.region is None or self.rv3d is None:
            self.report({'ERROR'}, "Khong tim thay vung 3D View")
            return {'CANCELLED'}

        # Dam bao dang Edit Mode tren line (cap nhat bmesh truc tiep)
        if not (context.mode == 'EDIT_MESH' and context.edit_object == line):
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            line.select_set(True)
            context.view_layer.objects.active = line
            bpy.ops.object.mode_set(mode='EDIT')
        self.bm = bmesh.from_edit_mesh(line.data)
        self.tip = self._pick_tip()
        self._select_only(self.tip)
        bmesh.update_edit_mesh(line.data, destructive=False)

        self._status(context, True)
        try:
            self.handle = bpy.types.SpaceView3D.draw_handler_add(
                self._draw_cb, (), 'WINDOW', 'POST_VIEW')
        except Exception:
            self.handle = None
        context.window_manager.modal_handler_add(self)
        if self.area:
            self.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _finish(self, context):
        self._status(context, False)
        if self.handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
            except Exception:
                pass
            self.handle = None
        if self.area:
            self.area.tag_redraw()

    def modal(self, context, event):
        if event.value == 'PRESS' and (
                event.type == 'E'
                or (event.type == 'LEFTMOUSE' and not event.alt)):
            self._add_point(context, event)
            return {'RUNNING_MODAL'}
        if event.value == 'PRESS' and event.type in {'BACK_SPACE', 'DEL'}:
            self._remove_last(context)
            return {'RUNNING_MODAL'}
        if event.value == 'PRESS' and event.type in {'RET', 'NUMPAD_ENTER',
                                                     'SPACE', 'ESC', 'RIGHTMOUSE'}:
            self._finish(context)
            self.report({'INFO'}, "Da xong ve line - sua line (Edit Mode) hoac Plane, "
                        "Bar Segment tu cap nhat")
            return {'FINISHED'}
        if event.type == 'MOUSEMOVE':
            self.hit_world = self._raycast(context, event.mouse_x, event.mouse_y)
            if self.area:
                self.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if (event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
                           'WHEELINMOUSE', 'WHEELOUTMOUSE', 'TRACKPADPAN',
                           'TRACKPADZOOM'}
                or (event.type == 'LEFTMOUSE' and event.alt)
                or (event.type.startswith('NUMPAD_')
                    and event.type != 'NUMPAD_ENTER')):
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}


class RMVB_OT_edit_bar_line(Operator):
    """Vao Edit Mode tren line de sua diem (Bar Segment tu cap nhat theo)"""
    bl_idname = "rmvb.edit_bar_line"
    bl_label = "Edit Line Bar"

    def execute(self, context):
        line = context.scene.rmvb.bar_line
        if not valid_obj(line):
            self.report({'ERROR'}, "Chua co line. Bam Draw Line Bar truoc")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        line.hide_set(False)
        line.select_set(True)
        context.view_layer.objects.active = line
        bpy.ops.object.mode_set(mode='EDIT')
        self.report({'INFO'}, "Edit line - Bar Segment tu cap nhat khi keo diem")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Modifier cua Bar Segment (chi ADD modifier, khong apply)
# ---------------------------------------------------------------------------
_MANIFOLD_CACHE = {}


def mesh_is_manifold(mesh):
    """Mesh kin: moi canh dung 2 mat va khong co dinh that nut - du dieu kien cho solver Manifold."""
    key = (mesh.name, len(mesh.vertices), len(mesh.polygons))
    cached = _MANIFOLD_CACHE.get(key)
    if cached is not None:
        return cached
    bm = bmesh.new()
    bm.from_mesh(mesh)
    ok = (bool(bm.faces) and all(edge.is_manifold for edge in bm.edges)
          and all(vert.is_manifold for vert in bm.verts))
    bm.free()
    if len(_MANIFOLD_CACHE) > 256:
        _MANIFOLD_CACHE.clear()
    _MANIFOLD_CACHE[key] = ok
    return ok


def add_boolean_modifier(target, operand, operation, name):
    """Them Boolean modifier (khong apply). Operand kin -> Manifold, khong kin -> Exact."""
    mod = target.modifiers.new(name=name, type='BOOLEAN')
    mod.operation = operation
    mod.operand_type = 'OBJECT'
    mod.object = operand
    manifold = operand.type == 'MESH' and mesh_is_manifold(operand.data)
    try:
        mod.solver = 'MANIFOLD' if manifold else 'EXACT'
    except TypeError:
        mod.solver = 'EXACT'
        manifold = False
    if mod.solver == 'EXACT':
        for prop, value in (("use_self", False), ("use_hole_tolerant", not manifold)):
            if hasattr(mod, prop):
                try:
                    setattr(mod, prop, value)
                except Exception:
                    pass
    mod.show_expanded = False
    return mod


ATT_PREFIX = MOD_PREFIX + "Att_"
CUTBASE_PREFIX = MOD_PREFIX + "CutBase_"
PREVIEW_PREFIXES = (ATT_PREFIX,)    # modifier do Enable / Disable Preview cua Attachment dieu khien
CUT_OPERAND_COLLECTIONS = {"pillar": "Rmvb Pillar Operands", "base": "Rmvb Base Operands"}


def preview_enabled(seg):
    """Preview Attachment (modifier Attachment hien trong Viewport). Mac dinh TAT; Add Attachment
    luon dua ve Disable Preview."""
    return bool(seg.get("rmvb_attach", False))


def cut_preview_enabled(seg):
    """Preview cat Top Bar (Gingiva, Pillar, PlaneCubeCut, Base hien trong Viewport). Mac dinh TAT: cac Boolean
    nang chi tinh khi can xem; Apply / Save / Sleeve luon tinh du phan cat. File cu (co `rmvb_cut`, chua co
    co moi) coi la dang bat."""
    if "rmvb_cut_preview" in seg.keys():
        return bool(seg["rmvb_cut_preview"])
    return bool(seg.get("rmvb_cut", False))


def is_cut_modifier(mod):
    """Modifier thuoc nhom Preview cat Top Bar: CutGingiva, Union Pillar, CutPlane, CutBase."""
    if not mod.name.startswith(MOD_PREFIX):
        return False
    short = mod.name[len(MOD_PREFIX):]
    return short in ("CutGingiva", "CutPlane") or short.startswith(("Union", "CutBase"))


@contextlib.contextmanager
def forced_cut_modifiers(seg):
    """Tam bat Realtime Display cua cac modifier cat Top Bar de Apply / Save / tao Sleeve luon thay du phan cat
    du Preview dang tat; khoi phuc trang thai cu khi xong."""
    saved = []
    if valid_obj(seg):
        saved = [(mod, mod.show_viewport) for mod in seg.modifiers if is_cut_modifier(mod)]
        for mod, _state in saved:
            mod.show_viewport = True
        bpy.context.view_layer.update()
    try:
        yield
    finally:
        for mod, state in saved:
            try:
                mod.show_viewport = state
            except (ReferenceError, RuntimeError):
                pass            # modifier da bi go (Apply)


def preview_target_count(props, seg):
    """So modifier Attachment ma Bar Segment phai co."""
    return sum(1 for g in props.groups if valid_obj(g.part_bar))


def operand_collection(key, objects):
    """Collection an (khong gan vao scene) giu cac operand cua 1 modifier Boolean kieu Collection."""
    name = CUT_OPERAND_COLLECTIONS[key]
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        coll.use_fake_user = True
    for obj in list(coll.objects):
        coll.objects.unlink(obj)
    for obj in objects:
        coll.objects.link(obj)
    return coll


def add_group_boolean(seg, entries, operation, all_name, one_prefix, key):
    """Them Boolean cho nhieu operand `entries` = [(ten, object)] cung 1 phep (Union / Difference).

    Moi operand dong (Manifold) -> 1 modifier kieu COLLECTION (tinh mot luot, nhanh gap ~2-3 lan nhieu modifier
    lien tiep); co operand khong kin -> moi operand 1 modifier nhu cu (Exact cho operand ho). Tra ve cac modifier."""
    if not entries:
        return []
    if all(obj.type == 'MESH' and mesh_is_manifold(obj.data) for _name, obj in entries):
        mod = seg.modifiers.new(name=MOD_PREFIX + all_name, type='BOOLEAN')
        mod.operation = operation
        mod.operand_type = 'COLLECTION'
        mod.collection = operand_collection(key, [obj for _name, obj in entries])
        try:
            mod.solver = 'MANIFOLD'
        except TypeError:
            seg.modifiers.remove(mod)
        else:
            mod.show_expanded = False
            return [mod]
    return [add_boolean_modifier(seg, obj, operation, MOD_PREFIX + one_prefix + name) for name, obj in entries]


# ---------------------------------------------------------------------------
# Khoi cat nuouu (GingivaCut / GingivaCut.Sleeve) cho phep Difference Gingiva
#
# HAI KHOI DOC LAP: 'GingivaCut' cat Bar Segment (Offset Gingiva Bar), 'GingivaCut.Sleeve' cat
# Sleeve (Offset Gingiva Sleeve) - doi thong so nay khong lam doi ket qua cua loai kia.
#
# Moi khoi LUON la mot ban copy cua Gingiva (mesh goac khong bao gio bi sua): copy duoc chuan bi
# thanh khoi kin (lam sach, dong mesh ho, de phang - xem prepare_gingiva_mesh) ROI moi doi
# TOAN BO dinh doc theo phap tuyen cua dinh (`v.co += v.normal * distance`, cach lam giong
# "Create Framework thickness" cua add-on ScansPrep), duong = phinh ra ngoai, am = thut vao
# trong. KHONG dung buoc Remesh cua ScansPrep: Remesh SMOOTH lam doi bien dang scan, trong
# khi day la khoi cat - moi lech nho deu vao ket qua cat cua Bar Segment. Khoi cat an
# trong Viewport + Render, la CON cua Gingiva; khoi cua Bar tao khi Create Top Bar Plane, khoi
# cua Sleeve tao khi Create Sleeve Design, sau do luon cap nhat theo Offset Gingiva tuong ung.
# ---------------------------------------------------------------------------
def offset_mesh_along_normals(mesh, distance):
    """Doi dinh cua `mesh` doc phap tuyen ngay tai cho. Tra ve so dinh da doi (0 neu distance ~ 0)."""
    if abs(distance) < 1e-9:
        return 0
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for vert in bm.verts:
        vert.co += vert.normal * distance
    count = len(bm.verts)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return count


def world_scale_factor(obj):
    """He so phong to world (trung binh nhan 3 truc) cua object.

    Mesh cua khoi cat nam trong toa do LOCAL cua Gingiva nen offset mm phai chia cho he so nay
    de trong world doi dung `offset` mm (scale khong deu thi ket qua gan dung)."""
    sx, sy, sz = obj.matrix_world.to_scale()
    factor = abs(sx * sy * sz) ** (1.0 / 3.0)
    return factor if factor > 1e-6 else 1.0


def gingiva_cutter_name(sleeve):
    """Ten object cua khoi cat nuouu theo loai: Bar = GingivaCut, Sleeve = GingivaCut.Sleeve."""
    return OBJ_GINGIVA_CUT_SLEEVE if sleeve else OBJ_GINGIVA_CUT


def get_gingiva_cutter(props, sleeve):
    """Pointer khoi cat nuouu dang luu tren scene theo loai (Bar / Sleeve)."""
    return props.gingiva_cutter_sleeve if sleeve else props.gingiva_cutter


def set_gingiva_cutter(props, sleeve, cut):
    if sleeve:
        props.gingiva_cutter_sleeve = cut
    else:
        props.gingiva_cutter = cut


def gingiva_offset_value(props, sleeve):
    """Offset dang dung cua loai khoi cat: Offset Gingiva Bar / Offset Gingiva Sleeve."""
    return (props.gingiva_offset_sleeve if sleeve else props.gingiva_offset) or 0.0


def remove_gingiva_cutter(props, sleeve=None):
    """Xoa khoi cat nuouu cua MOT loai (sleeve True/False) hoac CAC loai (sleeve None, dung khi
    Gingiva bi go bo) + mesh cache da chuan bi khi khong con khoi cat nao dung toi no."""
    for kind in ((False, True) if sleeve is None else (bool(sleeve),)):
        cut = get_gingiva_cutter(props, kind)
        if valid_obj(cut):
            remove_object(cut)
        set_gingiva_cutter(props, kind, None)
    if not any(valid_obj(get_gingiva_cutter(props, kind)) for kind in (False, True)):
        base = bpy.data.meshes.get(OBJ_GINGIVA_CUT_BASE)
        if base is not None:
            try:
                bpy.data.meshes.remove(base)
            except Exception:
                pass


def _attach_cutter_to(cut, gingiva):
    """Cho khoi cat lam con cua Gingiva: keo / xoay Gingiva la phan cat di theo, khoi khong can
    dung lai mesh (matrix_parent_inverse giu dung toa do world tai luc gan)."""
    cut.parent = gingiva
    cut.matrix_parent_inverse = gingiva.matrix_world.inverted()
    cut.matrix_world = gingiva.matrix_world.copy()


def _cutter_stamp(cut, gingiva, offset):
    """Ghi dau cac dau vao da dung de dung khoi cat: biet khi nao phai dung lai."""
    cut["rmvb_gcut_obj"] = gingiva.name
    cut["rmvb_gcut_mesh"] = gingiva.data.name
    cut["rmvb_gcut_verts"] = len(gingiva.data.vertices)
    cut["rmvb_gcut_polys"] = len(gingiva.data.polygons)
    cut["rmvb_gcut_offset"] = float(offset)
    cut["rmvb_gcut_scale"] = world_scale_factor(gingiva)


def _cutter_current(cut, gingiva, offset):
    return (cut.get("rmvb_gcut_obj") == gingiva.name
            and cut.get("rmvb_gcut_mesh") == gingiva.data.name
            and cut.get("rmvb_gcut_verts") == len(gingiva.data.vertices)
            and cut.get("rmvb_gcut_polys") == len(gingiva.data.polygons)
            and abs(float(cut.get("rmvb_gcut_offset", 0.0)) - float(offset)) < GINGIVA_OFFSET_EPS
            and abs(float(cut.get("rmvb_gcut_scale", 1.0)) - world_scale_factor(gingiva)) < 1e-6)


def _gingiva_signature(gingiva):
    """Chu ky cua mesh Gingiva (doi -> phai dung lai khoi cat nuouu)."""
    return "|".join((gingiva.name, gingiva.data.name,
                    str(len(gingiva.data.vertices)), str(len(gingiva.data.polygons)),
                    "%.9f" % world_scale_factor(gingiva)))


def _rebuild_gingiva_cut(cut, gingiva, offset, name=None):
    """Dung lai mesh cua mot khoi cat nuouu (Bar hoac Sleeve):
    - mesh cache `GingivaCut.base` (use_fake_user) giu ban DA CHUAN BI KIN theo chu ky mesh
      Gingiva va DU DUNG CHUNG cho ca hai khoi cat -> them loai thu hai chi copy + doi dinh
      (nhanh), khong chuan bi lai tu dau; chi khi nao chu ky Gingiva doi moi dung lai base;
    - Gingiva doi (mesh / so dinh / so mat / scale) thi chuan bi lai ban moi.
    Ket qua chuan bi (fill / khoi kin / canh bao) duoc luu len `cut` de Create Top Bar Plane
    bao cho nguoi dung biet."""
    sig = _gingiva_signature(gingiva)
    base = bpy.data.meshes.get(OBJ_GINGIVA_CUT_BASE)
    if base is None or base.get("rmvb_gcut_sig") != sig:
        if base is not None:
            bpy.data.meshes.remove(base)
        base = gingiva.data.copy()
        base.name = OBJ_GINGIVA_CUT_BASE
        base.use_fake_user = True              # mesh khong co object: khong bi purge, save van giu
        info = prepare_gingiva_mesh(base, gingiva.matrix_world)
        base["rmvb_gcut_sig"] = sig
        base["rmvb_gcut_filled"] = int(info["filled"])
        base["rmvb_gcut_manifold"] = bool(info["manifold"])
        base["rmvb_gcut_open_up"] = bool(info["open_side_up"])
        base["rmvb_gcut_floor"] = float(info["floor_z"] if info["floor_z"] is not None else 0.0)
    cut["rmvb_gcut_base"] = sig
    cut["rmvb_gcut_filled"] = int(base.get("rmvb_gcut_filled", 0))
    cut["rmvb_gcut_manifold"] = bool(base.get("rmvb_gcut_manifold", True))
    cut["rmvb_gcut_open_up"] = bool(base.get("rmvb_gcut_open_up", False))
    cut["rmvb_gcut_floor"] = float(base.get("rmvb_gcut_floor", 0.0))
    old = cut.data
    mesh = base.copy()
    mesh.name = name or cut.name
    cut.data = mesh
    if old.users == 0:
        bpy.data.meshes.remove(old)
    offset_mesh_along_normals(cut.data, offset / world_scale_factor(gingiva))
    _cutter_stamp(cut, gingiva, offset)


def ensure_gingiva_cutter(props, sleeve=False):
    """Khoi cat nuouu cho phep Difference Gingiva - CO HAI KHOI DOC LAP NHAU:

        sleeve=False -> 'GingivaCut'          cat Bar Segment  (offset props.gingiva_offset)
        sleeve=True  -> 'GingivaCut.Sleeve'   cat Sleeve       (offset props.gingiva_offset_sleeve)

    Moi khoi LUON la mot ban copy cua Gingiva da chuan bi thanh khoi kin (toi uu mesh / dong
    mesh ho / de phang) roi offset doc phap tuyen (0 = khong doi dinh), an trong Viewport +
    Render va lam CON cua Gingiva; ca hai dung chung mesh cache nen tao them loai thu hai
    khong phai chuan bi lai mesh.

    Khoi cat cua Bar duoc tao khi Create Top Bar Plane, khoi cat cua Sleeve khi Create Sleeve
    Design; sau do luon cap nhat theo thong so Offset Gingiva tuong ung tren panel. Chi dung
    lai mesh khi Gingiva doi (mesh / so dinh / so mat / scale) hoac offset cua loai do doi;
    keo / xoay Gingiva khong can dung lai vi khoi cat di theo transform cua Gingiva."""
    name = gingiva_cutter_name(sleeve)
    gingiva = props.gingiva_object
    if not valid_obj(gingiva) or gingiva.type != 'MESH':
        remove_gingiva_cutter(props)                 # Gingiva bi go bo -> xoa ca hai khoi cat
        return None
    offset = gingiva_offset_value(props, sleeve)
    cut = get_gingiva_cutter(props, sleeve)
    if not valid_obj(cut):
        cut = bpy.data.objects.get(name)             # pointer mat (file cu / undo) -> tai dung lai
        if valid_obj(cut):
            set_gingiva_cutter(props, sleeve, cut)
    if valid_obj(cut):
        # GIU NGUYEN object: modifier CutGingiva / boolean dang tro toi no, xoa roi tao la thi operand bi chet
        if cut.parent != gingiva:
            _attach_cutter_to(cut, gingiva)
        if not _cutter_current(cut, gingiva, offset):
            _rebuild_gingiva_cut(cut, gingiva, offset, name)
        return cut
    cut = bpy.data.objects.new(name, bpy.data.meshes.new(name))
    ensure_collection(COL_CUTPLANE).objects.link(cut)
    cut.hide_viewport = True               # an trong Viewport + render; Boolean van danh gia du (da do)
    cut.hide_render = True
    cut.hide_select = True
    cut.display_type = 'WIRE'
    cut["rmvb_role"] = "GINGIVA_CUT_SLEEVE" if sleeve else "GINGIVA_CUT"
    set_gingiva_cutter(props, sleeve, cut)
    _attach_cutter_to(cut, gingiva)
    _rebuild_gingiva_cut(cut, gingiva, offset, name)
    return cut


def rebuild_segment_modifiers(context):
    """Dung lai toan bo modifier cua Bar Segment theo thu tu co dinh:

        [Preview cat Top Bar]  Difference Gingiva
                               -> Union cac Bar Pillar (1 modifier Collection neu tat ca kin)
                               -> Difference PlaneCubeCut
                               -> Difference cac Base (1 modifier Collection neu tat ca kin)
        [Preview Attachment]   Union / Difference tung Part Bar (them ngay khi Add Attachment)

    Modifier luon duoc them san; Enable / Disable Preview chi bat / tat Realtime Display in Viewport cua tung
    nhom (mac dinh tat de Viewport nhe). Apply / Save / tao Sleeve luon tinh du phan cat Top Bar.
    Segment da Apply thi bo qua.
    """
    props = context.scene.rmvb
    seg = props.bar_segment
    if not valid_obj(seg) or seg.get("rmvb_applied"):
        return 0
    for mod in list(seg.modifiers):
        if mod.name.startswith(MOD_PREFIX):
            seg.modifiers.remove(mod)
    preview_att = preview_enabled(seg)
    preview_cut = cut_preview_enabled(seg)
    cut_mods = []
    gingiva = ensure_gingiva_cutter(props)      # Luon cat bang GingivaCut: ban copy da chuan bi kin + offset
    if valid_obj(gingiva):
        cut_mods.append(add_boolean_modifier(seg, gingiva, 'DIFFERENCE', MOD_PREFIX + "CutGingiva"))
    cut_mods += add_group_boolean(
        seg, [(ref.tooth, ref.object) for ref in props.pillars if valid_obj(ref.object)],
        'UNION', "UnionAll", "Union_", "pillar")
    if valid_obj(props.top_cutter):
        cut_mods.append(add_boolean_modifier(seg, props.top_cutter, 'DIFFERENCE', MOD_PREFIX + "CutPlane"))
    cut_mods += add_group_boolean(
        seg, [(item.tooth, item.base_object) for item in props.placed if valid_obj(item.base_object)],
        'DIFFERENCE', "CutBaseAll", "CutBase_", "base")
    for mod in cut_mods:
        mod.show_viewport = preview_cut
    for index, group in enumerate(props.groups):
        if valid_obj(group.part_bar):
            mod = add_boolean_modifier(
                seg, group.part_bar,
                'UNION' if group.on_bar else 'DIFFERENCE',
                "%sAtt_%d_%s" % (MOD_PREFIX, index, group.name[:30]))
            mod.show_viewport = preview_att
    return len([m for m in seg.modifiers if m.name.startswith(MOD_PREFIX)])


# ---------------------------------------------------------------------------
# Top Bar: PlaneVisual + PlaneCubeCut + khoi hinh binh hanh
# ---------------------------------------------------------------------------
def plane_mesh(name, half):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(-half, -half, 0.0), (half, -half, 0.0),
                      (half, half, 0.0), (-half, half, 0.0)], [], [(0, 1, 2, 3)])
    mesh.update()
    return mesh


def cube_mesh(name, half, height):
    """Plane `2*half` extrude +Z local `height` -> hop kin, normal ra ngoai."""
    bm = bmesh.new()
    bottom = [bm.verts.new(co) for co in ((-half, -half, 0.0), (half, -half, 0.0),
                                          (half, half, 0.0), (-half, half, 0.0))]
    top = [bm.verts.new((v.co.x, v.co.y, height)) for v in bottom]
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bm.faces.new(bottom)
    bm.faces.new(top)
    outward_solid(bm)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def design_bounds(context, direction):
    """(tam, cao do lon nhat doc `direction`) cua cac Bar Pillar (neu chua co thi
    cua cac Base; chua co nua thi lay 3D Cursor)."""
    props = context.scene.rmvb
    objs = [r.object for r in props.pillars if valid_obj(r.object)]
    if not objs:
        objs = [i.base_object for i in props.placed if valid_obj(i.base_object)]
    context.view_layer.update()
    corners = []
    for obj in objs:
        corners.extend(obj.matrix_world @ Vector(c) for c in obj.bound_box)
    if not corners:
        cursor = context.scene.cursor.location.copy()
        return cursor, cursor.dot(direction)
    center = sum(corners, Vector()) / len(corners)
    return center, max(co.dot(direction) for co in corners)


def replace_mesh_geometry(dst, src):
    """Thay hinh hoc cua mesh `dst` bang cua `src` (giu nguyen datablock + object)."""
    bm = bmesh.new()
    bm.from_mesh(src)
    bm.to_mesh(dst)
    bm.free()
    dst.update()
    bpy.data.meshes.remove(src)


def fit_plane_size(plane, cutter):
    """Plane/Cube tao tu ban cu (50 mm) duoc phong len PLANE_SIZE, giu nguyen vi tri,
    huong xoay va scale cua object. Mesh da bi sua tay (khac co luu) thi khong dong den.
    Tra ve True neu da doi co."""
    verts = plane.data.vertices
    if not len(verts):
        return False
    extent = 2.0 * max(abs(v.co.x) for v in verts)
    stored = plane.get("rmvb_size")
    if stored is None:
        stored = extent                    # ban cu chua ghi co: coi nhu dung co mesh
    resized = False
    if abs(stored - PLANE_SIZE) > 1e-6 and abs(extent - stored) < 1e-3:
        half = PLANE_SIZE * 0.5
        replace_mesh_geometry(plane.data, plane_mesh(OBJ_PLANE, half))
        if valid_obj(cutter):
            replace_mesh_geometry(cutter.data, cube_mesh(OBJ_CUTTER, half, PLANE_CUBE_HEIGHT))
        resized = True
    plane["rmvb_size"] = PLANE_SIZE if (resized or abs(extent - PLANE_SIZE) < 1e-3) else stored
    return resized


class RMVB_OT_create_top_bar_plane(Operator):
    """Buoc DAU TIEN cua Bar Segment: tao PlaneVisual (100 mm, xanh duong, opacity 0.4) va
    PlaneCubeCut (an) trong collection CutPlane + Mui ten huong lap. Neu da Set Gingiva, buoc
    nay cung la luc tao khoi cat nuouu (GingivaCut): ban copy da chuan bi khoi kin + offset
    theo thong so Offset Gingiva, an khoi Viewport. Sau do Draw Line Bar se ve tren
    PlaneVisual va Bar Segment tu cap nhat theo line, Plane, mui ten"""
    bl_idname = "rmvb.create_top_bar_plane"
    bl_label = "Create Top Bar Plane"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        coll = ensure_collection(COL_CUTPLANE)
        direction = arrow_direction(arrow_object(props))
        created = False
        plane = props.top_plane
        if not valid_obj(plane):
            center, top = design_bounds(context, direction)
            origin = center + direction * (top - center.dot(direction))
            plane = bpy.data.objects.new(OBJ_PLANE, plane_mesh(OBJ_PLANE, PLANE_SIZE * 0.5))
            coll.objects.link(plane)
            rot = direction.to_track_quat('Z', 'Y').to_matrix().to_4x4()
            plane.matrix_world = Matrix.Translation(origin) @ rot
            set_display_color(plane, (0.10, 0.35, 1.0, 0.4))
            plane["rmvb_role"] = "PLANE_VISUAL"
            plane["rmvb_size"] = PLANE_SIZE
            props.top_plane = plane
            created = True
        cutter = props.top_cutter
        if not valid_obj(cutter):
            cutter = bpy.data.objects.new(
                OBJ_CUTTER, cube_mesh(OBJ_CUTTER, PLANE_SIZE * 0.5, PLANE_CUBE_HEIGHT))
            coll.objects.link(cutter)
            cutter.parent = plane
            cutter.matrix_parent_inverse = Matrix.Identity(4)
            set_display_color(cutter, (1.0, 0.50, 0.10, 0.5))
            cutter["rmvb_role"] = "PLANE_CUBE_CUT"
            cutter.hide_render = True
            cutter.hide_set(True)                 # an khoi Viewport luc tao
            props.top_cutter = cutter
        resized = False if created else fit_plane_size(plane, cutter)
        context.view_layer.update()
        ensure_arrow(context, plane.matrix_world.translation)

        # Khoi cat nuouu CUA BAR: TU buoc nay moi bat dau tao (Set Gingiva chi doi mau + danh dau +
        # doi ten, mesh goac giu nguyen). Ban copy mesh Gingiva duoc toi uu / dong mesh ho
        # thanh khoi kin roi offset doc phap tuyen de toi uu cho Boolean; an khoi Viewport va
        # luon cap nhat theo thong so Offset Gingiva Bar tren panel. Sleeve co khoi cat
        # GingivaCut.Sleeve rieng, tao khi bam Create Sleeve Design
        gingiva_cut = ensure_gingiva_cutter(props)
        if valid_obj(gingiva_cut):
            filled = int(gingiva_cut.get("rmvb_gcut_filled", 0))
            manifold = bool(gingiva_cut.get("rmvb_gcut_manifold", True))
            floor_z = float(gingiva_cut.get("rmvb_gcut_floor", 0.0))
            self.report({'INFO'},
                        "Mesh cắt nướu Bar (ẩn): fill %d lỗ, đế phẳng Z=%.2f, offset %g mm, %s"
                        % (filled, floor_z, props.gingiva_offset or 0.0,
                           "khối kín + manifold" if manifold else "CHƯA kín"))
            if bool(gingiva_cut.get("rmvb_gcut_open_up", False)):
                self.report({'WARNING'},
                            "Mặt hở của Gingiva quay LÊN (+Z world): đế phẳng sẽ đùm lên trên "
                            "thay vì xuống. Xoay Gingiva cho mặt hở hướng xuống rồi Set lại")
            if not manifold:
                self.report({'WARNING'},
                            "Khối cắt nướu chưa kín manifold - Boolean có thể không ổn định")
        if valid_obj(props.bar_segment):
            rebuild_segment_modifiers(context)           # them modifier CutPlane (tat Preview)
        for group in props.groups:
            if group.lock_topbar or group.lock_rot_topbar or group.center_bar or group.align_x_bar:
                apply_group_locks(group, props)
        if valid_obj(props.bar_line):
            if valid_obj(props.bar_line) and props.bar_line.modifiers:
                props.bar_line.modifiers[0].target = plane
            sync_bar_segment(context.scene, force=True)
        activate(context, plane)
        if resized:
            message = "Da phong to PlaneVisual + PlaneCubeCut len %g mm" % PLANE_SIZE
        else:
            message = "%s PlaneVisual + PlaneCubeCut (%g mm) + Mui ten huong lap%s - bam Draw " \
                      "Line Bar de ve line tren Plane" % (
                          "Da tao" if created else "Da co", PLANE_SIZE,
                          " + mesh cat nuouu (an)" if valid_obj(gingiva_cut) else "")
        self.report({'INFO'}, message)
        return {'FINISHED'}


def set_cut_preview(context, enabled):
    """Bat / tat Preview cat Top Bar: Realtime Display in Viewport (show_viewport) cua cac modifier Gingiva, Pillar,
    PlaneCubeCut, Base tren Bar Segment, va an / hien Bar Pillar + ConnectionVisual (da nam gon trong ket qua cat).
    Tra ve so modifier cat."""
    props = context.scene.rmvb
    seg = props.bar_segment
    seg["rmvb_cut_preview"] = enabled
    rebuild_segment_modifiers(context)       # Pillar / Plane / Base / Gingiva co the vua doi; rebuild ap trang thai moi
    count = sum(1 for mod in seg.modifiers if is_cut_modifier(mod))
    for obj in ([r.object for r in props.pillars] + [i.visual_object for i in props.placed]):
        if valid_obj(obj):
            try:
                obj.hide_set(enabled)
            except RuntimeError:             # object khong nam trong View Layer
                pass
    return count


class RMVB_OT_enable_cut_preview(Operator):
    """Enable Preview: BAT Realtime Display in Viewport cua cac modifier cat Top Bar (Difference Gingiva, Union Bar
    Pillar, Difference PlaneCubeCut, Difference Base) tren Bar Segment, dong thoi AN Bar Pillar + ConnectionVisual.
    Modifier da duoc them san; nut nay khong apply"""
    bl_idname = "rmvb.enable_cut_preview"
    bl_label = "Enable Preview"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        seg = props.bar_segment
        if not valid_obj(seg):
            self.report({'ERROR'}, "Chua co Bar Segment")
            return {'CANCELLED'}
        if seg.get("rmvb_applied"):
            self.report({'ERROR'}, "Bar Segment da Apply - bam Delete Bar Design de sua tiep")
            return {'CANCELLED'}
        if not valid_obj(props.top_cutter):
            self.report({'ERROR'}, "Chua co PlaneCubeCut - bam Create Top Bar Plane truoc")
            return {'CANCELLED'}
        ensure_object_mode(context)     # dang Edit Line Bar -> chot diem line truoc khi tinh Boolean
        count = set_cut_preview(context, True)
        activate(context, seg)
        self.report({'INFO'}, "Enable Preview cat Top Bar: bat hien thi %d modifier, da an Bar Pillar + "
                    "ConnectionVisual (Boolean tinh lai moi khi doi line / Plane / Pillar - bam Disable Preview "
                    "khi chinh sua cho nhe)" % count)
        return {'FINISHED'}


class RMVB_OT_disable_cut_preview(Operator):
    """Disable Preview: TAT Realtime Display in Viewport cua cac modifier cat Top Bar (modifier van giu nguyen, Apply /
    Save / Sleeve van tinh du phan cat) va HIEN LAI Bar Pillar + ConnectionVisual de chinh sua"""
    bl_idname = "rmvb.disable_cut_preview"
    bl_label = "Disable Preview"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        seg = props.bar_segment
        if not valid_obj(seg):
            self.report({'ERROR'}, "Chua co Bar Segment")
            return {'CANCELLED'}
        if seg.get("rmvb_applied"):
            self.report({'ERROR'}, "Bar Segment da Apply - bam Delete Bar Design de sua tiep")
            return {'CANCELLED'}
        ensure_object_mode(context)
        count = set_cut_preview(context, False)
        self.report({'INFO'}, "Disable Preview cat Top Bar: tat hien thi %d modifier, da hien lai Bar Pillar + "
                    "ConnectionVisual" % count)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Attachment: moi lan Add = 1 group (Empty cha + Part Bar + Part Sleeve + Visual)
# ---------------------------------------------------------------------------
def current_attachment_name(props):
    names = get_attachment_items()
    if props.active_attachment in names:
        return props.active_attachment
    if names:
        return names[min(props.attachment_index, len(names) - 1)]
    return ""


def slugify(text):
    return re.sub(r"[^\w\-.]+", "_", (text or "att"), flags=re.UNICODE)


def unique_group_name(props, base):
    names = {group.name for group in props.groups}
    if base not in names:
        return base
    index = 2
    while "%s_%d" % (base, index) in names:
        index += 1
    return "%s_%d" % (base, index)


def group_by_name(props, name):
    for group in props.groups:
        if group.name == name:
            return group
    return None


def group_objects(group):
    """Moi object thuoc group (khong gom Empty)."""
    objs = [group.part_bar, group.part_sleeve] + [v.object for v in group.visuals]
    return [o for o in objs if valid_obj(o)]


def set_parts_hidden(groups, hidden):
    """An / hien Part Bar + Part Sleeve (khoi Boolean) cua cac group. Chi doi mat Viewport
    (hide_set) nen modifier Boolean tren Bar Segment van chay; Visual Object khong bi dong cham."""
    count = 0
    for group in groups:
        for obj in (group.part_bar, group.part_sleeve):
            if not valid_obj(obj):
                continue
            try:
                obj.hide_set(hidden)
                count += 1
            except RuntimeError:        # object khong nam trong View Layer
                pass
    return count


def attach_to(child, parent):
    """Gan child vao parent (toa do local cua child = toa do cua parent)."""
    child.parent = parent
    child.matrix_parent_inverse = Matrix.Identity(4)


def unparent_keep_world(obj):
    world = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = world


def _lock_cycle(props, group, target):
    """Lock tu group -> target co tao vong khep kin (A -> B -> A) khong?"""
    seen = {group.name}
    current = target
    while current is not None:
        if current.name in seen:
            return True
        seen.add(current.name)
        if current.lock_attachment and current.lock_target:
            current = group_by_name(props, current.lock_target)
        else:
            break
    return False


LOCK_CONSTRAINTS = (CST_CENTER, CST_ON_PLANE, CST_ROT_LIMIT, CST_ROT_PLANE, CST_COPY_LOC, CST_COPY_ROT)


def apply_group_locks(group, props):
    """Dung lai cac constraint khoa tren Empty cua group:

    - Can giua be mat Bar       : SHRINKWRAP (Nearest Surface Point, Snap Mode Inside) vao khoi hop
                                  mong kin doc tam bar - vi tri ngang luon nam tren duong tam line,
                                  chieu cao (Z) tu do (khong anh huong huong xoay)
    - Lock Z voi Top Bar        : LIMIT_LOCATION z = 0 trong he truc cua PlaneVisual
    - Truc X theo doc Bar       : giu Z vuong goc Plane (nhu Lock Rotation) + align_group_x dat goc
                                  (nut Dao 180 do them pi vao goc do)
                                  xoay quanh Z theo huong tam bar (handler depsgraph giu cap nhat)
    - Lock Rotation voi Top Bar : khoa nghieng X/Y theo PlaneVisual, Z tu do. LIMIT_ROTATION
                                  dua X/Y rieng cua group ve 0, roi COPY_ROTATION (Before
                                  Original) dat huong cua Plane lam he truc cha -> Z cua
                                  group luon vuong goc Plane, xoay Z la xoay quanh phap
                                  tuyen Plane
    - Lock Location & Rotation voi Attachment: COPY_LOCATION + COPY_ROTATION
    """
    empty = group.empty
    if not valid_obj(empty):
        return
    plane = props.top_plane
    if valid_obj(plane) and empty.parent == plane:
        bpy.context.view_layer.update()      # scene v0.2.0: Lock Z tung parent vao Plane
        unparent_keep_world(empty)
    for constraint in list(empty.constraints):
        if constraint.name in LOCK_CONSTRAINTS:
            empty.constraints.remove(constraint)
    if group.center_bar:
        try:
            guide = ensure_center_guide(props)
        except Exception as exc:
            guide = None
            print("[Rmvb-Bar] Khong dung duoc dai tam bar: %s" % exc)
        if guide is not None:
            add_center_constraint(empty, guide)
    if group.lock_topbar and valid_obj(plane):
        constraint = empty.constraints.new('LIMIT_LOCATION')
        constraint.name = CST_ON_PLANE
        constraint.owner_space = 'CUSTOM'
        constraint.space_object = plane
        constraint.use_min_z = True
        constraint.use_max_z = True
        constraint.min_z = 0.0
        constraint.max_z = 0.0
        if hasattr(constraint, "use_transform_limit"):
            constraint.use_transform_limit = True
    if (group.lock_rot_topbar or group.align_x_bar) and valid_obj(plane):
        if empty.rotation_mode != 'XYZ':
            empty.rotation_mode = 'XYZ'
        limit = empty.constraints.new('LIMIT_ROTATION')
        limit.name = CST_ROT_LIMIT
        limit.owner_space = 'WORLD'        # Empty khong co parent: world = local (LOCAL khong khoa duoc)
        for axis in ("x", "y"):
            setattr(limit, "use_limit_" + axis, True)
            setattr(limit, "min_" + axis, 0.0)
            setattr(limit, "max_" + axis, 0.0)
        if hasattr(limit, "use_transform_limit"):
            limit.use_transform_limit = True
        constraint = empty.constraints.new('COPY_ROTATION')
        constraint.name = CST_ROT_PLANE
        constraint.target = plane
        constraint.mix_mode = 'BEFORE'
    if group.lock_attachment and group.lock_target:
        target = group_by_name(props, group.lock_target)
        if (target is not None and target != group and valid_obj(target.empty)
                and not _lock_cycle(props, group, target)):
            for kind, name in (('COPY_LOCATION', CST_COPY_LOC),
                               ('COPY_ROTATION', CST_COPY_ROT)):
                constraint = empty.constraints.new(kind)
                constraint.name = name
                constraint.target = target.empty
    if group.align_x_bar:
        bpy.context.view_layer.update()
        try:
            align_group_x(group, props)
        except Exception as exc:
            print("[Rmvb-Bar] Khong canh duoc truc X: %s" % exc)
    bpy.context.view_layer.update()


def set_move_tool(context):
    """Chuyen cong cu 3D View sang Move (builtin.move). Bo qua neu khong co 3D View."""
    area = view_3d_area(context)
    if area is None:
        return False
    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    try:
        with context.temp_override(area=area, region=region):
            bpy.ops.wm.tool_set_by_id(name="builtin.move", space_type='VIEW_3D')
        return True
    except Exception as exc:
        print("[Rmvb-Bar] Khong dat duoc cong cu Move: %s" % exc)
        return False


def select_group_for_move(context, group):
    """Chon + active Plain Axes (Empty) cua group, Object Mode, cong cu Move."""
    empty = group.empty
    if not valid_obj(empty):
        return False
    try:
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:
        pass
    try:
        empty.hide_select = False
        empty.hide_set(False)
        for obj in context.view_layer.objects:
            if obj.select_get():
                obj.select_set(False)
        empty.select_set(True)
        context.view_layer.objects.active = empty
    except Exception as exc:
        print("[Rmvb-Bar] Khong chon duoc '%s': %s" % (empty.name, exc))
        return False
    set_move_tool(context)
    return True


class RMVB_OT_select_attachment_group(Operator):
    """Chon Plain Axes cua group Attachment (Object Mode, cong cu Move) de di chuyen nhanh"""
    bl_idname = "rmvb.select_attachment_group"
    bl_label = "Chon group Attachment"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(name="Index", default=-1)

    def execute(self, context):
        props = context.scene.rmvb
        index = self.index if self.index >= 0 else props.group_index
        if not (0 <= index < len(props.groups)):
            self.report({'ERROR'}, "Chua chon group Attachment")
            return {'CANCELLED'}
        set_group_index(props, index)
        if not select_group_for_move(context, props.groups[index]):
            self.report({'ERROR'}, "Khong chon duoc Empty cua group")
            return {'CANCELLED'}
        return {'FINISHED'}


class RMVB_OT_add_attachment(Operator):
    """Them nguyen bo Attachment da chon (Part Bar, Part Sleeve, Visual Object) thanh
    mot GROUP moi tai 3D Cursor"""
    bl_idname = "rmvb.add_attachment"
    bl_label = "Add selected Attachment"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        context.view_layer.update()
        name = current_attachment_name(props)
        if not name:
            self.report({'ERROR'}, "Chua chon Attachment trong Dental-Lib")
            return {'CANCELLED'}
        entry = lib_attachment(name) or {}
        lib = dlib()
        assets = {}
        for slot in ("part_bar", "part_sleeve"):
            path = lib.attachment_asset(name, slot) if lib else ""
            if path and os.path.exists(path):
                try:
                    assets[slot] = mesh_from_file(path)
                except Exception as exc:
                    self.report({'WARNING'}, "Loi doc %s cua '%s': %s" % (slot, name, exc))
        visuals = []
        if lib:
            for slot, path, rgba in lib_visuals(name):
                if not path or not os.path.exists(path):
                    continue
                try:
                    visuals.append((slot, mesh_from_file(path), rgba))
                except Exception as exc:
                    self.report({'WARNING'}, "Loi doc Visual Object '%s': %s" % (slot, exc))
        if not assets and not visuals:
            self.report({'ERROR'}, "Attachment '%s' chua co mesh nao (STL/PLY)" % name)
            return {'CANCELLED'}

        coll = ensure_collection(COL_ATTACHMENT)
        matrix = context.scene.cursor.matrix.copy()
        gname = unique_group_name(props, name)
        empty = bpy.data.objects.new("Att_" + gname, None)
        empty.empty_display_type = 'PLAIN_AXES'
        empty.empty_display_size = GROUP_AXES_SIZE
        empty.show_in_front = True
        coll.objects.link(empty)
        empty.matrix_world = matrix
        empty["rmvb_role"] = "ATTACHMENT_GROUP"

        group = props.groups.add()
        group.empty = empty
        group["prev_name"] = gname
        group.name = gname
        group.lib_name = name
        group.on_bar = bool(entry.get("on_bar", True))
        group.bar_in_sleeve = bool(entry.get("bar_in_sleeve", False))
        group.on_sleeve = bool(entry.get("on_sleeve", False))

        for slot, field, role in (("part_bar", "part_bar", "ATTACHMENT"),
                                  ("part_sleeve", "part_sleeve", "ATTACHMENT_SLEEVE")):
            mesh = assets.get(slot)
            if mesh is None:
                continue
            obj = object_from_mesh("%s_%s" % (gname, slot), mesh, coll)
            attach_to(obj, empty)
            set_display_color(obj, lib_slot_color(name, slot))
            obj["rmvb_role"] = role
            obj["rmvb_attachment"] = name
            setattr(group, field, obj)
        for label, mesh, rgba in visuals:
            vobj = object_from_mesh("%s_%s" % (gname, slugify(label)), mesh, coll)
            attach_to(vobj, empty)
            vobj["rmvb_role"] = "VISUAL"
            vobj["rmvb_attachment"] = name
            set_display_color(vobj, rgba)
            ref = group.visuals.add()
            ref.object = vobj
            ref.tooth = label

        set_group_index(props, len(props.groups) - 1)
        seg = props.bar_segment
        if valid_obj(seg) and not seg.get("rmvb_applied"):
            # Add Attachment luon ve Disable Preview: modifier Attachment tat trong Viewport, Part hien
            # de nguoi dung dat vi tri (bam Enable Preview de xem ket qua)
            set_attachment_preview(context, False)
        else:
            rebuild_segment_modifiers(context)
        self.report({'INFO'}, "Da them group Attachment '%s' (%d part, %d Visual Object)"
                    % (gname, len(assets), len(visuals)))
        return {'FINISHED'}


def remove_group(props, index):
    group = props.groups[index]
    for obj in group_objects(group):
        remove_object(obj)
    remove_object(group.empty)
    props.groups.remove(index)
    set_group_index(props, min(props.group_index, len(props.groups) - 1))


class RMVB_OT_remove_attachment_group(Operator):
    """Xoa group Attachment dang chon"""
    bl_idname = "rmvb.remove_attachment_group"
    bl_label = "Xoa group dang chon"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        if not (0 <= props.group_index < len(props.groups)):
            self.report({'ERROR'}, "Chua chon group Attachment")
            return {'CANCELLED'}
        name = props.groups[props.group_index].name
        remove_group(props, props.group_index)
        for group in props.groups:       # bo Lock dang tro toi group vua xoa
            if group.lock_target == name:
                group.lock_target = ""
        rebuild_segment_modifiers(context)
        self.report({'INFO'}, "Da xoa group '%s'" % name)
        return {'FINISHED'}


class RMVB_OT_clear_attachments(Operator):
    """Xoa toan bo group Attachment da dat"""
    bl_idname = "rmvb.clear_attachments"
    bl_label = "Xoa tat ca Attachment"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        while len(props.groups):
            remove_group(props, len(props.groups) - 1)
        rebuild_segment_modifiers(context)
        self.report({'INFO'}, "Da xoa Attachment")
        return {'FINISHED'}


def _preview_target(operator, context):
    """Bar Segment co the bat/tat preview Attachment, hoac None (da bao loi)."""
    seg = context.scene.rmvb.bar_segment
    if not valid_obj(seg):
        operator.report({'ERROR'}, "Chua co Bar Segment")
        return None
    if seg.get("rmvb_applied"):
        operator.report({'ERROR'}, "Bar Segment da Apply - bam Delete Bar Design de sua tiep")
        return None
    return seg


def set_attachment_preview(context, enabled):
    """Bat / tat Preview: Realtime Display in Viewport (show_viewport) cua cac modifier Attachment
    tren Bar Segment (CutBase khong bi dong cham), va an / hien Part Bar + Part Sleeve.
    Tra ve so modifier doi."""
    props = context.scene.rmvb
    seg = props.bar_segment
    seg["rmvb_attach"] = enabled
    have = sum(1 for m in seg.modifiers if m.name.startswith(PREVIEW_PREFIXES))
    if have != preview_target_count(props, seg):     # file cu / modifier bi xoa tay / group moi
        rebuild_segment_modifiers(context)
    count = 0
    for mod in seg.modifiers:
        if mod.name.startswith(PREVIEW_PREFIXES):
            mod.show_viewport = enabled
            count += 1
    set_parts_hidden(props.groups, enabled)
    return count


class RMVB_OT_enable_attachment_preview(Operator):
    """Enable Preview: BAT Realtime Display in Viewport cua cac modifier Attachment (Union /
    Difference Part Bar) tren Bar Segment, dong thoi AN Part Bar / Part Sleeve (Apply Part on Bar /
    on Sleeve). Modifier da duoc them san, nut nay khong them / xoa"""
    bl_idname = "rmvb.enable_attachment_preview"
    bl_label = "Enable Preview"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        seg = _preview_target(self, context)
        if seg is None:
            return {'CANCELLED'}
        if preview_target_count(props, seg) == 0:
            self.report({'ERROR'}, "Chua co Attachment nao co Part Bar")
            return {'CANCELLED'}
        count = set_attachment_preview(context, True)
        self.report({'INFO'}, "Enable Preview: bat hien thi %d modifier Attachment, da an "
                    "Part Bar / Part Sleeve" % count)
        return {'FINISHED'}


class RMVB_OT_disable_attachment_preview(Operator):
    """Disable Preview: TAT Realtime Display in Viewport cua cac modifier Attachment (modifier va
    group Attachment van giu nguyen) va HIEN LAI Part Bar / Part Sleeve"""
    bl_idname = "rmvb.disable_attachment_preview"
    bl_label = "Disable Preview"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        seg = _preview_target(self, context)
        if seg is None:
            return {'CANCELLED'}
        count = set_attachment_preview(context, False)
        self.report({'INFO'}, "Disable Preview: tat hien thi %d modifier Attachment, da hien "
                    "lai Part Bar / Part Sleeve" % count)
        return {'FINISHED'}


class RMVB_UL_attachment_groups(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon='EMPTY_AXIS')
        row.label(text="Bar:%s Sleeve:%s" % ("+" if item.on_bar else "-",
                                             "+" if item.on_sleeve else "-"))
        op = row.operator(RMVB_OT_select_attachment_group.bl_idname, text="",
                          icon=_ic('RESTRICT_SELECT_OFF'))
        op.index = index


# ---------------------------------------------------------------------------
# Sleeve: ham dung khoi (kin, dilate, solidify)
# ---------------------------------------------------------------------------
def world_copy(obj, name, coll):
    """Ban sao object cung toa do world (mesh local duoc copy)."""
    copy = bpy.data.objects.new(name, obj.data.copy())
    coll.objects.link(copy)
    copy.matrix_world = obj.matrix_world.copy()
    return copy


def fill_holes(obj, relax=1e-6):
    """Lap kin cac vung mo cua mesh de boolean solver ra khoi solid hop le.

    Neu chi co 2 vong bien gan dong phang va dong tam (thuong la 2 rim cua
    thanh wall) thi bridge thanh vong xuyen tam; nguoi dung lap day tung vong.
    Cuoi cung dao normal neu khoi am (normal quay vao trong).
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    loops = boundary_loops(bm)
    if len(loops) == 2:
        dz = abs(loops[0]["z"] - loops[1]["z"])
        c0 = sum((v.co for v in loops[0]["verts"]), Vector()) / len(loops[0]["verts"])
        c1 = sum((v.co for v in loops[1]["verts"]), Vector()) / len(loops[1]["verts"])
        radial = (c0 - c1).length
        if dz <= 0.05 and radial <= 0.05:
            edges = [e for loop in loops for e in loop["edges"]]
            try:
                bmesh.ops.bridge_loops(bm, edges=edges, use_disks=False)
            except Exception:
                pass
    boundary = [e for e in bm.edges if e.is_boundary]
    filled = False
    if boundary:
        try:
            bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
            filled = True
        except Exception:
            pass
        left = [e for e in bm.edges if e.is_boundary]
        if left:
            try:
                bmesh.ops.triangle_fill(bm, use_beauty=True, edges=left)
                filled = True
            except Exception:
                pass
    if filled:
        try:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=relax)
        except Exception:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    try:
        if bm.calc_volume(signed=True) < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
    except Exception:
        pass
    bm.to_mesh(obj.data)
    bm.free()
    if filled:
        # validate() co the thay doi topology nen chi dung khi thuc su lap lo
        obj.data.validate()
    obj.data.update()
    return obj


def closed_copy(obj, name, coll):
    """Ban sao da lap kin (manifold) - dung lam operand cho boolean."""
    return fill_holes(world_copy(obj, name, coll))


def _solidify(obj, thickness, offset):
    mod = obj.modifiers.new("RMVB_solidify", 'SOLIDIFY')
    mod.thickness = thickness
    mod.offset = offset
    for prop, value in (("use_even_offset", False), ("use_rim", False),
                        ("material_offset", 0), ("material_offset_rim", 0)):
        if hasattr(mod, prop):
            try:
                setattr(mod, prop, value)
            except Exception:
                pass
    bpy.context.view_layer.update()
    apply_modifiers_in_place(obj)
    for mod in list(obj.modifiers):
        obj.modifiers.remove(mod)
    return obj


def dilate_solid(source, distance, name, coll):
    """Solid mo rong cua source them `distance` mm ra ben ngoai theo normal.

    Shell solidify(offset=0, thickness=2d) duoc union voi ban da kin -> thanh
    solid moi, tranh truong hop 2 mat trung nhau gay treo boolean solver.
    """
    base = closed_copy(source, name, coll)
    if distance > 1e-6:
        shell = world_copy(source, name + ".shell", coll)
        _solidify(shell, distance * 2.0, 0.0)
        boolean_objects(base, [shell], 'UNION', solvers=solvers_for(source))
        remove_object(shell)
    return base


def triangulate_object(obj):
    """Tam giac hoa mesh cua obj (BEAUTY / EAR_CLIP). Boolean (Manifold) gop tam giac cung 1 polygon
    goc thanh n-gon co ca mat xuyen thung; n-gon do bi tam giac hoa sai khi xuat STL (canh > 2 mat).
    Vi vay dua tam giac vao Boolean de dau ra cung toan tam giac."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='EAR_CLIP')
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def remesh_object(obj, voxel):
    """Apply Remesh (Voxel) len obj: be mat luoi deu, tu go cac nep gap / giao cat."""
    mod = obj.modifiers.new(MOD_PREFIX + "Remesh", 'REMESH')
    mod.mode = 'VOXEL'
    mod.voxel_size = voxel
    mod.adaptivity = 0.0
    mod.use_smooth_shade = False
    bpy.context.view_layer.update()
    apply_modifiers_in_place(obj)
    for leftover in list(obj.modifiers):
        obj.modifiers.remove(leftover)
    return obj


def sleeve_shell(source, inner_gap, wall, name, coll, voxel=0.0):
    """Vo Sleeve: mat trong cach bar `inner_gap`, day `wall` mm.

    voxel > 0 (source da duoc Remesh): moi lan noi (inner_gap va inner_gap + wall) duoc Remesh
    lai de go cac nep gap cua Solidify tai goc lom, roi Vo = khoi ngoai - khoi trong (hai khoi
    sach nen vo khong con giao cat). voxel = 0: cach cu (noi bang Solidify theo phap tuyen).
    """
    if voxel <= 0.0:
        inner = dilate_solid(source, inner_gap, name + ".inner", coll)
        return _solidify(inner, wall, 1.0)
    outer = remesh_object(dilate_solid(source, inner_gap + wall, name + ".outer", coll), voxel)
    inner = remesh_object(dilate_solid(source, inner_gap, name + ".inner", coll), voxel)
    boolean_objects(outer, [inner], 'DIFFERENCE')
    remove_object(inner)
    return outer


# ---------------------------------------------------------------------------
# Sleeve Design
# ---------------------------------------------------------------------------
def sleeve_bar_part_names(props):
    """Ten Part Bar cua cac Attachment co tick 'Attachment on Bar khi tao Sleeve' (Dental-Lib)."""
    return {g.part_bar.name for g in props.groups if g.bar_in_sleeve and valid_obj(g.part_bar)}


def is_sleeve_source_modifier(mod, bar_parts=()):
    """Modifier dung de dung be mat Bar cho Sleeve: Union cac Bar Pillar, Difference
    PlaneCubeCut, va Union/Difference Part Bar cua Attachment co tick 'Attachment on Bar khi tao
    Sleeve' (`bar_parts` = ten cac Part Bar do). KHONG gom Difference Gingiva (Sleeve duoc cat nuou
    SAU CUNG, tren be mat sach, chu khong dung nguon da bi duong cat nuou lom chom cua scan lam
    hong), Difference Base va Attachment khong tick."""
    if not mod.name.startswith(MOD_PREFIX):
        return True                        # modifier do nguoi dung tu them: giu nguyen
    short = mod.name[len(MOD_PREFIX):]
    if short == "CutPlane" or short.startswith("Union"):
        return True
    return (short.startswith("Att_") and mod.type == 'BOOLEAN'
            and mod.object is not None and mod.object.name in bar_parts)


def bar_source(context, coll, voxel=None):
    """Ban sao (toa do world) cua Bar Segment sau khi Boolean voi Bar Pillar, CHUA cat nuou va
    CHUA ap Base - be mat dung de tao Sleeve. Attachment chi duoc ap khi co tick 'Attachment on Bar
    khi tao Sleeve' (Dental-Lib), con lai bi bo qua.

    Danh gia tren 1 ban sao tam cua Bar Segment (chi giu Union Pillar + CutPlane + Attachment co
    tick) cong them 1 lop
    Remesh (Voxel) dung RIENG cho Sleeve, nen Bar Segment that khong bi dong cham. Neu Bar Design
    da Apply thi dung BarSegmentBackup (con nguyen modifier) vi Bar Segment da nuong luon phan cat.
    voxel None = lay props.sleeve_voxel; 0 = khong Remesh."""
    props = context.scene.rmvb
    seg = props.bar_segment
    if not valid_obj(seg):
        return None
    if voxel is None:
        voxel = props.sleeve_voxel
    origin = props.bar_backup if valid_obj(props.bar_backup) else seg
    temp = origin.copy()
    temp.name = "BarSegment.sleeve_tmp"
    bar_parts = sleeve_bar_part_names(props)
    for mod in list(temp.modifiers):
        if not is_sleeve_source_modifier(mod, bar_parts):
            temp.modifiers.remove(mod)
        elif mod.name.startswith(MOD_PREFIX):
            mod.show_viewport = True        # Preview tat modifier cat / Attachment: Sleeve van phai theo day du
            mod.show_render = True
    if voxel > 0.0:
        remesh = temp.modifiers.new(MOD_PREFIX + "SleeveRemesh", 'REMESH')
        remesh.mode = 'VOXEL'
        remesh.voxel_size = voxel
        remesh.adaptivity = 0.0
        remesh.use_smooth_shade = False
    context.scene.collection.objects.link(temp)
    temp.matrix_world = origin.matrix_world.copy()
    try:
        return evaluated_mesh_object(temp, "BarSegment.src", coll)
    finally:
        bpy.data.objects.remove(temp, do_unlink=True)


class RMVB_OT_create_sleeve_design(Operator):
    """Tao Sleeve: vo mong bao quanh be mat Bar Segment (da Boolean voi Bar Pillar, chua ap
    Base; chi ap Attachment co tick 'Attachment on Bar khi tao Sleeve') voi offset + chieu day
    da chon, cat phan tiep xuc voi nuou"""
    bl_idname = "rmvb.create_sleeve_design"
    bl_label = "Create Sleeve Design"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        if not valid_obj(props.bar_segment):
            self.report({'ERROR'}, "Chua co Bar Segment (hay tao Bar Segment truoc)")
            return {'CANCELLED'}

        coll = ensure_collection(COL_SLEEVE)
        work = ensure_collection("Rmvb Temp", coll)
        if valid_obj(props.sleeve_object):
            remove_object(props.sleeve_object)

        inner_gap = max(props.sleeve_offset, 0.0)
        wall = max(props.sleeve_thickness, 0.01)
        cut_gingiva = False
        voxel = max(props.sleeve_voxel, 0.0)
        try:
            source = bar_source(context, work, voxel)
            if voxel > 0.0 and len(source.data.polygons) == 0:
                # Remesh khong ra be mat (nguon khong kin?) -> quay ve cach cu
                remove_object(source)
                voxel = 0.0
                source = bar_source(context, work, 0.0)
                self.report({'WARNING'}, "Remesh khong dung duoc be mat bar - tao Sleeve bang cach cu")
            sleeve = sleeve_shell(source, inner_gap, wall, "Sleeve", work, voxel)
            remove_object(source)
            sleeve.name = OBJ_SLEEVE
            sleeve.data.name = OBJ_SLEEVE
            for user in list(sleeve.users_collection):
                if user != coll:
                    user.objects.unlink(sleeve)
            if sleeve.name not in coll.objects:
                coll.objects.link(sleeve)

            # Add/Remove on Sleeve (Dental-Lib): Add = Union, Remove = Difference
            if props.apply_attachment_sleeve:
                for group in props.groups:
                    if not valid_obj(group.part_sleeve):
                        continue
                    copy = world_copy(group.part_sleeve, group.name + ".sleeve", work)
                    boolean_objects(sleeve, [copy],
                                    'UNION' if group.on_sleeve else 'DIFFERENCE')
                    remove_object(copy)

            # Cat phan tiep xuc voi nuou bang KHOI CAT RIENG CUA SLEEVE (GingivaCut.Sleeve +
            # Offset Gingiva Sleeve) - khong dung GingivaCut cua Bar nen Bar khong bi anh huong
            gingiva = ensure_gingiva_cutter(props, sleeve=True)
            if valid_obj(gingiva) and gingiva.type == 'MESH':
                # Ca Sleeve va Nuou deu duoc tam giac hoa truoc khi cat de STL xuat ra kin (khong n-gon thung)
                triangulate_object(sleeve)
                gingiva_tri = triangulate_object(world_copy(gingiva, "Gingiva.tri", work))
                boolean_objects(sleeve, [gingiva_tri], 'DIFFERENCE')
                remove_object(gingiva_tri)
                cut_gingiva = True
        except Exception as exc:
            purge_collection(work)
            self.report({'ERROR'}, "Loi tao Sleeve: %s" % exc)
            return {'CANCELLED'}

        purge_collection(work)
        try:
            bpy.data.collections.remove(work)
        except Exception:
            pass

        set_single_material(sleeve, SLEEVE_COLOR)
        sleeve["rmvb_role"] = "SLEEVE"
        if voxel > 0.0:
            sleeve.data.polygons.foreach_set("use_smooth", [True] * len(sleeve.data.polygons))
            sleeve.data.update()
        props.sleeve_object = sleeve
        activate(context, sleeve)
        purge_unused_meshes()
        bar_att = len(sleeve_bar_part_names(props))
        self.report({'INFO'}, "Da tao Sleeve tu be mat Bar sau Union Pillar (chua cat nuou, chua ap Base, "
                    "%s%s) roi cat nuou bang '%s' (Offset Gingiva Sleeve %g mm; gap bar %g mm, day %g mm%s)"
                    % ("ap %d Attachment tren Bar" % bar_att if bar_att else "chua ap Attachment tren Bar",
                       ", Remesh %g mm" % voxel if voxel > 0.0 else "", OBJ_GINGIVA_CUT_SLEEVE,
                       props.gingiva_offset_sleeve or 0.0, inner_gap, wall,
                       ", da cat Gingiva" if cut_gingiva else ""))
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Save Design
# ---------------------------------------------------------------------------
class RMVB_OT_apply_bar_design(Operator):
    """Backup Bar Segment (BarSegmentBackup, giu nguyen modifier) roi Apply toan bo
    modifier tren Bar Segment goc"""
    bl_idname = "rmvb.apply_bar_design"
    bl_label = "Apply Bar Design"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        seg = props.bar_segment
        if not valid_obj(seg):
            self.report({'ERROR'}, "Chua co Bar Segment")
            return {'CANCELLED'}
        if seg.get("rmvb_applied"):
            self.report({'WARNING'}, "Bar Design da Apply - bam Delete Bar Design de sua tiep")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        with forced_cut_modifiers(seg):          # phan cat Top Bar luon duoc nuong du Preview dang tat
            context.view_layer.update()
            depsgraph = context.evaluated_depsgraph_get()
            baked = _mesh_from_evaluated(seg.evaluated_get(depsgraph))
        if len(baked.polygons) == 0:
            bpy.data.meshes.remove(baked)
            self.report({'ERROR'}, "Ket qua modifier rong - kiem tra lai cac Boolean")
            return {'CANCELLED'}

        skipped = sum(1 for m in seg.modifiers
                      if m.name.startswith(PREVIEW_PREFIXES) and not m.show_viewport)

        backup = seg.copy()
        backup.data = seg.data.copy()
        backup.name = OBJ_BACKUP
        backup.data.name = OBJ_BACKUP
        for user in seg.users_collection:
            user.objects.link(backup)
        backup["rmvb_role"] = "SEGMENT_BACKUP"
        backup.hide_set(True)

        old = seg.data
        baked.name = old.name
        seg.data = baked
        if old.users == 0:
            bpy.data.meshes.remove(old)
        for mod in list(seg.modifiers):
            seg.modifiers.remove(mod)
        seg["rmvb_applied"] = True
        props.bar_backup = backup
        activate(context, seg)
        purge_unused_meshes()
        if skipped:
            self.report({'WARNING'}, "Preview dang tat: %d modifier Attachment tat trong Viewport nen "
                        "Part Bar CHUA duoc dua vao Bar (Delete Bar Design, bam Enable Preview roi Apply "
                        "lai neu can)" % skipped)
        self.report({'INFO'}, "Da Apply Bar Design (%d mat). Ban sua duoc luu o '%s' (an)"
                    % (len(baked.polygons), backup.name))
        return {'FINISHED'}


class RMVB_OT_delete_bar_design(Operator):
    """Xoa Bar Segment da Apply, dua BarSegmentBackup tro lai thanh ban chinh sua"""
    bl_idname = "rmvb.delete_bar_design"
    bl_label = "Delete Bar Design"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        props = context.scene.rmvb
        backup = props.bar_backup
        seg = props.bar_segment
        if not valid_obj(backup):
            self.report({'ERROR'}, "Khong co BarSegmentBackup - Bar Design chua duoc Apply")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if valid_obj(seg) and seg != backup:
            remove_object(seg)
        backup.name = OBJ_SEGMENT
        backup.data.name = OBJ_SEGMENT
        backup.hide_set(False)
        backup["rmvb_role"] = "SEGMENT"
        props.bar_segment = backup
        props.bar_backup = None
        rebuild_segment_modifiers(context)
        activate(context, backup)
        purge_unused_meshes()
        self.report({'INFO'}, "Da xoa Bar Design da Apply - dang chinh sua '%s'"
                    % backup.name)
        return {'FINISHED'}


def write_construction_info(stl_path, source_ci):
    """Chep constructionInfo goc va thay <Filename> dau bang ten STL moi (dung
    cach add-on iBar dang lam). Tra ve duong dan file ghi duoc."""
    src = bpy.path.abspath(source_ci) if source_ci else ""
    if not src or not os.path.exists(src):
        folder = os.path.dirname(stl_path)
        src = ""
        try:
            for name in sorted(os.listdir(folder)):
                if name.endswith('.constructionInfo'):
                    src = os.path.join(folder, name)
                    break
        except OSError:
            pass
    if not src or not os.path.exists(src):
        return ""
    try:
        with open(src, 'r', encoding='utf-8') as handle:
            content = handle.read()
    except OSError:
        return ""
    replacement = "<Filename>%s</Filename>" % os.path.basename(stl_path)
    updated, count = re.subn(r'<Filename>[^<]*</Filename>',
                             lambda _m: replacement, content, count=1)
    if not count:
        return ""
    ci_path = os.path.splitext(stl_path)[0] + ".constructionInfo"
    try:
        with open(ci_path, 'w', encoding='utf-8') as handle:
            handle.write(updated)
    except OSError:
        return ""
    return ci_path


class RMVB_OT_save_design(Operator):
    """Xuat STL cho Bar Design va Sleeve Design (+ constructionInfo). Khong xuat kem Attachment /
    Visual Object: file chi gom dung Bar Segment hoac Sleeve"""
    bl_idname = "rmvb.save_design"
    bl_label = "Save Bar & Sleeve Design"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        with forced_cut_modifiers(context.scene.rmvb.bar_segment):      # Bar xuat ra luon co du phan cat Top Bar
            return self._save(context)

    def _save(self, context):
        props = context.scene.rmvb
        items = []
        if valid_obj(props.bar_segment):
            items.append(("Rmvb_Bar", props.bar_segment))
        if valid_obj(props.sleeve_object):
            items.append(("Rmvb_Sleeve", props.sleeve_object))
        if not items:
            self.report({'ERROR'}, "Chua co Bar Segment hoac Sleeve de luu")
            return {'CANCELLED'}
        folder = bpy.path.abspath(props.save_dir) if props.save_dir else ""
        if not folder or not os.path.isdir(folder):
            self.report({'ERROR'}, "Chon thu muc luu (file .blend chua duoc luu)")
            return {'CANCELLED'}

        # Da transform theo before/transform.txt luc Place Connection -> xuat ve toa do file
        # (before x transform^-1), giong nut 'STLs ORG' cua add-on iBar
        back = org_matrix_from_props(props).inverted() if props.org_active else None
        stamp = timestamp()
        saved = []
        for prefix, obj in items:
            filepath = os.path.join(folder, "%s_%s.stl" % (prefix, stamp))
            targets = [obj]
            temps = []
            try:
                if back is not None:
                    for source in targets:
                        copy = evaluated_mesh_object(source, source.name + ".org")
                        copy.matrix_world = back @ source.matrix_world
                        temps.append(copy)
                    targets = temps
                export_stl(targets, filepath, context)
            except Exception as exc:
                self.report({'ERROR'}, "Khong xuat duoc %s: %s" % (prefix, exc))
                return {'CANCELLED'}
            finally:
                for temp in temps:
                    remove_object(temp)
            saved.append(filepath)
            ci_path = write_construction_info(filepath, props.construction_file)
            if ci_path:
                saved.append(ci_path)
            else:
                self.report({'WARNING'}, "Khong tim thay constructionInfo de cap nhat")
        self.report({'INFO'}, "Da luu%s: %s" % (
            " (toa do file goc)" if back is not None else "",
            ", ".join(os.path.basename(p) for p in saved)))
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
_ICON_NAMES = None


def _ic(name):
    """Ten icon hop le cho UILayout (icon sai lam Blender huy ca ham draw())."""
    global _ICON_NAMES
    if _ICON_NAMES is None:
        names = set()
        try:
            for func in bpy.types.UILayout.bl_rna.functions.values():
                for pname, prop in func.parameters.items():
                    if pname == "icon" and hasattr(prop, "enum_items"):
                        names.update(i.identifier for i in prop.enum_items)
        except Exception:
            pass
        _ICON_NAMES = names
    if not name:
        return 'NONE'
    return name if (not _ICON_NAMES or name in _ICON_NAMES) else 'NONE'


class RMVB_PT_panel(Panel):
    bl_label = "Rmvb-Bar"
    bl_idname = "VIEW3D_PT_rmvb_bar"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Rmvb-Bar"

    def draw(self, context):
        layout = self.layout
        props = context.scene.rmvb
        if dlib() is None:
            layout.label(text="Chua bat add-on Dental-Lib", icon=_ic('ERROR'))

        # ---- Set -----------------------------------------------------------
        box = layout.box()
        box.label(text="1. Set (chọn object rồi bấm Set)", icon=_ic('RESTRICT_SELECT_OFF'))
        for role, label, field in (
                ('GINGIVA', "Set Gingiva", "gingiva_object"),
                ('DENTURE', "Set Denture", "denture_object"),
                ('ANTAGONIST', "Set Antagonist", "antagonist_object")):
            row = box.row(align=True)
            row.operator(RMVB_OT_set_role.bl_idname, text=label,
                         icon=_ic('MESH_UVSPHERE')).role = role
            sub = row.row(align=True)
            sub.enabled = False
            sub.prop(props, field, text="")

        # ---- Connection ----------------------------------------------------
        box = layout.box()
        box.label(text="2. Connection Base", icon=_ic('MESH_CYLINDER'))
        box.label(text="Select Connection Base")
        box.menu("RMVB_MT_pick_connection",
                 text=current_connection_name(props) or "(Trống)",
                 icon=_ic('MESH_CYLINDER'))
        box.prop(props, "use_org_txt")
        row = box.row(align=True)
        row.operator(RMVB_OT_place_connection.bl_idname,
                     text="Place Connection (constructionInfo)",
                     icon=_ic('EMPTY_SINGLE_ARROW'))
        row.operator(RMVB_OT_clear_connection.bl_idname, text="", icon=_ic('TRASH'))
        if props.construction_file:
            box.label(text=os.path.basename(bpy.path.abspath(props.construction_file)),
                      icon=_ic('FILE'))
        box.label(text="Đã đặt: %d implant" % len(props.placed), icon=_ic('CHECKMARK'))
        if props.placed:
            sub = box.box()
            sub.label(text="Connection Base từng implant (bấm để đổi):", icon=_ic('MESH_CYLINDER'))
            col = sub.column(align=True)
            for index, item in enumerate(props.placed):
                split = col.split(factor=0.3, align=True)
                split.label(text="Răng %s" % item.tooth)
                op = split.operator(RMVB_OT_choose_implant_connection.bl_idname,
                                    text=item.lib_name or "(?)", icon=_ic('DOWNARROW_HLT'))
                op.index = index
            if props.org_active:
                box.label(text="Tọa độ: transform theo before/transform.txt", icon=_ic('ORIENTATION_GLOBAL'))
            else:
                box.label(text="Tọa độ: theo file constructionInfo (không dùng txt)",
                          icon=_ic('ORIENTATION_GLOBAL'))

        # ---- Bar Pillar ----------------------------------------------------
        box = layout.box()
        box.label(text="3. Bar Design - Bar Pillar", icon=_ic('MESH_CONE'))
        box.prop(props, "pillar_lift")
        col = box.column(align=True)
        col.operator(RMVB_OT_create_bar_pillar.bl_idname,
                     text="Create/Reset bar pillar", icon=_ic('MOD_SCREW'))
        row = col.row(align=True)
        row.operator(RMVB_OT_select_pillar_top.bl_idname,
                     text="Sửa đỉnh trụ bar", icon=_ic('VERTEXSEL'))
        row.operator(RMVB_OT_exit_edit.bl_idname, text="Thoát chỉnh sửa trụ",
                     icon=_ic('OBJECT_DATA'))
        box.label(text="Bar Pillar: %d" % len(props.pillars), icon=_ic('INFO'))

        # ---- Bar Segment + Top Bar ----------------------------------------
        box = layout.box()
        box.label(text="4. Bar Design - Bar Segment & Top Bar", icon=_ic('CURVE_PATH'))
        plane_ok = valid_obj(props.top_plane)
        box.operator(RMVB_OT_create_top_bar_plane.bl_idname,
                     text="Create Top Bar Plane" if not plane_ok else "Create Top Bar Plane (đã có)",
                     icon=_ic('MESH_PLANE'))
        if valid_obj(arrow_object(props)):
            box.label(text="Mũi tên hướng lắp: xoay '%s' để đổi hướng" % OBJ_ARROW,
                      icon=_ic('EMPTY_SINGLE_ARROW'))
        col = box.column(align=True)
        col.enabled = plane_ok
        col.operator(RMVB_OT_create_bar_line.bl_idname,
                     text="Draw Line Bar (snap Plane)", icon=_ic('GREASEPENCIL'))
        row = col.row(align=True)
        row.operator(RMVB_OT_edit_bar_line.bl_idname, text="Edit Line Bar",
                     icon=_ic('EDITMODE_HLT'))
        row.operator(RMVB_OT_exit_edit.bl_idname, text="Exit Edit",
                     icon=_ic('OBJECT_DATA'))
        col.prop(props, "bar_width")
        col.prop(props, "bar_height")
        col.operator(RMVB_OT_update_bar_segment.bl_idname, text="Cập nhật Bar Segment",
                     icon=_ic('FILE_REFRESH'))
        if plane_ok:
            box.label(text="Sửa line / dời-xoay Plane / mũi tên: Bar Segment tự cập nhật",
                      icon=_ic('INFO'))
        box.label(text="Preview cắt Top Bar (Gingiva, Pillar, Plane, Base):", icon=_ic('MOD_BOOLEAN'))
        seg = props.bar_segment
        cut_on = (valid_obj(seg) and cut_preview_enabled(seg)
                  and any(is_cut_modifier(m) and m.show_viewport for m in seg.modifiers))
        row = box.row(align=True)
        row.operator(RMVB_OT_enable_cut_preview.bl_idname, text="Enable Preview",
                     icon=_ic('HIDE_OFF'), depress=cut_on)
        row.operator(RMVB_OT_disable_cut_preview.bl_idname, text="Disable Preview",
                     icon=_ic('HIDE_ON'))
        box.prop(props, "gingiva_offset")
        if abs(props.gingiva_offset) >= GINGIVA_OFFSET_EPS:
            box.label(text="Cắt Bar bằng '%s': %s %g mm so với mặt nướu (Sleeve có offset riêng ở mục 6)"
                      % (OBJ_GINGIVA_CUT, "hở" if props.gingiva_offset > 0 else "ăn sâu",
                         abs(props.gingiva_offset)), icon=_ic('INFO'))

        # ---- Attachment ----------------------------------------------------
        box = layout.box()
        box.label(text="5. Attachment", icon=_ic('MESH_CUBE'))
        box.label(text="Select Attachment")
        box.menu("RMVB_MT_pick_attachment",
                 text=current_attachment_name(props) or "(Trống)",
                 icon=_ic('MESH_CUBE'))
        box.operator(RMVB_OT_add_attachment.bl_idname,
                     text="Add selected Attachment", icon=_ic('ADD'))
        if len(props.groups):
            box.template_list("RMVB_UL_attachment_groups", "", props, "groups",
                              props, "group_index", rows=3)
            if 0 <= props.group_index < len(props.groups):
                group = props.groups[props.group_index]
                box.prop(group, "name", text="Tên Attachment")
                box.prop(group, "bar_in_sleeve")
                box.prop(group, "center_bar")
                row = box.row(align=True)
                row.prop(group, "align_x_bar")
                sub = row.row(align=True)
                sub.enabled = group.align_x_bar
                sub.prop(group, "align_x_flip", toggle=True, icon=_ic('LOOP_BACK'))
                if (group.center_bar or group.align_x_bar) and not valid_obj(props.bar_center):
                    box.label(text="Chưa có Line Bar (≥ 2 điểm): vẽ line để căn giữa / canh trục X",
                              icon=_ic('INFO'))
                box.prop(group, "lock_topbar")
                box.prop(group, "lock_rot_topbar")
                box.prop(group, "lock_attachment")
                if group.lock_attachment:
                    box.prop_search(group, "lock_target", props, "groups",
                                    text="Attachment")
            row = box.row(align=True)
            row.operator(RMVB_OT_remove_attachment_group.bl_idname,
                         text="Xóa group", icon=_ic('X'))
            row.operator(RMVB_OT_clear_attachments.bl_idname,
                         text="Xóa tất cả", icon=_ic('TRASH'))
        seg = props.bar_segment
        previewing = (valid_obj(seg) and preview_enabled(seg)
                      and any(m.name.startswith(PREVIEW_PREFIXES) for m in seg.modifiers))
        row = box.row(align=True)
        row.operator(RMVB_OT_enable_attachment_preview.bl_idname, text="Enable Preview",
                     icon=_ic('HIDE_OFF'), depress=previewing)
        row.operator(RMVB_OT_disable_attachment_preview.bl_idname, text="Disable Preview",
                     icon=_ic('HIDE_ON'))

        # ---- Sleeve Design -------------------------------------------------
        box = layout.box()
        box.label(text="6. Sleeve Design", icon=_ic('MOD_SOLIDIFY'))
        box.prop(props, "sleeve_offset")
        box.prop(props, "sleeve_thickness")
        box.prop(props, "sleeve_voxel")
        box.prop(props, "apply_attachment_sleeve")
        col = box.column(align=True)
        col.prop(props, "gingiva_offset_sleeve")
        if abs(props.gingiva_offset_sleeve) >= GINGIVA_OFFSET_EPS:
            col.label(text="Cắt Sleeve bằng '%s': %s %g mm so với mặt nướu (không đổi Bar)"
                      % (OBJ_GINGIVA_CUT_SLEEVE,
                         "hở" if props.gingiva_offset_sleeve > 0 else "ăn sâu",
                         abs(props.gingiva_offset_sleeve)), icon=_ic('INFO'))
        elif not valid_obj(props.gingiva_cutter_sleeve):
            col.label(text="Khối cắt riêng '%s' sẽ được tạo khi bấm Create Sleeve Design"
                      % OBJ_GINGIVA_CUT_SLEEVE, icon=_ic('INFO'))
        box.operator(RMVB_OT_create_sleeve_design.bl_idname,
                     text="Create Sleeve Design", icon=_ic('MOD_SOLIDIFY'))

        # ---- Save Design ---------------------------------------------------
        box = layout.box()
        box.label(text="7. Save Design", icon=_ic('EXPORT'))
        col = box.column(align=True)
        col.operator(RMVB_OT_apply_bar_design.bl_idname, text="Apply Bar Design",
                     icon=_ic('CHECKMARK'))
        col.operator(RMVB_OT_delete_bar_design.bl_idname, text="Delete Bar Design",
                     icon=_ic('TRASH'))
        box.prop(props, "save_dir")
        box.operator(RMVB_OT_save_design.bl_idname, text="Save Bar & Sleeve Design",
                     icon=_ic('EXPORT'))


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
_classes = (
    RMVB_OT_pick_library_item,
    RMVB_MT_pick_connection,
    RMVB_MT_pick_attachment,
    RMVB_PG_PlacedConnection,
    RMVB_PG_PartRef,
    RMVB_PG_AttachmentGroup,
    RMVB_PG_props,
    RMVB_OT_set_role,
    RMVB_OT_place_connection,
    RMVB_OT_choose_implant_connection,
    RMVB_OT_set_implant_connection,
    RMVB_OT_clear_connection,
    RMVB_OT_create_bar_pillar,
    RMVB_OT_select_pillar_top,
    RMVB_OT_exit_edit,
    RMVB_OT_create_top_bar_plane,
    RMVB_OT_create_bar_line,
    RMVB_OT_draw_bar_line,
    RMVB_OT_edit_bar_line,
    RMVB_OT_update_bar_segment,
    RMVB_OT_enable_cut_preview,
    RMVB_OT_disable_cut_preview,
    RMVB_OT_add_attachment,
    RMVB_OT_select_attachment_group,
    RMVB_OT_remove_attachment_group,
    RMVB_OT_clear_attachments,
    RMVB_OT_enable_attachment_preview,
    RMVB_OT_disable_attachment_preview,
    RMVB_UL_attachment_groups,
    RMVB_OT_create_sleeve_design,
    RMVB_OT_apply_bar_design,
    RMVB_OT_delete_bar_design,
    RMVB_OT_save_design,
    RMVB_PT_panel,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rmvb = PointerProperty(type=RMVB_PG_props)
    if rmvb_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(rmvb_load_post)
    if rmvb_depsgraph_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(rmvb_depsgraph_handler)


def unregister():
    if rmvb_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(rmvb_load_post)
    if rmvb_depsgraph_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(rmvb_depsgraph_handler)
    del bpy.types.Scene.rmvb
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
