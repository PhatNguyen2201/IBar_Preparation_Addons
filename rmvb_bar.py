bl_info = {
    "name": "Rmvb-Bar",
    "author": "Phat Nguyen",
    "version": (0, 3, 2),
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

    Set Gingiva / Denture / Antagonist (chon object san co trong scene)
      -> Select Connection Base + Place Connection (doc .constructionInfo)
      -> Bar Pillar -> Create Top Bar Plane -> Draw Line Bar (snap Plane) -> Bar Segment
         tu cap nhat -> Cut Top Bar (chi them modifier)
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
COL_BARDESIGN = "BarDesign"          # Bar Pillar + Bar Segment (+ line, mui ten)
COL_PILLAR = COL_BARDESIGN
COL_SEGMENT = COL_BARDESIGN
COL_CUTPLANE = "CutPlane"            # PlaneVisual + PlaneCubeCut
COL_ATTACHMENT = "Rmvb Attachment"
COL_SLEEVE = "Rmvb Sleeve"
COL_PREVIEW = "Rmvb Preview"

OBJ_SEGMENT = "BarSegment"
OBJ_BACKUP = "BarSegmentBackup"
OBJ_LINE = "Rmvb_BarLine"
OBJ_ARROW = "InsertionArrow"
OBJ_PLANE = "PlaneVisual"
OBJ_CUTTER = "PlaneCubeCut"
OBJ_SLEEVE = "Rmvb_Sleeve"

# Tien to ten modifier do add-on tao (rebuild xoa theo tien to nay)
MOD_PREFIX = "RMVB_"

# Ngung dung (mm) khi xac dinh cac dinh nam cung mot cao do dinh mui extrude.
TOP_EPS = 1e-4

CST_ON_PLANE = "RMVB_on_plane"
CST_ROT_PLANE = "RMVB_lock_rot_topbar"
CST_ROT_LIMIT = "RMVB_lock_rot_xy"
CST_COPY_LOC = "RMVB_lock_location"
CST_COPY_ROT = "RMVB_lock_rotation"

# Thong so chuan bi mesh (mm, truc local cua mesh)
GINGIVA_BASE_DEPTH = 10.0       # Gingiva: extrude day xuong 10 mm roi fill
CONN_BOTTOM_EXTRUDE = 2.0       # Base ho day: extrude 2 mm
CONN_BOTTOM_SCALE = 2.0         # ... roi scale local x2
CONN_TOP_EXTRUDE = 30.0         # Base ho dinh (Screw): extrude 30 mm
PLANE_SIZE = 100.0              # PlaneVisual / PlaneCubeCut: 100 x 100 mm
PLANE_CUBE_HEIGHT = 100.0       # PlaneCubeCut: extrude +z local 100 mm (hop lap phuong)

# Mau dung khi thu vien khong khai bao (trung voi mac dinh cua Dental-Lib)
FALLBACK_PART_BAR_COLOR = (1.0, 0.0, 0.0, 0.5)       # do, alpha 0.5
FALLBACK_PART_SLEEVE_COLOR = (1.0, 0.45, 0.72, 0.5)  # hong, alpha 0.5
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


def activate(context, obj, select=True):
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
    """Dat transform orientation = Local (dung khi Edit Bar Pillar/Segment).

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


class RMVB_MT_pick_connection(Menu):
    bl_label = "Select Connection Base"

    def draw(self, context):
        _draw_library_menu(self.layout, 'CONNECTION', get_connection_items(),
                           'MESH_CYLINDER')


class RMVB_MT_pick_attachment(Menu):
    bl_label = "Select Attachment"

    def draw(self, context):
        _draw_library_menu(self.layout, 'ATTACHMENT', get_attachment_items(),
                           'MESH_CUBE')


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


class RMVB_PG_PlacedConnection(PropertyGroup):
    tooth: StringProperty(name="Tooth", default="?")
    lib_name: StringProperty(name="Library", default="")
    base_object: PointerProperty(name="Base", type=bpy.types.Object)
    analog_object: PointerProperty(name="Analog", type=bpy.types.Object)
    screw_object: PointerProperty(name="Screw", type=bpy.types.Object)
    scanbody_object: PointerProperty(name="Scanbody", type=bpy.types.Object)


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
    on_sleeve: BoolProperty(
        name="Add/Remove on Sleeve", default=False,
        description="Lay tu Dental-Lib: True = Union len Sleeve, False = Difference")
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

    # Connection Base + constructionInfo
    connection_index: IntProperty(name="Connection Index", default=0, min=0)
    connection_name: StringProperty(name="Connection Name", default="")
    construction_file: StringProperty(name="constructionInfo",
                                      subtype='FILE_PATH', default="")
    placed: CollectionProperty(type=RMVB_PG_PlacedConnection)
    place_parts: BoolProperty(
        name="Đặt kèm Analog / Screw / Scanbody",
        description="Tao them cac mesh con lai cua Connection (an) tai cung "
                    "vi tri implant",
        default=False)

    # Bar Pillar
    pillars: CollectionProperty(type=RMVB_PG_PartRef)
    pillar_lift: FloatProperty(
        name="Extrude lên (mm)",
        description="Extrude vung ho ket noi (day Base) thang len theo local Z "
                    "(mac dinh 7 li)",
        default=7.0, min=0.1, unit='LENGTH')

    # Bar Segment + Top Bar
    bar_line: PointerProperty(name="Bar Line", type=bpy.types.Object)
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


def prepare_gingiva(obj, depth=GINGIVA_BASE_DEPTH):
    """Bien mesh Gingiva thanh KHOI kin:

    1. Cac vung ho nho (mat tren): fill de khong bi lung.
    2. Vong ho lon nhat (mat duoi): extrude `depth` mm theo local Z ra phia mo,
       roi fill de tao de -> toan bo Gingiva thanh khoi.
    """
    info = {"loops": 0, "filled": 0, "extruded": False, "closed": False,
            "direction": 0}
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    loops = boundary_loops(bm)
    info["loops"] = len(loops)
    if loops:
        base = max(loops, key=loop_perimeter)
        for loop in loops:
            if loop is base:
                continue
            if cap_loop(bm, loop):
                info["filled"] += 1
        rim_verts = unique_loop_verts(base)
        rim_center = sum((v.co for v in rim_verts), Vector()) / max(1, len(rim_verts))
        body = sum((v.co for v in bm.verts), Vector()) / max(1, len(bm.verts))
        # Than mesh nam phia tren vanh -> mat mo quay xuong -> extrude -Z local
        sign = -1.0 if body.z >= rim_center.z else 1.0
        scale_z = (obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).length or 1.0
        new_verts = _extrude_loop(bm, base)
        for vert in new_verts:
            vert.co.z += sign * depth / scale_z
        for loop in _loops_within(bm, new_verts):
            cap_loop(bm, loop)
        info["extruded"] = True
        info["direction"] = int(sign)
        outward_solid(bm)
        bm.to_mesh(obj.data)
        obj.data.update()
    info["closed"] = not any(e.is_boundary for e in bm.edges)
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
    """Gan object mesh dang chon vao vai tro Gingiva / Denture / Antagonist
    (doi mau hien thi; Gingiva con duoc chuan bi thanh khoi kin)"""
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
            if obj.get("rmvb_gingiva_ready"):
                message = " (da la khoi kin tu truoc)"
            else:
                if obj.data.users > 1:
                    obj.data = obj.data.copy()      # khong sua mesh dung chung
                try:
                    info = prepare_gingiva(obj)
                except Exception as exc:
                    self.report({'ERROR'}, "Khong chuan bi duoc Gingiva: %s" % exc)
                    return {'CANCELLED'}
                obj["rmvb_gingiva_ready"] = True
                message = " (fill %d lo mat tren, extrude de %s%g mm, %s)" % (
                    info["filled"], "-" if info["direction"] < 0 else "+",
                    GINGIVA_BASE_DEPTH,
                    "khoi kin" if info["closed"] else "CHUA kin")
                if not info["closed"]:
                    self.report({'WARNING'},
                                "Gingiva van con ho - Boolean co the khong on dinh")
        obj.name = ROLE_OBJECT_NAME[self.role]
        obj["rmvb_role"] = self.role
        set_display_color(obj, ROLE_COLOR[self.role])
        setattr(props, ROLE_PROPERTY[self.role], obj)
        activate(context, obj)
        self.report({'INFO'}, "Set %s: %s%s" % (self.role.title(), obj.name, message))
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Place Connection - doc .constructionInfo va dat theo toa do XML
# ---------------------------------------------------------------------------
def clear_placed_connections(context, remove_pillars=False):
    props = context.scene.rmvb
    for item in list(props.placed):
        for field in ("base_object", "analog_object", "screw_object",
                      "scanbody_object"):
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

    1. Base ho day (Connection): extrude -2 mm theo local Z, scale local x2.
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

        new_bottom = _extrude_loop(bm, bottom)
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
            base_mesh, base_info = prepare_connection_mesh(mesh_from_file(base_path))
        except Exception as exc:
            self.report({'ERROR'}, "Loi doc mesh Base: %s" % exc)
            return {'CANCELLED'}

        part_meshes = {}
        if props.place_parts:
            for slot in ("analog", "screw", "scanbody"):
                asset = lib_connection_asset(lib_name, slot)
                if asset and os.path.exists(asset):
                    try:
                        part_meshes[slot] = mesh_from_file(asset)
                    except Exception as exc:
                        self.report({'WARNING'}, "%s: %s" % (slot, exc))

        clear_placed_connections(context, remove_pillars=True)
        coll = ensure_collection(COL_CONNECTION)
        for implant in implants:
            tooth = str(implant["tooth"])
            matrix = implant["matrix"]
            obj = object_from_mesh("Conn_%s_Base" % tooth, base_mesh, coll, matrix)
            set_color(obj, (0.72, 0.74, 0.78, 1.0))
            item = props.placed.add()
            item.tooth = tooth
            item.lib_name = lib_name
            item.base_object = obj
            for slot, field in (("analog", "analog_object"),
                                ("screw", "screw_object"),
                                ("scanbody", "scanbody_object")):
                mesh = part_meshes.get(slot)
                if mesh is None:
                    continue
                part = object_from_mesh("Conn_%s_%s" % (tooth, slot.capitalize()),
                                        mesh, coll, matrix)
                part.hide_set(True)
                setattr(item, field, part)

        props.construction_file = path
        props.connection_name = lib_name
        rebuild_segment_modifiers(context)
        if base_info["loops"] != 2:
            self.report({'WARNING'}, "Base co %d vung ho (can 2: day + dinh)"
                        % base_info["loops"])
        self.report({'INFO'}, "Da dat %d Connection (%s) tu %s%s"
                    % (len(implants), lib_name, os.path.basename(path),
                       "" if base_info["closed"] else " (Base chua kin)"))
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


class RMVB_OT_create_bar_pillar(Operator):
    """Tao Bar Pillar: sao chep vung ho day (Connection) cua tung Base, extrude len
    theo local Z va fill kin"""
    bl_idname = "rmvb.create_bar_pillar"
    bl_label = "Create Bar Pillar"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        if not props.placed:
            self.report({'ERROR'}, "Chua dat Connection nao (bam Place Connection)")
            return {'CANCELLED'}
        coll = ensure_collection(COL_PILLAR)
        for ref in list(props.pillars):
            remove_object(ref.object)
        props.pillars.clear()

        made = 0
        notes = []
        for item in props.placed:
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
            obj = bpy.data.objects.new("BarPillar_%s" % item.tooth, mesh)
            coll.objects.link(obj)
            obj.matrix_world = base.matrix_world.copy()
            obj["rmvb_role"] = "PILLAR"
            obj["rmvb_tooth"] = item.tooth
            obj["rmvb_top_z"] = float(info["top_z"])
            set_color(obj, (0.85, 0.65, 0.25, 1.0))
            ref = props.pillars.add()
            ref.object = obj
            ref.tooth = item.tooth
            made += 1
            if not info["closed"]:
                notes.append("rang %s pillar chua kin" % item.tooth)
        if not made:
            self.report({'ERROR'}, "Khong tao duoc Bar Pillar nao")
            return {'CANCELLED'}
        rebuild_segment_modifiers(context)
        purge_unused_meshes()
        if notes:
            self.report({'WARNING'}, "; ".join(notes))
        self.report({'INFO'}, "Da tao %d Bar Pillar (extrude len %g mm, solid kin)"
                    % (made, props.pillar_lift))
        return {'FINISHED'}


class RMVB_OT_edit_bar_pillar(Operator):
    """Vao Edit Mode (transform orientation Local) de chinh Bar Pillar"""
    bl_idname = "rmvb.edit_bar_pillar"
    bl_label = "Edit Bar Pillar"

    def execute(self, context):
        pillars = _enter_pillar_edit(context)
        if not pillars:
            self.report({'ERROR'}, "Chua co Bar Pillar. Bam Create Bar Pillar truoc")
            return {'CANCELLED'}
        self.report({'INFO'}, "Edit Bar Pillar - Transform Orientation: Local")
        return {'FINISHED'}


def _enter_pillar_edit(context):
    props = context.scene.rmvb
    pillars = [r.object for r in props.pillars
               if r.object is not None and r.object.name in bpy.data.objects]
    if not pillars:
        return []
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in pillars:
        obj.hide_set(False)
        obj.select_set(True)
    context.view_layer.objects.active = pillars[0]
    bpy.ops.object.mode_set(mode='EDIT')
    use_local_orientation(context)
    return pillars


class RMVB_OT_select_pillar_top(Operator):
    """Vao Edit Mode va CHI chon phan dinh da extrude cua Bar Pillar"""
    bl_idname = "rmvb.select_pillar_top"
    bl_label = "Select Top"

    def execute(self, context):
        pillars = _enter_pillar_edit(context)
        if not pillars:
            self.report({'ERROR'}, "Chua co Bar Pillar. Bam Create Bar Pillar truoc")
            return {'CANCELLED'}
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
        self.report({'INFO'}, "Da chon %d dinh o dinh mui extrude cua %d Bar Pillar"
                    % (total, len(pillars)))
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
    if not valid_obj(arrow):
        arrow = bpy.data.objects.new(OBJ_ARROW, None)
        arrow.empty_display_type = 'SINGLE_ARROW'
        arrow.empty_display_size = 12.0
        arrow.show_in_front = True
        arrow.color = (0.1, 0.9, 0.2, 1.0)
        arrow.location = location
        arrow["rmvb_role"] = "ARROW"
        ensure_collection(COL_BARDESIGN).objects.link(arrow)
        props.bar_arrow = arrow
    return arrow


def arrow_direction(arrow, depsgraph=None):
    """Huong lap (world, don vi) = truc Z cua mui ten (Z+ neu chua co mui ten)."""
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
    direction = arrow_direction(props.bar_arrow, depsgraph)
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
    constraint kieu moi (chi khoa X/Y)."""
    for scene in bpy.data.scenes:
        props = getattr(scene, "rmvb", None)
        if props is None:
            continue
        for group in props.groups:
            if (group.lock_rot_topbar and valid_obj(group.empty)
                    and CST_ROT_LIMIT not in group.empty.constraints):
                try:
                    apply_group_locks(group, props)
                except Exception as exc:
                    print("[Rmvb-Bar] Khong nang cap duoc Lock Rotation: %s" % exc)


@persistent
def rmvb_depsgraph_handler(scene, depsgraph):
    """Line / PlaneVisual / mui ten duoc sua (ke ca trong Edit Mode) -> cap nhat Bar Segment."""
    if _SYNC["busy"]:
        return
    try:
        props = scene.rmvb
    except AttributeError:
        return
    line, plane = props.bar_line, props.top_plane
    if not (valid_obj(line) and valid_obj(plane)):
        return
    watched = {line.name, line.data.name, plane.name, plane.data.name}
    if valid_obj(props.bar_arrow):
        watched.add(props.bar_arrow.name)
    if not any(update.id.name in watched for update in depsgraph.updates):
        return
    try:
        sync_bar_segment(scene, depsgraph)
    except Exception as exc:
        message = str(exc)
        if message != _SYNC["error"]:
            _SYNC["error"] = message
            print("[Rmvb-Bar] Khong cap nhat duoc Bar Segment: %s" % message)


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
    """Mesh kin (moi canh dung 2 mat) - du dieu kien cho solver Manifold."""
    key = (mesh.name, len(mesh.vertices), len(mesh.polygons))
    cached = _MANIFOLD_CACHE.get(key)
    if cached is not None:
        return cached
    bm = bmesh.new()
    bm.from_mesh(mesh)
    ok = bool(bm.faces) and all(edge.is_manifold for edge in bm.edges)
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


def rebuild_segment_modifiers(context):
    """Dung lai toan bo modifier cua Bar Segment theo thu tu co dinh:

        Difference Gingiva
        -> [Cut Top Bar]   Union tung Bar Pillar -> Difference PlaneCubeCut
                           -> Difference tung Base
        -> [Apply Attachment on Bar]  Union / Difference tung Part Bar

    Chi them modifier; Segment da Apply thi bo qua.
    """
    props = context.scene.rmvb
    seg = props.bar_segment
    if not valid_obj(seg) or seg.get("rmvb_applied"):
        return 0
    for mod in list(seg.modifiers):
        if mod.name.startswith(MOD_PREFIX):
            seg.modifiers.remove(mod)
    gingiva = props.gingiva_object
    if valid_obj(gingiva):
        add_boolean_modifier(seg, gingiva, 'DIFFERENCE', MOD_PREFIX + "CutGingiva")
    if seg.get("rmvb_cut"):
        for ref in props.pillars:
            if valid_obj(ref.object):
                add_boolean_modifier(seg, ref.object, 'UNION',
                                     MOD_PREFIX + "Union_" + ref.tooth)
        if valid_obj(props.top_cutter):
            add_boolean_modifier(seg, props.top_cutter, 'DIFFERENCE',
                                 MOD_PREFIX + "CutPlane")
        for item in props.placed:
            if valid_obj(item.base_object):
                add_boolean_modifier(seg, item.base_object, 'DIFFERENCE',
                                     MOD_PREFIX + "CutBase_" + item.tooth)
    if seg.get("rmvb_attach"):
        for index, group in enumerate(props.groups):
            if valid_obj(group.part_bar):
                add_boolean_modifier(
                    seg, group.part_bar,
                    'UNION' if group.on_bar else 'DIFFERENCE',
                    "%sAtt_%d_%s" % (MOD_PREFIX, index, group.name[:30]))
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
    PlaneCubeCut (an) trong collection CutPlane + Mui ten huong lap. Sau do Draw Line Bar
    se ve tren PlaneVisual va Bar Segment tu cap nhat theo line, Plane, mui ten"""
    bl_idname = "rmvb.create_top_bar_plane"
    bl_label = "Create Top Bar Plane"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        coll = ensure_collection(COL_CUTPLANE)
        direction = arrow_direction(props.bar_arrow)
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
        for group in props.groups:
            if group.lock_topbar or group.lock_rot_topbar:
                apply_group_locks(group, props)
        if valid_obj(props.bar_line):
            if valid_obj(props.bar_line) and props.bar_line.modifiers:
                props.bar_line.modifiers[0].target = plane
            sync_bar_segment(context.scene, force=True)
        activate(context, plane)
        if resized:
            message = "Da phong to PlaneVisual + PlaneCubeCut len %g mm" % PLANE_SIZE
        else:
            message = "%s PlaneVisual + PlaneCubeCut (%g mm) + Mui ten huong lap - bam Draw " \
                      "Line Bar de ve line tren Plane" % ("Da tao" if created else "Da co", PLANE_SIZE)
        self.report({'INFO'}, message)
        return {'FINISHED'}


class RMVB_OT_cut_top_bar(Operator):
    """Them modifier: Union Bar Segment voi tat ca Bar Pillar, Difference PlaneCubeCut
    (Manifold), Difference Base. Chi them modifier, khong apply"""
    bl_idname = "rmvb.cut_top_bar"
    bl_label = "Cut Top Bar"
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
        seg["rmvb_cut"] = True
        count = rebuild_segment_modifiers(context)
        activate(context, seg)
        self.report({'INFO'}, "Da them modifier Cut Top Bar (Bar Segment co %d modifier, "
                    "chua apply)" % count)
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


LOCK_CONSTRAINTS = (CST_ON_PLANE, CST_ROT_LIMIT, CST_ROT_PLANE, CST_COPY_LOC, CST_COPY_ROT)


def apply_group_locks(group, props):
    """Dung lai cac constraint khoa tren Empty cua group:

    - Lock Z voi Top Bar        : LIMIT_LOCATION z = 0 trong he truc cua PlaneVisual
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
    if group.lock_rot_topbar and valid_obj(plane):
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
        empty.empty_display_size = 4.0
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


class RMVB_OT_apply_attachment_bar(Operator):
    """Apply Part Bar cua cac group Attachment len Bar Segment: Union (Add on Bar)
    hoac Difference (Remove on Bar). Chi them modifier, khong apply"""
    bl_idname = "rmvb.apply_attachment_bar"
    bl_label = "Apply Attachment on Bar"
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
        parts = [g for g in props.groups if valid_obj(g.part_bar)]
        if not parts:
            self.report({'ERROR'}, "Chua co Attachment nao co Part Bar")
            return {'CANCELLED'}
        seg["rmvb_attach"] = True
        rebuild_segment_modifiers(context)
        unions = sum(1 for g in parts if g.on_bar)
        self.report({'INFO'}, "Da them %d modifier Attachment (%d Union, %d Difference)"
                    % (len(parts), unions, len(parts) - unions))
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


def sleeve_shell(source, inner_gap, wall, name, coll):
    """Vo Sleeve: mat trong cach bar `inner_gap`, day `wall` mm."""
    inner = dilate_solid(source, inner_gap, name + ".inner", coll)
    return _solidify(inner, wall, 1.0)


# ---------------------------------------------------------------------------
# Sleeve Design
# ---------------------------------------------------------------------------
def bar_source(context, coll):
    """Ban sao (da ap modifier) cua Bar Segment, toa do world."""
    seg = context.scene.rmvb.bar_segment
    if not valid_obj(seg):
        return None
    return evaluated_mesh_object(seg, "BarSegment.src", coll)


class RMVB_OT_create_sleeve_design(Operator):
    """Tao Sleeve: vo mong bao quanh bar voi offset + chieu day da chon, cat phan
    tiep xuc voi nuou (Difference Gingiva)"""
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
        try:
            source = bar_source(context, work)
            sleeve = sleeve_shell(source, inner_gap, wall, "Sleeve", work)
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

            # Cat phan tiep xuc voi nuou
            gingiva = props.gingiva_object
            if valid_obj(gingiva) and gingiva.type == 'MESH':
                boolean_objects(sleeve, [gingiva], 'DIFFERENCE')
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

        set_display_color(sleeve, lib_slot_color(
            current_attachment_name(props) or "", "part_sleeve"))
        sleeve["rmvb_role"] = "SLEEVE"
        props.sleeve_object = sleeve
        activate(context, sleeve)
        purge_unused_meshes()
        self.report({'INFO'}, "Da tao Sleeve (offset %g mm, day %g mm%s)"
                    % (inner_gap, wall, ", da cat Gingiva" if cut_gingiva else ""))
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

        context.view_layer.update()
        depsgraph = context.evaluated_depsgraph_get()
        baked = _mesh_from_evaluated(seg.evaluated_get(depsgraph))
        if len(baked.polygons) == 0:
            bpy.data.meshes.remove(baked)
            self.report({'ERROR'}, "Ket qua modifier rong - kiem tra lai cac Boolean")
            return {'CANCELLED'}

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
    """Xuat STL cho Bar Design va Sleeve Design (kem Visual Object + constructionInfo)"""
    bl_idname = "rmvb.save_design"
    bl_label = "Save Bar & Sleeve Design"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
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

        # Visual Object chi duoc xuat kem, khong tham gia boolean
        visuals = []
        for group in props.groups:
            visuals.extend(v.object for v in group.visuals if valid_obj(v.object))

        stamp = timestamp()
        saved = []
        for prefix, obj in items:
            filepath = os.path.join(folder, "%s_%s.stl" % (prefix, stamp))
            try:
                export_stl([obj] + visuals, filepath, context)
            except Exception as exc:
                self.report({'ERROR'}, "Khong xuat duoc %s: %s" % (prefix, exc))
                return {'CANCELLED'}
            saved.append(filepath)
            ci_path = write_construction_info(filepath, props.construction_file)
            if ci_path:
                saved.append(ci_path)
            else:
                self.report({'WARNING'}, "Khong tim thay constructionInfo de cap nhat")
        self.report({'INFO'}, "Da luu: " + ", ".join(os.path.basename(p) for p in saved))
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
        box.prop(props, "place_parts")
        row = box.row(align=True)
        row.operator(RMVB_OT_place_connection.bl_idname,
                     text="Place Connection (constructionInfo)",
                     icon=_ic('EMPTY_SINGLE_ARROW'))
        row.operator(RMVB_OT_clear_connection.bl_idname, text="", icon=_ic('TRASH'))
        if props.construction_file:
            box.label(text=os.path.basename(bpy.path.abspath(props.construction_file)),
                      icon=_ic('FILE'))
        box.label(text="Đã đặt: %d implant" % len(props.placed), icon=_ic('CHECKMARK'))

        # ---- Bar Pillar ----------------------------------------------------
        box = layout.box()
        box.label(text="3. Bar Design - Bar Pillar", icon=_ic('MESH_CONE'))
        box.prop(props, "pillar_lift")
        col = box.column(align=True)
        col.operator(RMVB_OT_create_bar_pillar.bl_idname,
                     text="Create Bar Pillar", icon=_ic('MOD_SCREW'))
        sub = col.column(align=True)
        sub.operator(RMVB_OT_edit_bar_pillar.bl_idname,
                     text="Edit Bar Pillar (Local)", icon=_ic('EDITMODE_HLT'))
        sub.operator(RMVB_OT_select_pillar_top.bl_idname,
                     text="Select Top", icon=_ic('VERTEXSEL'))
        sub.operator(RMVB_OT_exit_edit.bl_idname, text="Exit Edit Bar Pillar",
                     icon=_ic('OBJECT_DATA'))
        box.label(text="Bar Pillar: %d" % len(props.pillars), icon=_ic('INFO'))

        # ---- Bar Segment + Top Bar ----------------------------------------
        box = layout.box()
        box.label(text="4. Bar Design - Bar Segment & Top Bar", icon=_ic('CURVE_PATH'))
        plane_ok = valid_obj(props.top_plane)
        box.operator(RMVB_OT_create_top_bar_plane.bl_idname,
                     text="Create Top Bar Plane" if not plane_ok else "Create Top Bar Plane (đã có)",
                     icon=_ic('MESH_PLANE'))
        if valid_obj(props.bar_arrow):
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
        box.operator(RMVB_OT_cut_top_bar.bl_idname, text="Cut Top Bar",
                     icon=_ic('MOD_BOOLEAN'))

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
        box.operator(RMVB_OT_apply_attachment_bar.bl_idname,
                     text="Apply Attachment on Bar", icon=_ic('MOD_BOOLEAN'))

        # ---- Sleeve Design -------------------------------------------------
        box = layout.box()
        box.label(text="6. Sleeve Design", icon=_ic('MOD_SOLIDIFY'))
        box.prop(props, "sleeve_offset")
        box.prop(props, "sleeve_thickness")
        box.prop(props, "apply_attachment_sleeve")
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
    RMVB_OT_clear_connection,
    RMVB_OT_create_bar_pillar,
    RMVB_OT_edit_bar_pillar,
    RMVB_OT_select_pillar_top,
    RMVB_OT_exit_edit,
    RMVB_OT_create_top_bar_plane,
    RMVB_OT_create_bar_line,
    RMVB_OT_draw_bar_line,
    RMVB_OT_edit_bar_line,
    RMVB_OT_update_bar_segment,
    RMVB_OT_cut_top_bar,
    RMVB_OT_add_attachment,
    RMVB_OT_select_attachment_group,
    RMVB_OT_remove_attachment_group,
    RMVB_OT_clear_attachments,
    RMVB_OT_apply_attachment_bar,
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
