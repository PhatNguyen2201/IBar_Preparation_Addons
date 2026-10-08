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
- **Tên**: Custom Preparation Panel (tab **ScansPrep**)
- **Category**: iBar Preparation Panel
- **Vị trí**: View3D Panel (sidebar)

## 🔄 Lịch sử cập nhật

Dưới đây là lịch sử các thay đổi dựa trên Git commit history:

| Commit | Ngày | Mô tả thay đổi |
|---|---|---|
| `pending` | 08/10/2026 | Rmvb-Bar v0.8.0 + Dental-Lib v0.4.0: **Connection Base và Attachment được truy xuất theo cả tên nhóm lẫn tên mục** — trước đây Rmvb-Bar chỉ lưu / tra theo *tên*, nên khi thư viện có hai mục trùng tên ở hai nhóm khác nhau thì mọi thao tác (menu *Select Connection Base*, *Place Connection*, đổi Connection từng răng, *Add selected Attachment*, màu Apply Part, danh sách Visual) đều **nhận nhầm mục đầu tiên** và không sao chọn được mục thứ 2–3. Nay mỗi mục là một cặp **(Nhóm, Tên)**: Dental-Lib thêm `connection_list()` / `attachment_list()` trả `[(tên nhóm, tên mục), ...]` theo thứ tự thư viện và thêm tham số `group` vào `get_connection` / `get_attachment` / `connection_asset` / `connection_scanbodies` / `attachment_asset` / `attachment_visuals` / `attachment_visuals_rgba` / `attachment_slot_color` (`group=None` = bỏ qua nhóm như cũ, `""` = mục chưa nhóm, `"X"` = mục thuộc nhóm X; không tìm đúng cặp thì quay về khớp theo tên để không hỏng khi nhóm bị đổi tên / xoá). Rmvb-Bar lưu thêm `connection_group`, `attachment_group` (mục đang chọn) và `lib_group` trên từng implant đã đặt + từng group Attachment; menu vẽ theo **vị trí của mục trong danh sách thư viện** nên hai bản trùng tên là hai mục thật sự khác nhau. **Hiện đủ trên màn hình**: nút *Select Connection Base* / *Select Attachment* hiển thị `Nhóm / Tên`, các dòng *Răng N* hiển thị `Nhóm / Tên` của Connection đang dùng, group Attachment hiện thêm dòng *Từ thư viện: Nhóm / Tên*, và trong menu những tên bị trùng được gắn hậu tố `(Tên nhóm)` (mục chưa nhóm là `(chưa nhóm)`) để phân biệt. Danh sách đổi Connection từng răng tick đúng theo cặp (nhóm, tên), báo lỗi / báo kết quả cũng ghi đủ `Nhóm / Tên`. **File cũ**: không phải chuyển đổi gì, mở bình thường — nếu thư viện có mục trùng tên thì lần đầu có thể cần bấm lại menu chọn đúng mục (panel đã hiện rõ `Nhóm / Tên` để biết đang chọn mục nào); Dental-Lib cũ (không có `connection_list`) vẫn chạy được, chỉ mất khả năng lọc theo nhóm. Kiểm chứng headless Blender: `.tmp_group_test/test_pick_by_group.py` (45 check — 3 Connection trùng tên ở 3 nhóm, 2 Attachment trùng tên, ALL_OK) và `.tmp_group_test/test_register.py` (đăng ký add-on + property mới) |
| `pending` | 08/10/2026 | Rmvb-Bar v0.7.0: **tách khối cắt nướu của Bar và của Sleeve thành hai object độc lập** — trước đây *Create Sleeve Design* dùng chung `GingivaCut` với Bar Segment nên đổi *Offset Gingiva* là ảnh hưởng cả hai. Nay có **hai thông số riêng**: **Offset Gingiva Bar (mm)** (mục 4, giữ nguyên tên property `gingiva_offset` nên file cũ không mất giá trị) điều khiển `GingivaCut` cắt Bar Segment, và **Offset Gingiva Sleeve (mm)** (mục 6, property mới `gingiva_offset_sleeve`) điều khiển `GingivaCut.Sleeve` cắt Sleeve ở bước cuối. `GingivaCut.Sleeve` **được tạo lazy** (lần đầu bấm *Create Sleeve Design*), cũng là bản copy đã đóng kín của Gingiva, **ẩn**, nằm trong `CutPlane` và **là con của Gingiva** nên đi theo khi kéo / xoay Gingiva; cả hai khối **dùng chung cache `GingivaCut.base`** nên tạo thêm khối thứ hai chỉ tốn copy + dời đỉnh, không chuẩn bị lại mesh (đo: sleeve cutter bán kính 6.000 mm với Gingiva r=5 + offset +1, bar cutter vẫn 7.000 mm với offset Bar +2; đổi offset Sleeve → Bar không đổi và ngược lại; Set Gingiva khác → cả hai dựng lại; gỡ Gingiva → xoá cả hai + cache). Lưu ý Sleeve là khối **đã bake** nên phải bấm lại *Create Sleeve Design* để offset Sleeve mới có hiệu lực. Kiểm chứng headless Blender 4.5: `.tmp_color_test/test_gingiva_cut_split.py` (45 check, ALL_OK). **File cũ**: lần mở đầu tiên với bản mới, *Offset Gingiva Sleeve* được lấy đúng bằng *Offset Gingiva Bar* đang có (khi đã tồn tại Sleeve) để Sleeve cắt y như trước, đánh dấu một lần bằng key `rmvb_gcut_split` trên scene và không dựng lại mesh ngay lúc mở file |
| `pending` | 08/10/2026 | Rmvb-Bar v0.6.0: thêm thông số **Offset Gingiva (mm)** dùng khi Boolean Difference với Gingiva — **số dương** nới khối cắt ra ngoài để Bar Segment bị cắt **hở** (cách mặt nướu đúng số mm đó), **số âm** thu khối cắt lại để Bar **ăn sâu** vào nướu, **0** = cắt sát mặt nướu (không dời đỉnh). *Set Gingiva* giờ **chỉ đổi màu + đánh dấu (`rmvb_role`) + đổi tên mesh — mesh gốc giữ nguyên vẹn, không chuẩn bị gì**; **Create Top Bar Plane** mới bắt đầu tạo **mesh cắt nướu** `GingivaCut`: bản copy mesh của Gingiva được **tối ưu / đóng mesh hở thành khối kín manifold** (làm sạch: gộp đỉnh trùng, xoá đỉnh thắt nút / cạnh >2 mặt / mảnh rác; fill lỗ mặt trên; extrude vòng hở lớn nhất xuống **một mặt phẳng song song Oxy (world) cách điểm thấp nhất của vành hở đúng 10 mm** rồi fill tạo đế phẳng) rồi mới dời **toàn bộ đỉnh dọc pháp tuyến của đỉnh** (`v.co += v.normal × offset`, cùng cách làm với *Create Framework thickness* của add-on ScansPrep nhưng **bỏ bước Remesh** nên biên dạng scan giữ nguyên), mang tên `GingivaCut`, nằm trong `CutPlane`, **ẩn** trong Viewport/Render và là **con của Gingiva** nên kéo/xoay Gingiva là phần cắt đi theo ngay; mesh cắt luôn ở trạng thái **ẩn** và **luôn cập nhật theo thông số Offset Gingiva trên panel** (kể cả offset 0 — Boolean luôn cắt bằng `GingivaCut`, không còn cắt bằng chính mesh Gingiva); bản đã chuẩn bị được cache (`GingivaCut.base`, fake user) nên đổi offset chỉ copy + dời đỉnh, không chuẩn bị lại từ đầu; chỉ dựng lại khi mesh Gingiva đổi hoặc offset đổi. Áp dụng cho cả *Create Sleeve Design* và *Apply / Save* |
| `pending` | 08/10/2026 | Rmvb-Bar v0.6.1: khối hướng dẫn *Căn giữa bề mặt Bar* `Rmvb_BarCenter` giờ **dài theo hướng mũi tên** (cùng trục extrude của Bar Segment, rộng 0.001 mm, dài ±100 mm) thay vì thẳng theo pháp tuyến Plane — pháp tuyến Plane nằm ngang chính là **trục Z**, nên bản cũ dựng khối đứng dọc trục Z dù mũi tên nghiêng; mũi tên nghiêng / đổi hướng lắp thì khối nghiêng theo, mặt bên khối luôn song song mặt bên bar nên Shrinkwrap Inside căn giữa đúng theo bar nghiêng (đo với bar gấp khúc + mũi tên nghiêng 20°: Empty bám vào khối lệch mặt phẳng tâm bar **0.0005 mm**, kiểu cũ lệch 10.2 mm); xoay mũi tên cũng dựng lại khối; **không còn âm thầm trở về trục Z khi mất tham chiếu mũi tên** — `props.bar_arrow` hỏng (file cũ, undo) thì add-on tự tìm lại object `InsertionArrow` theo tên rồi mới dùng Z+; trục đã dựng được lưu trên khối (`rmvb_guide_dir`) nên khối dựng sai hướng tự dựng lại khi mở file (kèm dựng lại cả Bar Segment cho khớp, bỏ qua khi Bar đã Apply) hoặc khi tick *Căn giữa bề mặt Bar* (nâng `rmvb_guide_ver` 3 → 4). Sau khi sửa phải chạy `python install_addons.py --all` để bản đã cài trong Blender được thay thế |
| `pending` | 08/10/2026 | Rmvb-Bar v0.5.1 + Dental-Lib v0.3.0: **Scanbody nhiều file** — mỗi nhóm Implant Connection và từng Connection có danh sách Scanbody (nút *+ Add Scanbody* chọn một hoặc nhiều STL/PLY, ✕ bỏ từng file; Connection không có Scanbody riêng thì kế thừa danh sách của nhóm); Place Connection / đổi Connection của implant **không còn đặt Scanbody** vào scene (v0.5.0 vẫn đặt nhưng ẩn). |
| `pending` | 08/10/2026 | Rmvb-Bar v0.5.0 + Dental-Lib v0.2.1: nút *Cut Top Bar* thành **Enable / Disable Preview** cắt Top Bar (modifier thêm sẵn, mặc định tắt; Pillar gộp vào một modifier Boolean Collection, Base cũng vậy; Apply / Save / Sleeve luôn tính đủ phần cắt); **Create/Reset bar pillar** tạo / dựng lại theo từng răng, có hộp thoại xác nhận khi ghi đè; đổi tên nút *Sửa đỉnh trụ bar* / *Thoát chỉnh sửa trụ*, bỏ *Edit Bar Pillar (Local)*; Dental-Lib **gom file của nhóm Implant Connection và nhóm Attachment vào thư mục nhóm** (tự gom khi nạp thư viện và khi đổi nhóm, nút *Gom file nhóm*); tab panel iBar đổi tên thành **ScansPrep**; Dental-Lib v0.2.0 + Rmvb-Bar v0.4.14: Dental-Lib thêm **nhóm Implant Connection** với bộ file chung (Base / Analog / Screw / Scanbody) nằm trong thư mục của nhóm, Connection trong nhóm kế thừa từng thành phần hoặc ghi đè bằng file riêng; **mỗi mục Connection / Attachment có đúng một thư mục riêng chứa mọi file 3D** (ghi đè đúng chỗ khi thay file, đổi tên mục thì đổi tên thư mục theo, thư viện cũ giữ nguyên và chỉ gom khi gắn lại file); các nút xóa trong Dental-Lib có hộp thoại xác nhận; menu *Select Connection Base* và danh sách đổi Connection từng implant bên Rmvb-Bar gom theo nhóm; Rmvb-Bar v0.4.13 + Dental-Lib v0.1.9: Dental-Lib thêm **nhóm (thư mục) cho Attachment** (ô Nhóm + nút chọn nhóm có sẵn, panel gom theo nhóm có thu / mở, menu *Select Attachment* bên Rmvb-Bar gom theo nhóm); Rmvb-Bar cho **đặt Connection Base khác nhau trên từng trụ implant** (đổi riêng từng răng, CutBase tự cập nhật, cảnh báo Bar Pillar cũ); *Save Bar & Sleeve Design* không còn xuất kèm Attachment / Visual Object vào file Bar và Sleeve; Rmvb-Bar v0.4.12 (`InsertionArrow` nằm cùng collection `CutPlane` với `PlaneVisual`, file cũ tự chuyển khi mở); v0.4.11 (tick *Căn giữa bề mặt Bar* không còn khóa chiều Z: đích Shrinkwrap đổi từ dải phẳng sát Plane sang khối hộp mỏng kín dựng vuông góc Plane, constraint `RMVB_center_bar` dùng Snap Mode Inside, chỉ đổi vị trí ngang; nút *Đảo 180°* cạnh tick *Trục X theo dọc Bar*; Plain Axes của nhóm Implant / Attachment còn 1 mm, file cũ tự cập nhật khi mở); v0.4.10 + Dental-Lib v0.1.8: sửa lỗi bấm *Cut Top Bar* khi đang ở *Edit Line Bar* (`select_all.poll() failed`: `activate()` tự thoát Edit Mode); Dental-Lib thêm tick *Attachment on Bar khi tạo Sleeve* (Part Bar của Attachment có tick vẫn được áp lên Bar khi *Create Sleeve Design*, kể cả đang Disable Preview hoặc đã Apply Bar Design); Rmvb-Bar thêm tick *Căn giữa bề mặt Bar* (Shrinkwrap Snap Mode Inside vào khối hộp mỏng kín `Rmvb_BarCenter` dọc tâm bar, chỉ đổi vị trí ngang, Z tự do) và *Trục X theo dọc Bar* (xoay group quanh pháp tuyến Plane theo hướng tâm bar, có nút Đảo 180°) cho từng group Attachment |
| `pending` | 07/10/2026 | Rmvb-Bar v0.4.9 (Base hở đáy làm CutBase: extrude +0.1 mm, rồi extrude tiếp −1 mm + scale local ×1.5); v0.4.8 (Base hở đáy extrude −1 mm, scale ×1.5 thay cho −2 mm, ×2); v0.4.7 (Enable / Disable Preview không tính modifier CutBase nữa, CutBase luôn bật; Preview mặc định tắt); v0.4.6 (Enable / Disable Preview tính cả modifier CutBase; Add Attachment luôn đưa Preview về Disable; Apply Bar Design cảnh báo theo số modifier CutBase / Attachment đang tắt); Dental-Lib v0.1.7 (tooltip); v0.4.5 (modifier Attachment thêm ngay khi Add Attachment; Enable / Disable Preview chỉ bật / tắt Realtime Display in Viewport + ẩn / hiện Part Bar, Part Sleeve); Dental-Lib v0.1.6 (tooltip); v0.4.4 (Enable Preview ẩn Part Bar / Part Sleeve, Disable Preview hiện lại); v0.4.3 (nút Apply Attachment on Bar thay bằng 2 nút Enable Preview / Disable Preview, Apply Bar Design cảnh báo khi Preview đang tắt); Dental-Lib v0.1.5 (tooltip); Rmvb-Bar v0.4.2 (Sleeve chỉ còn 1 lớp màu vàng nhạt, opacity 0.5 thay vì nhiều slot material cộng dồn từ Boolean); v0.4.1 (Sleeve đẹp hơn: nguồn là Bar chưa cắt nướu, thêm lớp Remesh Voxel dùng riêng cho Sleeve + thuộc tính `Remesh voxel`, nới bằng khối sạch rồi lấy khối ngoài − khối trong, cắt nướu ở bước cuối với mesh đã tam giác hoá; trên scan thật: tam giác xấu 24 % → 4 %, tự giao cắt 1800 → 18, STL xuất ra kín 0 cạnh lỗi; v0.4.0 là bản Remesh trước khi sửa STL); v0.3.11 (Sleeve lấy theo bề mặt Bar sau Union Pillar, chưa áp Base / Attachment, vẫn cắt nướu); v0.3.10 (mỗi implant là một nhóm Plain Axes Implant_<răng> chứa Base / ConnectionVisual / Analog / Screw / Scanbody / Bar Pillar); v0.3.9 (Set Gingiva luôn tạo khối kín + manifold: sửa điểm thắt nút / mảnh rác / đỉnh chưa gộp, nhiều mảnh; Boolean cắt bar không còn bị Manifold từ chối); v0.3.8 (Cut Top Bar tự ẩn Bar Pillar + ConnectionVisual; đế Gingiva là mặt phẳng Oxy cách điểm thấp nhất của vành hở 10 mm); v0.3.7 (Select Top theo object Bar Pillar đang chọn, bỏ combobox Vị trí implant); v0.3.6 (Gingiva: extrude đáy −10 mm theo Z world thay vì local); v0.3.5 (ẩn Base, thêm ConnectionVisual xám, luôn đặt Analog xanh lam / Screw xám 0.8 / Scanbody ẩn trong 1 collection, bỏ checkbox đặt kèm); v0.3.4 (Place Connection đọc before/transform.txt để đặt đúng vị trí, Save xuất về toạ độ file gốc); v0.3.3 (combobox Vị trí implant cho Select Top); v0.3.2 (Lock Rotation với Top Bar chỉ khóa X/Y, Z tự do; file cũ tự nâng cấp); v0.3.1 (PlaneVisual và PlaneCubeCut 100 mm, Plane bản cũ tự phóng to); v0.3.0 (Create Top Bar Plane lên đầu, line vẽ trên PlaneVisual chỉ với 1 modifier Shrinkwrap, Bar Segment tự tạo/tự cập nhật theo line-Plane-mũi tên, bỏ nút Create Bar Segment/Nối đầu-cuối/Edit Bar Segment/khe hở Gingiva); v0.2.2 (thêm Lock Rotation với Top Bar; bấm mục danh sách Attachment chọn Plain Axes + công cụ Move; Lock Z không còn parent vào Plane); v0.2.1 (combobox Connection/Attachment chuyển sang menu thả xuống + operator, sửa lỗi không đổi được lựa chọn); v0.2.0: Set thay Import, Gingiva thành khối, Base chuẩn bị Boolean, Pillar từ vòng hở đáy, line theo thuật toán Splitter, Top Bar hình bình hành + mũi tên hướng lắp, Attachment theo group, Apply/Delete Bar Design; Dental-Lib v0.1.4 (tooltip) |
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
`connections/<thư mục>/` và `attachments/<thư mục>/` nên thư viện mang sang máy khác được.

