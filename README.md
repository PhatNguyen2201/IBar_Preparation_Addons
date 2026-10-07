# IBar Preparation Addon

Blender addon dành cho thiết kế khung xương hàm giả (iBar) trong nha khoa. Addon cung cấp bộ công cụ toàn diện để chuẩn bị, căn chỉnh, tạo khung và xuất các mô hình 3D phục vụ cho quy trình sản xuất khung xương hàm.

## 📋 Yêu cầu hệ thống

- **Blender**: 4.5.3 trở lên (đã kiểm chứng trên Blender 5.2 LTS)
- **Hệ điều hành**: Windows, **Ubuntu/Linux** và macOS cho phần cài đặt; riêng Hardware ID của iBar vẫn dùng cơ chế Windows API và có dự phòng theo MAC/hostname trên Linux/macOS
- **Python**: 3.8+ (để chạy script cài đặt; bản thân add-on dùng Python tích hợp trong Blender)

## 🚀 Cài đặt

### Cách 1 — Script cài tự động (khuyên dùng)

Script `install_addons.py` cài **4 add-on**: `Final_addon_Ibar_to_ORG.py`,
`Gingiva_Teeth_Splitter.py`, `dental_lib.py`, `rmvb_bar.py`
(thứ tự bật *Dental-Lib trước Rmvb-Bar* vì Rmvb-Bar import Dental-Lib).

Script sẽ: dò mọi profile Blender đã từng chạy → copy file vào
`scripts/addons` của bản được chọn → gọi `blender --background` để bật add-on
và lưu preferences → in trạng thái từng module.

| Hệ điều hành | Lệnh |
|---|---|
| Windows | double-click `install_addons.bat` hoặc `python install_addons.py` |
| Ubuntu / Linux | `./install_addons.sh` (hoặc `python3 install_addons.py`) |
| macOS | `python3 install_addons.py` |

Tuỳ chọn (dùng được trên cả 3 hệ điều hành):

```text
--list                 liệt kê profile + đường dẫn blender tìm thấy
--all                  cài cho mọi phiên bản, không hỏi
--versions 5.2 5.1     chỉ cài các phiên bản liệt kê
--no-enable            chỉ copy file, không tự bật add-on
--skip-license         không sinh file ~/addon_ibar.key
--no-pause             không chờ nhấn Enter (dùng cho .sh / CI)
```

Ví dụ trên Ubuntu:

```bash
cd IBar_Preparation_Addons
./install_addons.sh --list          # xem máy đang có bản Blender nào
./install_addons.sh --all           # cài cho tất cả
./install_addons.sh --versions 5.2  # chỉ cài 5.2
```

Blender được dò từ `PATH`, `/snap/bin/blender` (bản snap), `/usr/bin/blender`,
`/opt/blender*/blender`, Steam và `flatpak run org.blender.Blender`.
Vị trí profile:

| HĐH | Thư mục add-on |
|---|---|
| Windows | `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons` |
| Ubuntu/Linux | `~/.config/blender/<version>/scripts/addons` |
| macOS | `~/Library/Application Support/Blender/<version>/scripts/addons` |

Nếu script không tự bật được add-on, mở Blender → Edit → Preferences → Add-ons
→ tìm **Dental-Lib** / **Rmvb-Bar** rồi tick thủ công.

### Cách 2 — Cài thủ công

1. Mở Blender → Edit → Preferences → Add-ons
2. Nhấn **Install...** và chọn từng file `.py` (bật `dental_lib.py` trước `rmvb_bar.py`)
3. Tick checkbox để kích hoạt

## 📖 Chức năng chính

### 1. IBar Function Prepare

| Nút chức năng | Mô tả |
|---|---|
| **Check Update** | Kiểm tra phiên bản mới trên GitHub |
| **Update** | Cập nhật addon từ GitHub tự động |
| **Select STLs** | Chọn nhiều file STL để import |
| **Import all STL** | Import tất cả file STL trong thư mục project |
| **Join** | Hợp nhất các object được chọn |
| **Separate** | Tách object thành các phần riêng lẻ |
| **Set Object ORG** | Đặt đối tượng gốc (ORG) làm tham chiếu tọa độ |

### 2. Occlusal Alignment (Căn chỉnh hàm)

