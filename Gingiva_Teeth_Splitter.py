bl_info = {
    "name": "Gingiva/Teeth Surface Splitter",
    "author": "Phat Nguyen",
    "version": (2, 5, 3),
    "blender": (4, 5, 3),
    "location": "View3D > Sidebar > IBAR Split",
    "description": "Ve mot vong line dang object bam tren be mat Target va tach thanh Gingiva / Teeth",
    "category": "Object",
}

import bpy
import bmesh
import os
import math
import uuid
import hashlib
from mathutils import Vector


# ---------------------------------------------------------------------------
# Hang so hinh hoc cua cutter "long chao" (basin). De co dinh de xem thu, sau co
# the dua len UI neu can.
# ---------------------------------------------------------------------------
WALL_RINGS = 3         # so vong chia "thanh" khi extrude margin vao trong.
FLOOR_FILL_CUTS = 2    # chia DEU moi canh (ap dung toan bo) - chi can du bat cong
                       # be mat offset; PyMeshLab lo mat do cuoi nen khong can cao.
SMOOTH_CONTINUITY_FACTOR = 0.5   # Smooth lam lien tuc be mat cutter (tru rim).
SMOOTH_CONTINUITY_ITERS = 8      # so vong Smooth lien tuc (0 = tat).
SMOOTH_RIM_WEIGHT = 0.0          # rim phai giu cung tren be mat -> tach moi chay (0).
MARGIN_LOOP_SNAP = 0.4           # muc keo rim ve be mat sau khi lam muot (thap=muot hon).

# Remesh ISOTROPIC bang PyMeshLab (mac dinh, giong cutter iBar): luoi tam giac DEU.
ISO_PML_ITERS = 8          # so vong isotropic remeshing cua PyMeshLab.
ISO_PML_TARGET_FACTOR = 1.0  # do dai canh muc tieu = (chu vi rim / so diem) * factor.
# Lam muot day TRUOC PyMeshLab (khong chieu lai) -> khu tu cat o vung lom (ke rang)
# de PyMeshLab khong ra non-manifold/nhieu vien (nguyen nhan rot fallback tren ca that).
PML_PRESMOOTH_ITERS = 8    # so vong Laplacian lam muot day moi lan thu (cong don).
PML_PRESMOOTH_FACTOR = 0.5 # he so moi vong.
PML_MAX_ATTEMPTS = 4       # so lan thu PyMeshLab (moi lan muot them + remesh tho hon).

# Fallback (khi khong co PyMeshLab): flip (Delaunay) + Laplacian nhe, chi thao tac
# AN TOAN ve topo (xem ghi chu trong _isotropic_remesh).
ISO_REMESH_ITERS = 20     # so vong flip + relax day (cang cao cang muot, 0 = tat).
ISO_RELAX_FACTOR = 0.5    # he so Laplacian relaxation moi vong (0..1).

# Tinh chinh duong margin (line) bang stack modifier: Subdivision -> Shrinkwrap
# -> Smooth (theo dung thong so trong anh tham chieu).
MARGIN_SUBDIV_LEVELS = 3         # Subdivision Surface (Catmull-Clark) Levels Viewport.
MARGIN_SHRINKWRAP_OFFSET = 0.1   # Shrinkwrap Offset (Above Surface) ~0.1 mm.
MARGIN_SMOOTH_FACTOR = 0.5       # Smooth Factor.
MARGIN_SMOOTH_REPEAT = 4         # Smooth Repeat (iterations).
MARGIN_LOOP_SMOOTH_ITERS = 10    # so vong lam muot + cach deu duong rim (khu rang cua).


# ---------------------------------------------------------------------------
# ViewLayer safety helpers (sao chép de add-on doc lap voi add-on iBar).
# ---------------------------------------------------------------------------
def _is_in_view_layer(obj, viewlayer=None):
    if obj is None:
        return False
    if viewlayer is None:
        viewlayer = bpy.context.view_layer
    return obj.name in viewlayer.objects


def _set_active_object(obj, viewlayer=None):
    if viewlayer is None:
        viewlayer = bpy.context.view_layer
    if not _is_in_view_layer(obj, viewlayer):
        return False
    viewlayer.objects.active = obj
    return True


def _select_object(obj, state=True, viewlayer=None):
    if viewlayer is None:
        viewlayer = bpy.context.view_layer
    if not _is_in_view_layer(obj, viewlayer):
        return False
    obj.select_set(state)
    return True


# ---------------------------------------------------------------------------
# Surface snapping helpers
# ---------------------------------------------------------------------------
# Bat "Face Project" snapping kieu retopo: khi extrude/di chuyen, chinh DINH THAT
# (tam/gizmo) duoc chieu thang xuong be mat Target, chu khong chi rieng cage hien
# thi cua Shrinkwrap. Nho do ca tam va diem extrude deu nam tren be mat.
_SNAP_BACKUP = None


def _enable_surface_snap(context):
    global _SNAP_BACKUP
    ts = context.scene.tool_settings

    if _SNAP_BACKUP is None:
        backup = {"use_snap": ts.use_snap}
        for attr in ("use_snap_translate", "use_snap_nonedit", "use_snap_self",
                     "use_snap_project"):
            if hasattr(ts, attr):
                backup[attr] = getattr(ts, attr)
        for attr in ("snap_elements", "snap_elements_individual"):
            if hasattr(ts, attr):
                backup[attr] = set(getattr(ts, attr))
        _SNAP_BACKUP = backup

    ts.use_snap = True
    if hasattr(ts, "use_snap_translate"):
        try:
            ts.use_snap_translate = True
        except Exception:
            pass
    # Blender 4.x: chieu tung phan tu len be mat object khac.
    if hasattr(ts, "snap_elements_individual"):
        try:
            ts.snap_elements_individual = {'FACE_PROJECT'}
        except Exception:
            pass
    elif hasattr(ts, "snap_elements"):
        try:
            ts.snap_elements = {'FACE'}
        except Exception:
            pass
        if hasattr(ts, "use_snap_project"):
            try:
                ts.use_snap_project = True
            except Exception:
                pass
    # Cho phep snap len object khong o edit mode (Target), khong snap len chinh line.
    if hasattr(ts, "use_snap_nonedit"):
        try:
            ts.use_snap_nonedit = True
        except Exception:
            pass
    if hasattr(ts, "use_snap_self"):
        try:
            ts.use_snap_self = False
        except Exception:
            pass


def _restore_snap(context):
    global _SNAP_BACKUP
    if _SNAP_BACKUP is None:
        return
    ts = context.scene.tool_settings
    for attr, value in _SNAP_BACKUP.items():
        if hasattr(ts, attr):
            try:
                setattr(ts, attr, value)
            except Exception:
                pass
    _SNAP_BACKUP = None


def _snap_bmesh_verts_to_surface(bm, line, target):
    """Ghi de toa do DINH THAT cua line ve dung be mat Target (world).

    Dam bao moi diem (ke ca tam) nam tren be mat du truoc do co bi troi.
    """
    if target is None or target.type != 'MESH':
        return
    mw_t = target.matrix_world
    mwi_t = mw_t.inverted()
    mwl = line.matrix_world
    mwi_l = mwl.inverted()
    for v in bm.verts:
        world_co = mwl @ v.co
        hit, location, _nrm, _idx = target.closest_point_on_mesh(mwi_t @ world_co)
        if hit:
            v.co = mwi_l @ (mw_t @ location)


# ---------------------------------------------------------------------------
# License check (sao chép nguyen khoi tu Final_addon_Ibar_to_ORG.py).
# Dung chung file key ~/addon_ibar.key voi add-on iBar hien tai.
# ---------------------------------------------------------------------------
def create_hash(data, algorithm="sha512"):
    hash_func = hashlib.new(algorithm)
    hash_func.update(data.encode('utf-8'))
    return hash_func.hexdigest()


def _read_windows_machine_guid():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return str(value).strip()
    except Exception:
        return ""


def _build_machine_fingerprint():
    machine_guid = _read_windows_machine_guid()
    mac_address = str(uuid.getnode())
    host_name = os.environ.get("COMPUTERNAME", "") or os.environ.get("HOSTNAME", "")
    processor = os.environ.get("PROCESSOR_IDENTIFIER", "")
    cpu_count = os.environ.get("NUMBER_OF_PROCESSORS", "")

    parts = [machine_guid, mac_address, host_name, processor, cpu_count]
    raw_fingerprint = "|".join(part for part in parts if part)
    if not raw_fingerprint:
        raw_fingerprint = mac_address

    return create_hash(raw_fingerprint, "sha256")[:32].upper()