**Mỗi mục Connection / Attachment có đúng một thư mục riêng** (riêng Connection thuộc nhóm thì dùng thư mục của nhóm, xem bên dưới) (lưu trong `library.json` ở khóa `folder`, hiển thị ở dòng *Thư mục:* của mục) chứa mọi file 3D của mục đó: slot dùng tên cố định (`base`, `analog`, `screw`, `scanbody`, `part_bar`, `part_sleeve`), Visual Object dùng `visual_NN`. Quy tắc khi tạo / sửa:
- Gắn file khác vào slot đã có thì **ghi đè đúng chỗ** (đổi đuôi `.stl` ↔ `.ply` thì file cũ của slot đó bị gỡ), không sinh thư mục `Tên_2` và không để file rác.
- **Đổi tên mục thì thư mục đổi tên theo** và mọi đường dẫn trong `library.json` được sửa (đổi tên thất bại thì giữ thư mục cũ, file vẫn cùng một chỗ).
- Tên thư mục luôn duy nhất, không dùng chung hay lẫn với mục khác (trùng thì thêm `_2`, `_3`…); xóa mục chỉ xóa khỏi `library.json`, thư mục và file được giữ lại.
- Thư viện cũ **giữ nguyên**, không tự động di chuyển file. Mục cũ nào được gắn lại file thì mới được gom: nếu mọi file của mục đã nằm chung một thư mục trong thư viện và chưa mục nào dùng thì mục nhận luôn thư mục đó; ngược lại tạo thư mục riêng và **copy** các file còn lại vào đó (file cũ không bị xóa, kể cả file nằm ngoài thư viện).


