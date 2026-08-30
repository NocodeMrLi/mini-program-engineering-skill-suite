<p align="center">
  <img src="assets/readme-cover.webp?v=3.1.6" alt="Mini Program Engineering Skill Suite cover" width="100%">
</p>

# Mini Program Engineering Skill Suite

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT">
  <img src="https://github.com/NocodeMrLi/mini-program-engineering-skill-suite/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/platform-WeChat%20%7C%20Alipay%20%7C%20Douyin-07C160.svg" alt="Platform: WeChat | Alipay | Douyin">
  <img src="https://img.shields.io/badge/type-Agent%20Skill%20Suite-7B61FF.svg" alt="Type: Agent Skill Suite">
  <img src="https://img.shields.io/badge/category-Evidence--First%20Engineering-FF6B35.svg" alt="Category: Evidence-First Engineering">
  <img src="https://img.shields.io/badge/stack-Taro%20%7C%20uni--app%20%7C%20native-4CAF50.svg" alt="Stack: Taro / uni-app / native">
  <img src="https://img.shields.io/badge/runtime-Python%203.9%2B-3776AB.svg" alt="Runtime: Python 3.9+">
  <img src="https://img.shields.io/badge/lang-Bahasa%20Indonesia-16A34A.svg" alt="Language: Bahasa Indonesia">
  <img src="https://img.shields.io/badge/status-Active%20Development-22C55E.svg" alt="Status: Active Development">
  <img src="https://img.shields.io/badge/version-3.1.6-0EA5E9.svg" alt="Version: 3.1.6">
</p>

<p align="center">
  <a href="./README.md">中文</a> ·
  <a href="./README.zh-Hant.md">繁體中文</a> ·
  <a href="./README.en.md">English</a> ·
  <a href="./README.ja.md">日本語</a> ·
  <a href="./README.th.md">ไทย</a> ·
  <a href="./README.id.md">Bahasa Indonesia</a>
</p>

**Mini Program Engineering Skill Suite** adalah kumpulan Agent Skill untuk membantu pengembangan WeChat Mini Program dari nol, mengambil alih proyek yang sudah ada, dan menyiapkan rilis dengan bukti yang jelas. Suite ini memecah pekerjaan menjadi alur yang dapat dieksekusi: apa yang harus dikonfirmasi, bagaimana membangunnya, sejauh mana pekerjaan sudah selesai, dan bukti apa yang tersedia.

Nama Tionghoa: **小程序开发工程技能套件**.

> Catatan: lapisan fakta platform kini mencakup WeChat, Alipay, dan Douyin (kemampuan deteksi dilabeli jujur — lihat "Kesegaran Aturan Platform" di bawah). Untuk LINE MINI App, Telegram Mini Apps, atau ekosistem mini app lain, prinsip suite ini dapat dijadikan referensi, tetapi aturan platform tetap perlu diadaptasi secara terpisah.

---

## Sorotan Utama