| Nút chức năng | Mô tả |
|---|---|
| **Molar Q1-3 Point (Red)** | Tạo điểm cầu đỏ tại vị trí cursor cho răng hàm số 1-3 (quai hàm trên) |
| **Central Incisor Point (Green)** | Tạo điểm cầu xanh lá tại điểm giữa răng cửa |
| **Molar Q2-4 Point (Blue)** | Tạo điểm cầu xanh dương cho răng hàm số 2-4 (quai hàm dưới) |
| **Align to OcclusalPlane** | Căn chỉnh đối tượng theo mặt phẳng hàm sử dụng 3 điểm trên |
| **Save Transform Info** | Lưu thông tin transform vào file `transform.txt` |
| **Offset Transform Object** | Dịch chuyển đối tượng từ ORG sang vị trí hiện tại |

**Cơ chế căn chỉnh hàm:**
- Sử dụng 3 điểm (Left Molar, Incisor, Right Molar) để tính toán mặt phẳng hàm (Occlusal Plane)
- Chuyển đổi ma trận 4x4 từ 3 điểm thành ma trận xoay và dịch chuyển
- Tự động tính toán vector chuẩn từ 3 điểm tạo thành mặt phẳng

### 3. IBar Custom Function

| Nút chức năng | Mô tả |
|---|---|
| **Cursor to Object** | Di chuyển 3D cursor đến đối tượng được chọn |
| **Clean other mesh** | Xóa tất cả mesh ngoại trừ object "Models" |
| **Create Tubes Automatically** | Tự động tạo tubes dựa trên file `.constructionInfo` và `.xml` |
| **Create Framework thickness** | Tạo framework **1 lớp** từ Waxup design: Remesh kín rồi offset bề mặt theo ô **Dày** (không dùng Solidify nên không còn 2 lớp ngoài–trong) |

**Tạo Tubes tự động:**
- Đọc file `.constructionInfo` (XML format) để lấy thông tin implant
- Đọc file `ImplantDirectionPosition*.xml` để lấy hướng implant
- Tạo đường cong 3 điểm (Start-Middle-End) cho mỗi implant
- Áp dụng skin và subdivision surface để tạo ống 3D
- Tự động căn chỉnh theo vị trí và hướng implant

**Lỗ ốc nghiêng (Screw Angle):**
- exocad không ghi góc nghiêng vào constructionInfo (`AxisScrew` trùng `AxisImplant`). Vì vậy add-on đo hướng lỗ ốc trực tiếp trên STL thiết kế đang có trong scene.
- Cách đo: cắt lưới liên tiếp phía trên `ScrewChannelStart`, bám theo tâm lỗ tới miệng lỗ, rồi fit trục.
- Lỗ nghiêng trên 2°: bẻ tube tại điểm bắt đầu kênh nghiêng, đầu **Start** đi theo hướng lỗ. Phần trên được phóng to để bao trọn tiết diện lỗ, kể cả lỗ oval, với khe hở 0.3 mm.
- Giữ nguyên cạnh End→Middle và bán kính End/Middle, để Cone và Selector của iBar không đổi. Chỉ thêm 1 đỉnh giữa Middle và Start.
- Không tìm thấy STL có lỗ ốc: tube giữ thẳng như cũ và có cảnh báo. Nếu constructionInfo có ghi `AxisScrew` nghiêng thì dùng hướng đó.

### 4. Object Control (Điều khiển đối tượng)

| Nhóm | Nút Set | Nút Show | Nút Hide |
|---|---|---|---|
| **Gingiva** | Đặt màu hồng nhạt cho đối tượng | Hiển thị Gingiva | Ẩn Gingiva |
| **Antagonist** | Đặt màu xám cho đối tượng | Hiển thị Antagonist | Ẩn Antagonist |
| **Screws** | Đặt màu tối + căn giữa khối lượng | Hiển thị Screws | Ẩn Screws |
| **Preop** | Đặt màu xanh lá cho đối tượng | Hiển thị Preop | Ẩn Preop |
| **Hybrid** | - | Hiển thị Hybrid | Ẩn Hybrid |
| **Bar** | - | Hiển thị Bar (iBar) | Ẩn Bar (iBar) |
| **Bar Thick** | - | Hiển thị độ dày khung | Ẩn độ dày khung |

**Select basic bar area:**

