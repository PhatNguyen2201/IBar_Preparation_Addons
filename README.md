# IBar Preparation Addon

Blender addon dành cho thiết kế khung xương hàm giả (iBar) trong nha khoa. Addon cung cấp bộ công cụ toàn diện để chuẩn bị, căn chỉnh, tạo khung và xuất các mô hình 3D phục vụ cho quy trình sản xuất khung xương hàm.

## 📋 Yêu cầu hệ thống

- **Blender**: 4.5.3 trở lên
- **Hệ điều hành**: Windows (do sử dụng Windows API cho Hardware ID)
- **Python**: Tích hợp trong Blender

## 🚀 Cài đặt

1. Tải file `Final_addon_Ibar_to_ORG.py` từ repository
2. Mở Blender → Edit → Preferences → Add-ons
3. Nhấn "Install..." và chọn file `.py`
4. Tick checkbox để kích hoạt addon

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
| **Create Framework thickness** | Tạo độ dày khung xương (1.5mm) từ Waxup design |

**Tạo Tubes tự động:**
- Đọc file `.constructionInfo` (XML format) để lấy thông tin implant
- Đọc file `ImplantDirectionPosition*.xml` để lấy hướng implant
- Tạo đường cong 3 điểm (Start-Middle-End) cho mỗi implant
- Áp dụng skin và subdivision surface để tạo ống 3D
- Tự động căn chỉnh theo vị trí và hướng implant

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

## 📄 License

Addon này yêu cầu license key để sử dụng đầy đủ. Liên hệ tác giả để được cấp license.
