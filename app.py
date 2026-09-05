import math
import json
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

BASE = "https://fapi.binance.com"
STEP = 15 * 60 * 1000


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Angka tidak valid pada data Binance.")
    return result


def utc(ms):
    return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def candle_metrics(rows, now):
    closed = sorted([r for r in rows if int(r[6]) < now], key=lambda r: int(r[0]))
    if len(closed) < 21:
        raise ValueError("Perlu minimal 21 candle tertutup.")
    recent = closed[-21:]
    if any(int(b[0]) - int(a[0]) != STEP for a, b in zip(recent, recent[1:])):
        raise ValueError("Ada candle hilang atau duplikat.")
    if not 0 <= now - int(closed[-1][6]) <= STEP + 60000:
        raise ValueError("Candle kedaluwarsa atau waktu tidak sesuai.")
    price = number(closed[-1][4])
    old = number(closed[-5][4])
    volumes = [number(r[7]) for r in closed[-21:-1]]
    last_volume = number(closed[-1][7])
    average = sum(volumes) / 20
    if old <= 0 or price <= 0 or average <= 0 or min(volumes + [last_volume]) < 0:
        raise ValueError("Harga/volume tidak valid untuk perhitungan.")
    return closed, (price / old - 1) * 100, last_volume / average


def oi_metrics(rows, now):
    ordered = sorted(rows, key=lambda r: int(r["timestamp"]))
    if len(ordered) < 5:
        raise ValueError("Riwayat open interest belum cukup.")
    latest = ordered[-1]
    target = int(latest["timestamp"]) - 3600000
    matches = [r for r in ordered if int(r["timestamp"]) == target]
    if not matches:
        raise ValueError("Titik open interest satu jam sebelumnya tidak tersedia.")
    if not 0 <= now - int(latest["timestamp"]) <= 2 * STEP:
        raise ValueError("Riwayat open interest kedaluwarsa atau bertanggal masa depan.")
    old = number(matches[-1]["sumOpenInterest"])
    new = number(latest["sumOpenInterest"])
    if old <= 0 or new < 0:
        raise ValueError("Open interest tidak valid.")
    return latest, (new / old - 1) * 100


def score_rules(ret, rvol, oi_change, funding, breakout, breakdown):
    ret, rvol, oi_change, funding = map(number, (ret, rvol, oi_change, funding))
    if rvol < 0 or (breakout and breakdown):
        raise ValueError("Input skor tidak konsisten.")
    rules = [
        ("Momentum 1H", "Naik >= 2% / turun <= -2%", 25, ret >= 2, ret <= -2),
        ("Volume", "RVOL >= 2, dengan arah return 1H", 20, rvol >= 2 and ret > 0, rvol >= 2 and ret < 0),
        ("Open interest", "OI naik >= 3%, dengan arah return 1H", 20, oi_change >= 3 and ret > 0, oi_change >= 3 and ret < 0),
        ("Funding", "Negatif + harga naik / positif + harga turun", 15, funding < 0 and ret > 0, funding > 0 and ret < 0),
        ("Struktur harga", "Close melewati high/low 20 candle sebelumnya", 20, breakout, breakdown),
    ]
    details = [{"Komponen": name, "Aturan": rule, "Poin short-pressure": weight if short else 0, "Poin long-pressure": weight if long else 0} for name, rule, weight, short, long in rules]
    return sum(r["Poin short-pressure"] for r in details), sum(r["Poin long-pressure"] for r in details), details


def build_score(data, symbol, now, local_now):
    if not -60000 <= local_now - now <= 120000:
        raise ValueError("Snapshot lama atau jam komputer berbeda. Klik Ambil data lengkap.")
    # Align to a boundary actually present in BOTH feeds, never to future data.
    candle_boundaries = {int(r[6]) + 1 for r in data["candles"] if int(r[6]) < now}
    oi_boundaries = {int(r["timestamp"]) for r in data["oi"]}
    common = candle_boundaries & oi_boundaries
    if not common:
        raise ValueError("Tidak ada waktu yang cocok antara candle dan OI.")
    boundary = max(common)
    if not 0 <= now - boundary <= 2 * STEP:
        raise ValueError("Data bersama candle/OI lebih lama dari 30 menit. Ambil data lagi.")
    aligned_candles = [r for r in data["candles"] if int(r[6]) < boundary]
    closed, ret, rvol = candle_metrics(aligned_candles, boundary)
    history = [r for r in data["oi"] if int(r["timestamp"]) <= boundary]
    latest, oi_change = oi_metrics(history, now)
    if int(latest["timestamp"]) != boundary:
        raise ValueError("Waktu OI belum selaras dengan candle. Tunggu lalu ambil data lagi.")
    funding = data["funding"]
    if funding["symbol"] != symbol or any(r["symbol"] != symbol for r in history):
        raise ValueError("Simbol tidak sesuai.")
    if abs(now - int(funding["time"])) > 120000:
        raise ValueError("Data funding terlalu lama.")
    for row in closed[-21:]:
        o, h, low, c = map(number, row[1:5])
        if low <= 0 or low > min(o, c) or h < max(o, c) or low > h:
            raise ValueError("OHLC tidak valid.")
    price = number(closed[-1][4])
    breakout = price > max(number(r[2]) for r in closed[-21:-1])
    breakdown = price < min(number(r[3]) for r in closed[-21:-1])
    rate = number(funding["lastFundingRate"])
    short, long, details = score_rules(ret, rvol, oi_change, rate, breakout, breakdown)
    return {"symbol": symbol, "rules_version": "prototype-0.1", "source": "Binance Futures REST API", "server_time_utc": utc(now), "candle_oi_boundary_utc": utc(boundary), "funding_time_utc": utc(funding["time"]), "return_1h_pct": ret, "rvol": rvol, "oi_change_1h_pct": oi_change, "funding_raw": rate, "breakout": breakout, "breakdown": breakdown, "short_pressure": short, "long_pressure": long, "components": details, "limitations": "Heuristic index, not probability. Not backtested. No AI model or MCP integration. Funding is a current contextual reading, not aligned historical funding."}


