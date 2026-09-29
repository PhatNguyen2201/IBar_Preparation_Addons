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

Tab **Rmvb-Bar** trong Sidebar. Quy trình: Import → Connection → Bar Pillar →
Bar Segment → Top Bar → Attachment → Sleeve → Save.

| Nhóm | Nút | Hành vi |
|---|---|---|
| Import | Import Gingiva / Denture-reference / Antagonist | Đọc STL/PLY (chọn nhiều file), gộp về 1 object theo vai trò, tô màu riêng |
| Connection | Select Connection Base (combobox) | Danh sách lấy từ Dental-Lib |
| Connection | Place Connection (XML constructionInfo) | Chọn file `.constructionInfo`/`.xml`, đặt Base theo `MatrixImplantGeometry` của từng răng có `ImplantType != None` |
| Bar Pillar | Create Bar Pillar | Detect 2 boundary loop của Base → extrude cả hai lên theo local Z (vùng 2 đúng `pillar_lift`, mặc định 7 li = 7 mm; vùng 1 về cùng cao độ) → **nối 2 miệng extrude thành solid kín** (manifold, không còn shell hở). Vertex group `Screw`/`Outside` **chỉ chứa các đỉnh nằm ở đỉnh mũi extrude** (không ghi vòng miệng lỗ gốc) |
| Bar Pillar | Edit / Select Screws / Select Outside / Exit | Edit Mode + Transform Orientation **Local**; chỉ chọn **các đỉnh đã extrude** (lọc theo cao độ đỉnh lưu trong `obj["rmvb_top_Screw"/"rmvb_top_Outside"]`, tự làm mới khi chỉ còn 1 mặt phẳng đỉnh). Pillar tạo bằng bản cũ vẫn chọn đúng nếu có metadata; bật thuộc tính `All Levels` của operator nếu muốn chọn cả vòng miệng lỗ |
| Bar Segment | Draw Line Bar | Vẽ **polyline mở** theo kiểu GingivaWaxupDetection: giữ danh sách điểm world rồi dựng lại mesh mỗi lần thêm điểm → mọi điểm đều nối liên tục thành 1 đường (không còn lỗi chỉ nối 2 điểm đầu). Snap trên bề mặt Gingiva bằng ray riêng của object (không dính mesh khác); E/click thêm điểm, Backspace/Ctrl+Z xoá điểm cuối, Enter xong, Esc khôi phục line như trước khi vẽ. **Không tự nối điểm đầu–cuối**; muốn kín thì bấm nút "Nối điểm đầu-cuối (tuy chọn)". |
| Bar Segment | Create / Edit / Exit | Sweep tiết diện chữ nhật (rộng × cao) theo line — **đáy bar nằm đúng trên line** (kiểm chứng: sai số 0.0000 mm) |
| Top Bar | Create Top Bar Plane | Mặt phẳng hiển thị + khối cắt (ẩn) parent theo mặt phẳng |
| Top Bar | Cut Top Bar | 3 bước: (1) **Bar Segment − cột Connection** (mỗi Connection được extrude 2 vùng hở ra 2 hướng **ngược nhau** ~10 mm rồi nap 2 đầu → lăng trụ kin cắt xuyen hoan toan) → (2) **union Pillar + Segment** → (3) cắt bằng khối ẩn (DIFFERENCE). Sau đó union/difference các Attachment theo toggle. Khoảng chỗi chỉnh bằng *Chỗi Connection (mm)* |
| Attachment | Select / Add | Apply Part Bar được đặt tại **3D Cursor** (vị trí + hướng), bấm Add nhiều lần để đặt nhiều cái |
| Attachment | Group Axis Attachment | Gom các Attachment dưới một Empty trục chung |
| Attachment | Group Axis với Top Bar | Attachment **xoay theo Plane** và **tâm luôn nằm trên Plane** (chỉ khoá translate dọc Z của Plane; X/Y tự do) |
| Sleeve | Offset / Thickness / Apply attachment / Create | Vo = bar nới `offset` rồi đổ dày `thickness` |
| Save | Save Bar Design / Save Sleeve Design | Xuất STL (`Rmvb_Bar_<yyMMdd-HHmm>.stl`) + **Visual Objects xuất kèm** (không tham gia boolean) + ghi `.constructionInfo` mới với `<Filename>` đổi sang tên STL (như add-on iBar) |

Toggle **Add/Remove on Bar** và **Add/Remove on Sleeve** trong Dental-Lib được hiểu là
**UNION (true) / DIFFERENCE (false)** khi gộp Attachment vào Bar hoặc Sleeve.

Vận hành đã kiểm chứng (Blender 5.2 LTS, headless): import → place 6 implant từ
`Ex/*.constructionInfo` → 6 Bar Pillar **solid kín** (boundary=0, non-manifold=0,
80.91 mm³/cái) → Bar Segment (đáy đúng trên line, cao 3.00 mm) → Cut Top Bar
(bar manifold ~1.77e3 mm³, **giao với cột Connection = 0.00 mm³**, bấm 2 lần
cho cùng kết quả và không sinh object rác) → Attachment tại cursor + Visual
Object, tâm bám Plane khi xoay/kéo → Sleeve manifold → xuất STL
+ `.constructionInfo` hợp lệ.

## 📄 License

Addon này yêu cầu license key để sử dụng đầy đủ. Liên hệ tác giả để được cấp license.
