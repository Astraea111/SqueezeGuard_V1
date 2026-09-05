# Squeeze Guard

Squeeze Guard adalah prototipe dashboard untuk memeriksa kondisi pasar Binance USDT perpetual futures. Dashboard menampilkan data pasar dan dua indeks berbasis aturan: **short-pressure** dan **long-pressure**. Setiap komponen skor dapat diperiksa, lalu laporan JSON dapat diverifikasi melalui Binance Agent OS di ChatGPT.

## Alur kerja

1. Pengguna mengambil data publik Binance melalui dashboard Streamlit.
2. Python memvalidasi waktu data dan menghitung indikator serta skor.
3. Pengguna mengunduh laporan JSON dan mengunggahnya ke ChatGPT.
4. ChatGPT menggunakan koneksi Binance Agent OS yang tersedia untuk memeriksa data pada waktu laporan dan menjelaskan hasilnya.

Pemindahan laporan dilakukan manual. Dashboard belum terhubung otomatis ke model AI atau MCP. Nama antarmuka “Squeeze Guard AI” merujuk pada proyek; perhitungan di dashboard sendiri menggunakan aturan Python.

## Fitur saat ini

- Pilihan BTCUSDT, ETHUSDT, BNBUSDT, dan SOLUSDT.
- Harga terakhir, perubahan harga dan volume USDT 24 jam.
- Grafik garis harga penutupan dan tabel OHLC candle 15 menit.
- Return 1 jam dan relative volume (RVOL) dari candle tertutup.
- Funding dan riwayat open interest (OI).
- Skor dengan rincian poin per komponen dan waktu data.
- Ekspor JSON dan log keberhasilan pengambilan data.

Pembaruan dilakukan dengan tombol **Ambil data lengkap**. Cache permintaan berlaku maksimal 30 detik; data tidak diperbarui otomatis.

## Berkas proyek

| Berkas | Fungsi |
|---|---|
| `app.py` | Dashboard dan perhitungan indikator |
| `SQUEEZE_GUARD_INSTRUCTIONS.md` | Instruksi pemeriksaan laporan melalui ChatGPT dan Binance Agent OS |
| `README.md` | Panduan ini |
| `squeeze_guard_BTCUSDT.json` | Contoh nama laporan yang diunduh dari dashboard |

## Menjalankan di Windows

Prasyarat: Python dengan perintah `py`, koneksi internet, dan berkas proyek dalam satu folder. Proyek ini telah dijalankan pengguna dengan Python 3.14.7.

### Instalasi pertama

Buka folder SqueezeGuard di File Explorer. Klik bilah alamat, ketik `cmd`, lalu tekan Enter. Jalankan perintah berikut satu per satu:

```bat
py -m venv .venv
.venv\Scripts\python.exe -m pip install streamlit pandas requests
.venv\Scripts\python.exe -m streamlit run app.py
```

Buka `http://localhost:8501` jika browser tidak terbuka otomatis. Biarkan jendela CMD tetap terbuka selama aplikasi digunakan.

### Menjalankan kembali

Jika dependensi sudah dipasang, buka CMD dari folder proyek dan jalankan:

```bat
.venv\Scripts\python.exe -m streamlit run app.py
```

Tidak perlu menginstal ulang Python setiap kali membuka aplikasi. Untuk menghentikan server, tekan Ctrl+C di CMD.

## Memakai dashboard dan Agent OS

1. Pilih pasangan, misalnya BTCUSDT.
2. Klik **Ambil data lengkap** dan tunggu proses selesai.
3. Periksa waktu data, indikator, dan tabel skor.
4. Klik **Unduh laporan JSON**.
5. Unggah JSON ke ChatGPT yang memiliki koneksi Binance Agent OS. Sertakan instruksi dari `SQUEEZE_GUARD_INSTRUCTIONS.md`.
6. Minta pemeriksaan pada waktu laporan yang sama. Bedakan data yang cocok, berbeda, dan belum dapat diverifikasi.

Contoh pesan:

> Periksa laporan JSON ini mengikuti SQUEEZE_GUARD_INSTRUCTIONS.md. Gunakan Binance Agent OS untuk memverifikasi candle pada candle_oi_boundary_utc. Tampilkan close terakhir, high tertinggi 20 candle sebelumnya, hasil breakout, dan waktu data. Jangan mengakses saldo atau melakukan transaksi. Jika tool gagal, jelaskan kegagalannya tanpa mengarang data.

Alur ini tidak memerlukan pembelian kredit API model untuk dashboard. Penggunaan ChatGPT dan koneksi Agent OS mengikuti akses serta batas penggunaan akun pengguna.

## Data dan perhitungan

Dashboard memakai API publik di `https://fapi.binance.com`:

