# IBar_Preparation_Addons

Bộ add-on Blender (Python/`bpy`) cho thiết kế khung iBar / bar implant nha khoa. README.md là tài liệu người dùng (tiếng Việt); file này là hướng dẫn cho agent.

## Cấu trúc

Mỗi add-on là **một file `.py` đơn** (không package), có `bl_info` ở đầu file:

| File | Add-on | Ghi chú |
|---|---|---|
| `Final_addon_Ibar_to_ORG.py` | Custom Preparation Panel (tab **ScansPrep**) | Tự cập nhật từ GitHub `PhatNguyen2201/IBar_Preparation_Addons`, nhánh `main`, so sánh `bl_info["version"]` |
| `Gingiva_Teeth_Splitter.py` | Gingiva/Teeth Surface Splitter | Tab **IBAR Split** |
| `dental_lib.py` | Dental-Lib | Thư viện Connection / Attachment dùng chung |
| `rmvb_bar.py` | Rmvb-Bar | Thiết kế bar, **import `dental_lib` lúc khởi động** |
| `install_addons.py` (+ `.bat`, `.sh`) | Bộ cài | Copy file vào `scripts/addons`, bật add-on bằng `blender --background` |
| `ibar_keygen.py`, `ibar_make_key.py`, `ibar_copy_key_to_user.py` | Tạo / chép license key | Xem mục License |

Thứ tự bật add-on bắt buộc: **`dental_lib` trước `rmvb_bar`**. Giữ thứ tự này trong `ADDON_FILES` của `install_addons.py`.

## Làm việc với code

- File rất lớn (`rmvb_bar.py` ~5000 dòng). Dùng Grep tìm operator / hàm trước, chỉ đọc đoạn cần sửa.
- `bl_info`, docstring và comment trong code viết **tiếng Việt không dấu** (ASCII). Chuỗi hiển thị trên UI và README dùng tiếng Việt có dấu. File lưu UTF-8.
- Tối thiểu Blender **4.5.3** (`bl_info["blender"]`). Không dùng API chỉ có ở bản mới hơn mà không kiểm tra `bpy.app.version`.
- Dữ liệu lưu trên object / scene dùng key tiền tố `rmvb_` (ví dụ `rmvb_role`, `rmvb_top_z`). File `.blend` cũ phải mở được: khi đổi cấu trúc dữ liệu, thêm bước tự nâng cấp lúc mở file (tham khảo `rmvb_gcut_split`, `rmvb_guide_ver`), đừng yêu cầu người dùng chuyển đổi.
- Khi đổi API công khai của `dental_lib` (ví dụ thêm tham số `group`), giữ tương thích ngược: `rmvb_bar` phải chạy được với `dental_lib` cũ.

## Quy ước phiên bản và commit

- Sửa add-on nào thì **tăng `bl_info["version"]` của add-on đó**. Với `Final_addon_Ibar_to_ORG.py` điều này còn quyết định auto-update của người dùng.
- Commit theo dạng `feat|fix|refactor(<add-on>): <mô tả> (<add-on> vX.Y.Z)`, ví dụ `fix(rmvb_bar): ... (rmvb_bar v0.8.1)`. Thay đổi chạm hai add-on thì ghi cả hai version.
- Mỗi thay đổi có ý nghĩa thêm một dòng vào bảng **Lịch sử cập nhật** trong README.md (cột Commit ghi `pending` cho đến khi commit).
- Nhánh chính là `main`. Có remote `origin` trên GitHub; không push khi chưa được yêu cầu.

## Kiểm chứng

Không có test suite. Kiểm chứng bằng Blender headless:

```
"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --background --python <script_test.py>
```

- Máy này có Blender 4.0, 4.5, 5.1. Test với **4.5** (phiên bản tối thiểu) và 5.1 khi sửa logic phụ thuộc API.
- Đăng ký thử add-on (`register()` / `unregister()`) sau mỗi thay đổi, vì lỗi property hay operator chỉ lộ lúc đăng ký.
- Test tạo scene thật (ví dụ dựng Pillar bằng `build_pillar_mesh`) rồi kiểm số liệu, tránh chỉ kiểm cú pháp.
- Hiển thị overlay chọn đỉnh của object không active: dùng `bpy.ops.render.opengl(view_context=True)`, `bpy.ops.screen.screenshot` không phản ánh đúng.
- Script test tạm và log để trong `.tmp_*` (chưa được git theo dõi); không commit.
- Sau khi sửa, chạy `python install_addons.py --all` để bản **đã cài trong Blender** được thay thế. Nếu không, Blender vẫn chạy bản cũ.

## License và dữ liệu nhạy cảm

- Add-on kiểm tra `~/addon_ibar.key` (SHA-512 của Hardware ID) và `~/.ibar_machine_id`. **Không in, không commit** các file key / hwid (`*.key`, `IbarPrep.hwid`, `.ibar_machine_id`) và đừng đưa chúng vào log.
- File ca bệnh (`*.dentalProject`, `*.constructionInfo`, STL) chứa tên bệnh nhân. Thư mục `Ex/` là mẫu: không dán nội dung hay tên bệnh nhân vào commit, README hay phản hồi.
- `Save STL by Part` đổi tên file theo `{PartName}_{PatientFirstName}`: khi viết test, dùng tên giả.