| Nút | Mô tả |
|---|---|
| **Select top** | Chọn vùng đỉnh thanh bar |
| **Select extrude** | Chọn vùng cần extrude |
| **Select flat** | Chọn vùng phẳng |
| **Select margin** | Chọn vùng margin |
| **Bevel extrude area** | Tạo bevel cho vùng extrude (offset 0.75, 3 segments) |

### 5. IBar Retention

| Nút chức năng | Mô tả |
|---|---|
| **Add Retention** | Tạo retention cube tại 3D cursor |
| **Cut on Cutter** | Boolean difference retention lên CUTTER |
| **Cut on Bar** | Boolean difference retention lên iBar |

**Cơ chế Retention:**
- Tạo cube với vertex groups: Top, Bottom, Extrude, Flat, MARGIN
- Resize Top (1.7x), resize Bottom với bevel 128 segments
- Boolean modifier để cắt retention vào thanh bar

### 6. IBar Save STL

| Nút chức năng | Mô tả |
|---|---|
| **STL only** | Export STL các đối tượng chính (Hybrid_Shell, iBar, Closed_Bar) |
| **Save All STL** | Export tất cả mesh trong scene |
| **Save STL by Part** | Export từng phần theo ConstructionInfo, tự động đặt tên với PartName và PatientName |

**Mesh size guard:**
- Tự động kiểm tra STL của `Hybrid`, `Hybrid_Shell*`, `iBar`, `iBar_*` khi export.
- Nếu file vượt 30 MB, addon tạo mesh tạm, giảm tam giác bằng Decimate và chỉ thay file đích khi STL mới <= 30 MB.
- Mesh gốc trong scene không bị thay đổi.

**Save STL by Part:**
- Transform về ORG trước khi xuất
- Đổi tên object theo format: `{PartName}_{PatientFirstName}`
- Đổi tên file STL khớp với tên object mới
- Tạo file `.constructionInfo` mới với tên file STL cập nhật

## 🔐 Xác thực & License

### Hardware ID
- Sử dụng Windows Machine GUID + MAC Address + Hostname + Processor để tạo Hardware ID
- Hash SHA-256, lưu 32 ký tự đầu vào file `.ibar_machine_id` trong thư mục user
- Fallback sử dụng MAC address nếu không truy cập được registry

### License Key
- File license: `addon_ibar.key` trong thư mục user (~)
- Format: Hash SHA-512 của Hardware ID nhân đôi
- Nếu không có file, tự động tạo `IbarPrep.hwid` trên Desktop

## 🔄 Auto-Update từ GitHub

### Cơ chế
- Tự động kiểm tra update sau 5 giây khi khởi động addon
- So sánh version trong `bl_info["version"]` với remote
- Tự động download source từ GitHub API
- Backup file cũ thành `.bak` trước khi cập nhật
- Thông báo cần reload addon sau khi cập nhật thành công

### GitHub Repository
- **Owner**: PhatNguyen2201
- **Repo**: IBar_Preparation_Addons
- **Branch**: main (fallback: master)
- **File**: Final_addon_Ibar_to_ORG.py

### Manual Update
- Nút "Check Update" trong panel: so sánh version, hiển thị thông báo
- Nút "Update" trong panel: tự động cập nhật lên version mới nhất

## 📁 File output

| File | Mô tả |
|---|---|
| `before.txt` | Lưu ma trận 4x4 của ORG object |
| `transform.txt` | Lưu ma trận 4x4 của transform hiện tại |
| `*.stl` | File STL xuất từ các đối tượng |
| `*.constructionInfo` | File XML thông tin construction, cập nhật tên file STL |
| `{ObjectName}.bak` | Backup file trước khi update addon |

## 📐 Công thức tính toán

### Ma trận từ 3 điểm (Occlusal Plane)
```
AveragePoint = (P1 + P2 + P3) / 3
Vector1 = P2 - P1
Vector2 = P3 - P2
Vector3 = P1 - P3
ZVector = Cross(Vector2, Vector1)
YVector = Cross(ZVector, Vector3)
XVector = Cross(YVector, ZVector)
Normalise tất cả vectors
Matrix = [[X, Y, Z, AveragePoint], [...], [...], [...], [0, 0, 0, 1]]
```

