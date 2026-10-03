# ⚡ Ungoogled-Thorium

<p align="center">
  <img src="assets/logo.svg" alt="Ungoogled-Thorium Logo" width="136" height="136" />
</p>

<p align="center">
  <strong>The fastest Chromium fork meets absolute privacy and freedom.</strong><br/>
  <em>Bản fork Chromium nhanh nhất kết hợp cùng sự tự do và riêng tư tuyệt đối.</em>
</p>

<p align="center">
  <a href="https://github.com/starfish367/ungoogled-thorium/actions/workflows/thorium_ungoogled.yml"><img src="https://github.com/starfish367/ungoogled-thorium/actions/workflows/thorium_ungoogled.yml/badge.svg" alt="Build Status" /></a>
  <img src="https://img.shields.io/badge/Platform-Linux%20ARM64%20%7C%20Windows%20x64-blue.svg" alt="Platform" />
  <img src="https://img.shields.io/badge/License-BSD--3--Clause-green.svg" alt="License" />
  <img src="https://img.shields.io/badge/Hardware-Optimized%20for%20S905X%20%2F%20ARM64-orange.svg" alt="Optimized" />
</p>

<p align="center">
  <a href="#-english">English</a> • <a href="#-tiếng-việt">Tiếng Việt</a>
</p>

---

## 🌐 English

### Overview
**Ungoogled-Thorium** combines the aggressive compiler optimizations and performance enhancements of **[Thorium Browser](https://github.com/Alex313031/Thorium)** with the total privacy and de-Googling architecture of **[Ungoogled-Chromium](https://github.com/ungoogled-software/ungoogled-chromium)**.

Designed for raw speed without compromises, this project provides modern, ultra-responsive builds with specialized hardware optimizations for **Linux ARM64** (including Amlogic S905X TV Boxes / Raspberry Pi on Armbian) and **Windows x64**.

### Key Features
* 🚀 **Thorium Engine Optimizations:** Compiler-level tuning with SIMD vectorization (NEON / AVX), ThinLTO, fast page load and smooth multimedia rendering.
* 🛡️ **Zero Google Dependency:** Completely stripped of Google background telemetry, sync daemons, tracking requests, and proprietary binary blobs.
* 🎬 **Hardware Video Decoding:** Enforces H.264 (`avc1`) playback for smooth hardware acceleration on low-power VPUs (Mali-450 / S905X), eliminating CPU bottlenecks from VP9/AV1.
* 🔒 **Widevine DRM Support:** Enjoy protected streaming services with out-of-the-box CDM compatibility.
* 🧊 **Lightweight Memory Footprint:** Tailored for 1–2 GB RAM devices with aggressive background tab discarding to prevent out-of-memory crashes.
* 🤖 **Automated CI/CD:** Fully automated cross-compilation pipeline yielding standalone `.AppImage` (Linux ARM64) and `mini_installer.exe` (Windows x64) artifacts.

### Downloads
Download the latest binaries directly from **[Releases](https://github.com/starfish367/ungoogled-thorium/releases)** or the **[Actions Artifacts](https://github.com/starfish367/ungoogled-thorium/actions)** tab.

#### Running on Linux ARM64 (Armbian / Raspberry Pi / TV Box)
```bash
chmod +x Thorium-Ungoogled-Linux-arm64.AppImage
./Thorium-Ungoogled-Linux-arm64.AppImage
```

#### Running on Windows x64
Download `mini_installer.exe` and execute it directly.

---

## 🇻🇳 Tiếng Việt

### Giới Thiệu
**Ungoogled-Thorium** là dự án kết hợp sức mạnh vượt trội của **[Thorium Browser](https://github.com/Alex313031/Thorium)** (trình duyệt Chromium nhanh nhất thế giới) với kiến trúc bảo mật, riêng tư của **[Ungoogled-Chromium](https://github.com/ungoogled-software/ungoogled-chromium)** (gỡ bỏ 100% dịch vụ và kết nối ngầm của Google).

Dự án mang lại trải nghiệm duyệt web siêu tốc độ, nhẹ nhàng và an toàn, đặc biệt được tối ưu hóa cho các dòng máy cấu hình nhẹ như **TV Box Amlogic S905X (chạy Armbian OS, CPU Cortex-A53, RAM 1-2GB)** cũng như máy tính cá nhân **Windows x64**.

### Tính Năng Nổi Bật
* 🚀 **Tối ưu hóa phần cứng & Tốc độ:** Khai thác tập lệnh SIMD (NEON trên ARM64, AVX trên x86_64), tối ưu bộ nhớ đệm và công cụ kết xuất đồ họa.
* 🛡️ **Triệt tiêu dịch vụ Google:** Loại bỏ toàn bộ telemetry, báo cáo lỗi ngầm, Google Sync, Google Host Detector và thay thế bằng domain giả lập an toàn (`qjz9zk`).
* 🎬 **Tối ưu xem video mượt mà:** Ép giải mã phần cứng chuẩn video H.264 (`avc1`), bảo vệ chip S905X không bị quá tải 100% CPU hay giật lag khi xem YouTube.
* 🔒 **Tích hợp Widevine CDM:** Hỗ trợ xem các trang phim và truyền hình bản quyền mượt mà.
* 🧊 **Tiết kiệm RAM tối đa:** Cơ chế tự động đóng băng các tab chạy ngầm khi RAM chạm ngưỡng, giúp thiết bị 1–2GB RAM không bao giờ bị tràn bộ nhớ hay văng ứng dụng.
* 🤖 **Quy trình Build tự động:** Tự động biên dịch qua GitHub Actions, xuất bản trực tiếp định dạng di động **`.AppImage`** cho Linux và **`mini_installer.exe`** cho Windows.

### Hướng Dẫn Cài Đặt & Sử Dụng
Tải bản dựng mới nhất tại mục **[Releases](https://github.com/starfish367/ungoogled-thorium/releases)** hoặc tab **[Actions Artifacts](https://github.com/starfish367/ungoogled-thorium/actions)**.

#### Dành cho Linux ARM64 (Armbian / TV Box S905X / Raspberry Pi)
```bash
chmod +x Thorium-Ungoogled-Linux-arm64.AppImage
./Thorium-Ungoogled-Linux-arm64.AppImage
```

#### Dành cho Windows x64
Tải file `mini_installer.exe` và khởi chạy để cài đặt như bình thường.

---

## 🛠️ Build from Source / Tự Biên Dịch

### Kích hoạt tự động trên GitHub Actions:
1. Truy cập tab **Actions** -> Chọn workflow **Build Thorium + Ungoogled**.
2. Bấm **Run workflow**, chọn target mong muốn (`linux-arm64`, `windows-x64`, hoặc `all`).
3. Đợi pipeline hoàn tất và tải về file thành phẩm.

### Biên dịch thủ công qua Command Line:
```bash
# Yêu cầu Python 3.11+
python build_thorium_ungoogled.py --target-os linux --target-cpu arm64 --src-dir src
```

---

## 🤝 Credits / Lời Cảm Ơn
* **[Alex313031](https://github.com/Alex313031)** & Thorium Browser Team.
* **[Ungoogled-Chromium Project](https://github.com/ungoogled-software/ungoogled-chromium)** & Contributors.
* **The Chromium Project**.

---

## 📄 License / Bản Quyền
Distributed under the **[BSD 3-Clause License](LICENSE)**.