| Endpoint | Penggunaan |
|---|---|
| `/fapi/v1/time` | Waktu server |
| `/fapi/v1/ticker/24hr` | Ringkasan harga dan volume 24 jam |
| `/fapi/v1/klines` | 60 candle, interval 15 menit |
| `/fapi/v1/premiumIndex` | Pembacaan `lastFundingRate` dan waktu funding |
| `/futures/data/openInterestHist` | 8 titik OI, interval 15 menit |

Candle yang masih berjalan dikeluarkan dari perhitungan. Untuk skor, aplikasi memilih batas waktu terakhir yang tersedia pada candle dan OI, maksimal 30 menit sebelum waktu server snapshot. Indikator bagian atas dashboard dapat memakai data lebih baru daripada skor.

- **Return 1H:** `(close terakhir / close empat interval sebelumnya − 1) × 100`.
- **RVOL:** quote volume candle terakhir dibagi rata-rata quote volume 20 candle sebelumnya.
- **Perubahan OI 1H:** `(sumOpenInterest pada batas waktu / sumOpenInterest satu jam sebelumnya − 1) × 100`.
- **Breakout:** close terakhir lebih besar daripada high tertinggi 20 candle sebelumnya.
- **Breakdown:** close terakhir lebih kecil daripada low terendah 20 candle sebelumnya.

Candle terakhir tidak masuk ke kelompok 20 candle pembanding. Close yang sama dengan high/low pembanding tidak memenuhi breakout/breakdown. OI memakai unit aset dasar, bukan nilai dolar. Funding memakai pembacaan terbaru sebagai konteks, bukan data historis yang diselaraskan ke batas candle.

## Aturan skor prototype-0.1

Setiap kondisi memberikan seluruh bobot atau nol. Kedua kolom dijumlahkan secara terpisah, masing-masing maksimum 100.

| Komponen | Bobot | Short-pressure | Long-pressure |
|---|---:|---|---|
| Momentum | 25 | Return 1H ≥ +2% | Return 1H ≤ −2% |
| Volume | 20 | RVOL ≥ 2 dan return > 0 | RVOL ≥ 2 dan return < 0 |
| Open interest | 20 | Perubahan OI ≥ +3% dan return > 0 | Perubahan OI ≥ +3% dan return < 0 |
| Funding | 15 | Funding negatif dan return > 0 | Funding positif dan return < 0 |
| Struktur harga | 20 | Breakout terpenuhi | Breakdown terpenuhi |

Skor adalah indeks heuristik yang belum diuji akurasi prediksinya. Skor bukan probabilitas squeeze, bukti likuidasi, atau rekomendasi transaksi. Skor rendah tidak berarti aman. OI sendiri tidak mengungkap arah posisi; funding sendiri tidak membuktikan penumpukan posisi long atau short.

## Jika terjadi masalah

| Gejala | Langkah |
|---|---|
| `localhost refused to connect` | Jalankan kembali perintah Streamlit dari folder proyek dan biarkan CMD terbuka. Jika gagal, baca pesan error di CMD. |
| `SKOR BELUM TERSEDIA` | Baca penyebab yang ditampilkan, periksa jam komputer, lalu ambil data lagi setelah jeda. Data candle dan OI mungkin belum memiliki waktu bersama yang cukup baru. |
| SSL hostname mismatch | Periksa sertifikat dan koneksi jaringan. Sertifikat untuk domain lain menunjukkan koneksi belum mencapai identitas host yang diharapkan. Jangan menonaktifkan verifikasi SSL. |
| Batas permintaan tercapai | Tunggu sebelum mengambil data lagi; hindari menekan tombol berulang kali. |
| Tool Agent OS tidak tersedia atau gagal | Laporkan bagian yang belum terverifikasi. Jangan mengganti data hilang dengan angka buatan. |

Mengubah DNS hanya di browser tidak otomatis mengubah koneksi Python. Pada pengujian pengguna, akses aplikasi berhasil setelah memakai WARP di Windows; hasil pada jaringan lain dapat berbeda.

## Ruang lingkup dan demo

Aplikasi menggunakan data pasar publik tanpa meminta API key Binance. Tidak ada akses saldo, order, transfer, atau transaksi. Belum ada pemindaian seluruh pasangan, pemantauan otomatis, backtest, atau model AI di dashboard.

Untuk demo, tampilkan pemilihan pasangan, pengambilan data, waktu candle/OI, rincian skor, unduhan JSON, lalu pemeriksaan melalui Agent OS di ChatGPT. Sebutkan dengan jelas jika verifikasi hanya mencakup candle; OI dan funding tidak boleh dinyatakan terverifikasi tanpa bukti pada waktu yang sesuai.

Dokumentasi ini menjelaskan prototipe yang ada dan tidak menyatakan jaminan kelayakan atau hasil kompetisi.