### Xử lý hướng implant từ ConstructionInfo
- Phân tích `MatrixImplantGeometry` và `AxisImplant`
- So sánh các cột ma trận với trục implant để xác định hướng (X, Y, Z hoặc -X, -Y, -Z)
- Tính rotation: X và Y theo hướng implant (radian)
- Z luôn = 0 (không xoay theo trục Z)

## 📝 Quy trình làm việc điển hình

1. **Import STL**: Import các file STL từ file design
2. **Set ORG**: Chọn đối tượng Models và Set Object ORG
3. **Căn chỉnh hàm**:
   - Đặt 3 điểm (Molar Q1-3, Incisor, Molar Q2-4)
   - Align to OcclusalPlane
   - Save Transform Info
4. **Offset Transform**: Dịch chuyển đối tượng về vị trí hiện tại
5. **Tạo Tubes**: Create Tubes Automatically từ ConstructionInfo
6. **Tạo Framework**: Create Framework thickness
7. **Tạo Retention**: Add Retention, Cut on Bar
8. **Xuất STL**: Save STL by Part hoặc Save All STL

## 🏷️ Thông tin

- **Tác giả**: Phat Nguyen
- **Tên**: Custom Ibar Preparation Panel
- **Category**: iBar Preparation Panel
- **Vị trí**: View3D Panel (sidebar)

## 🔄 Lịch sử cập nhật

Dưới đây là lịch sử các thay đổi dựa trên Git commit history:

