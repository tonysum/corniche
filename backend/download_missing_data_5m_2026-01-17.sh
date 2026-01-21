#!/bin/bash
# 根据数据完整性检查结果自动生成的下载脚本
# 生成时间: 2026-01-17 18:01:50
# K线间隔: 5m

# 下载缺失的交易对和缺失日期的数据

# 下载缺失日期的数据
python download_klines.py --interval 5m --symbols SUPERUSDT --start-time 2025-07-21 --end-time 2025-07-21 --update
python download_klines.py --interval 5m --symbols OMUSDT --start-time 2025-09-01 --end-time 2025-09-10 --update
python download_klines.py --interval 5m --symbols STRKUSDT --start-time 2025-06-04 --end-time 2025-06-13 --update
python download_klines.py --interval 5m --symbols METISUSDT --start-time 2025-10-23 --end-time 2025-11-01 --update
python download_klines.py --interval 5m --symbols VANRYUSDT --start-time 2025-09-01 --end-time 2025-09-10 --update
python download_klines.py --interval 5m --symbols ETHFIUSDT --start-time 2025-06-04 --end-time 2025-06-09 --update
python download_klines.py --interval 5m --symbols TAOUSDT --start-time 2025-12-19 --end-time 2025-12-28 --update
python download_klines.py --interval 5m --symbols BBUSDT --start-time 2025-09-16 --end-time 2025-09-25 --update
python download_klines.py --interval 5m --symbols TURBOUSDT --start-time 2025-08-21 --end-time 2025-08-30 --update
python download_klines.py --interval 5m --symbols ZKUSDT --start-time 2025-11-07 --end-time 2025-11-16 --update
python download_klines.py --interval 5m --symbols RENDERUSDT --start-time 2025-09-01 --end-time 2025-09-10 --update
python download_klines.py --interval 5m --symbols DEXEUSDT --start-time 2025-12-29 --end-time 2026-01-07 --update
python download_klines.py --interval 5m --symbols BIOUSDT --start-time 2025-08-16 --end-time 2025-08-25 --update
python download_klines.py --interval 5m --symbols SUSDT --start-time 2025-07-16 --end-time 2025-07-25 --update
python download_klines.py --interval 5m --symbols AVAAIUSDT --start-time 2025-06-04 --end-time 2025-06-09 --update
python download_klines.py --interval 5m --symbols VINEUSDT --start-time 2025-06-20 --end-time 2025-06-29 --update
python download_klines.py --interval 5m --symbols IPUSDT --start-time 2025-07-16 --end-time 2025-07-25 --update
python download_klines.py --interval 5m --symbols KAITOUSDT --start-time 2025-06-14 --end-time 2025-06-23 --update
python download_klines.py --interval 5m --symbols EPICUSDT --start-time 2025-06-30 --end-time 2025-07-09 --update
python download_klines.py --interval 5m --symbols FORMUSDT --start-time 2025-07-05 --end-time 2025-07-14 --update
python download_klines.py --interval 5m --symbols BROCCOLI714USDT --start-time 2025-09-21 --end-time 2025-09-30 --update