st.set_page_config(page_title="Squeeze Guard AI", page_icon="🛡️", layout="wide")
st.title("🛡️ Squeeze Guard AI")
st.caption("Tahap 3 • Skor berbasis aturan • Binance USDT perpetual futures")
st.info("Skor prototipe, bukan probabilitas squeeze. Belum ada model AI. Sumber: Binance REST API.")
symbol = st.sidebar.selectbox("Pilih pasangan", ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"])
st.sidebar.caption("Tanpa API key Binance, tanpa transaksi. Pembaruan manual.")


@st.cache_data(ttl=30, show_spinner=False)
def fetch(path, pairs=()):
    response = requests.get(BASE + path, params=dict(pairs), timeout=(5, 15))
    if response.status_code in (418, 429):
        raise RuntimeError("Batas permintaan Binance tercapai. Tunggu sebelum mencoba lagi.")
    response.raise_for_status()
    return response.json()


if st.button("Ambil data lengkap", type="primary"):
    result = {"data": {}, "errors": {}, "log": [], "fetched": utc(datetime.now(timezone.utc).timestamp() * 1000)}
    endpoints = [
        ("time", "/fapi/v1/time", {}),
        ("ticker", "/fapi/v1/ticker/24hr", {"symbol": symbol}),
        ("candles", "/fapi/v1/klines", {"symbol": symbol, "interval": "15m", "limit": 60}),
        ("funding", "/fapi/v1/premiumIndex", {"symbol": symbol}),
        ("oi", "/futures/data/openInterestHist", {"symbol": symbol, "period": "15m", "limit": 8}),
    ]
    with st.spinner("Mengambil lima kelompok data. Mohon tunggu..."):
        for name, path, params in endpoints:
            try:
                result["data"][name] = fetch(path, tuple(sorted(params.items())))
                result["log"].append({"Sumber": path, "Status": "Diterima / cache maksimal 30 detik"})
            except (requests.RequestException, ValueError, RuntimeError) as err:
                result["errors"][name] = str(err)
                result["log"].append({"Sumber": path, "Status": "Gagal"})
                if isinstance(err, RuntimeError):
                    break
    st.session_state["snapshot_" + symbol] = result

snapshot = st.session_state.get("snapshot_" + symbol)
if snapshot:
    data = snapshot["data"]
    st.caption("Snapshot diambil: " + snapshot["fetched"] + " • Cache maksimal 30 detik. Klik tombol untuk memperbarui.")
    for name, message in snapshot["errors"].items():
        st.error("Gagal mengambil " + name)
        st.code(message, language="text")
    try:
        now = int(data["time"]["serverTime"])
        elapsed = (datetime.now(timezone.utc).timestamp() * 1000 - now) / 1000
        if elapsed > 120 or elapsed < -60:
            st.warning("Snapshot sudah lama atau jam komputer berbeda. Periksa waktu lalu ambil data lagi.")
    except (KeyError, TypeError, ValueError):
        st.error("Waktu server tidak tersedia. Indikator belum dapat divalidasi.")
        st.stop()

    try:
        ticker = data["ticker"]
        if ticker["symbol"] != symbol or abs(now - int(ticker["closeTime"])) > 120000:
            raise ValueError("Simbol/waktu ticker tidak sesuai.")
        a, b, c = st.columns(3)
        a.metric("Harga terakhir (USDT)", f"{number(ticker['lastPrice']):,.4f}")
        b.metric("Perubahan 24H", f"{number(ticker['priceChangePercent']):+.2f}%")
        c.metric("Volume 24H (USDT)", f"{number(ticker['quoteVolume']):,.0f}")
    except (KeyError, TypeError, ValueError) as err:
        st.warning("Ticker belum valid: " + str(err))

    st.subheader("Candle 15 menit dan volume")
    try:
        closed, change, rvol = candle_metrics(data["candles"], now)
        a, b = st.columns(2)
        a.metric("Perubahan 1H • candle tertutup", f"{change:+.2f}%")
        b.metric("Relative volume • candle 15m", f"{rvol:.2f}x")
        st.caption("RVOL = volume USDT candle terakhir / rata-rata 20 candle sebelumnya. Candle yang masih berjalan tidak dipakai.")
        frame = pd.DataFrame([{"Waktu UTC": pd.to_datetime(int(r[0]), unit="ms", utc=True), "Open": number(r[1]), "High": number(r[2]), "Low": number(r[3]), "Close": number(r[4]), "Volume USDT": number(r[7])} for r in closed])
        st.line_chart(frame.set_index("Waktu UTC")[["Close"]])
        st.caption("Grafik garis harga penutupan; tabel OHLC tersedia di bawah.")
        with st.expander("Lihat candle OHLC dan volume"):
            st.dataframe(frame, hide_index=True)
        st.caption("Candle terakhir ditutup: " + utc(closed[-1][6]))
    except (KeyError, IndexError, TypeError, ValueError) as err:
        st.warning("Indikator candle belum tersedia: " + str(err))

    st.subheader("Funding dan open interest")
    try:
        funding = data["funding"]
        if funding["symbol"] != symbol or abs(now - int(funding["time"])) > 120000:
            raise ValueError("Simbol/waktu funding tidak sesuai.")
        st.metric("Funding • lastFundingRate", f"{number(funding['lastFundingRate']) * 100:+.5f}%")
        st.caption("Waktu data: " + utc(funding["time"]) + " • Funding berikutnya: " + utc(funding["nextFundingTime"]))
        st.caption("Nilai dari premiumIndex; tidak dinormalisasi per 8 jam dan bukan prediksi funding berikutnya.")
    except (KeyError, TypeError, ValueError) as err:
        st.warning("Funding belum tersedia: " + str(err))
    try:
        latest, change = oi_metrics(data["oi"], now)
        if latest["symbol"] != symbol:
            raise ValueError("Simbol open interest tidak sesuai.")
        a, b = st.columns(2)
        a.metric("OI • sumOpenInterest (unit aset dasar)", f"{number(latest['sumOpenInterest']):,.3f}")
        b.metric("Perubahan OI 1H", f"{change:+.2f}%")
        st.caption("Waktu titik OI terakhir: " + utc(latest["timestamp"]) + " • Interval riwayat: 15 menit. Bukan OI tick saat ini.")
    except (KeyError, TypeError, ValueError) as err:
        st.warning("Open interest belum tersedia: " + str(err))
    st.subheader("Skor kondisi squeeze • prototipe 0.1")
    st.caption("Dihitung pada snapshot, tidak dipantau otomatis. Skor rendah tidak berarti aman.")
    try:
        report = build_score(data, symbol, now, datetime.now(timezone.utc).timestamp() * 1000)
        a, b = st.columns(2)
        a.metric("Short-pressure • tekanan terhadap short", str(report["short_pressure"]) + " / 100")
        b.metric("Long-pressure • tekanan terhadap long", str(report["long_pressure"]) + " / 100")
        st.dataframe(report["components"], hide_index=True)
        st.caption("Waktu bersama untuk skor: " + report["candle_oi_boundary_utc"] + " • Maksimal tertinggal 30 menit dari waktu server snapshot.")
        st.caption(f"Input skor pada waktu tersebut: return 1H {report['return_1h_pct']:+.2f}% | RVOL {report['rvol']:.2f}x | OI 1H {report['oi_change_1h_pct']:+.2f}%. Indikator di atas dapat memakai data lebih baru.")
        st.caption("Funding memakai pembacaan terbaru sebagai konteks; bukan funding historis pada batas candle.")
        st.warning("Bobot dan ambang adalah rancangan awal yang belum diuji akurasi prediksinya. OI tidak mengungkap arah posisi; funding saja tidak membuktikan penumpukan short/long. Squeeze dapat terjadi tanpa skor tinggi.")
        st.download_button("Unduh laporan JSON", json.dumps(report, indent=2, allow_nan=False), file_name=f"squeeze_guard_{symbol}.json", mime="application/json")
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as err:
        st.warning("SKOR BELUM TERSEDIA — " + str(err))
    with st.expander("Log sumber data"):
        st.dataframe(snapshot["log"], hide_index=True)
else:
    st.info("Pilih BTCUSDT lalu klik Ambil data lengkap.")
st.divider()
st.caption("Belum ada rekomendasi transaksi, pemindaian seluruh pasar, model AI, atau MCP. Skor bukan bukti likuidasi aktual.")