| Mục | Trường |
|---|---|
| **Implant Connection** | Library Name, **Nhóm** (xem dưới), Base (STL/PLY), Implant-Analog, Screw (mỗi slot 1 file), **Scanbody (nhiều file)** |
| **Attachment** | Attachment Name, **Nhóm** (thư mục; ô Nhóm + nút ▼ chọn nhóm có sẵn, để trống = chưa nhóm; panel gom theo nhóm có thu / mở, menu *Select Attachment* bên Rmvb-Bar cũng gom theo nhóm; mỗi Attachment thuộc tối đa 1 nhóm; chưa có nhóm nào thì danh sách phẳng như cũ; ghi `group` vào `library.json` ngay khi đổi; file của các Attachment cùng nhóm nằm chung trong thư mục nhóm, xem bên dưới), toggle *Add/Remove on Bar* + tick *Attachment on Bar khi tạo Sleeve* + Apply Part Bar, toggle *Add/Remove on Sleeve* + Apply Part Sleeve, Visual Objects (không giới hạn số lượng, đặt tên từng object) |

**Nhóm Attachment cũng có thư mục chung**: mỗi nhóm có một thư mục `attachments/<thư mục nhóm>/` (tên được giữ trong `library.json` ở khóa `attachment_groups`, tự tạo khi gõ / chọn nhóm và tự bỏ khi nhóm hết thành viên) chứa phẳng mọi file của các Attachment trong nhóm, kể cả Visual Object: `<thư mục Attachment>_part_bar.stl`, `<thư mục Attachment>_part_sleeve.stl`, `<thư mục Attachment>_visual_NN.stl` (Attachment thuộc nhóm không có thư mục riêng). Cơ chế giống nhóm Implant Connection: gán / đổi / bỏ nhóm thì file **tự di chuyển theo** (ra khỏi nhóm thì về lại `attachments/<thư mục Attachment>/` với tên `part_bar`, `part_sleeve`, `visual_NN`; thư mục cũ rỗng được gỡ); gắn file mới vào Attachment trong nhóm thì file nằm thẳng trong thư mục nhóm; đổi tên Attachment thì đổi tiền tố tên file; file rải rác hoặc ngoài thư viện được COPY (file gốc giữ nguyên). **Khi nạp thư viện** (mở file `.blend`, nút *Nạp thư viện*, lúc bật add-on) và khi bấm *Gom file nhóm*, mọi Attachment đang thuộc nhóm mà file còn nằm riêng được gom vào thư mục nhóm; thư viện cũ chỉ có nhãn nhóm được tự nâng cấp lên thư mục nhóm. Chạy lại nhiều lần không đổi gì thêm.