| Commit | Ngày | Mô tả thay đổi |
|---|---|---|
| `pending` | 07/10/2026 | Rmvb-Bar v0.4.6 (Enable / Disable Preview tính cả modifier CutBase; Add Attachment luôn đưa Preview về Disable; Apply Bar Design cảnh báo theo số modifier CutBase / Attachment đang tắt); Dental-Lib v0.1.7 (tooltip); v0.4.5 (modifier Attachment thêm ngay khi Add Attachment; Enable / Disable Preview chỉ bật / tắt Realtime Display in Viewport + ẩn / hiện Part Bar, Part Sleeve); Dental-Lib v0.1.6 (tooltip); v0.4.4 (Enable Preview ẩn Part Bar / Part Sleeve, Disable Preview hiện lại); v0.4.3 (nút Apply Attachment on Bar thay bằng 2 nút Enable Preview / Disable Preview, Apply Bar Design cảnh báo khi Preview đang tắt); Dental-Lib v0.1.5 (tooltip); Rmvb-Bar v0.4.2 (Sleeve chỉ còn 1 lớp màu vàng nhạt, opacity 0.5 thay vì nhiều slot material cộng dồn từ Boolean); v0.4.1 (Sleeve đẹp hơn: nguồn là Bar chưa cắt nướu, thêm lớp Remesh Voxel dùng riêng cho Sleeve + thuộc tính `Remesh voxel`, nới bằng khối sạch rồi lấy khối ngoài − khối trong, cắt nướu ở bước cuối với mesh đã tam giác hoá; trên scan thật: tam giác xấu 24 % → 4 %, tự giao cắt 1800 → 18, STL xuất ra kín 0 cạnh lỗi; v0.4.0 là bản Remesh trước khi sửa STL); v0.3.11 (Sleeve lấy theo bề mặt Bar sau Union Pillar, chưa áp Base / Attachment, vẫn cắt nướu); v0.3.10 (mỗi implant là một nhóm Plain Axes Implant_<răng> chứa Base / ConnectionVisual / Analog / Screw / Scanbody / Bar Pillar); v0.3.9 (Set Gingiva luôn tạo khối kín + manifold: sửa điểm thắt nút / mảnh rác / đỉnh chưa gộp, nhiều mảnh; Boolean cắt bar không còn bị Manifold từ chối); v0.3.8 (Cut Top Bar tự ẩn Bar Pillar + ConnectionVisual; đế Gingiva là mặt phẳng Oxy cách điểm thấp nhất của vành hở 10 mm); v0.3.7 (Select Top theo object Bar Pillar đang chọn, bỏ combobox Vị trí implant); v0.3.6 (Gingiva: extrude đáy −10 mm theo Z world thay vì local); v0.3.5 (ẩn Base, thêm ConnectionVisual xám, luôn đặt Analog xanh lam / Screw xám 0.8 / Scanbody ẩn trong 1 collection, bỏ checkbox đặt kèm); v0.3.4 (Place Connection đọc before/transform.txt để đặt đúng vị trí, Save xuất về toạ độ file gốc); v0.3.3 (combobox Vị trí implant cho Select Top); v0.3.2 (Lock Rotation với Top Bar chỉ khóa X/Y, Z tự do; file cũ tự nâng cấp); v0.3.1 (PlaneVisual và PlaneCubeCut 100 mm, Plane bản cũ tự phóng to); v0.3.0 (Create Top Bar Plane lên đầu, line vẽ trên PlaneVisual chỉ với 1 modifier Shrinkwrap, Bar Segment tự tạo/tự cập nhật theo line-Plane-mũi tên, bỏ nút Create Bar Segment/Nối đầu-cuối/Edit Bar Segment/khe hở Gingiva); v0.2.2 (thêm Lock Rotation với Top Bar; bấm mục danh sách Attachment chọn Plain Axes + công cụ Move; Lock Z không còn parent vào Plane); v0.2.1 (combobox Connection/Attachment chuyển sang menu thả xuống + operator, sửa lỗi không đổi được lựa chọn); v0.2.0: Set thay Import, Gingiva thành khối, Base chuẩn bị Boolean, Pillar từ vòng hở đáy, line theo thuật toán Splitter, Top Bar hình bình hành + mũi tên hướng lắp, Attachment theo group, Apply/Delete Bar Design; Dental-Lib v0.1.4 (tooltip) |
| `pending` | 29/09/2026 | Create Tubes: tube đi theo lỗ ốc nghiêng đo từ STL, phóng to đầu top bao trọn lỗ ốc (v2.9.1) |
| `pending` | 28/09/2026 | Thêm 2 add-on mới Dental-Lib + Rmvb-Bar (thiết kế bar implant) và script cài đặt đa nền tảng (Ubuntu/macOS) |
| `pending` | 24/06/2026 | Add mesh size guard for Hybrid/iBar STL export over 30 MB |
| `3328b14` | 03/06/2026 | Fix ViewLayer object activation safety - Sửa lỗi kích hoạt object trong ViewLayer |
| `d0a2ede` | 02/06/2026 | Add empty 4Implants vertex group - Thêm vertex group rỗng cho 4 implants |
| `14b2c22` | 26/05/2026 | Gộp LoadConstructionInfo vào CreateTubes và thêm auto-update khi khởi động |
| `eb6686c` | 02/04/2026 | Tăng số lượng mesh của retentioncube |
| `7525951` | 26/03/2026 | Sửa lỗi tên object Blender nhiều hơn 64 ký tự |
| `0a2f80a` | 26/03/2026 | Rename Output STL với PatientName |
| `76ac47e` | 26/03/2026 | Save file với Object Name Hybrid_Shell |
| `14c2c41` | 14/03/2026 | Cải thiện thuật toán HardwareID |
| `35b8cd9` | 14/03/2026 | Fix bug Cut Retention |
| `d7b1190` | 13/03/2026 | Improve updater với GitHub API discovery và branch fallback |
| `0017646` | 13/03/2026 | Add Blender addon auto-update từ GitHub |

## 🦷 Add-on mới: Dental-Lib & Rmvb-Bar (Bar Design)

Hai add-on độc lập với iBar panel, phục vụ quy trình thiết kế khung bar implant.

### `dental_lib.py` — Dental-Lib (thư viện dùng chung)

Tab **Dental-Lib** trong Sidebar (N). Dữ liệu lưu bền trong
`<thư mục thư viện>/library.json`, mesh được copy vào
`connections/<Tên>/` và `attachments/<Tên>/` nên thư viện mang sang máy khác được.

| Mục | Trường |
|---|---|
| **Implant Connection** | Library Name, Base (STL/PLY), Implant-Analog, Screw, Scanbody |
| **Attachment** | Attachment Name, toggle *Add/Remove on Bar* + Apply Part Bar, toggle *Add/Remove on Sleeve* + Apply Part Sleeve, Visual Objects (không giới hạn số lượng, đặt tên từng object) |

API cho add-on khác: `dental_lib.connection_names()`, `get_connection(name)`,
`connection_asset(name, slot)`, `attachment_names()`, `get_attachment(name)`,
`attachment_asset(name, slot)`, `attachment_visuals(name)`.