def get_stable_hardware_id():
    user_folder = os.path.expanduser("~")
    machine_id_path = os.path.join(user_folder, ".ibar_machine_id")

    if os.path.exists(machine_id_path):
        try:
            with open(machine_id_path, "r", encoding="utf-8") as file_read:
                cached_id = file_read.read().strip()
                if cached_id:
                    return cached_id
        except Exception:
            pass

    hardware_id = _build_machine_fingerprint()
    try:
        with open(machine_id_path, "w", encoding="utf-8") as file_write:
            file_write.write(hardware_id)
    except Exception:
        pass
    return hardware_id


def hw_read_key():
    hardware_id = get_stable_hardware_id()
    hashed_text = create_hash(hardware_id * 2)
    legacy_hardware_id = str(uuid.getnode())
    legacy_hashed_text = create_hash(legacy_hardware_id * 2)
    user_folder = os.path.expanduser("~")

    license_path = os.path.join(user_folder, "addon_ibar.key")
    if not os.path.exists(license_path):
        hardware_id_filepart = os.path.join(user_folder, "Desktop", "IbarPrep.hwid")
        try:
            if not os.path.exists(hardware_id_filepart):
                with open(hardware_id_filepart, "w", encoding="utf-8") as file_write:
                    file_write.write(hardware_id)
        except Exception:
            pass
        print('No License Found')
        return False

    with open(license_path, "r", encoding="utf-8") as hardware_id_input:
        lines = hardware_id_input.readlines()
    if lines and lines[0].strip() in {hashed_text, legacy_hashed_text}:
        return True
    print('Wrong license key')
    return False


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def _world_normal(obj, normal_local):
    """Chuyen normal tu local sang world (dung cho ca scale khong deu)."""
    return (obj.matrix_world.to_3x3().inverted().transposed() @ normal_local).normalized()