Các nút **xóa** trong Dental-Lib (thùng rác của Connection / Attachment / Visual Object và nút ✕ bỏ liên kết file của slot) đều hỏi lại bằng hộp thoại xác nhận trước khi thực hiện, tránh nhấn nhầm; file mesh trong thư mục thư viện không bị xóa. Gọi bằng script (`bpy.ops.dental_lib.remove_*`) vẫn xóa thẳng, không qua hộp thoại.

**Nhóm Implant Connection** (`+ Group` cạnh `+ Add Connection Base`, hoặc gõ tên vào ô *Nhóm* của một Connection để tự tạo nhóm; nút ▼ chọn nhóm có sẵn): mỗi nhóm có **bộ file chung** gồm Base, Analog, Screw (1 file mỗi thành phần) và danh sách **Scanbody (nhiều file)** nằm trong thư mục riêng của nhóm `connections/<thư mục nhóm>/`. Connection trong nhóm **kế thừa** từng thành phần: thành phần nào chưa có file riêng thì dùng file chung của nhóm (hiện `Nhóm: <tên file>`), bấm *Gan file* để ghi đè bằng file riêng (file riêng cũng nằm **trong thư mục của nhóm**, ghi tên `<thư mục Connection>_<thành phần>`, vd. `connections/Straumann/Straumann_RN_base.stl`, còn file chung ghi tên `base.stl`…; Connection thuộc nhóm không có thư mục riêng), bấm ✕ để bỏ file riêng và kế thừa lại. **Scanbody** là danh sách không giới hạn số file (file ghi tên `scanbody_00.stl`, `scanbody_01.stl`…, file riêng của Connection trong nhóm ghi `<thư mục Connection>_scanbody_NN`): *+ Add Scanbody* cho chọn một hoặc nhiều file cùng lúc, ✕ bỏ từng file; Connection có ít nhất 1 Scanbody riêng thì dùng danh sách của mình, chưa có thì kế thừa cả danh sách của nhóm. Thư viện cũ (khóa `scanbody` 1 file) tự chuyển thành danh sách 1 file. API: `dental_lib.connection_scanbodies(name)` trả về mọi đường dẫn. Sửa file chung của nhóm thì mọi Connection đang kế thừa đổi theo. Đổi tên nhóm thì các Connection trong nhóm và thư mục chung của nhóm đổi theo (tên nhóm trống hoặc trùng nhóm khác thì giữ tên cũ). Xóa nhóm (có hộp thoại xác nhận) thì các Connection thành chưa nhóm, file riêng của chúng được chuyển ra thư mục riêng và phần kế thừa mất; file chung vẫn được giữ trong thư mục nhóm. Gán / đổi / bỏ nhóm của một Connection thì file riêng của nó **tự di chuyển theo** (vào thư mục nhóm mới, hoặc về lại thư mục riêng `connections/<thư mục Connection>/` khi ra khỏi nhóm; thư mục cũ rỗng thì được gỡ); đổi tên Connection trong nhóm thì đổi tiền tố tên file. File nằm rải rác hoặc ngoài thư viện thì được COPY (file gốc giữ nguyên). **Khi nạp thư viện** (mở file `.blend`, nút *Nạp thư viện*, lúc bật add-on) và khi bấm nút *Gom file nhóm* trên nhóm, mọi Connection đang thuộc nhóm mà file còn nằm riêng bên ngoài sẽ được gom vào thư mục nhóm và `library.json` được sửa đường dẫn; chạy lại nhiều lần không đổi gì thêm. Panel và menu *Select Connection Base* / danh sách đổi Connection từng implant bên Rmvb-Bar đều gom theo nhóm; chưa có nhóm nào thì danh sách phẳng như cũ. Thư viện cũ không có nhóm vẫn nạp bình thường.

API cho add-on khác: `dental_lib.connection_names()` / `connection_list()`,
`get_connection(name, group=None)`, `connection_asset(name, slot, group=None)`,
`connection_scanbodies(name, group=None)`, `attachment_names()` / `attachment_list()`,
`get_attachment(name, group=None)`, `attachment_asset(name, slot, group=None)`,
`attachment_visuals(name, group=None)` / `attachment_visuals_rgba(name, group=None)` /
`attachment_slot_color(name, slot, group=None)`.
`connection_asset(name, slot)` trả về file riêng của Connection, nếu không có thì file chung của nhóm; `connection_groups()` / `attachment_groups()` trả `[(tên nhóm, [tên mục, ...]), ...]`.

