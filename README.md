# ⚡ Ungoogled-Thorium

<p align="center">
  <img src="https://raw.githubusercontent.com/Alex313031/Thorium/main/logos/thorium_logo.png" alt="Ungoogled-Thorium Logo" width="128" height="128" />
</p>

<p align="center">
  <strong>The fastest Chromium browser meets complete privacy & freedom.</strong>
</p>

<p align="center">
  <a href="https://github.com/starfish367/ungoogled-thorium/actions/workflows/thorium_ungoogled.yml"><img src="https://github.com/starfish367/ungoogled-thorium/actions/workflows/thorium_ungoogled.yml/badge.svg" alt="Build Status" /></a>
  <img src="https://img.shields.io/badge/Platform-Linux%20ARM64%20%7C%20Windows%20x64-blue.svg" alt="Platform" />
  <img src="https://img.shields.io/badge/License-BSD--3--Clause-green.svg" alt="License" />
  <img src="https://img.shields.io/badge/Hardware-Optimized%20for%20S905X%20%2F%20ARM64-orange.svg" alt="Optimized" />
</p>

---

## 📖 Giới Thiệu (Overview)

**Ungoogled-Thorium** là sự kết hợp hoàn hảo giữa hai dự án mã nguồn mở đình đám:
1. **[Thorium Browser](https://github.com/Alex313031/Thorium)**: Bản fork Chromium được tối ưu hóa tối đa về hiệu năng với các cờ biên dịch tối tân (SIMD, AVX/AVX2, Polly, tối ưu render engine và multimedia).
2. **[Ungoogled-Chromium](https://github.com/ungoogled-software/ungoogled-chromium)**: Triệt tiêu 100% các kết nối ngầm, dịch vụ theo dõi, tài khoản và telemetry của Google.

Mục tiêu chính của dự án là mang lại trải nghiệm duyệt web **nhanh nhất, mượt nhất nhưng hoàn toàn riêng tư**, đặc biệt tối ưu cho các thiết bị cấu hình nhẹ như **TV Box Amlogic S905X (Armbian Linux ARM64)** và máy tính cá nhân (Windows x64).

---

## ✨ Điểm Nổi Bật (Key Features)

### 🚀 Tốc Độ & Tối Ưu Phần Cứng (Thorium Performance)
* **Tối ưu hóa tập lệnh SIMD:** Tận dụng tối đa tập lệnh CPU trên cả x86_64 và ARM64 (NEON).
* **Giải mã phần cứng mượt mà:** Ép chuẩn video H.264 (`avc1`) tương thích hoàn hảo với phần cứng VPU Mali-450 / S905X, tránh giật lag 100% CPU do VP9/AV1.
* **Hỗ trợ Widevine CDM:** Thưởng thức nội dung đa phương tiện chất lượng cao có bản quyền DRM.
* **Gọn nhẹ cho RAM 1-2GB:** Cơ chế đóng băng tab nền thông minh, tránh tối đa tràn RAM trên thiết bị nhúng.

### 🛡️ Riêng Tư Tuyệt Đối (Ungoogled Privacy)
* **Không dịch vụ Google:** Gỡ bỏ Google Sync, Safe Browsing telemetry, Google Host Detector, WebRTC IP leakage.
* **Domain Substitution:** Thay thế các domain theo dõi của Google bằng tên miền giả lập không thể kết nối (`qjz9zk`).
* **Pruned Binaries:** Loại bỏ toàn bộ binary blob đóng của Google khỏi mã nguồn biên dịch.

### 🤖 CI/CD Tự Động Hóa (GitHub Actions)
* Tự động build và đóng gói định dạng **`.AppImage`** cho Linux ARM64.
* Tự động build file cài đặt **`mini_installer.exe`** cho Windows x64.
* Sử dụng bộ nhớ đệm `sccache` và tối ưu dung lượng đĩa giúp quá trình build thông suốt.

---

## 📦 Tải Về & Cài Đặt (Downloads)

Các bản dựng mới nhất được tạo tự động tại mục **[Releases](https://github.com/starfish367/ungoogled-thorium/releases)** hoặc tab **[Actions Artifacts](https://github.com/starfish367/ungoogled-thorium/actions)**.

### 1. Linux ARM64 (Armbian / Raspberry Pi / TV Box)
Tải file `Thorium-Ungoogled-Linux-arm64.AppImage`, cấp quyền thực thi và chạy:
```bash
chmod +x Thorium-Ungoogled-Linux-arm64.AppImage
./Thorium-Ungoogled-Linux-arm64.AppImage
```

### 2. Windows x64
Tải file `mini_installer.exe` và chạy trực tiếp để cài đặt.

---

## 🛠️ Hướng Dẫn Tự Biên Dịch (Building from Source)

Dự án hỗ trợ biên dịch trực tiếp trên máy hoặc thông qua **GitHub Actions Workflow**:

### Kích hoạt qua GitHub Actions:
1. Vào tab **Actions** -> Chọn workflow **Build Thorium + Ungoogled**.
2. Bấm **Run workflow**, chọn target mong muốn (`linux-arm64`, `windows-x64`, hoặc `all`).
3. Chờ workflow hoàn tất và tải về artifact ở cuối trang.

### Biên dịch thủ công (CLI):
```bash
# Cài đặt môi trường Python 3.11+
python build_thorium_ungoogled.py --target-os linux --target-cpu arm64 --src-dir src
```

---

## 🤝 Đóng Góp & Lời Cảm Ơn (Credits)

Dự án xin chân thành gửi lời cảm ơn đến:
* **[Alex313031](https://github.com/Alex313031)** cùng đội ngũ phát triển **Thorium Browser**.
* Đội ngũ phát triển **[Ungoogled-Chromium](https://github.com/ungoogled-software/ungoogled-chromium)**.
* **The Chromium Project**.

---

## 📄 Bản Quyền (License)

Dự án được phân phối dưới giấy phép **[BSD 3-Clause License](LICENSE)**.