def _bbox_center_world(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    center = Vector((0.0, 0.0, 0.0))
    for c in corners:
        center += c
    return center / len(corners)


def _walk_ordered_loop(me, mw):
    """Doc vong dinh theo thu tu noi canh tu mot mesh (vong dinh valence 2).

    Tra ve (points_world, closed).
    """
    nverts = len(me.vertices)
    adj = {i: [] for i in range(nverts)}
    for e in me.edges:
        a, b = e.vertices
        adj[a].append(b)
        adj[b].append(a)

    endpoints = [i for i, nb in adj.items() if len(nb) == 1]
    closed = (nverts >= 3 and not endpoints and all(len(nb) == 2 for nb in adj.values()))

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

    pts = [mw @ me.vertices[i].co for i in order]
    return pts, closed


def _resample_closed_loop(pts, count):
    """Lay lai `count` diem cach DEU theo chieu dai cung tren vong kin.

    Khu tinh trang diem thua/trung (canh dai 0) lam rang cua.
    """
    n = len(pts)
    if n < 3 or count < 3:
        return [p.copy() for p in pts]
    seg = [(pts[(i + 1) % n] - pts[i]).length for i in range(n)]
    total = sum(seg)
    if total < 1e-9:
        return [p.copy() for p in pts]
    cum = [0.0]
    for s in seg:
        cum.append(cum[-1] + s)
    step = total / count
    out = []
    i = 0
    for k in range(count):
        d = k * step
        while i < n - 1 and cum[i + 1] < d:
            i += 1
        seglen = seg[i]
        t = (d - cum[i]) / seglen if seglen > 1e-9 else 0.0
        out.append(pts[i].lerp(pts[(i + 1) % n], t))
    return out


def _smooth_loop_on_surface(target, bbox_center, pts, iterations, factor, snap):
    """Lam muot vong rim bang TAUBIN (khong co rut) trong 3D roi bam GAN be mat.

    Taubin (lam muot +lambda roi -mu) khu rang cua tan so cao (ke ca dao dong theo
    huong phap tuyen lam vien rang cua khi nhin nghieng) ma KHONG lam rut vong.
    Sau do keo MOT PHAN ve be mat (snap) de rim bam gan be mat (van tach duoc)
    nhung khong bam theo tung mau bump -> bo mat lien tuc hon.
    """
    mw = target.matrix_world
    mwti = mw.inverted()
    out = [p.copy() for p in pts]
    n = len(out)
    lam = factor
    mu = -factor * 1.05
    for it in range(max(0, iterations) * 2):
        k = lam if (it % 2 == 0) else mu
        new = []
        for i in range(n):
            avg = (out[(i - 1) % n] + out[(i + 1) % n]) * 0.5
            new.append(out[i] + (avg - out[i]) * k)
        out = new
    if snap > 0:
        res = []
        for p in out:
            hit, loc, _nor, _idx = target.closest_point_on_mesh(mwti @ p)
            res.append(p.lerp(mw @ loc, snap) if hit else p)
        out = res
    return out


def _processed_margin_loop(context, line, target):
    """Tinh chinh duong margin (line) bang stack modifier giong anh tham chieu:

        Subdivision Surface (Catmull-Clark, levels=MARGIN_SUBDIV_LEVELS)
          -> Shrinkwrap (Nearest Surface Point, Above Surface, offset)
          -> Smooth (factor, repeat).

    Lam tren mot ban sao tam de khong dung cham vao line goc. Tra ve
    (loop_pts_world, loop_nrms_world, closed) - vong margin da tinh chinh va
    day diem, kem normal be mat Target tai moi diem (de dinh huong long chao).
    """
    tmp_me = line.data.copy()
    tmp = bpy.data.objects.new("GT_MarginTmp", tmp_me)
    tmp.matrix_world = line.matrix_world.copy()
    context.collection.objects.link(tmp)
    tmp.modifiers.clear()

    # 1) Subdivision Surface: lam muot + tang mat do duong margin.
    sub = tmp.modifiers.new(name="GT_Subsurf", type='SUBSURF')
    sub.subdivision_type = 'CATMULL_CLARK'
    sub.levels = MARGIN_SUBDIV_LEVELS
    if hasattr(sub, "render_levels"):
        sub.render_levels = 2
    for attr, val in (("use_limit_surface", True), ("quality", 3),
                      ("use_creases", True), ("uv_smooth", 'PRESERVE_BOUNDARIES'),
                      ("boundary_smooth", 'ALL')):
        if hasattr(sub, attr):
            try:
                setattr(sub, attr, val)
            except Exception:
                pass

    # 2) Shrinkwrap: bam ve be mat Target, nho len tren be mat (Above Surface).
    sw = tmp.modifiers.new(name="GT_Shrinkwrap", type='SHRINKWRAP')
    sw.target = target
    sw.wrap_method = 'NEAREST_SURFACEPOINT'
    sw.wrap_mode = 'ABOVE_SURFACE'
    sw.offset = MARGIN_SHRINKWRAP_OFFSET

    # 3) Smooth: lam diu (relax) vong margin.
    sm = tmp.modifiers.new(name="GT_Smooth", type='SMOOTH')
    for axis in ("use_x", "use_y", "use_z"):
        if hasattr(sm, axis):
            setattr(sm, axis, True)
    sm.factor = MARGIN_SMOOTH_FACTOR
    sm.iterations = MARGIN_SMOOTH_REPEAT

    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = tmp.evaluated_get(depsgraph)
    eval_me = eval_obj.to_mesh()
    pts, closed = _walk_ordered_loop(eval_me, tmp.matrix_world)
    eval_obj.to_mesh_clear()

    bpy.data.objects.remove(tmp, do_unlink=True)
    if tmp_me.users == 0:
        bpy.data.meshes.remove(tmp_me, do_unlink=True)

    # Lam muot + cach deu duong rim, bam lai be mat -> khu rang cua (zigzag do
    # shrinkwrap tren be mat chi tiet cao), giu rim lien tuc.
    if closed and len(pts) >= 3:
        bbc = _bbox_center_world(target)
        pts = _resample_closed_loop(pts, len(pts))
        pts = _smooth_loop_on_surface(target, bbc, pts, MARGIN_LOOP_SMOOTH_ITERS,
                                      0.5, MARGIN_LOOP_SNAP)

    # Normal be mat Target tai moi diem margin (de dung lam huong long chao).
    mwti = target.matrix_world.inverted()
    loop_nrms = []
    for p in pts:
        hit, _loc, nor, _idx = target.closest_point_on_mesh(mwti @ p)
        if hit:
            loop_nrms.append(_world_normal(target, nor))
        else:
            loop_nrms.append(Vector((0.0, 0.0, 1.0)))
    return pts, loop_nrms, closed


def _smooth_normals(normals, iterations=2):
    """Lam muot vong-tron cac normal bang trung binh truot."""
    n = len(normals)
    if n < 3:
        return [v.normalized() for v in normals]
    result = [v.copy() for v in normals]
    for _ in range(iterations):
        new = []
        for i in range(n):
            prev = result[(i - 1) % n]
            cur = result[i]
            nxt = result[(i + 1) % n]
            avg = (prev + cur + nxt)
            if avg.length > 1e-9:
                avg = avg.normalized()
            else:
                avg = cur.normalized()
            new.append(avg)
        result = new
    return result


def _smooth_cutter_continuity(context, cutter):
    """Lam mat cutter LIEN TUC hon: Smooth toan bo dinh TRU vien rim.

    Dung vertex group (rim=0, con lai=1) + Smooth modifier -> bo bump/rang cua,
    bo mat muot lien tuc. Rim (boundary) giu nguyen tuyet doi -> vet cat van cham
    be mat doc margin nen tach duoc 2 manh.
    """
    me = cutter.data
    if len(me.polygons) < 8 or SMOOTH_CONTINUITY_ITERS <= 0:
        return
    bm = bmesh.new()
    bm.from_mesh(me)
    boundary = set(v.index for e in bm.edges if e.is_boundary for v in e.verts)
    bm.free()
    interior = [v.index for v in me.vertices if v.index not in boundary]
    if not interior:
        return
    vg = cutter.vertex_groups.new(name="gt_interior")
    vg.add(interior, 1.0, 'REPLACE')
    # Rim (boundary) duoc lam muot NHE (weight thap) -> bot rang cua nhung gan nhu
    # giu nguyen vi tri tren be mat -> tach 2 manh van chay.
    if boundary:
        vg.add(list(boundary), SMOOTH_RIM_WEIGHT, 'REPLACE')
    sm = cutter.modifiers.new(name="GT_Continuity", type='SMOOTH')
    sm.factor = SMOOTH_CONTINUITY_FACTOR
    sm.iterations = SMOOTH_CONTINUITY_ITERS
    sm.vertex_group = vg.name
    bpy.ops.object.select_all(action='DESELECT')
    _set_active_object(cutter, context.view_layer)
    _select_object(cutter, True, context.view_layer)
    bpy.ops.object.modifier_apply(modifier=sm.name)
    g = cutter.vertex_groups.get("gt_interior")
    if g is not None:
        cutter.vertex_groups.remove(g)


def _orient_faces_outward(obj, bbox_center):
    """Lat toan bo normal cua obj huong RA NGOAI than (xa tam bbox)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        facing = 0.0
        for f in bm.faces:
            facing += f.normal.dot(f.calc_center_median() - bbox_center)
        if facing < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()


def _smooth_floor_bmesh(bm, move_layer, factor, iterations):
    """Laplacian smooth DAY long chao (KHONG chieu lai be mat) -> khu cac nep tu cat
    (self-intersection) khi be mat offset huong vao trong tu cat o vung lom (ke rang).
    Bat buoc chay TRUOC PyMeshLab: PyMeshLab tren luoi tu cat se ra non-manifold/
    nhieu vien -> bi guard loai. CHI di chuyen dinh day (move_layer==1); rim/thanh
    giu nguyen."""
    for _ in range(max(0, iterations)):
        moved = {}
        for v in bm.verts:
            if not v[move_layer]:
                continue
            nbrs = [e.other_vert(v) for e in v.link_edges]
            if not nbrs:
                continue
            avg = Vector((0.0, 0.0, 0.0))
            for p in nbrs:
                avg += p.co
            avg /= len(nbrs)
            moved[v] = v.co.lerp(avg, factor)
        for v, co in moved.items():
            v.co = co
    bm.normal_update()


def _isotropic_remesh(bm, move_layer, project_fn, iterations, relax_factor):
    """FALLBACK (khi khong co PyMeshLab): lam DEU + MUOT luoi day long chao bang
    cac thao tac AN TOAN ve topo: beautify edge-flip (Delaunay) + Laplacian nhe co
    chieu lai be mat that (project_fn). CHI dinh "noi that day" (move_layer==1);
    rim/thanh/vong day-thanh GIU CO DINH -> tach 2 manh van chay.

    GHI CHU: remesh ISOTROPIC thuc su (Botsch-Kobbelt: split + COLLAPSE diem qua
    gan + flip + relax) cho luoi DEU nhu cutter iBar (CV~0.15, 0 sliver) duoc lam
    bang PyMeshLab trong _remesh_basin_pymeshlab (mac dinh). MOI cach collapse
    trong bmesh thuan (bmesh.ops.collapse, remove_doubles) deu lam DAM THUNG /
    NON-MANIFOLD luoi day (vi lap tu n-gon co nhieu diem gan nhau ve KHONG-GIAN
    nhung xa ve TOPO) -> Boolean vo vun; nen bmesh chi dung lam fallback flip+relax
    (giu boundary_loops=1, non-manifold=0)."""
    if iterations <= 0:
        return
    for _ in range(iterations):
        # FLIP (beautify/Delaunay): cai thien hinh tam giac, bo tam giac tua tua,
        # keo valence ve ~6 -> KHONG tao/xoa dinh nen KHONG dam thung luoi. Chi canh
        # co CA HAI dinh movable (giu nguyen vong day-thanh, thanh va rim).
        tris = [f for f in bm.faces if len(f.verts) == 3]
        if tris:
            tri_edges = list({e for f in tris for e in f.edges
                              if e.verts[0][move_layer] and e.verts[1][move_layer]})
            if tri_edges:
                bmesh.ops.beautify_fill(bm, faces=tris, edges=tri_edges)

        # RELAXATION nhe (Laplacian nua duong) + chieu lai be mat that. Di chuyen
        # NHE + chieu lai -> KHONG gap mep/self-intersect (truot manh lam boolean vo
        # vun). Chi dinh movable (move_layer==1).
        moved = {}
        for v in bm.verts:
            if not v[move_layer]:
                continue
            nbrs = [e.other_vert(v) for e in v.link_edges]
            if not nbrs:
                continue
            avg = Vector((0.0, 0.0, 0.0))
            for p in nbrs:
                avg += p.co
            avg /= len(nbrs)
            tgt = v.co.lerp(avg, relax_factor)
            pr = project_fn(tgt)
            moved[v] = pr if pr is not None else tgt
        for v, co in moved.items():
            v.co = co

    bm.normal_update()


# ---------------------------------------------------------------------------
# Isotropic remesh bang PyMeshLab (giong cutter iBar). PyMeshLab la ban Python
# cua MeshLab; filter meshing_isotropic_explicit_remeshing cho luoi tam giac DEU
# (CV~0.15, 0 sliver), GIU duoc vien ho (rim).
#
# QUAN TRONG: KHONG import pymeshlab TRONG tien trinh Blender - cac thu vien native
# (Qt/MSVCP140) cua no XUNG DOT voi cua Blender -> EXCEPTION_ACCESS_VIOLATION (crash).
# Vi vay chay pymeshlab O TIEN TRINH RIENG (subprocess) bang chinh python.exe cua
# Blender (chay doc lap khong load Blender -> khong xung dot). Trao doi mesh qua file
# .npz. Neu khong cai/chay duoc -> fallback flip+relax (_isotropic_remesh).
# ---------------------------------------------------------------------------
_PYMESHLAB_ENV = None
_PYMESHLAB_TRIED = False

# Script worker chay trong subprocess (python.exe cua Blender, KHONG co Blender).
_PML_WORKER = r'''
import sys, numpy as np, pymeshlab as ml
inp, out, tlen, iters = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
d = np.load(inp)
ms = ml.MeshSet()
ms.add_mesh(ml.Mesh(vertex_matrix=d["v"].astype("float64"),
                    face_matrix=d["f"].astype("int32")), "m")

def _try(name, **kw):
    try:
        getattr(ms, name)(**kw)
    except Exception:
        pass

# Lam sach input truoc khi remesh -> tranh remesh ra non-manifold.
_try("meshing_remove_duplicate_vertices")
_try("meshing_remove_duplicate_faces")
_try("meshing_remove_unreferenced_vertices")
_try("meshing_remove_null_faces")
_try("meshing_repair_non_manifold_edges")
_try("meshing_repair_non_manifold_vertices")

ms.meshing_isotropic_explicit_remeshing(targetlen=ml.PureValue(tlen), iterations=iters)

# Don lai sau remesh (dam bao 1 vien rim, 0 non-manifold).
_try("meshing_repair_non_manifold_edges")
_try("meshing_remove_unreferenced_vertices")

cm = ms.current_mesh()
np.savez(out, v=cm.vertex_matrix(), f=cm.face_matrix())
'''


def _blender_python_exe():
    """Tra ve duong dan python.exe cua Blender (chay subprocess), khong phai blender.exe."""
    import sys
    if sys.platform == "win32":
        cand = os.path.join(sys.prefix, "bin", "python.exe")
        if os.path.exists(cand):
            return cand
    else:
        import glob
        for c in sorted(glob.glob(os.path.join(sys.prefix, "bin", "python*"))):
            if os.path.exists(c):
                return c
    return sys.executable


_PML_MODULES_DIR = None   # cache thu muc modules cua user (lay tren MAIN thread)


def _pml_modules_dir():
    """Thu muc modules cua user (cache). Goi bpy.utils.user_resource CHI tren main
    thread (warm o register) -> luong nen kiem tra PyMeshLab khong dung bpy."""
    global _PML_MODULES_DIR
    if _PML_MODULES_DIR is None:
        _PML_MODULES_DIR = bpy.utils.user_resource('SCRIPTS', path='modules',
                                                   create=True)
    return _PML_MODULES_DIR


def _pml_env():
    """Moi truong cho subprocess: them thu muc modules cua user vao PYTHONPATH."""
    target = _pml_modules_dir()
    env = dict(os.environ)
    env['PYTHONPATH'] = target + os.pathsep + env.get('PYTHONPATH', '')
    return target, env


def _pymeshlab_ready(force=False):
    """KIEM TRA (cache) xem PyMeshLab dung duoc trong subprocess chua. KHONG cai dat
    -> goi trong Create Cutter se KHONG bao gio lam dung Blender bat ngo. Tra ve
    (python_exe, env) hoac None. force=True de kiem tra lai sau khi cai."""
    global _PYMESHLAB_ENV, _PYMESHLAB_TRIED
    if _PYMESHLAB_TRIED and not force:
        return _PYMESHLAB_ENV
    _PYMESHLAB_TRIED = True
    _PYMESHLAB_ENV = None
    import subprocess
    py = _blender_python_exe()
    target, env = _pml_env()
    try:
        r = subprocess.run([py, "-c", "import pymeshlab"], env=env,
                           capture_output=True, text=True, timeout=180)
        if r.returncode == 0:
            _PYMESHLAB_ENV = (py, env)
    except Exception:
        pass
    return _PYMESHLAB_ENV


def _install_pymeshlab_blocking():
    """pip install PyMeshLab vao thu muc modules cua user (KHONG can admin). Ham nay
    CHAN (blocking) -> goi trong luong nen (thread) cua operator de Blender khong dung.
    Tra ve (ok, message)."""
    if _pymeshlab_ready(force=True) is not None:
        return True, "Da co san."
    import subprocess
    py = _blender_python_exe()
    target, _env = _pml_env()
    try:
        subprocess.run([py, "-m", "pip", "install", "--target", target, "pymeshlab"],
                       check=True, capture_output=True, text=True, timeout=1800)
    except subprocess.CalledProcessError as e:
        return False, ((e.stderr or e.stdout or "")[-300:])
    except Exception as e:
        return False, str(e)[-300:]
    ok = _pymeshlab_ready(force=True) is not None
    return ok, ("" if ok else "Cai xong nhung van khong import duoc.")


def _closest_on_polyline(pts, p):
    """Diem gan nhat tren duong gap kin pts (de bam rim ve dung margin)."""
    best = pts[0]
    bestd = (p - pts[0]).length_squared
    n = len(pts)
    for i in range(n):
        a = pts[i]; b = pts[(i + 1) % n]
        ab = b - a
        L2 = ab.length_squared
        t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / L2))
        c = a + ab * t
        d = (p - c).length_squared
        if d < bestd:
            bestd = d; best = c
    return best


def _boundary_loops_edges(bm):
    """Gom cac canh vien thanh tung vong (list cac list canh)."""
    from collections import defaultdict
    bm.edges.ensure_lookup_table()
    bnd = [e for e in bm.edges if e.is_boundary]
    eadj = defaultdict(list)
    for e in bnd:
        eadj[e.verts[0].index].append(e); eadj[e.verts[1].index].append(e)
    seen = set(); loops = []
    for e in bnd:
        if e in seen:
            continue
        comp = []; st = [e]
        while st:
            ce = st.pop()
            if ce in seen:
                continue
            seen.add(ce); comp.append(ce)
            for v in ce.verts:
                for ne_ in eadj[v.index]:
                    if ne_ not in seen:
                        st.append(ne_)
        loops.append(comp)
    return loops


def _fill_small_holes(bm):
    """Va moi vong vien TRU vong lon nhat (rim) -> chi con 1 vien rim duy nhat. Cac
    lo nho la do PyMeshLab repair (khong xac dinh) de lai o vung tu cat."""
    loops = _boundary_loops_edges(bm)
    if len(loops) <= 1:
        return
    loops.sort(key=len, reverse=True)
    small = [e for comp in loops[1:] for e in comp]
    if small:
        bmesh.ops.holes_fill(bm, edges=small, sides=0)
        ntri = [f for f in bm.faces if len(f.verts) > 3]
        if ntri:
            bmesh.ops.triangulate(bm, faces=ntri, quad_method='BEAUTY',
                                  ngon_method='BEAUTY')
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()


def _remesh_basin_pymeshlab(env, bm, loop_pts, target_len, iterations):
    """Remesh isotropic toan bo long chao bang PyMeshLab (O SUBPROCESS) roi dung lai
    vao bm. Trao doi mesh qua file .npz. Sau remesh: chieu cac dinh VIEN (rim) ve
    dung duong margin (loop_pts) -> duong cat khop be mat -> tach 2 manh chuan.
    Tra ve True neu thanh cong, False -> caller fallback flip+relax.
    """
    import numpy as np, subprocess, tempfile, shutil
    py, runenv = env
    # PyMeshLab can luoi tam giac -> tam giac hoa truoc khi xuat.
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY',
                          ngon_method='BEAUTY')
    bm.verts.ensure_lookup_table()
    for i, v in enumerate(bm.verts):
        v.index = i
    vmat = np.array([(v.co.x, v.co.y, v.co.z) for v in bm.verts], dtype=np.float64)
    fmat = np.array([[vt.index for vt in f.verts] for f in bm.faces], dtype=np.int64)
    if len(vmat) < 4 or len(fmat) < 2:
        return False

    tmpdir = tempfile.mkdtemp(prefix="gtsplit_")
    try:
        inp = os.path.join(tmpdir, "in.npz")
        out = os.path.join(tmpdir, "out.npz")
        worker = os.path.join(tmpdir, "worker.py")
        np.savez(inp, v=vmat, f=fmat)
        with open(worker, "w", encoding="utf-8") as fh:
            fh.write(_PML_WORKER)
        try:
            r = subprocess.run([py, worker, inp, out, str(target_len), str(iterations)],
                               env=runenv, capture_output=True, text=True, timeout=600)
        except Exception as ex:
            print("[GTSplit] PyMeshLab subprocess loi, fallback:", ex)
            return False
        if r.returncode != 0 or not os.path.exists(out):
            tail = (r.stderr or "")[-600:]
            print("[GTSplit] PyMeshLab worker loi, fallback:", tail)
            return False
        data = np.load(out)
        nv = data["v"]; nf = data["f"]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if len(nv) < 4 or len(nf) < 2:
        return False

    # SAFETY: chi commit ket qua remesh khi topo SACH (dung 1 vien rim, 0 canh
    # non-manifold). Neu input long chao go ghe/tu cat khien remesh sinh lo hoac
    # non-manifold -> tra False de caller fallback flip+relax (khong bao gio xuat
    # cutter hong lam Boolean vo vun). bm chua bi dung lai nen fallback chay duoc.
    from collections import defaultdict
    ef = defaultdict(int)
    for f in nf:
        a, b, c = int(f[0]), int(f[1]), int(f[2])
        for x, y in ((a, b), (b, c), (c, a)):
            ef[(x, y) if x < y else (y, x)] += 1
    if any(cnt > 2 for cnt in ef.values()):
        print("[GTSplit] PyMeshLab ra non-manifold -> fallback flip+relax.")
        return False
    # Gom vong vien + kich thuoc. PyMeshLab tren vung tu cat (ke rang) co the de lai
    # vai LO NHO khong xac dinh -> KHONG bo het; chi bo neu RIM bi XE (co 2 vong lon
    # tuong duong). Cac lo nho se duoc va lai trong bmesh -> 1 vien rim duy nhat.
    adj = defaultdict(list)
    for (a, b), cnt in ef.items():
        if cnt == 1:
            adj[a].append(b); adj[b].append(a)
    seen = set(); loop_sizes = []
    for v0 in list(adj):
        if v0 in seen:
            continue
        cnt = 0; st = [v0]
        while st:
            x = st.pop()
            if x in seen:
                continue
            seen.add(x); cnt += 1
            st.extend(y for y in adj[x] if y not in seen)
        loop_sizes.append(cnt)
    if not loop_sizes:
        return False
    loop_sizes.sort(reverse=True)
    if len(loop_sizes) > 1 and loop_sizes[1] > loop_sizes[0] * 0.25:
        print(f"[GTSplit] PyMeshLab xe rim {loop_sizes[:3]} -> fallback flip+relax.")
        return False

    # Dung lai bm tu ket qua remesh.
    bm.clear()
    nverts = [bm.verts.new((float(p[0]), float(p[1]), float(p[2]))) for p in nv]
    bm.verts.ensure_lookup_table()
    for f in nf:
        try:
            bm.faces.new((nverts[int(f[0])], nverts[int(f[1])], nverts[int(f[2])]))
        except (ValueError, IndexError):
            pass
    bm.normal_update()
    # Va cac lo nho (tru vong rim lon nhat) -> chi con 1 vien rim.
    _fill_small_holes(bm)
    # Chieu rim ve dung margin (loop_pts) -> bam be mat, tach chuan.
    for v in bm.verts:
        if v.is_boundary:
            v.co = _closest_on_polyline(loop_pts, v.co)
    bm.normal_update()
    return True


def _build_cutter(context, target, loop_pts, loop_nrms, offset, gap,
                  apply_solidify=True, name="GT_Cutter"):
    """Dung cutter "long chao" theo thuat toan extrude + be mat offset + remesh.

    Quy trinh:
      1) Extrude toan bo duong margin VAO TRONG (nguoc Face Normal cua Target),
         sau = offset -> tao "thanh" (curtain wall).
      2) Tao be mat OFFSET cat ngang day thanh, gioi han trong vung margin
         (be mat Target offset vao trong = offset) -> lam "day" long chao,
         noi lien voi thanh.
      3) Lap day (fill) + chia nho thanh luoi mesh co the EDIT/SMOOTH/FREEFORM
         (buoc "Create Cutter"). Moi dinh day duoc chieu ve dung be mat offset
         (robust ca khi margin lom/hinh mong ngua, khong dung quat-ve-tam).

    Giu Solidify (do day gap) dang modifier de xem truoc / boolean.

    apply_solidify=True  -> apply luon Solidify (dung khi cat ngay).
    apply_solidify=False -> giu Solidify dang modifier de xem truoc / chinh sua.

    Tra ve object cutter, hoac None neu loi.
    """
    n = len(loop_pts)
    if n < 3:
        return None

    bbox_center = _bbox_center_world(target)
    mw = target.matrix_world
    mwi = mw.inverted()

    # Normal be mat tai rim, lat ra NGOAI than object (huong +Face Normal), lam muot.
    out_nrms = []
    for p, nrm in zip(loop_pts, loop_nrms):
        nn = nrm.normalized()
        if nn.dot(p - bbox_center) < 0:   # phai huong ra ngoai (roi xa tam bbox)
            nn = -nn
        out_nrms.append(nn)
    out_nrms = _smooth_normals(out_nrms, iterations=2)
    in_nrms = [-nn for nn in out_nrms]

    def _project_offset(world_co):
        """Chieu 1 diem ve be mat Target roi day vao trong = offset (be mat offset)."""
        hit, loc, nor, _idx = target.closest_point_on_mesh(mwi @ world_co)
        if not hit:
            return None
        surf = mw @ loc
        nworld = _world_normal(target, nor)
        if nworld.dot(surf - bbox_center) < 0:
            nworld = -nworld
        return surf - nworld * offset

    bm = bmesh.new()
    # Layer danh dau dinh "noi that day" (movable) cho remesh isotropic. Tao TRUOC
    # khi them dinh (tao layer sau se lam mat tham chieu dinh do op cap phat lai).
    move = bm.verts.layers.int.new("gt_move")

    # --- 1) Extrude margin vao trong tao "thanh" (rim -> day thanh sau = offset) -
    rings = []
    for s in range(WALL_RINGS + 1):
        f = s / float(WALL_RINGS)
        ring = [bm.verts.new(loop_pts[i] + in_nrms[i] * (offset * f)) for i in range(n)]
        rings.append(ring)
    bm.verts.ensure_lookup_table()
    for ring_a, ring_b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            try:
                bm.faces.new((ring_a[i], ring_a[j], ring_b[j], ring_b[i]))
            except ValueError:
                pass

    # --- 2+3) Lap day long chao + chia luoi DEU (TAT CA tam giac, KHONG n-gon) ---
    # QUAN TRONG (sua bug): truoc day day lap bang 1 n-gon 320 canh, roi subdivide
    # cac canh cua no - von DUNG CHUNG voi thanh (wall) - khien mat thanh bi bien
    # thanh n-gon 9 canh, tam giac hoa ra non-manifold -> luoi hong + PyMeshLab bi
    # loai. Cach moi: lap day bang triangle_fill (Delaunay), TAM GIAC HOA TOAN BO
    # (wall quads -> tris), roi subdivide TAT CA canh (moi tam giac chia deu) -> chi
    # con tam giac sach, KHONG n-gon -> PyMeshLab nhan input sach -> luoi DEU.
    bottom = rings[-1]
    bottom_edges = []
    for i in range(n):
        e = bm.edges.get((bottom[i], bottom[(i + 1) % n]))
        if e is not None:
            bottom_edges.append(e)
    floor_faces = []
    if bottom_edges:
        fres = bmesh.ops.triangle_fill(bm, edges=bottom_edges, use_beauty=True)
        floor_faces = [g for g in fres.get('geom', [])
                       if isinstance(g, bmesh.types.BMFace)]
    if not floor_faces:
        try:
            floor_faces = [bm.faces.new(bottom)]
        except ValueError:
            pass

    # Tam giac hoa TOAN BO (wall quads + bat ky n-gon nao) -> dong nhat tam giac.
    nontri = [f for f in bm.faces if len(f.verts) > 3]
    if nontri:
        bmesh.ops.triangulate(bm, faces=nontri, quad_method='BEAUTY',
                              ngon_method='BEAUTY')
    # Chia DEU tat ca canh: moi tam giac da bi chia het canh -> tach sach 4 tam
    # giac/lan, KHONG tao n-gon (khac han subdivide tap con cu).
    if FLOOR_FILL_CUTS > 0:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=FLOOR_FILL_CUTS,
                                  use_grid_fill=True)
    # Danh dau dinh DAY (move=1) + chieu ve be mat offset that. Dinh "day" = co do
    # sau vao trong >= ~offset (phan biet voi thanh dang nong, depth < offset).
    mw = target.matrix_world
    mwi = mw.inverted()
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        hit, loc, _nor, _idx = target.closest_point_on_mesh(mwi @ v.co)
        if not hit:
            continue
        depth = (v.co - (mw @ loc)).length
        if depth >= offset * 0.85:        # dinh thuoc DAY long chao
            v[move] = 1
            proj = _project_offset(v.co)
            if proj is not None:
                v.co = proj

    # --- REMESH (buoc "Create Cutter"): luoi tam giac DEU giong cutter iBar ---
    # Do dai canh muc tieu = mat do rim (chu vi / so diem) * he so.
    perim = sum((loop_pts[(i + 1) % n] - loop_pts[i]).length for i in range(n))
    target_len = (perim / n) * ISO_PML_TARGET_FACTOR if n else 0.0

    # B1) LUON flip + relax truoc: don sach topo + bo tam giac tua tua cua luoi day
    #     lap tu n-gon (88% sliver, gan suy bien). Day la dieu kien BAT BUOC de
    #     PyMeshLab chay sach - dua THANG luoi n-gon tho vao PyMeshLab se ra
    #     non-manifold -> guard loai -> rot fallback (da kiem chung tren data that).
    #     Day cung la ket qua fallback neu PyMeshLab khong dung duoc.
    _isotropic_remesh(bm, move, _project_offset, ISO_REMESH_ITERS, ISO_RELAX_FACTOR)

    # B1.5 + B2) Lam muot day (KHONG chieu lai) de khu nep TU CAT o vung lom (be mat
    #   offset huong vao trong tu cat o ke rang) -> roi PyMeshLab isotropic remesh ->
    #   luoi tam giac DEU (giong iBar). Tu cat khong on dinh nen LAP: moi vong lam
    #   muot THEM + remesh THO hon mot chut roi thu lai; tang dan dam bao khu het tu
    #   cat -> luon dung duoc PyMeshLab tren ca lom (khong rot fallback). Het vong ma
    #   van loi -> giu ket qua da lam muot (fallback se tinh chinh tiep).
    pml_env = _pymeshlab_ready()
    used_pml = False
    if pml_env is not None and target_len > 0:
        for attempt in range(PML_MAX_ATTEMPTS):
            _smooth_floor_bmesh(bm, move, PML_PRESMOOTH_FACTOR, PML_PRESMOOTH_ITERS)
            tl = target_len * (1.0 + 0.5 * attempt)
            used_pml = _remesh_basin_pymeshlab(pml_env, bm, loop_pts, tl, ISO_PML_ITERS)
            if used_pml:
                break

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mv = bm.verts.layers.int.get("gt_move")   # co the da bi xoa khi PyMeshLab dung lai bm
    if mv is not None:
        bm.verts.layers.int.remove(mv)

    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()

    cutter = bpy.data.objects.new(name, me)
    context.collection.objects.link(cutter)

    # Chi can lam lien tuc them khi DUNG fallback (flip+relax). PyMeshLab da cho mat
    # muot + DEU san; smooth them se keo dinh roi be mat offset, giam do net.
    if not used_pml:
        _smooth_cutter_continuity(context, cutter)

    # Lat normal huong RA NGOAI than (xa tam bbox). Nho the Solidify voi
    # use_flip_normals=False luon day do day VAO TRONG than -> boolean cat sach.
    _orient_faces_outward(cutter, bbox_center)

    # Smooth shading: mat long chao muot, san sang edit/sculpt/freeform.
    for poly in cutter.data.polygons:
        poly.use_smooth = True

    # Solidify len do day Gap. use_flip_normals=False -> day vao trong than object
    # (normal da huong ra ngoai) de boolean DIFFERENCE cat dut, tach 2 manh.
    mod = cutter.modifiers.new(name="Solidify", type='SOLIDIFY')
    mod.solidify_mode = 'NON_MANIFOLD'
    mod.nonmanifold_thickness_mode = 'FIXED'
    mod.thickness = gap
    mod.use_flip_normals = False

    if apply_solidify:
        bpy.ops.object.select_all(action='DESELECT')
        _set_active_object(cutter, context.view_layer)
        _select_object(cutter, True, context.view_layer)
        bpy.ops.object.modifier_apply(modifier=mod.name)

    return cutter


def _apply_cutter_solidify(context, cutter, gap):
    """Cap nhat do day gap roi apply Solidify cho cutter da co (truoc khi boolean)."""
    sol = None
    for m in cutter.modifiers:
        if m.type == 'SOLIDIFY':
            sol = m
            break
    if sol is None:
        sol = cutter.modifiers.new(name="Solidify", type='SOLIDIFY')
        sol.solidify_mode = 'NON_MANIFOLD'
        sol.nonmanifold_thickness_mode = 'FIXED'
        sol.use_flip_normals = False
    sol.thickness = gap
    bpy.ops.object.select_all(action='DESELECT')
    _set_active_object(cutter, context.view_layer)
    _select_object(cutter, True, context.view_layer)
    bpy.ops.object.modifier_apply(modifier=sol.name)


def _mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    vol = abs(bm.calc_volume(signed=True))
    bm.free()
    return vol


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------
def _poll_mesh(self, obj):
    return obj.type == 'MESH'


def _gap_update(self, context):
    """Cap nhat live do day Solidify cua cutter xem truoc khi keo Gap."""
    cutter = self.cutter_object
    if cutter is not None and cutter.name in bpy.data.objects:
        for m in cutter.modifiers:
            if m.type == 'SOLIDIFY':
                m.thickness = self.gap
                break


class GTSplitProps(bpy.types.PropertyGroup):
    target_object: bpy.props.PointerProperty(
        name="Target Object",
        description="Object MESH se duoc ve len va tach (line se tu snap vao be mat object nay)",
        type=bpy.types.Object,
        poll=_poll_mesh,
    )
    line_object: bpy.props.PointerProperty(
        name="Line Object",
        description="Object line dang ve",
        type=bpy.types.Object,
    )
    cutter_object: bpy.props.PointerProperty(
        name="Cutter Object",
        description="Cutter xem truoc (co the chinh sua truoc khi Split)",
        type=bpy.types.Object,
    )
    offset: bpy.props.FloatProperty(
        name="Offset",
        description="Khoang cach mat cat so voi be mat object",
        default=0.3, min=0.0, unit='LENGTH',
    )
    gap: bpy.props.FloatProperty(
        name="Gap",
        description="Do day khe ho giua 2 thanh phan (phai > 0)",
        default=0.1, min=0.0001, unit='LENGTH',
        update=_gap_update,
    )


# ---------------------------------------------------------------------------
# Operator: dat Target Object
# ---------------------------------------------------------------------------
class GTSPLIT_OT_set_target(bpy.types.Operator):
    """Dat object MESH dang active lam Target (line se snap vao be mat object nay)"""
    bl_idname = "object.gtsplit_set_target"
    bl_label = "Chon Target Object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Hay chon mot object MESH lam active truoc")
            return {'CANCELLED'}
        context.scene.gt_split.target_object = obj
        self.report({'INFO'}, "Da dat Target: %s" % obj.name)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: tao line object + vao edit mode de ve
# ---------------------------------------------------------------------------
class GTSPLIT_OT_create_line(bpy.types.Operator):
    """Tao object line bam tren be mat Target va vao Edit Mode de ve (E de extrude diem)"""
    bl_idname = "object.gtsplit_create_line"
    bl_label = "Ve duong cat (tao line)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'}, "Vui long dang ky key de kich hoat su dung")
            return {'CANCELLED'}

        props = context.scene.gt_split
        target = props.target_object
        if target is None or target.type != 'MESH':
            self.report({'ERROR'}, "Hay dat Target Object truoc (nut Chon Target Object)")
            return {'CANCELLED'}

        # Bao dam dang o Object Mode truoc khi tao.
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Xoa line cu neu con.
        if props.line_object is not None and props.line_object.name in bpy.data.objects:
            bpy.data.objects.remove(props.line_object, do_unlink=True)

        # Diem bat dau: vi tri 3D Cursor hien tai, snap ve be mat target.
        cursor_world = context.scene.cursor.location.copy()
        local_cursor = target.matrix_world.inverted() @ cursor_world
        hit, location, _nrm, _idx = target.closest_point_on_mesh(local_cursor)
        start_world = target.matrix_world @ location if hit else cursor_world

        me = bpy.data.meshes.new("GT_Line")
        me.from_pydata([start_world], [], [])
        me.update()

        line = bpy.data.objects.new("GT_Line", me)
        context.collection.objects.link(line)

        # Shrinkwrap giu moi dinh line dung tren be mat Target.
        sw = line.modifiers.new(name="GT_Shrinkwrap", type='SHRINKWRAP')
        sw.target = target
        sw.wrap_method = 'NEAREST_SURFACEPOINT'
        sw.wrap_mode = 'ON_SURFACE'
        sw.show_in_editmode = True
        sw.show_on_cage = True

        props.line_object = line

        viewlayer = context.view_layer
        bpy.ops.object.select_all(action='DESELECT')
        _set_active_object(line, viewlayer)
        _select_object(line, True, viewlayer)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        # Bat snapping Face Project: dinh that duoc chieu len be mat khi extrude.
        _enable_surface_snap(context)

        self.report(
            {'INFO'},
            "Nhan E de extrude diem tiep theo, xoay view tu do. Xong nhan 'Noi diem dau-cuoi'.")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: noi 2 diem dau-cuoi (tuong tu chon 2 diem roi nhan F)
# ---------------------------------------------------------------------------
class GTSPLIT_OT_close_loop(bpy.types.Operator):
    """Noi diem dau va diem cuoi cua line thanh vong kin (tuong tu chon 2 diem + F)"""
    bl_idname = "object.gtsplit_close_loop"
    bl_label = "Noi diem dau-cuoi"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gt_split
        line = props.line_object
        if line is None or line.name not in bpy.data.objects:
            self.report({'ERROR'}, "Chua co line. Hay 'Ve duong cat' truoc.")
            return {'CANCELLED'}

        target = props.target_object
        in_edit = (context.mode == 'EDIT_MESH' and context.edit_object == line)

        if in_edit:
            bm = bmesh.from_edit_mesh(line.data)
            ends = [v for v in bm.verts if len(v.link_edges) == 1]
            if len(ends) != 2:
                self.report({'WARNING'},
                            "Can dung 2 diem dau cuoi (line dang co %d diem ho)" % len(ends))
                return {'CANCELLED'}
            try:
                bm.edges.new((ends[0], ends[1]))
            except ValueError:
                self.report({'INFO'}, "Hai diem da duoc noi san")
                return {'CANCELLED'}
            _snap_bmesh_verts_to_surface(bm, line, target)
            bmesh.update_edit_mesh(line.data)
        else:
            bm = bmesh.new()
            bm.from_mesh(line.data)
            bm.verts.ensure_lookup_table()
            ends = [v for v in bm.verts if len(v.link_edges) == 1]
            if len(ends) != 2:
                bm.free()
                self.report({'WARNING'},
                            "Can dung 2 diem dau cuoi (line dang co %d diem ho)" % len(ends))
                return {'CANCELLED'}
            try:
                bm.edges.new((ends[0], ends[1]))
            except ValueError:
                bm.free()
                self.report({'INFO'}, "Hai diem da duoc noi san")
                return {'CANCELLED'}
            _snap_bmesh_verts_to_surface(bm, line, target)
            bm.to_mesh(line.data)
            bm.free()
            line.data.update()

        self.report({'INFO'}, "Da noi diem dau-cuoi (vong kin), moi diem da bam be mat")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: tao cutter de xem truoc / chinh sua
# ---------------------------------------------------------------------------
class GTSPLIT_OT_create_cutter(bpy.types.Operator):
    """Tao cutter tu vong line de xem truoc va chinh sua (chua cat object)"""
    bl_idname = "object.gtsplit_create_cutter"
    bl_label = "Create Cutter"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'}, "Vui long dang ky key de kich hoat su dung")
            return {'CANCELLED'}

        props = context.scene.gt_split
        target = props.target_object
        if target is None or target.type != 'MESH':
            self.report({'ERROR'}, "Chua co Target Object")
            return {'CANCELLED'}

        line = props.line_object
        if line is None or line.name not in bpy.data.objects:
            self.report({'ERROR'}, "Chua co line. Hay 'Ve duong cat' truoc.")
            return {'CANCELLED'}

        # Ve Object Mode de doc/xu ly an toan.
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        loop_pts, loop_nrms, closed = _processed_margin_loop(context, line, target)
        if not closed:
            self.report({'ERROR'},
                        "Vong chua kin. Hay nhan 'Noi diem dau-cuoi' truoc.")
            return {'CANCELLED'}
        if len(loop_pts) < 3:
            self.report({'ERROR'}, "Can it nhat 3 diem de tao vong kin")
            return {'CANCELLED'}

        # Xoa cutter cu neu con.
        if props.cutter_object is not None and props.cutter_object.name in bpy.data.objects:
            bpy.data.objects.remove(props.cutter_object, do_unlink=True)

        # Giu Solidify dang modifier de co the chinh sua / doi Gap truoc khi Split.
        cutter = _build_cutter(context, target, loop_pts, loop_nrms,
                               props.offset, props.gap,
                               apply_solidify=False, name="GT_Cutter")
        if cutter is None:
            self.report({'ERROR'}, "Khong dung duoc cutter")
            return {'CANCELLED'}

        props.cutter_object = cutter
        viewlayer = context.view_layer
        bpy.ops.object.select_all(action='DESELECT')
        _set_active_object(cutter, viewlayer)
        _select_object(cutter, True, viewlayer)

        if _PYMESHLAB_ENV is not None:
            self.report({'INFO'},
                        "Da tao cutter (luoi min PyMeshLab). Chinh sua/doi Gap roi 'Split Object'.")
        else:
            self.report({'WARNING'},
                        "Da tao cutter voi luoi co ban. Bam 'Cai PyMeshLab' de co luoi min nhu iBar.")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: thuc hien cat -> Gingiva / Teeth
# ---------------------------------------------------------------------------
class GTSPLIT_OT_execute_cut(bpy.types.Operator):
    """Tach Target thanh Gingiva / Teeth bang cutter (tu cutter da tao hoac tu line)"""
    bl_idname = "object.gtsplit_execute_cut"
    bl_label = "Split Object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'}, "Vui long dang ky key de kich hoat su dung")
            return {'CANCELLED'}

        props = context.scene.gt_split
        target = props.target_object
        if target is None or target.type != 'MESH':
            self.report({'ERROR'}, "Chua co Target Object")
            return {'CANCELLED'}

        gap = props.gap
        if gap <= 0:
            self.report({'ERROR'}, "Gap phai > 0")
            return {'CANCELLED'}

        # Ve Object Mode de doc/xu ly an toan.
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Uu tien cutter da tao (xem truoc/chinh sua); neu chua co thi dung tu line.
        cutter = props.cutter_object
        if cutter is not None and cutter.name in bpy.data.objects:
            _apply_cutter_solidify(context, cutter, gap)
        else:
            line = props.line_object
            if line is None or line.name not in bpy.data.objects:
                self.report({'ERROR'},
                            "Chua co cutter/line. Hay 'Ve duong cat' & 'Create Cutter' truoc.")
                return {'CANCELLED'}

            loop_pts, loop_nrms, closed = _processed_margin_loop(context, line, target)
            if not closed:
                self.report({'ERROR'},
                            "Vong chua kin. Hay nhan 'Noi diem dau-cuoi' truoc khi tach.")
                return {'CANCELLED'}
            if len(loop_pts) < 3:
                self.report({'ERROR'}, "Can it nhat 3 diem de tao vong kin")
                return {'CANCELLED'}

            cutter = _build_cutter(context, target, loop_pts, loop_nrms,
                                   props.offset, gap, apply_solidify=True)
            if cutter is None:
                self.report({'ERROR'}, "Khong dung duoc cutter")
                return {'CANCELLED'}

        viewlayer = context.view_layer

        # Boolean DIFFERENCE (giong pattern add-on iBar).
        boolean = target.modifiers.new(name="GT_Boolean", type='BOOLEAN')
        boolean.object = cutter
        boolean.operation = 'DIFFERENCE'
        try:
            boolean.solver = 'EXACT'
        except Exception:
            pass
        bpy.ops.object.select_all(action='DESELECT')
        _set_active_object(target, viewlayer)
        _select_object(target, True, viewlayer)
        bpy.ops.object.modifier_apply(modifier="GT_Boolean")

        # Xoa cutter.
        bpy.data.objects.remove(cutter, do_unlink=True)
        props.cutter_object = None

        # Separate by LOOSE.
        before = set(context.scene.objects)
        _set_active_object(target, viewlayer)
        bpy.ops.object.select_all(action='DESELECT')
        _select_object(target, True, viewlayer)
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.editmode_toggle()
        after = set(context.scene.objects)

        pieces = list((after - before)) + [target]
        pieces = [o for o in pieces if o.name in context.scene.objects and o.type == 'MESH']

        if len(pieces) < 2:
            self.report({'ERROR'},
                        "Vong line chua xuyen het be day object. Hay tang Gap hoac ve lai vong.")
            return {'CANCELLED'}

        # Tinh the tich, sap xep, giu 2 manh lon nhat.
        vols = [(o, _mesh_volume(o)) for o in pieces]
        vols.sort(key=lambda x: x[1], reverse=True)
        total = sum(v for _o, v in vols) or 1.0

        kept = vols[:2]
        scrap = vols[2:]
        removed = 0
        for o, v in scrap:
            if v < 0.01 * total:
                bpy.data.objects.remove(o, do_unlink=True)
                removed += 1

        # kept[0] = lon nhat -> Teeth ; kept[1] = nho hon -> Gingiva
        teeth_obj, _tv = kept[0]
        gingiva_obj, _gv = kept[1]
        teeth_obj.name = "Teeth"
        gingiva_obj.name = "Gingiva"

        # Don dep line + khoi phuc cai dat snap cua nguoi dung.
        if props.line_object is not None and props.line_object.name in bpy.data.objects:
            bpy.data.objects.remove(props.line_object, do_unlink=True)
        props.line_object = None
        _restore_snap(context)

        msg = "Da tach: Teeth + Gingiva (%d manh)." % len(pieces)
        if removed:
            msg += " Da xoa %d manh vun." % removed
        if len(scrap) - removed > 0:
            msg += " Con %d manh dang ke khong duoc gan ten." % (len(scrap) - removed)
            self.report({'WARNING'}, msg)
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: xoa line hien tai
# ---------------------------------------------------------------------------
class GTSPLIT_OT_clear(bpy.types.Operator):
    """Xoa object line dang ve"""
    bl_idname = "object.gtsplit_clear"
    bl_label = "Xoa duong cat"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gt_split
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        removed_any = False
        if props.cutter_object is not None and props.cutter_object.name in bpy.data.objects:
            bpy.data.objects.remove(props.cutter_object, do_unlink=True)
            props.cutter_object = None
            removed_any = True

        line = props.line_object
        if line is not None and line.name in bpy.data.objects:
            bpy.data.objects.remove(line, do_unlink=True)
            props.line_object = None
            removed_any = True

        _restore_snap(context)
        if removed_any:
            self.report({'INFO'}, "Da xoa line / cutter")
        else:
            self.report({'INFO'}, "Khong co line/cutter de xoa")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: cai PyMeshLab (luoi cutter min nhu iBar) - co canh bao + chay nen
# ---------------------------------------------------------------------------
class GTSPLIT_OT_install_pymeshlab(bpy.types.Operator):
    """Cai PyMeshLab de tao luoi cutter MIN, DEU nhu iBar (chay nen, ~100MB)"""
    bl_idname = "object.gtsplit_install_pymeshlab"
    bl_label = "Cai PyMeshLab (luoi min)"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        # Hien hop thoai CANH BAO TRUOC khi cai -> nguoi dung khong bo ngo.
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text="Se tai & cai PyMeshLab (~100MB) cho luoi cutter", icon='INFO')
        col.label(text="MIN, DEU nhu iBar (khong rang cua).")
        col.separator()
        col.label(text="- Can ket noi Internet.", icon='WORLD')
        col.label(text="- Cai chay NEN, Blender van dung duoc; co the", icon='SORTTIME')
        col.label(text="  mat vai phut. Theo doi thanh trang thai ben duoi.")
        col.label(text="- Nhan OK de bat dau, hoac Cancel de bo qua", icon='CHECKMARK')
        col.label(text="  (van tao cutter duoc voi luoi co ban).")

    def execute(self, context):
        import threading
        self._result = None
        self._timer = None

        def _work():
            self._result = _install_pymeshlab_blocking()

        self._thread = threading.Thread(target=_work, daemon=True)
        self._thread.start()
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)
        try:
            context.workspace.status_text_set(
                "Dang cai PyMeshLab... vui long doi, dung tat Blender")
        except Exception:
            pass
        self.report({'INFO'}, "Bat dau cai PyMeshLab (chay nen)...")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'RUNNING_MODAL'}
        if self._result is None:
            return {'RUNNING_MODAL'}     # van dang cai
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None
        try:
            context.workspace.status_text_set(None)
        except Exception:
            pass
        ok, msg = self._result
        if ok:
            self.report({'INFO'},
                        "Da cai PyMeshLab. Tu gio cutter se co luoi min nhu iBar.")
        else:
            self.report({'WARNING'},
                        "Cai PyMeshLab that bai (van dung luoi co ban). " + (msg or ""))
        # Cap nhat lai panel.
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
class GTSPLIT_PT_panel(bpy.types.Panel):
    bl_label = "Gingiva / Teeth Split"
    bl_idname = "OBJECT_PT_gtsplit"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "IBAR Split"

    def draw(self, context):
        layout = self.layout
        props = context.scene.gt_split

        # 1) Target Object - nut doi ten thanh ten Target khi da chon.
        box = layout.box()
        box.label(text="1. Target Object", icon='OBJECT_DATA')
        target = props.target_object
        if target is not None and target.name in bpy.data.objects:
            box.operator(GTSPLIT_OT_set_target.bl_idname,
                         text=target.name, icon='RESTRICT_SELECT_OFF')
        else:
            box.operator(GTSPLIT_OT_set_target.bl_idname,
                         text="Chon Target Object", icon='EYEDROPPER')

        # 2) Ve line.
        box = layout.box()
        box.label(text="2. Ve duong cat", icon='GREASEPENCIL')
        col = box.column(align=True)
        row = col.row()
        row.enabled = target is not None
        row.operator(GTSPLIT_OT_create_line.bl_idname, text="Ve duong cat (tao line)",
                     icon='GREASEPENCIL')

        line = props.line_object
        has_line = line is not None and line.name in bpy.data.objects
        col.label(text="Diem dau = vi tri 3D Cursor", icon='PIVOT_CURSOR')
        col.label(text="Edit Mode: E them diem (da bat snap be mat)", icon='INFO')
        sub = col.column(align=True)
        sub.enabled = has_line
        sub.operator(GTSPLIT_OT_close_loop.bl_idname, text="Noi diem dau-cuoi (F)",
                     icon='MESH_CIRCLE')
        sub.operator(GTSPLIT_OT_clear.bl_idname, text="Xoa line / cutter", icon='X')

        cutter = props.cutter_object
        has_cutter = cutter is not None and cutter.name in bpy.data.objects

        # 3) Tao cutter (xem truoc + chinh sua).
        box = layout.box()
        box.label(text="3. Create Cutter (xem truoc)", icon='MOD_SOLIDIFY')
        box.prop(props, "offset")
        row = box.row()
        row.enabled = has_line and target is not None
        row.operator(GTSPLIT_OT_create_cutter.bl_idname, text="Create Cutter",
                     icon='MOD_SOLIDIFY')
        if has_cutter:
            box.label(text="Cutter san sang - co the chinh sua", icon='CHECKMARK')

        # Trang thai PyMeshLab (luoi min nhu iBar). Chi DOC cache (khong chay
        # subprocess trong draw). Kiem tra that su xay ra o Create Cutter.
        if _PYMESHLAB_ENV is not None:
            box.label(text="Luoi min: PyMeshLab da san sang", icon='CHECKMARK')
        elif _PYMESHLAB_TRIED:
            box.label(text="Dang dung luoi co ban (chua co PyMeshLab)", icon='INFO')
            box.operator(GTSPLIT_OT_install_pymeshlab.bl_idname,
                         text="Cai PyMeshLab (luoi min nhu iBar)", icon='IMPORT')
        else:
            box.operator(GTSPLIT_OT_install_pymeshlab.bl_idname,
                         text="Cai PyMeshLab (luoi min nhu iBar)", icon='IMPORT')

        # 4) Chon Gap + Split.
        box = layout.box()
        box.label(text="4. Split Object", icon='MOD_BOOLEAN')
        box.prop(props, "gap")
        row = box.row()
        row.enabled = (has_cutter or has_line) and target is not None
        row.operator(GTSPLIT_OT_execute_cut.bl_idname, text="Split Object",
                     icon='MOD_BOOLEAN')


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
_classes = [
    GTSplitProps,
    GTSPLIT_OT_set_target,
    GTSPLIT_OT_create_line,
    GTSPLIT_OT_close_loop,
    GTSPLIT_OT_create_cutter,
    GTSPLIT_OT_execute_cut,
    GTSPLIT_OT_clear,
    GTSPLIT_OT_install_pymeshlab,
    GTSPLIT_PT_panel,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.gt_split = bpy.props.PointerProperty(type=GTSplitProps)
    # Kiem tra trang thai PyMeshLab o luong nen -> panel hien dung ngay tu dau ma
    # KHONG lam dung Blender (khong chay subprocess trong main thread / draw).
    # Warm cache thu muc modules tren MAIN thread truoc -> luong nen khong dung bpy.
    try:
        import threading
        _pml_modules_dir()
        threading.Thread(target=_pymeshlab_ready, daemon=True).start()
    except Exception:
        pass


def unregister():
    if hasattr(bpy.types.Scene, "gt_split"):
        del bpy.types.Scene.gt_split
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


if __name__ == "__main__":
    register()