- **Lapisan fakta tiga platform**: satu sumber kebenaran aturan platform WeChat / Alipay / Douyin, dengan capability doctor yang mendeteksi stack dan platform target secara otomatis. Kemampuan deteksi dilabeli jujur: WeChat mendukung pemantauan fingerprint deterministik, sementara Alipay / Douyin mengandalkan pemeriksaan dokumen resmi saat runtime dan laporan pengguna, bukan berpura-pura deteksi otomatis (lihat [Kesegaran Aturan Platform](#kesegaran-aturan-platform)).
- **Pipeline kesegaran aturan platform**: eksekusi selalu selaras dengan dokumen resmi terkini saat runtime, sementara lapisan konten menjalankan deteksi drift otomatis mingguan (perbandingan fingerprint → ekstraksi → audit bayangan → issue putusan). Instalasi lokal yang sedikit lama tidak akan membuat tugas dieksekusi dengan aturan kedaluwarsa (lihat [Kesegaran Aturan Platform](#kesegaran-aturan-platform)).
- **Verifikasi gerbang penuh di Agent CLI nyata**: gerbang rilis tiga tingkat (struktur / routing / perilaku) beserta penandatanganan independen berjalan penuh dalam sesi Agent CLI nyata — versi awal diuji terima melalui Codex CLI, dan engine evaluasi kini dapat ditukar (Codex CLI / Claude Code / Gemini / API kompatibel OpenAI). Lolos lintas engine adalah bukti yang lebih kuat (lihat [Verifikasi](#verifikasi) dan [EVALUATIONS.md](EVALUATIONS.md)).
- **Disiplin rekayasa berbasis bukti**: setiap klaim status harus didukung bukti yang cocok, jika tidak maka dilabeli unknown secara jujur. Sejak 3.0 disiplin ini dirapikan menjadi lapisan skill fondasi `foundation/` yang netral domain dan dapat digunakan ulang oleh suite rekayasa Agent mana pun (lihat [Prinsip Desain](#prinsip-desain)).
- **Evaluasi berlapis + penandatanganan independen**: evaluasi tiga tingkat tier1 struktur / tier2 routing / tier3 perilaku, penilaian independen with-skill vs. baseline, dan batch held-out yang tetap dibekukan hingga rilis — semua gerbang harus PASS sebelum rilis (lihat [EVALUATIONS.md](EVALUATIONS.md)).
- **Tata kelola rilis kelas supply chain**: SHA256 + dual manifest + packaging fail-closed + verifikasi ulang sisi penerima + pemindaian informasi sensitif tanpa temuan; konsistensi struktur README enam bahasa dijaga oleh skrip (lihat [Integritas Paket](#integritas-paket)).

---

## Pahami Skill Ini dalam 32 Detik

Jika Anda ingin melihat gambaran singkat tentang masalah yang diselesaikan, asal-usulnya, dan cara penggunaannya, mulai dari [video penjelasan 32 detik](https://raw.githubusercontent.com/NocodeMrLi/mini-program-engineering-skill-suite/main/assets/readme-promo.mp4) ini.

https://github.com/user-attachments/assets/d382951e-5175-48be-b0c0-44ba210706f1

<sub>Video ini hanya menjelaskan posisi suite, asal-usul, dan batas penggunaannya.</sub>

---

## Status Proyek

Repository ini adalah halaman publik untuk suite ini dan dirilis dengan **MIT License**. Siapa pun dapat melihat, menggunakan, mengubah, dan mendistribusikannya kembali. Lihat [LICENSE](LICENSE) untuk detailnya.

---

## Masalah yang Diselesaikan

Bagi orang yang belum pernah mengirimkan mini program, tantangan utamanya bukan hanya menulis kode. Yang sulit adalah mengetahui apa yang perlu dikonfirmasi terlebih dahulu, keputusan mana yang berdampak ke tahap berikutnya, kapan harus berhenti untuk memverifikasi, dan langkah rilis mana yang tidak boleh dilewati berdasarkan asumsi.

Masalah umum:

- environment dan konfigurasi tidak konsisten；
- permission atau privacy policy baru diketahui kurang setelah siap rilis；
- UI terlihat benar di simulator tetapi rusak di perangkat nyata；
- build, submission, acceptance, dan release tercampur；
- perubahan yang belum disetujui terdorong ke online dan perlu rollback cepat.

Suite ini membantu Agent mengubah risiko tersebut menjadi alur engineering: memahami tujuan dan batas, membuat spesifikasi dan rencana, melakukan perubahan kecil, memverifikasi bertingkat, lalu menutup risiko rilis. Suite ini tidak menggantikan keputusan bisnis atau produk, tetapi membantu pengguna tahu langkah berikutnya, alasan langkah itu diperlukan, dan bukti apa yang cukup.

---

## Asal dari Proyek Nyata: WordPet

Skill ini tidak ditulis dari tutorial abstrak. Ia disarikan dari kolaborasi jangka panjang pada WeChat Mini Program nyata bernama **WordPet**. Yang dipublikasikan di sini adalah metode engineering yang dapat digunakan ulang: pemecahan produk, implementasi bertahap, verifikasi, acceptance, kesiapan rilis, dan manajemen bukti.

<p align="center">
  <img src="assets/wordpet-origin-case.png" alt="WordPet real project origin case" width="100%">
</p>

<sub>WordPet ditampilkan hanya sebagai contoh asal-usul metode. Repository ini tidak menyertakan source code aplikasi, AppID, cloud resources, konfigurasi privat, data bisnis, status review, atau catatan pengembangan internal. Kode QR hanya disediakan untuk mencoba contoh nyata, dan hasil pemindaian bergantung pada status platform WeChat saat ini.</sub>

---

## Yang Dibantu untuk Agent

- **Mengambil alih proyek**: memahami status sebelum mengubah apa pun；
- **Memperjelas kebutuhan**: mengubah ide kabur menjadi spesifikasi yang dapat diterima；
- **Mencatat keputusan**: menurunkan keputusan produk ke architecture, data, API, permission, dan fallback；
- **Mengubah kode dengan aman**: perubahan kecil, terukur, dan dapat di-rollback；
- **Verifikasi bertahap**: membedakan UI preview, konfirmasi pengguna, integrasi, perangkat, dan final acceptance；
- **Debug berbasis bukti**: mencari masalah dari evidence, bukan dugaan；
- **Melapor dengan jujur**: hanya menyatakan apa yang benar-benar sudah diverifikasi.

---

## Peta Kemampuan

| Area | Tujuan |
| --- | --- |
| Project intake | Read-only discovery, fact map, risk map, dan change boundary |
| Product specification | MVP scope, user flow, state matrix, acceptance criteria |
| Architecture | Module, data, API, permission, dan failure strategy |
| Platform adaptation | Tooling WeChat Mini Program, privacy, permission, dan platform evidence |
| Implementation | Perubahan kecil dengan test dan perlindungan pekerjaan yang sudah diterima |
| UI and device adaptation | Preview-first, responsive, dan pengecekan multi-perangkat |
| Debugging | Reproduction, competing hypotheses, root cause, dan regression coverage |
| Verification | Evidence tiers untuk static, unit, integration, simulator, device, cloud, dan release |
| Release readiness | Version, build, security, privacy, rollback, upload / review / release governance |

---

## Prinsip Desain

- Fakta sebelum tindakan: jangan mengubah proyek lama sebelum statusnya jelas.
- Status mengikuti bukti: hanya laporkan hal yang sudah diverifikasi.
- Tahap tidak boleh dicampur: preview, implementation, build, upload, review, acceptance, dan release adalah tahap berbeda.
- External action perlu izin terpisah: cloud change, upload, submit review, dan publish harus disetujui satu per satu.
- Informasi privat dipisahkan: public package dan README assets harus melewati sensitive-content scan.

---

## Kesegaran Aturan Platform

Aturan platform terus berubah, sehingga aturan yang di-hardcode ke dalam skill pasti kedaluwarsa. Sejak 2.0 suite ini memakai "segar saat eksekusi, evolusi terkontrol":

- **Eksekusi selalu mengikuti sumber resmi.** Untuk langkah yang menyentuh platform (upload, pengajuan review, rilis, deklarasi privasi, kuota), agent memeriksa dulu apakah fakta yang tercatat masih segar (setiap fakta membawa tanggal verifikasi dan sidik jari sumber); langkah kedaluwarsa atau berisiko tinggi memeriksa dokumentasi resmi terkini sebelum dieksekusi. **Versi lokal yang sedikit lama tidak akan menjalankan aturan kedaluwarsa** — hanya mengubah seberapa sering sumber resmi dikonsultasikan, bukan ketepatan.
- **Konten berevolusi terkontrol.** Pemelihara mendeteksi perubahan aturan dengan alat drift (perbandingan sidik jari halaman resmi) dan mengirimkan pembaruan melalui audit independen beberapa putaran; Anda dapat melaporkan perubahan yang Anda temukan lewat templat **Platform rule drift** di Issues.
- **Ingin versi terbaru?** Unduh paket baru dari Releases dan instal ulang dengan `install.sh --force`; suite tidak pernah memperbarui instalasi lokal secara diam-diam.

Fakta platform dan peta aturan berada di direktori `platforms/`, kini mencakup WeChat, Alipay, dan Douyin. WeChat mendukung pemantauan fingerprint deterministik dengan deteksi drift otomatis mingguan; pusat dokumen Alipay dan Douyin bersifat client-rendered sehingga fingerprint tidak dapat mengamati perubahan konten dan keduanya dilabeli jujur sebagai `manual-only` — kesegaran bergantung pada pemeriksaan dokumen resmi saat runtime dan laporan pengguna, bukan berpura-pura deteksi otomatis. Platform di luar cakupan selalu diperiksa ke sumber resmi dan dibiarkan `unknown`, tidak pernah ditebak.

---

## Cara Menggunakan

Clone repository ini ke direktori skill atau rules pada aplikasi Agent yang mendukung `SKILL.md`. Jika tidak ingin menjalankan perintah sendiri, kirim kalimat berikut ke Agent yang Anda gunakan:

```text
https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git bantu saya menginstal skill ini
```

Untuk Codex App / Codex local skills:

```bash
git clone https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git \
  ~/.codex/skills/mini-program-engineering-suite
```

Untuk universal Agent Skills runners:

```bash
git clone https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git \
  ~/.agents/skills/mini-program-engineering-suite
```

Jika memakai installer, `--target codex` mengarah ke `~/.codex/skills`, sedangkan `--target agents` mengarah ke `~/.agents/skills`.

Setelah instalasi, buka sesi Agent baru dan jalankan:

```text
/mini-program-engineering-suite Saya ingin membuat WeChat Mini Program dari nol. Bantu mulai dari scope produk dan langkah pengembangan.
```

---

## Yang Tidak Dilakukan

Suite ini tidak otomatis menginstal dependency, membuat cloud resources, mengunggah package, mengirim review, merilis versi, atau mengubah status online. Setiap external write action tetap membutuhkan otorisasi terpisah.

---

## Verifikasi

Sebelum dianggap siap dibekukan, suite ini melewati structural validation, sensitive-content scanning, deterministic public-package export, manifest verification, routing evaluation, behavior evaluation, dan independent final judgment.

Mulai 2.0 ada **platform rule freshness**: langkah yang menyentuh platform (upload/review/privacy) selalu mengikuti aturan resmi terkini — versi lokal yang sedikit lama tidak akan menjalankan aturan kedaluwarsa. Engine evaluasi dan model dapat diganti-ganti (codex / claude / gemini / API kompatibel OpenAI).

Lapisan evaluasi, batas bukti, dan ringkasan publik per versi dijelaskan di [EVALUATIONS.md](EVALUATIONS.md).

Pemeriksaan lokal:

```bash
python3 -m unittest discover -s tests -q
python3 scripts/validate_suite.py .
python3 scripts/check_i18n_readme_structure.py .
python3 scripts/scan_sensitive_content.py . --format json
```

---

## Integritas Paket

Utamakan package berversi dari [GitHub Releases](https://github.com/NocodeMrLi/mini-program-engineering-skill-suite/releases). Setiap Release menyertakan archive, `package-manifest.json`, dan `SHA256SUMS`. Di Linux / GitHub Actions gunakan `sha256sum -c SHA256SUMS`; di macOS gunakan `shasum -a 256 -c SHA256SUMS`. Setelah diekstrak, verifikasi ulang manifest dengan `verify_public_package.py` di dalam package.

Untuk memeriksa package yang diterima:

```bash
python3 <package-dir>/scripts/verify_public_package.py <package-dir>
```

Contoh v3.1.6 (setelah mengunduh dari Release):

```bash
tar -xzf mini-program-engineering-suite-v3.1.6.tar.gz
python3 mini-program-engineering-suite-v3.1.6/scripts/verify_public_package.py \
  mini-program-engineering-suite-v3.1.6
```

---

## Versi

Versi saat ini: **3.1.6**.

---

## Lisensi

Lisensi: **MIT License**.