**Tên mục KHÔNG được đảm bảo duy nhất**: hai Connection (hay hai Attachment) ở hai nhóm khác nhau có thể trùng tên, nên mỗi mục được nhận diện bằng **cặp (tên nhóm, tên mục)**. `connection_list()` / `attachment_list()` trả `[(tên nhóm, tên mục), ...]` theo đúng thứ tự thư viện (vị trí trong danh sách là chỉ số dùng chung cho menu). Mọi hàm tra cứu nhận thêm tham số `group`: `group=None` = không lọc nhóm (trả mục đầu tiên trùng tên — hành vi của thư viện cũ), `group=""` = mục chưa nhóm, `group="X"` = mục thuộc nhóm X; nếu không tìm thấy đúng cặp (nhóm, tên) — ví dụ nhóm bị đổi tên / xoá — hàm quay về khớp theo tên. Rmvb-Bar lưu cả nhóm lẫn tên (`connection_group` + `connection_name`, `attachment_group` + `active_attachment`, `lib_group` + `lib_name` trên mỗi implant / group Attachment) nên chọn mục thứ 2–3 trùng tên là lấy đúng mesh của mục đó.

### `rmvb_bar.py` — Rmvb-Bar

Tab **Rmvb-Bar** trong Sidebar. Quy trình: Set → Connection → Bar Pillar →
Create Top Bar Plane → Draw Line Bar → (Bar Segment tự cập nhật) → Enable Preview cắt Top Bar → Attachment → Sleeve → Save. Mọi bước trên Bar Segment
chỉ **thêm modifier** (không apply) cho tới khi bấm *Apply Bar Design*.