### `rmvb_bar.py` — Rmvb-Bar

Tab **Rmvb-Bar** trong Sidebar. Quy trình: Set → Connection → Bar Pillar →
Create Top Bar Plane → Draw Line Bar → (Bar Segment tự cập nhật) → Cut Top Bar → Attachment → Sleeve → Save. Mọi bước trên Bar Segment
chỉ **thêm modifier** (không apply) cho tới khi bấm *Apply Bar Design*.

| Nhóm | Nút | Hành vi |
|---|---|---|
| Set | Set Gingiva / Denture / Antagonist | Không còn Import: chọn object mesh có sẵn rồi bấm Set. Gingiva màu hồng (opacity 0.5), Denture xanh lá (0.5), Antagonist nâu (1). **Gingiva được chuẩn bị thành khối kín**: fill các lỗ nhỏ mặt trên, extrude vòng hở lớn nhất (mặt dưới) xuống **một mặt phẳng song song Oxy (world) cách điểm thấp nhất của vành hở đúng 10 mm** (mọi điểm đã extrude cùng Z, XY giữ nguyên, không phụ thuộc xoay/scale của object) rồi fill tạo đế phẳng; nếu mặt hở quay lên +Z thì Set Gingiva cảnh báo. **Làm sạch trước khi tạo khối** (nguyên nhân Boolean cắt bar lỗi): gộp đỉnh trùng, xoá điểm thắt nút ở vành / cạnh >2 mặt / đỉnh rời, bỏ mảnh rác nhỏ (<1% mảnh lớn nhất), mỗi mảnh lớn được extrude riêng về cùng mặt phẳng đế; sau đó kiểm tra lại khối **kín + manifold** (không còn cạnh hở) và báo số cặp tam giác còn tự giao nhau do nếp cuộn của scan |
| Connection | Select Connection Base (menu thả xuống từ Dental-Lib) + Place Connection | Đặt Base theo `MatrixImplantGeometry`. Mỗi Base được chuẩn bị: vùng hở đáy **extrude −2 mm, scale local ×2**; vùng hở đỉnh (Screw) **extrude +30 mm**; nắp kín 2 đầu + Flip Normal (normal ra ngoài) để làm khối Boolean. Base này **bị ẩn** (chỉ làm operand Boolean, vẫn cắt bình thường). Hiển thị bằng `ConnectionVisual_<răng>` lấy đúng hình Base gốc trong thư viện (xám 0.5, opacity 1). Luôn đặt cả **Analog** (xanh lam, opacity 1), **Screw** (xám 0.3, opacity 0.8) và **Scanbody** (ẩn); tất cả nằm chung collection `Rmvb Connections`, không còn checkbox 'Đặt kèm Analog / Screw / Scanbody'. **Mỗi implant là một nhóm Plain Axes `Implant_<răng>`** (giống cách Attachment được add): Base, ConnectionVisual, Analog, Screw, Scanbody và `BarPillar_<răng>` đều là con của Empty đó với toạ độ local đơn vị, nên kéo/xoay Plain Axes là cả nhóm di chuyển theo (Boolean của Bar Segment tự tính lại). Khi bật **Transform theo before/transform.txt** (mặc định), Place Connection đọc `before.txt` + `transform.txt` do add-on iBar ghi (thư mục chứa constructionInfo, nếu không có thì thư mục file `.blend`) và đặt implant bằng `M = transform @ before⁻¹ @ implant` (giống *Create Tubes* / *Offset from ORG to current* của iBar). Không thấy đủ 2 file hoặc file hỏng thì đặt theo toạ độ file như cũ và báo cảnh báo; tên file không phân biệt hoa/thường |
| Connection | Clear Connection | Xoá Base + Bar Pillar đã đặt để chọn lại constructionInfo |
| Bar Pillar | Create Bar Pillar | Chỉ lấy **vùng hở đáy (Connection)**: sao chép vòng điểm gốc của Base ra object `BarPillar_<răng>`, extrude lên `Extrude lên` mm (mặc định 7) theo local Z, fill kín đáy + đỉnh → solid manifold |
| Bar Pillar | Edit / Select Top / Exit | **Select Top**: chọn trực tiếp object `BarPillar_<răng>` trong viewport (một hoặc nhiều Pillar) rồi bấm Select Top → các Pillar đó vào Edit Mode (Transform Orientation Local) và chỉ chọn các đỉnh ở đỉnh mũi extrude; Pillar active giữ nguyên, Pillar không được chọn bị bỏ chọn đỉnh. Chưa chọn Pillar nào (hoặc chọn object khác) thì báo lỗi. Combobox Vị trí implant đã bỏ |
| Bar Segment | **Create Top Bar Plane** (bước đầu tiên) | Tạo trong collection `CutPlane`: `PlaneVisual` 100 mm (xanh dương, opacity 0.4) và `PlaneCubeCut` (plane 100 mm extrude +100 mm = khối lập phương, opacity 0.5, **ẩn**, parent theo PlaneVisual); đặt ở đỉnh Bar Pillar. **Mũi tên hướng lắp** (`InsertionArrow`, Empty mũi tên Z+) cũng hiện ở bước này, xoay nó để đổi hướng lắp |
| Bar Segment | Draw Line Bar (snap Plane) | Line chỉ có **1 modifier `RMVB_Shrinkwrap`** (Nearest Surface Point, Above Surface) bám vào PlaneVisual, hiện ngay trong Edit Mode (On Cage). Modal vẽ theo con trỏ: E/click thêm điểm **ngay trên Plane**, Backspace xoá điểm cuối, Enter/Esc/chuột phải xong. Không còn nút nối đầu–cuối. *Edit Line Bar* vào lại Edit Mode để sửa |
| Bar Segment | Bar Segment **tự tạo và tự cập nhật** | Khi line có từ 2 điểm: line (nằm trên Plane) được extrude **ngược chiều mũi tên** `Chiều cao bar` (đo vuông góc Plane), rộng `Bề rộng bar`, cạnh bên song song mũi tên (tiết diện hình bình hành, vát mép ở góc). Sửa điểm line (kể cả đang Edit Mode), dời/xoay Plane hoặc mũi tên, đổi thông số đều dựng lại mesh ngay (handler `depsgraph_update_post`). Nút *Cập nhật Bar Segment* chỉ là dự phòng. Modifier đầu tiên của Bar Segment: Difference với Gingiva. Bar Segment không còn sửa tay được (mesh được dựng lại từ line) |
| Top Bar | Cut Top Bar | Chỉ **Add Modifier** lên Bar Segment: Union với từng Bar Pillar → Difference `PlaneCubeCut` (Manifold) → Difference từng Base. Kiểu cắt luôn là cắt bỏ phần trong khối. Sau đó **tự ẩn** (con mắt) mọi Bar Pillar và ConnectionVisual vì đã gộp vào Bar Segment (Boolean vẫn dùng Pillar ẩn làm operand bình thường; *Edit Bar Pillar* hiện lại các Pillar) |
| Attachment | Add selected Attachment | Mỗi lần Add = **1 group** (Empty cha + Part Bar + Part Sleeve + Visual Object) tại 3D Cursor; tên group tự đề xuất theo tên Attachment, sửa được ngay trên panel |
| Attachment | Lock Z / Lock Rotation với Top Bar, Lock Location & Rotation với Attachment | Theo từng group, dùng constraint trên Empty: *Lock Z* giữ tâm group trên mặt PlaneVisual (khóa Z local của Plane, X/Y tự do, không đổi hướng xoay); *Lock Rotation* chỉ khóa xoay **X và Y** theo PlaneVisual (trục Z của group luôn vuông góc Plane, nghiêng Plane thì group nghiêng theo), **không khóa xoay Z** (vẫn xoay được quanh pháp tuyến Plane), không đổi vị trí; *Lock Location & Rotation* chọn tên group gốc trong combobox, group này luôn cùng vị trí + hướng |
| Attachment | Bấm vào mục trong danh sách group | Chọn và active **Plain Axes** của group, về **Object Mode**, chuyển sang công cụ **Move** để kéo nhanh vị trí. Nút ô vuông cuối mỗi hàng làm lại việc này khi mục đã đang active |
| Attachment | Add selected Attachment (modifier) | Modifier Boolean của Part Bar (Union nếu Add on Bar, Difference nếu Remove on Bar) được **thêm vào Bar Segment ngay lúc Add Attachment**. Mỗi lần Add Attachment, Preview luôn về trạng thái **Disable Preview**: modifier Attachment **và CutBase** tắt *Realtime Display in Viewport*, mọi Part Bar / Part Sleeve hiện để đặt vị trí |
| Attachment | Enable Preview | Thay nút *Apply Attachment on Bar*. Chỉ **bật Realtime Display in Viewport** của các modifier **CutBase (Difference Base) + Attachment** (không thêm / xoá modifier) và **ẩn Part Bar + Part Sleeve** (Apply Part on Bar / on Sleeve) của mọi group; Empty và Visual Object vẫn hiện. Nút sáng khi Preview đang bật. Trước khi Add Attachment đầu tiên, Preview mặc định bật nên CutBase vẫn cắt Bar như cũ |
| Attachment | Disable Preview | **Tắt Realtime Display in Viewport** của các modifier CutBase + Attachment (modifier và group giữ nguyên) và **hiện lại Part Bar / Part Sleeve**. **Apply Bar Design** lúc Preview đang tắt sẽ cảnh báo vì CutBase / Attachment chưa được đưa vào Bar |
| Sleeve | Create Sleeve Design | Vỏ = nới `offset` rồi đổ dày `thickness` quanh **bề mặt Bar Segment sau khi Boolean với Bar Pillar nhưng chưa cắt nướu, chưa áp Base và Attachment** (bản sao tạm chỉ giữ Union Pillar + Difference PlaneCubeCut, **không** có CutGingiva / CutBase / Attachment; nếu đã *Apply Bar Design* thì lấy từ `BarSegmentBackup`). Bản sao tạm có thêm **1 lớp Remesh (Voxel) dùng riêng cho Sleeve** (`Remesh voxel`, mặc định 0.15 mm, 0 = tắt) nên Bar Segment thật không bị đổi; mặt ngoài và mặt trong của vỏ cũng được Remesh lại sau mỗi lần nới rồi lấy *khối ngoài − khối trong*. Sau đó áp Part Sleeve theo toggle Add/Remove on Sleeve, và **cuối cùng mới Difference với Gingiva** (Sleeve và Gingiva được tam giác hoá trước khi cắt để STL xuất ra kín). Sleeve ra toàn tam giác đều, shading smooth, **chỉ 1 lớp màu vàng nhạt, opacity 0.5** (Boolean cộng dồn slot material của Bar / Part Sleeve / Gingiva nên add-on xoá hết slot cũ rồi gán 1 material duy nhất) |
| Save | Apply Bar Design | Backup Bar Segment ra `BarSegmentBackup` (ẩn, giữ nguyên modifier) rồi apply toàn bộ modifier trên Bar Segment gốc |
| Save | Delete Bar Design | Xoá Bar Segment đã apply, `BarSegmentBackup` đổi tên lại thành `BarSegment` để tiếp tục sửa thiết kế |
| Save | Save Bar & Sleeve Design | Một nút xuất `Rmvb_Bar_*.stl` + `Rmvb_Sleeve_*.stl` (+ Visual Object, + `.constructionInfo` mới). Thư mục lưu mặc định là thư mục chứa file `.blend`, để trống nếu chưa lưu file. Nếu Place Connection đã dùng before/transform.txt thì STL được đưa **về toạ độ file gốc** (`before @ transform⁻¹`, như nút *STLs ORG* của iBar) để khớp constructionInfo; thiết kế trong Blender vẫn ở toạ độ làm việc |

Bar Pillar và Bar Segment nằm trong collection `BarDesign`.

Toggle **Add/Remove on Bar** và **Add/Remove on Sleeve** trong Dental-Lib được hiểu là
**Add = UNION / Remove = DIFFERENCE** khi gộp Attachment vào Bar (bấm *Enable
Preview*) hoặc Sleeve (bấm *Create Sleeve Design*).

Đã kiểm chứng headless trên Blender 4.5 và 5.1 (đường dẫn đầy đủ Set → Place →
Pillar → Line → Segment → Top Bar → Cut → Attachment → Sleeve → Apply/Delete →
Save) và trên giao diện thật (mô phỏng sự kiện chuột/phím cho chế độ vẽ line,
vẽ panel không lỗi).

## 📄 License

Addon này yêu cầu license key để sử dụng đầy đủ. Liên hệ tác giả để được cấp license.