| Nhóm | Nút | Hành vi |
|---|---|---|
| Set | Set Gingiva / Denture / Antagonist | Không còn Import: chọn object mesh có sẵn rồi bấm Set. Gingiva màu hồng (opacity 0.5), Denture xanh lá (0.5), Antagonist nâu (1). **Set Gingiva không còn chuẩn bị mesh** — mesh gốc giữ nguyên vẹn; việc chuẩn bị Gingiva thành khối kín cho Boolean chuyển sang **mesh cắt nướu `GingivaCut` và được làm khi Create Top Bar Plane** (xem mục Bar Segment / Top Bar): bản copy mesh Gingiva được làm sạch (gộp đỉnh trùng, xoá điểm thắt nút ở vành / cạnh >2 mặt / đỉnh rời, bỏ mảnh rác nhỏ <1% mảnh lớn nhất), fill các lỗ nhỏ mặt trên, extrude vòng hở lớn nhất (mặt dưới) xuống **một mặt phẳng song song Oxy (world) cách điểm thấp nhất của vành hở đúng 10 mm** (mọi điểm đã extrude cùng Z, XY giữ nguyên, không phụ thuộc xoay/scale của object) rồi fill tạo đế phẳng, kiểm tra lại khối **kín + manifold** (không còn cạnh hở) và báo số cặp tam giác còn tự giao nhau do nếp cuộn của scan; nếu mặt hở quay lên +Z thì Create Top Bar Plane cảnh báo |
| Connection | Select Connection Base (menu thả xuống từ Dental-Lib) + Place Connection | Đặt Base theo `MatrixImplantGeometry`. **Menu *Select Connection Base* gom theo nhóm của Dental-Lib và truy xuất theo cặp (Nhóm, Tên)** — hai Connection trùng tên ở hai nhóm khác nhau là hai mục riêng biệt, chọn mục thứ 2–3 là lấy đúng mesh của mục đó (tên bị trùng hiện thêm `(tên nhóm)`, nút đang chọn hiện đầy đủ `Nhóm / Tên`, dòng *Răng N* cũng vậy).**Mỗi trụ implant có thể dùng Connection Base khác nhau**: Place Connection đặt Connection đang chọn cho tất cả các răng, sau đó bấm tên Connection trên dòng *Răng N* (mục *Connection Base từng implant*) để đổi riêng răng đó sang Connection khác trong Dental-Lib — Base / ConnectionVisual / Analog / Screw của răng đó được thay bằng bộ mesh mới tại đúng vị trí cũ, modifier CutBase cập nhật theo; nếu đã tạo Bar Pillar thì có cảnh báo bấm *Create Bar Pillar* để tạo lại theo Base mới; không đổi được khi đã *Apply Bar Design*. Mỗi Base được chuẩn bị: vùng hở đáy **extrude +0.1 mm theo z local, rồi từ phần mới extrude tiếp −1 mm theo z local và scale local ×1.5** (đáy cuối nằm ở z = −0.9 mm, bán kính ×1.5); vùng hở đỉnh (Screw) **extrude +30 mm**; nắp kín 2 đầu + Flip Normal (normal ra ngoài) để làm khối Boolean. Base này **bị ẩn** (chỉ làm operand Boolean, vẫn cắt bình thường). Hiển thị bằng `ConnectionVisual_<răng>` lấy đúng hình Base gốc trong thư viện (xám 0.5, opacity 1). Luôn đặt cả **Analog** (xanh lam, opacity 1) và **Screw** (xám 0.3, opacity 0.8); tất cả nằm chung collection `Rmvb Connections`. **Scanbody (Dental-Lib) không được đặt vào scene.** **Mỗi implant là một nhóm Plain Axes `Implant_<răng>`** (giống cách Attachment được add): Base, ConnectionVisual, Analog, Screw, Scanbody và `BarPillar_<răng>` đều là con của Empty đó với toạ độ local đơn vị, nên kéo/xoay Plain Axes là cả nhóm di chuyển theo (Boolean của Bar Segment tự tính lại). Khi bật **Transform theo before/transform.txt** (mặc định), Place Connection đọc `before.txt` + `transform.txt` do add-on iBar ghi (thư mục chứa constructionInfo, nếu không có thì thư mục file `.blend`) và đặt implant bằng `M = transform @ before⁻¹ @ implant` (giống *Create Tubes* / *Offset from ORG to current* của iBar). Không thấy đủ 2 file hoặc file hỏng thì đặt theo toạ độ file như cũ và báo cảnh báo; tên file không phân biệt hoa/thường |
| Connection | Clear Connection | Xoá Base + Bar Pillar đã đặt để chọn lại constructionInfo |
| Bar Pillar | Create/Reset bar pillar | **Tạo / Reset theo từng răng**: chưa chọn gì thì chỉ tạo Pillar cho các răng *chưa có* (lần đầu = tạo tất cả; đã đủ thì báo hướng dẫn, không đụng gì). Chọn Pillar `BarPillar_<răng>`, Plain Axes `Implant_<răng>` hoặc bất kỳ phần nào của implant (ConnectionVisual, Base…) trong viewport rồi bấm thì chỉ các răng đó được dựng lại theo Base hiện tại (răng chưa có Pillar thì tạo mới), các răng khác và chỉnh sửa của chúng giữ nguyên. **Reset một Pillar đã có thì hiện hộp thoại xác nhận** (liệt kê răng, báo sẽ mất chỉnh sửa đỉnh / vị trí); chỉ tạo mới Pillar còn thiếu thì chạy thẳng. Pillar mới dựng thành công mới xóa Pillar cũ nên dựng lỗi thì Pillar cũ còn nguyên; Pillar vừa tạo / reset luôn hiện để chỉnh tiếp; modifier Union của Bar Segment tự trỏ sang Pillar mới. Mỗi Pillar: Chỉ lấy **vùng hở đáy (Connection)**: sao chép vòng điểm gốc của Base ra object `BarPillar_<răng>`, extrude lên `Extrude lên` mm (mặc định 7) theo local Z, fill kín đáy + đỉnh → solid manifold |
| Bar Pillar | Sửa đỉnh trụ bar / Thoát chỉnh sửa trụ | **Sửa đỉnh trụ bar** (trước là *Select Top*): chọn trực tiếp object `BarPillar_<răng>` trong viewport (một hoặc nhiều Pillar) rồi bấm *Sửa đỉnh trụ bar* → các Pillar đó vào Edit Mode (Transform Orientation Local) và chỉ chọn các đỉnh ở đỉnh mũi extrude; Pillar active giữ nguyên, Pillar không được chọn bị bỏ chọn đỉnh. Chưa chọn Pillar nào (hoặc chọn object khác) thì báo lỗi. Nút *Thoát chỉnh sửa trụ* (trước là *Exit Edit Bar Pillar*) nằm cùng hàng để quay về Object Mode. Nút *Edit Bar Pillar (Local)* và combobox Vị trí implant đã bỏ |
| Bar Segment | **Create Top Bar Plane** (bước đầu tiên) | Tạo trong collection `CutPlane`: `PlaneVisual` 100 mm (xanh dương, opacity 0.4) và `PlaneCubeCut` (plane 100 mm extrude +100 mm = khối lập phương, opacity 0.5, **ẩn**, parent theo PlaneVisual); đặt ở đỉnh Bar Pillar. **Mũi tên hướng lắp** (`InsertionArrow`, Empty mũi tên Z+) cũng hiện ở bước này **trong cùng collection `CutPlane` với `PlaneVisual`** (file cũ để mũi tên ở `BarDesign` được chuyển sang khi mở), xoay nó để đổi hướng lắp. Nếu đã Set Gingiva, **bước này mới bắt đầu tạo mesh cắt nướu `GingivaCut`**: bản copy mesh Gingiva được tối ưu / đóng mesh hở thành khối kín manifold rồi offset theo thông số *Offset Gingiva* để tối ưu cho Boolean, **ẩn trong Viewport + Render**, là con của Gingiva, nằm trong `CutPlane`, luôn cập nhật theo offset trên panel (báo số lỗ đã fill, đế phẳng Z, cảnh báo mặt hở quay lên / chưa kín) |
| Bar Segment | Draw Line Bar (snap Plane) | Line chỉ có **1 modifier `RMVB_Shrinkwrap`** (Nearest Surface Point, Above Surface) bám vào PlaneVisual, hiện ngay trong Edit Mode (On Cage). Modal vẽ theo con trỏ: E/click thêm điểm **ngay trên Plane**, Backspace xoá điểm cuối, Enter/Esc/chuột phải xong. Không còn nút nối đầu–cuối. *Edit Line Bar* vào lại Edit Mode để sửa |
| Bar Segment | Bar Segment **tự tạo và tự cập nhật** | Khi line có từ 2 điểm: line (nằm trên Plane) được extrude **ngược chiều mũi tên** `Chiều cao bar` (đo vuông góc Plane), rộng `Bề rộng bar`, cạnh bên song song mũi tên (tiết diện hình bình hành, vát mép ở góc). Sửa điểm line (kể cả đang Edit Mode), dời/xoay Plane hoặc mũi tên, đổi thông số đều dựng lại mesh ngay (handler `depsgraph_update_post`). Nút *Cập nhật Bar Segment* chỉ là dự phòng. Modifier đầu tiên của Bar Segment: Difference với `GingivaCut` (bản copy kín của Gingiva, ẩn). Bar Segment không còn sửa tay được (mesh được dựng lại từ line) |
| Top Bar | Enable / Disable Preview (thay nút *Cut Top Bar*) | Các modifier cắt **luôn được thêm sẵn** lên Bar Segment: Difference `GingivaCut` → Union các Bar Pillar → Difference `PlaneCubeCut` → Difference các Base (kiểu cắt luôn là cắt bỏ phần trong khối). Nút này chỉ **bật / tắt Realtime Display in Viewport** của nhóm modifier đó (giống nút Preview của Attachment): *Enable Preview* bật nhóm cắt và **ẩn** Bar Pillar + ConnectionVisual (vì đã gộp vào Bar Segment); *Disable Preview* tắt nhóm cắt và **hiện lại** Pillar + ConnectionVisual để chỉnh (*Sửa đỉnh trụ bar* cần Pillar đang hiện). Mặc định **TẮT** để Viewport nhẹ khi vẽ line, đặt Attachment, chỉnh Pillar. **Apply Bar Design, Save Bar & Sleeve và Create Sleeve Design luôn tính đủ phần cắt** dù Preview đang tắt (Preview chỉ là hiển thị). File cũ đã Cut Top Bar (khóa `rmvb_cut`) được coi là Preview đang bật. **Tối ưu hiệu năng**: (1) tắt Preview thì Bar Segment không phải tính Boolean (đo trên dữ liệu mô phỏng 6 implant: tắt ≈ 1 ms; bật dạng Collection 30–90 ms, dạng từng modifier 80–190 ms, Gingiva hở Exact thêm 0.1–0.3 s; tăng theo độ chi tiết của Base / Gingiva); (2) các Pillar được gộp vào **một modifier Boolean kiểu Collection** (Manifold), các Base cũng vậy — nhanh gấp ~2–2.7 lần so với một modifier cho mỗi vật; chỉ cần một operand không kín thì quay về một modifier cho mỗi vật (Exact cho vật hở) như trước; (3) mỗi lần dựng lại stack chỉ dựng lại một lần, không tính Boolean khi Preview tắt |
| Top Bar | **Offset Gingiva Bar (mm)** (mục 4, ngay dưới Enable / Disable Preview) | Số mm nới / thu **khối cắt nướu của Bar** (`GingivaCut`) trước khi Boolean Difference với Bar Segment — **chỉ áp dụng cho Bar Segment**; Sleeve có khối cắt `GingivaCut.Sleeve` và offset riêng ở mục 6. **Dương** = phình khối cắt ra ngoài → Bar bị cắt **hở**, cách mặt nướu đúng số mm này (khe vệ sinh, chỗ cho xi măng); **Âm** = thu khối cắt lại → Bar **ăn sâu** vào nướu; **0** = cắt sát mặt nướu (không dời đỉnh). Khối cắt là bản copy mesh của Gingiva **đã được tối ưu / đóng mesh hở thành khối kín manifold** (làm sạch như mô tả ở mục Set) rồi mới được dời **toàn bộ đỉnh dọc theo pháp tuyến của đỉnh** (`v.co += v.normal × offset`) — cùng cách làm với *Create Framework thickness* của add-on ScansPrep nhưng **không dùng bước Remesh**, vì Remesh SMOOTH làm đổi biên dạng scan còn đây là khối cắt nên mọi sai lệch đều vào kết quả. Object `GingivaCut` ở collection `CutPlane`, **ẩn trong Viewport + Render** (Boolean vẫn đánh giá — đã kiểm chứng), là **con của Gingiva** nên kéo / xoay Gingiva thì phần cắt đi theo mà không phải dựng lại mesh; Gingiva có scale ≠ 1 thì offset được chia cho hệ số scale để vẫn đúng mm trong world. **Tạo từ lúc Create Top Bar Plane** (Set Gingiva chỉ đổi màu + đánh dấu + đổi tên, mesh gốc giữ nguyên) và **luôn cập nhật theo thông số này trên panel, kể cả offset 0** — Boolean luôn cắt bằng `GingivaCut`, không còn cắt bằng chính mesh Gingiva. Bản đã chuẩn bị được cache (`GingivaCut.base`, fake user) **dùng chung cho cả hai khối cắt** nên đổi offset chỉ copy + dời đỉnh (nhanh); chỉ dựng lại mesh khi Gingiva đổi (sửa mesh, đổi object, đổi scale — nhận ra bằng chữ ký tên/đỉnh/mặt/scale/offset lưu trên `GingivaCut`) hoặc khi đổi offset; *Set Gingiva* (khi mesh cắt đã có) và *Enable/Disable Preview* dựng lại stack modifier ngay sau đó. Lưu ý: offset theo pháp tuyến **đỉnh** nên ở góc nhọn/khúc cong gắt, bề mặt xê dịch ít hơn số mm nhập vào. Đo trên Blender 4.5: thanh 20×5×5 mm cắt bằng khối cầu r=5 mm, offset +2 mm cho biên cắt 3.96 mm (lý thuyết 3.96 mm), offset −1.5 mm cắt ít hơn và +0.3 mm → 6.06 mm; dựng khối cắt cho mesh 1.0 triệu đỉnh tốn 0.77 s, gọi lại khi không có gì đổi ~0 s |
| Attachment | Add selected Attachment | Mỗi lần Add = **1 group** (Empty cha + Part Bar + Part Sleeve + Visual Object) tại 3D Cursor; tên group tự đề xuất theo tên Attachment, sửa được ngay trên panel; menu *Select Attachment* cũng gom theo nhóm và truy xuất theo cặp **(Nhóm, Tên)** nên hai Attachment trùng tên ở hai nhóm là hai mục riêng, panel hiện thêm dòng *Từ thư viện: Nhóm / Tên* của group đang chọn |
| Attachment | Căn giữa bề mặt Bar, Trục X theo dọc Bar, Lock Z / Lock Rotation với Top Bar, Lock Location & Rotation với Attachment | Theo từng group, dùng constraint trên Empty: *Căn giữa bề mặt Bar* giữ tâm group NGAY GIỮA bề mặt Bar Segment theo bề rộng bar (trên đường tâm line; kéo group dọc theo Bar thì group trượt theo tâm, bị kẹp ở hai đầu bar, không đổi hướng xoay; **chỉ đổi vị trí ngang, chiều cao Z so với Plane vẫn tự do** — muốn giữ group trên Plane thì tick thêm *Lock Z*; constraint `RMVB_center_bar` là Shrinkwrap *Nearest Surface Point* với **Snap Mode = Inside**; Shrinkwrap không bám được vào line chỉ có cạnh nên add-on tạo thêm 1 khối hộp mỏng **kín** ẩn `Rmvb_BarCenter` (rộng 0.001 mm, dài ±100 mm **theo hướng mũi tên** — cùng trục extrude của Bar Segment, mũi tên nghiêng / đổi hướng lắp thì khối nghiêng theo, không còn thẳng theo pháp tuyến Plane (bằng trục Z khi Plane nằm ngang); mất tham chiếu mũi tên thì tự tìm lại object `InsertionArrow` nên không bao giờ quay về dựng đứng) dọc tâm bar, tự cập nhật cùng Bar Segment (xoay mũi tên cũng dựng lại; khối dựng sai hướng tự dựng lại khi mở file) (Inside chỉ bám đúng với khối kín, pháp tuyến hướng ra ngoài; mặt hở chỉ snap được các điểm ở một phía); file cũ còn dải phẳng / tường hở được nâng cấp khi mở; tick trước khi vẽ line thì tự căn giữa khi line có ≥ 2 điểm; bỏ tick thì group trở về vị trí gốc, giống các Lock khác); *Trục X theo dọc Bar* (độc lập với Căn giữa) xoay group quanh pháp tuyến Plane để trục X chạy dọc theo tâm bar tại vị trí group, theo chiều vẽ line (điểm đầu → điểm cuối); tự giữ trục Z vuông góc Plane như *Lock Rotation*, nên xoay tay quanh Z bị ghi đè; group đổi vị trí dọc bar, hoặc line / Plane đổi thì trục X xoay theo (handler depsgraph), bỏ tick thì giữ nguyên góc đang có; nút **Đảo 180°** cạnh tick (chỉ bật khi tick *Trục X theo dọc Bar*) xoay thêm 180° quanh Z để Attachment hướng ngược chiều line, trạng thái đảo được lưu theo group nên vẫn giữ khi group đổi vị trí; *Lock Z* giữ tâm group trên mặt PlaneVisual (khóa Z local của Plane, X/Y tự do, không đổi hướng xoay); *Lock Rotation* chỉ khóa xoay **X và Y** theo PlaneVisual (trục Z của group luôn vuông góc Plane, nghiêng Plane thì group nghiêng theo), **không khóa xoay Z** (vẫn xoay được quanh pháp tuyến Plane), không đổi vị trí; *Lock Location & Rotation* chọn tên group gốc trong combobox, group này luôn cùng vị trí + hướng |
| Attachment | Bấm vào mục trong danh sách group | Chọn và active **Plain Axes** của group, về **Object Mode**, chuyển sang công cụ **Move** để kéo nhanh vị trí. Nút ô vuông cuối mỗi hàng làm lại việc này khi mục đã đang active |
| Attachment | Add selected Attachment (modifier) | Modifier Boolean của Part Bar (Union nếu Add on Bar, Difference nếu Remove on Bar) được **thêm vào Bar Segment ngay lúc Add Attachment**. Mỗi lần Add Attachment, Preview luôn về trạng thái **Disable Preview**: modifier Attachment tắt *Realtime Display in Viewport*, mọi Part Bar / Part Sleeve hiện để đặt vị trí |
| Attachment | Enable Preview | Thay nút *Apply Attachment on Bar*. Chỉ **bật Realtime Display in Viewport** của các modifier Attachment (không thêm / xoá modifier) và **ẩn Part Bar + Part Sleeve** (Apply Part on Bar / on Sleeve) của mọi group; Empty và Visual Object vẫn hiện. Nút sáng khi Preview đang bật. **Modifier CutBase không thuộc Enable / Disable Preview**, luôn bật |
| Attachment | Disable Preview | **Tắt Realtime Display in Viewport** của các modifier Attachment (modifier và group giữ nguyên) và **hiện lại Part Bar / Part Sleeve**. **Apply Bar Design** lúc Preview đang tắt sẽ cảnh báo vì Part Bar chưa được đưa vào Bar |
| Sleeve | Create Sleeve Design | Vỏ = nới `offset` rồi đổ dày `thickness` quanh **bề mặt Bar Segment sau khi Boolean với Bar Pillar nhưng chưa cắt nướu, chưa áp Base và Attachment không tick** (bản sao tạm chỉ giữ Union Pillar + Difference PlaneCubeCut, **không** có CutGingiva / CutBase; Attachment cũng bị bỏ qua **trừ** những Attachment có tick *Attachment on Bar khi tạo Sleeve* trong Dental-Lib — Part Bar của chúng vẫn được Union / Difference (theo Add/Remove on Bar) lên bề mặt nguồn, bất kể Enable / Disable Preview; nếu đã *Apply Bar Design* thì lấy từ `BarSegmentBackup`). Bản sao tạm có thêm **1 lớp Remesh (Voxel) dùng riêng cho Sleeve** (`Remesh voxel`, mặc định 0.15 mm, 0 = tắt) nên Bar Segment thật không bị đổi; mặt ngoài và mặt trong của vỏ cũng được Remesh lại sau mỗi lần nới rồi lấy *khối ngoài − khối trong*. Sau đó áp Part Sleeve theo toggle Add/Remove on Sleeve, và **cuối cùng mới Difference với khối cắt nướu RIÊNG CỦA SLEEVE** `GingivaCut.Sleeve` (không dùng `GingivaCut` của Bar) theo **Offset Gingiva Sleeve** (Sleeve và khối cắt được tam giác hoá trước khi cắt để STL xuất ra kín). Sleeve ra toàn tam giác đều, shading smooth, **chỉ 1 lớp màu vàng nhạt, opacity 0.5** (Boolean cộng dồn slot material của Bar / Part Sleeve / Gingiva nên add-on xoá hết slot cũ rồi gán 1 material duy nhất) |
| Sleeve | **Offset Gingiva Sleeve (mm)** (mục 6, ngay trên *Create Sleeve Design*) | Khối cắt nướu **thứ hai** `GingivaCut.Sleeve` — bản copy đã đóng kín của Gingiva giống hệt khối của Bar nhưng dời đỉnh theo số mm này, chỉ dùng ở bước cắt Sleeve cuối cùng. **Hoàn toàn độc lập với *Offset Gingiva Bar***: đổi một bên không làm đổi bên kia (modifier `CutGingiva` của Bar Segment vẫn trỏ `GingivaCut`). Cùng quy tắc như khối của Bar: **ẩn** trong Viewport/Render, nằm trong `CutPlane`, là **con của Gingiva** (kéo / xoay Gingiva là phần cắt đi theo), offset được chia hệ số scale để đúng mm trong world, và **dùng chung cache `GingivaCut.base`** nên chỉ copy + dời đỉnh chứ không chuẩn bị lại mesh. Khối Sleeve được tạo **lazy**: chưa bấm *Create Sleeve Design* lần nào thì chưa dựng `GingivaCut.Sleeve`; đã có thì đổi offset dựng lại mesh cắt ngay. Vì Sleeve là khối **đã bake** (không giữ modifier sống) nên cần bấm lại *Create Sleeve Design* để offset mới áp dụng lên Sleeve |
| Save | Apply Bar Design | Backup Bar Segment ra `BarSegmentBackup` (ẩn, giữ nguyên modifier) rồi apply toàn bộ modifier trên Bar Segment gốc |
| Save | Delete Bar Design | Xoá Bar Segment đã apply, `BarSegmentBackup` đổi tên lại thành `BarSegment` để tiếp tục sửa thiết kế |
| Save | Save Bar & Sleeve Design | Một nút xuất `Rmvb_Bar_*.stl` + `Rmvb_Sleeve_*.stl` (+ `.constructionInfo` mới). **Mỗi file chỉ gồm đúng Bar Segment hoặc Sleeve, không xuất kèm Attachment / Visual Object** (Part Bar đã Union / Difference vào Bar là một phần của Bar nên vẫn nằm trong `Rmvb_Bar`). Thư mục lưu mặc định là thư mục chứa file `.blend`, để trống nếu chưa lưu file. Nếu Place Connection đã dùng before/transform.txt thì STL được đưa **về toạ độ file gốc** (`before @ transform⁻¹`, như nút *STLs ORG* của iBar) để khớp constructionInfo; thiết kế trong Blender vẫn ở toạ độ làm việc |

Bar Pillar và Bar Segment nằm trong collection `BarDesign`.

Toggle **Add/Remove on Bar** và **Add/Remove on Sleeve** trong Dental-Lib được hiểu là
**Add = UNION / Remove = DIFFERENCE** khi gộp Attachment vào Bar (bấm *Enable
Preview*) hoặc Sleeve (bấm *Create Sleeve Design*).

Tick **Attachment on Bar khi tạo Sleeve** (Dental-Lib, mặc định tắt, ghi `library.json` ngay khi đổi) được
sao vào group lúc *Add selected Attachment*; sửa lại từng group ở ô cùng tên trong mục 5. Attachment
không tick thì bị bỏ qua khi tạo Sleeve.

Đã kiểm chứng headless trên Blender 4.5 và 5.1 (đường dẫn đầy đủ Set → Place →
Pillar → Line → Segment → Top Bar → Cut → Attachment → Sleeve → Apply/Delete →
Save) và trên giao diện thật (mô phỏng sự kiện chuột/phím cho chế độ vẽ line,
vẽ panel không lỗi).

## 📄 License

Addon này yêu cầu license key để sử dụng đầy đủ. Liên hệ tác giả để được cấp license.
