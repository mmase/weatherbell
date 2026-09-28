# Upstream data specifications of NWP / analysis datasets (ingest sizing, as of 2026-09-28)

**Method note (read first).** Egress from this research session let S3 through: `*.s3.amazonaws.com` anonymous ListObjectsV2 worked. Everything else was blocked, including NOMADS (nomads.ncep.noaa.gov), MSC Datamart (dd.weather.gc.ca), DWD opendata (opendata.dwd.de), www.ecmwf.int, www.weather.gov and gribstream.com (proxy returned 403 / EGRESS_BLOCKED). As a result:
- **MEASURED** = summed object sizes from a full S3 listing of one real day, **2026-09-27** (listed on 2026-09-28). `.idx` files are excluded. GB = 10^9 bytes. Latency = S3 `LastModified` minus cycle time. Because AWS mirrors lag the origin, NOMADS or dissemination is usually a few minutes earlier.
- **CITED** = from web-search result snippets of primary or secondary sources. The pages could not be opened, so each fact rests on the snippet.
- **ESTIMATE** = computed from grid spec × fields × bits per value. Where a grid spec comes from my background knowledge and was not verified in this session, it is flagged "(unverified spec)".
- Listing script: anonymous `https://<bucket>.s3.amazonaws.com/?list-type=2&prefix=<prefix>`, paginated, sizes summed and grouped by filename pattern.

---

## Q1. Raw bytes per run and per day for each dataset, and which are heaviest

### Takeaway
Measured on 2026-09-27, the heaviest full-product feeds are ECMWF open data at ~3.2 TB/day (driven by the 51-member IFS ENS at 6.6 GB per step), GEFS at ~2.7 TB/day, HAFS-A+B at ~2.3 TB/day in-season, and GFS at ~1.8 TB/day. The per-day ranking continues with HRRR (CONUS 0.86 TB + Alaska 0.25 TB), NBM (~1.06 TB), NAM (0.56 TB, retiring), RTOFS (0.38 TB), Met Office global (0.39 TB), CFSv2 (0.31 TB), GOES ABI L1b (~0.16 TB per satellite) and MRMS CONUS (~0.10 TB). Subsetting cuts this sharply: GFS pgrb2.0p25 alone is 113 GB/run, and HRRR without the native-level `wrfnat` files is ~434 GB/day.

### Cited Findings

#### A. Measured day totals (S3, 2026-09-27)

| Dataset | Bucket / prefix | Per run (measured) | Per day (measured) | Notes |
|---|---|---|---|---|
| **ECMWF open data** (IFS HRES + ENS + AIFS single + AIFS ENS + wave, 0.25°) | `ecmwf-forecasts/20260927/{00,06,12,18}z/` | 00z 934.8 GB; 06z 670.9 GB; 12z 936.0 GB; 18z 671.5 GB | **3,213 GB** | [S3 listing](https://ecmwf-forecasts.s3.amazonaws.com/?list-type=2&prefix=20260927/) |
| **GEFS** (atmos + wave + chem + init) | `noaa-gefs-pds/gefs.20260927/HH/` | 00z (35-day) 870.0 GB; 12z 602.0 GB; 18z 601.9 GB; 06z atmos only 544.2 GB (+wave/chem ≈ 58 GB) | **≈2,676 GB** | [S3](https://noaa-gefs-pds.s3.amazonaws.com/?list-type=2&prefix=gefs.20260927/) |
| **HAFS-A** | `noaa-nws-hafs-pds/hfsa/20260927/` | ~40–90 GB per storm-cycle (depends on storm and length) | **1,310 GB** (15 E-Pac storm-cycles + W-Pac + Atlantic that day) | [S3](https://noaa-nws-hafs-pds.s3.amazonaws.com/?list-type=2&prefix=hfsa/20260927/) |
| **HAFS-B** | `noaa-nws-hafs-pds/hfsb/20260927/` | similar | **960 GB** | [S3](https://noaa-nws-hafs-pds.s3.amazonaws.com/?list-type=2&prefix=hfsb/20260927/) |
| **GFS** (all atmos incl. native netCDF, + wave) | `noaa-gfs-bdp-pds/gfs.20260927/` | 06z/12z atmos ≈ 411.5–412.1 GB; wave 39.7 GB | **1,808 GB** (60,264 objects) | [S3](https://noaa-gfs-bdp-pds.s3.amazonaws.com/?list-type=2&prefix=gfs.20260927/) |
| **NBM v4.x** (core + qmd + text, all domains) | `noaa-nbm-grib2-pds/blend.20260927/` | 12z (core+qmd) 156.5 GB; 13z (core only) 28.6 GB | **1,062 GB** (19,496 objects, 24 cycles) | [S3](https://noaa-nbm-grib2-pds.s3.amazonaws.com/?list-type=2&prefix=blend.20260927/) |
| **HRRR CONUS** | `noaa-hrrr-bdp-pds/hrrr.20260927/conus/` | 00z (f00–f48) 70.7 GB; 01z (f00–f18) 28.9 GB | **862.8 GB** (2,232 files) | [S3](https://noaa-hrrr-bdp-pds.s3.amazonaws.com/?list-type=2&prefix=hrrr.20260927/conus/) |
| **HRRR Alaska** | `…/hrrr.20260927/alaska/` | ~31 GB (8 cycles/day) | **251.4 GB** | [S3](https://noaa-hrrr-bdp-pds.s3.amazonaws.com/?list-type=2&prefix=hrrr.20260927/alaska/) |
| **NAM** (all domains incl. nests) | `noaa-nam-pds/nam.20260927/` | ~141 GB | **564.2 GB** (4,092 files) | [S3](https://noaa-nam-pds.s3.amazonaws.com/?list-type=2&prefix=nam.20260927/) |
| **Met Office global deterministic 10 km** (netCDF) | `met-office-atmospheric-model-data/global-deterministic-10km/` | 00z/12z 116.7 GB (4,527 files); 06z/18z 78.6 GB (3,035 files) | **390.6 GB** | [S3](https://met-office-atmospheric-model-data.s3.amazonaws.com/?list-type=2&prefix=global-deterministic-10km/20260927T1200Z/) |
| **RTOFS global** | `noaa-nws-rtofs-pds/rtofs.20260927/` | 1 run/day | **380.3 GB** (forecast `f*` files 267.8 GB) | [S3](https://noaa-nws-rtofs-pds.s3.amazonaws.com/?list-type=2&prefix=rtofs.20260927/) |
| **CFSv2** (6-hourly + monthly + time series) | `noaa-cfs-pds/cfs.20260927/HH/` | 00z 103.8 GB; 06z 69.3; 12z 69.2; 18z 69.2 | **311.5 GB** | [S3](https://noaa-cfs-pds.s3.amazonaws.com/?list-type=2&prefix=cfs.20260927/) |
| **GOES-19 (East) ABI L1b** RadF+RadC+RadM | `noaa-goes19/ABI-L1b-Rad{F,C,M}/2026/270/` | — | 103.5 + 32.7 + 24.6 = **160.8 GB** | [S3](https://noaa-goes19.s3.amazonaws.com/?list-type=2&prefix=ABI-L1b-RadF/2026/270/) |
| GOES-18 (West) ABI L1b | `noaa-goes18/…` | — | 103.5 + 32.7 + 26.0 = **162.2 GB** | [S3](https://noaa-goes18.s3.amazonaws.com/?list-type=2&prefix=ABI-L1b-RadF/2026/270/) |
| GOES-19 ABI L2 MCMIP (cloud & moisture imagery, all 16 bands in one file) | `ABI-L2-MCMIPF`, `ABI-L2-MCMIPC` | Full disk 331 MB per scan; CONUS 52 MB per scan | 44.3 (F) + 14.5 (C) = 58.8 GB | [S3](https://noaa-goes19.s3.amazonaws.com/?list-type=2&prefix=ABI-L2-MCMIPF/2026/270/) |
| GOES-19 GLM L2 LCFA | `GLM-L2-LCFA` | 20-s files, ~0.3 MB | **1.5 GB** (4,314 files) | [S3](https://noaa-goes19.s3.amazonaws.com/?list-type=2&prefix=GLM-L2-LCFA/2026/270/) |
| **MRMS CONUS** (all 243 products) | `noaa-mrms-pds/CONUS/*/20260927/` | 2-min cadence | **102.6 GB** (99,820 files) | [S3](https://noaa-mrms-pds.s3.amazonaws.com/?list-type=2&prefix=CONUS/) |
| **AIGFS** (GraphCast-based) | `noaa-nws-graphcastgfs-pds/aigfs.20260927/` | ~5.5 GB (65 steps × (71 MB pres + 8 MB sfc)) | **22.1 GB** | [S3](https://noaa-nws-graphcastgfs-pds.s3.amazonaws.com/?list-type=2&prefix=aigfs.20260927/) |
| Met Office UK deterministic 2 km | `met-office-atmospheric-model-data/uk-deterministic-2km/` | 12z 19.0 GB (3,788 files) | not summed (≈ runs × 19 GB) | [S3](https://met-office-atmospheric-model-data.s3.amazonaws.com/?list-type=2&prefix=uk-deterministic-2km/20260927T1200Z/) |
| URMA 2.5 km CONUS | `noaa-urma-pds/urma2p5.20260927/` | 24 hourly analyses | **5.72 GB** | [S3](https://noaa-urma-pds.s3.amazonaws.com/?list-type=2&prefix=urma2p5.20260927/) |
| RTMA 2.5 km CONUS (hourly) | `noaa-rtma-pds/rtma2p5.20260927/` | 24 hourly analyses | **5.56 GB** | [S3](https://noaa-rtma-pds.s3.amazonaws.com/?list-type=2&prefix=rtma2p5.20260927/) |
| OISST v2.1 AVHRR (0.25° daily) | `noaa-cdr-sea-surface-temp-optimum-interpolation-pds/data/v2.1/avhrr/202609/` | 1 file/day ≈ 1.55 MB netCDF | ~1.5 MB/day (preliminary and final versions both published) | [S3](https://noaa-cdr-sea-surface-temp-optimum-interpolation-pds.s3.amazonaws.com/?list-type=2&prefix=data/v2.1/avhrr/202609/) |

#### B. Measured per-file / per-forecast-hour sizes (the key numbers for pipeline sizing)

**HRRR CONUS** (3 km, `noaa-hrrr-bdp-pds`) — [S3](https://noaa-hrrr-bdp-pds.s3.amazonaws.com/?list-type=2&prefix=hrrr.20260927/conus/)
- `wrfprsf` (pressure levels): avg 431 MB/fh (f01 of 12z = 409.4 MB; f18 = 430 MB); 248.4 GB/day
- `wrfnatf` (native levels): avg 744 MB/fh; 428.7 GB/day — the single biggest HRRR stream
- `wrfsfcf` (surface/2D): avg 157 MB/fh; 90.7 GB/day
- `wrfsubhf` (15-min sub-hourly, 4 time levels per file): avg 202 MB/fh; 92.2 GB/day
- Per-run counts: 00z has 49 steps (f00–f48); 01z has 19 steps (f00–f18). The day held 576 prs files = 4 × 49 + 20 × 19, so the 00/06/12/18z runs go to 48 h.
- HRRR Alaska (`*.ak.grib2`): prs 269 MB, nat 479 MB, sfc 100 MB, subh 136 MB per fh; 272 files/day ⇒ 8 cycles (every 3 h), mix of 18 h and 48 h runs.

**GFS** (`noaa-gfs-bdp-pds`, per cycle) — [S3](https://noaa-gfs-bdp-pds.s3.amazonaws.com/?list-type=2&prefix=gfs.20260927/00/atmos/)
- `pgrb2.0p25.fFFF`: 209 files per cycle (f000–f120 hourly + f123–f384 3-hourly), avg **542 MB** (f000 = 494.4 MB, f001 = 524.1 MB), **113.4 GB per cycle**, 453.6 GB/day
- `pgrb2b.0p25`: avg 233 MB, 48.7 GB per cycle
- `pgrb2.0p50`: 129 files, avg 160 MB, 20.6 GB per cycle; `pgrb2b.0p50`: 68 MB avg, 8.8 GB
- `pgrb2full.0p50`: 228 MB avg, 29.4 GB per cycle
- `pgrb2.1p00`: 45 MB avg, 5.8 GB per cycle
- `sfluxgrbf` (native T1534 Gaussian surface-flux GRIB2): 209 files, avg **297 MB**, 62.1 GB per cycle
- Native netCDF history `atmfFFF.nc` (only 13 files posted, f000–f012): **7.1 GB each**, 92.9 GB per cycle; `atmanl.nc` 14.0 GB; `sfcfFFF.nc` 1.07 GB each
- Cycle total 411.5–412.1 GB (06z, 12z); day total 1,807.7 GB.
- GFS-Wave (`gfs.YYYYMMDD/HH/wave/`): 39.7 GB per cycle, 13,577 objects. Gridded global 0.25°/0.16° ≈ 11.5 MB/fh (4.8 GB per cycle); arctic 9 km 7.3 MB/fh; gsouth 5.2 MB/fh. The rest is station spectra tarballs (`ibp_tar` alone is 11.4 GB). — [S3](https://noaa-gfs-bdp-pds.s3.amazonaws.com/?list-type=2&prefix=gfs.20260927/12/wave/)

**GEFS v12** (`noaa-gefs-pds`) — [S3](https://noaa-gefs-pds.s3.amazonaws.com/?list-type=2&prefix=gefs.20260927/00/atmos/)
- 30 perturbed members (`gep01–30`) + control (`gec00`) + mean (`geavg`) + spread (`gespr`).
- `pgrb2ap5` (0.5°, primary fields): 15.2 MB per member-step
- `pgrb2bp5` (0.5°, secondary fields): 98.2 MB per member-step — the bulk of GEFS
- `pgrb2sp25` (0.25°, subset of fields, to f240 only = 81 steps): 18.8 MB per member-step
- 00z has 181 steps (0–240 h 3-hourly + 246–840 h 6-hourly ⇒ **35 days**); 06/12/18z have 105 steps (to 384 h).
- `init/` cold-start netCDF: ≈117 GB per cycle (580 MB × 6 tiles × 31 members).
- Totals: atmos 812.6 GB at 00z vs 544.2 GB at 06z. Wave (0.25° global, 31 members): 48.4 GB per cycle, 13.7 MB per member-step. Chem (aerosol, 0.25°): 9.0 GB per cycle, 110 MB/fh.
- The GEFS `init/` (117 GB/cycle) is pure model-restart data; an ingest pipeline would normally skip it, which cuts GEFS to ≈2.2 TB/day.

**ECMWF open data on AWS** (`ecmwf-forecasts`, all 0.25° GRIB2) — [S3](https://ecmwf-forecasts.s3.amazonaws.com/?list-type=2&prefix=20260927/00z/)
- IFS HRES (`ifs/0p25/oper/*-oper-fc.grib2`): **144 MB per step**. 00/12z: 85 steps (0–144 h 3-hourly + 150–360 h 6-hourly) = 12.2 GB per run. 06/18z: 49 steps (to 144 h) = 7.0 GB.
- IFS ENS (`ifs/0p25/enfo/*-enfo-ef.grib2`, 50 perturbed + control in one file): **6.63 GB per step**. 00/12z: 85 steps = **563 GB per run**. 06/18z: 49 steps = 325 GB. ENS products (`-ep`, probabilities): ~0.97 GB per run.
- IFS wave HRES: 10.8 MB per step (0.9 GB per run). Wave ENS (`waef-ef`): 537 MB per step (45.6 GB per run).
- AIFS single (`aifs-single/0p25/oper`): **85 MB per step**, 61 steps (0–360 h 6-hourly), 5.2 GB per run, 4 runs/day. AIFS wave single 8.2 MB per step.
- AIFS ENS (`aifs-ens/0p25/enfo`): perturbed members `-pf` **4.48 GB per step**, 61 steps, **273 GB per run**; control `-cf` 89 MB per step; 4 runs/day (≈1.1 TB/day). AIFS ENS wave `-pf` 421 MB per step.
- Day: 3,213 GB (IFS ENS ≈ 1.78 TB; AIFS ENS ≈ 1.09 TB).

**NAM** (`noaa-nam-pds`) — [S3](https://noaa-nam-pds.s3.amazonaws.com/?list-type=2&prefix=nam.20260927/)
- CONUS nest 3 km `conusnest.hiresfFF`: **997 MB/fh**, 61 steps (f00–f60), 243 GB/day
- Alaska nest: 843 MB/fh (205.7 GB/day). Puerto Rico nest: 86 MB/fh. Hawaii nest: 27 MB/fh. Fire-weather nest: 122 MB/fh (148 files/day).
- 12 km parent grids: `awphys` (grid 218) 64 MB/fh; `awip12`/`awip32` etc. 36 MB avg; `bgrdsf` 49 MB/fh.
- Day 564 GB.

**NBM** (`noaa-nbm-grib2-pds`) — [S3](https://noaa-nbm-grib2-pds.s3.amazonaws.com/?list-type=2&prefix=blend.20260927/12/)
- CONUS core (2.5 km): 67–119 MB/fh depending on cycle and lead.
- CONUS `qmd` (quantile/percentile) files: **240 MB/fh**, 276 files in the 12z run; Alaska qmd 285 MB/fh; oceanic qmd 261 MB/fh.
- The 12z run with qmd is 156.5 GB; hourly core-only cycles are ~29 GB. Day 1,062 GB over 24 cycles.

**RTOFS global** (1/12° HYCOM) — [S3](https://noaa-nws-rtofs-pds.s3.amazonaws.com/?list-type=2&prefix=rtofs.20260927/)
- `archv.a.tgz` 3-D archives: 5.75 GB each (32 per day = 184 GB)
- `archs.a.tgz` surface archives: 437 MB each (hourly)
- netCDF 2-D diag 194 MB and ice 67 MB per step; 3-D US_east/US_west/alaska subsets 138–282 MB per 3-hourly step
- Restart 11.8 GB
- Day 380 GB. A typical user-facing subset (2-D netCDF diag + ice ≈ 30 GB/day) is much smaller.

**CFSv2** (`noaa-cfs-pds`) — [S3](https://noaa-cfs-pds.s3.amazonaws.com/?list-type=2&prefix=cfs.20260927/00/)
- Per 6-hourly step: `pgbf` 22.1 MB, `ocnf` 9.7 MB, `ipvf` 4.7 MB, `flxf` 4.1 MB.
- 4 members per cycle (`6hrly_grib_01..04`). The 00z cycle has longer runs (1,900 pgbf files vs 1,287 at 06z).
- Monthly means: `ocnh` 42 MB, `pgbf` 27 MB. Daily time series: `wnd`, `ocn*`, `z` etc., 25–237 MB each.
- Day 311.5 GB.

**MRMS CONUS** — [S3](https://noaa-mrms-pds.s3.amazonaws.com/?list-type=2&prefix=CONUS/MergedReflectivityQCComposite_00.50/20260927/)
- 243 product directories, 99,820 gzip-GRIB2 files per day.
- Composite reflectivity: 1.16 MB per 2-min file (0.83 GB/day). PrecipRate: 0.47 MB (0.34 GB/day). Each 3-D MergedReflectivityQC tilt: 0.26 MB.
- Largest products: BrightBandTop/BottomHeight 12.5–12.8 GB/day each; SeamlessHSRHeight 11.0 GB/day; MergedReflectivityComposite 6.6 GB/day.
- Other regions exist: ALASKA, CARIB, GUAM, HAWAII, CONUS_5KM, ProbSevere.

**GOES ABI** (M6 scan mode) — [S3](https://noaa-goes19.s3.amazonaws.com/?list-type=2&prefix=ABI-L1b-RadF/2026/270/12/)
- Full disk: 96 L1b files per hour (16 bands × 6 scans ⇒ 10-min cadence), avg 51 MB on G19 and 36 MB on G18 (at 12 UTC).
- CONUS/PACUS: 192 files per hour (16 bands × 12 ⇒ 5-min), avg 7.6 MB.
- Mesoscale: 1,920 files per hour (2 sectors × 16 bands × 60 ⇒ 1-min), avg 0.64 MB.
- GLM: 180 files per hour (20-s), ~0.3 MB.

**AIGFS** — [S3](https://noaa-nws-graphcastgfs-pds.s3.amazonaws.com/?list-type=2&prefix=aigfs.20260927/)
- `aigfs.tHHz.pres.fFFF.grib2`: 71 MB. `sfc`: 8 MB. 65 steps per cycle (6-hourly to 384 h), 4 cycles.
- Input GDAS init stored as zarr: 257 MB.

**Met Office global 10 km** (netCDF, one variable per file per step) — [S3](https://met-office-atmospheric-model-data.s3.amazonaws.com/?list-type=2&prefix=global-deterministic-10km/20260927T1200Z/)
- 89 time steps at 00/12z vs 60 at 06/18z.
- Pressure-level wind speed: 227 MB per step. RH on pressure levels: 210 MB. Screen-level fields: ~7–9 MB each.

**RRFS prototype (rrfsdesi)** — [S3](https://noaa-rrfs-pds.s3.amazonaws.com/?list-type=2&prefix=rrfsdesi/)
- Only a sample ensemble cycle (2026-09-02) was present: per member-fh `prslevnomads.3km.conus` 159 MB; `2dfldnomads.conus` 49 MB; `ak` 147 MB; `pr`/`hi` 2.5 km grids 1.7–13 MB.
- No real-time RRFS stream was found in `noaa-rrfs-pds`; the only prefixes are `retro_output_final/`, `rrfs_retro_maps/`, `rrfsdesi/` and `sample_rotlat_awips/`.

**RTMA / URMA 2.5 km CONUS**
- `2dvaranl_ndfd.grb2_wexp` 84.6 MB (RTMA) / 87.3 MB (URMA) per hour; background (`ges`) and error (`err`) files are similar in size — [S3 RTMA](https://noaa-rtma-pds.s3.amazonaws.com/?list-type=2&prefix=rtma2p5.20260927/), [S3 URMA](https://noaa-urma-pds.s3.amazonaws.com/?list-type=2&prefix=urma2p5.20260927/)

**HAFS** (A and B) — [S3](https://noaa-nws-hafs-pds.s3.amazonaws.com/?list-type=2&prefix=hfsa/20260927/)
- Parent domain `parent.atm.fFFF.grb2`: 887–931 MB per 3-hourly step (HAFS-A); 848–869 MB (HAFS-B).
- Storm (moving nest) `storm.atm`: 229–246 MB per step.
- ~43 steps per storm-cycle (0–126 h 3-hourly).
- Volume scales with the number of active storms (zero out of season).

**NDFD** (`noaa-ndfd-pds`)
- `opnl/AR.conus/VP.*` holds a rolling current set of only ~0.7 GB (92 `ds.*.bin` files) — [S3](https://noaa-ndfd-pds.s3.amazonaws.com/?list-type=2&prefix=opnl/AR.conus/)
- The `wmo/apt/` archive holds very large per-issuance YTUZ files, avg 31 MB (4.6 TB in the first 400k objects listed; the listing was capped, so the true total is higher) — [S3](https://noaa-ndfd-pds.s3.amazonaws.com/?list-type=2&prefix=wmo/)

#### C. Grid specs and licences found in-session
- DWD ICON global: 2,949,120 triangles (~13 km effective mesh). ICON-D2 is 2.2 km over Germany, Benelux, Switzerland, Austria and parts of neighbouring countries. DWD open-data licence: CC BY 4.0 — [DWD ICON description](https://www.dwd.de/EN/research/weatherforecasting/num_modelling/01_num_weather_prediction_modells/icon_description.html); [GDI-DE ICON-D2 record](https://gdk.gdi-de.org/geonetwork/srv/api/records/urn:wmo:md:de-dwd:7388e134-e88a-4b7e-aaee-0f8e9e45b0e0?language=eng); [DWD NWP data](https://www.dwd.de/EN/ourservices/nwp_forecast_data/nwp_forecast_data.html)
- MSC HRDPS: 2.5 km pan-Canadian, 4 runs/day. RDPS: ~10 km. GDPS: described as 10 km in the search snippet (this conflicts with my recollection of 15 km — verify). Data is under the ECCC end-user licence / Open Government Licence — Canada — [HRDPS readme](https://eccc-msc.github.io/open-data/msc-data/nwp_hrdps/readme_hrdps-datamart_en/); [RDPS readme](https://eccc-msc.github.io/open-data/msc-data/nwp_rdps/readme_rdps_en/); [GEPS readme](https://eccc-msc.github.io/open-data/msc-data/nwp_geps/readme_geps_en/); [Open Gov portal HRDPS](https://open.canada.ca/data/en/dataset/5b401fa0-6c29-57f0-b3d5-749f301d829d)
- ECMWF made its entire real-time catalogue open on 1 Oct 2025 under **CC-BY-4.0** with no data (information) cost. Delivery of the full high-volume data may carry service charges. The free online subset is 0.25°, and a 9 km subset with ~2 h latency was announced for later in 2026 — [ECMWF news](https://www.ecmwf.int/en/about/media-centre/news/2025/ecmwf-makes-its-entire-real-time-catalogue-open-all); [ECMWF Newsletter 180](https://www.ecmwf.int/en/newsletter/180/news/ecmwf-moves-final-stages-open-data-transition)
- NOAA EAGLE / AIGFS is on AWS as `noaa-nws-graphcastgfs-pds` (the registry now labels it "NOAA EAGLE") — [AWS registry](https://registry.opendata.aws/noaa-nws-graphcastgfs-pds/)

### Inferences
- **Calibrated bits-per-value.** These let you estimate sizes where no listing exists.
  - GFS 0.25° f000 is 494.4 MB. The .idx is 31,814 B; at ~53 B per line that is ≈600 records. Grid is 1440×721 = 1,038,240 points. ⇒ 494.4e6 × 8 / (1.038e6 × 600) ≈ **6.3 bits/value**.
  - HRRR wrfprs is 409.4 MB with an idx of 38,094 B (≈690 records). Grid is 1799×1059 = 1,905,141 points (unverified spec). ⇒ ≈ **2.5 bits/value** (smooth hi-res fields compress well with complex packing and spatial differencing).
  - Rule of thumb: **3–7 bits per grid point per field** for NCEP complex-packed GRIB2 (the record count per line is approximate).
- **Estimates for datasets not listable in-session.** All grid specs below are unverified background knowledge; formula = points × fields × bpv / 8.
  - **DWD ICON global** (2,949,120 cells, cited): GRIB2 on the native icosahedral grid, bz2 per field. Assume ~5 bpv ≈ 1.8 MB per 2-D field. Assume ≈ 60 single-level + 7 variables × 20 pressure levels + model-level uploads, roughly 250–400 files per step, and ~93 steps (hourly to 78 h, 3-hourly to 180 h at 00/12z).
    ⇒ ~0.2 × 93 × 300 ≈ **40–70 GB per 00/12z run**, ~150–200 GB/day.
    Only order-of-magnitude — the file listing was blocked.
  - **ICON-EU** (6.5 km, ~904×658 regular lat-lon (unverified), 8 runs/day to 120 h): ~5–15 GB per run.
  - **ICON-D2** (2.2 km, ~1215×746 regular (unverified), 8 runs/day to 48 h hourly, plus a 20-member EPS): ~5–10 GB per deterministic run.
  - **MSC HRDPS** (2.5 km continental; grid ~2540×1290 = 3.28 M points, unverified): 4 runs × 49 hourly steps. At ~300 fields × 5 bpv ≈ 600 MB per step ⇒ ~30 GB per run, ~120 GB/day.
  - **RDPS** (10 km, ~935×824 (unverified)): 4 runs × 84 h. **GDPS**: 2 runs × 240 h. **GEPS**: 21 members, 16 d (32 d weekly). **CanSIPS**: monthly, 20 members × 2 models, 1°.
  - **JMA GSM** (TL959 ≈ 20 km; distributed 0.25° surface / 0.5°–1.25° pressure via JMBSC — paid, redistribution restrictions): 4 runs/day, 132 h / 264 h. Small, ~1–3 GB per run in the distributed resolution.
  - **ECMWF licensed full resolution (O1280 ≈ 9 km, 6,599,680 points)**: 6.36× the 0.25° point count (1,038,240). Scaling the measured 0.25° open-data volumes by 6.36 gives HRES ≈ 0.9 GB per step and ENS ≈ 42 GB per step for the same parameter set.
    The full MARS catalogue has many more levels and parameters, so full-catalogue volumes are much larger — not verified.
    SEAS5 (51 members, 7 months, O320 ~36 km) and extended range (101 members, 46 d, twice weekly → daily since 2023) are also not measured.
  - **RRFS v1 (post-Oct-2026)**: the 3 km North American rotated lat-lon grid is ~1.5–2× the HRRR point count (unverified). The prototype sample shows 159 MB per fh for the CONUS-cut `prslevnomads` per member. Expect 24 hourly cycles (18 h, extended to 60/84 h at synoptic hours) plus a REFS ensemble (unverified member count).
    ⇒ plausibly ≥1 TB/day once NOMADS/AWS distribution is live.
- **Heaviest ranking (measured, full product sets):** ECMWF open data 3.2 TB > GEFS 2.7 TB > HAFS-A+B 2.3 TB (in season) > GFS 1.8 TB > HRRR CONUS+AK 1.1 TB ≈ NBM 1.06 TB > NAM 0.56 TB > Met Office global 0.39 TB ≈ RTOFS 0.38 TB > CFS 0.31 TB > GOES ABI L1b 0.16 TB per satellite > MRMS 0.10 TB.
  - The total measured AWS-accessible volume above is **≈15 TB/day** if everything is ingested raw. A "forecast-useful" subset is on the order of 2–4 TB/day: GFS 0.25° a+b, GEFS a/b/s without init, ECMWF oper + AIFS single + ENS, HRRR prs+sfc+subh, NBM core, MRMS key products, and GOES MCMIP.
  - The biggest single decisions for the pipeline are whether to ingest the ECMWF ENS / AIFS ENS all-member files (6.6 GB and 4.5 GB per step), HRRR `wrfnat` (430 GB/day), GFS native netCDF (≈370 GB/day, 4 × 93 GB + analyses) and GEFS `init`.

### Gaps
- NOMADS-only products (HiResW ARW/FV3, HREF, SREF, RAP, GFS `sfluxgrb` on NOMADS, NDFD GRIB2 via tgftp, WPC/SPC GRIB, CMAQ AQM, Stage IV, CPC, NOHRSC, IMS, OSTIA, PRISM, CDAS, GEOS-FP) could not be listed: NOMADS, NCO pages and non-AWS servers were egress-blocked. No measured sizes, and no cited grid specs beyond those above.
- `noaa-sref-pds`, `noaa-href-pds` and `noaa-hiresw-pds` do not exist (HTTP 404), so these ensembles are NOMADS-only (as far as could be checked).
- AIGEFS (31 members) and HGEFS were not found in `noaa-nws-graphcastgfs-pds` (only `aigfs.*` daily prefixes). A search snippet claims EAGLE on AWS carries current AIGEFS, but no `aigefs` prefix was found — possibly a different prefix or path. Estimate: 31 × 5.5 GB ≈ 170 GB per cycle if files are the same size as AIGFS.
- DWD, MSC and JMA sizes are estimates only. The Met Office AWS licence text could not be confirmed (it is believed to be CC BY-SA 4.0 — verify).
- ECMWF 9 km / MARS full-catalogue per-run volumes are not published in anything reachable.

---

## Q2. Status in 2026 (retirements, new operational systems)

### Takeaway
NCEP is retiring **NAM, SREF, HREF, HiResW and NAM MOS** on the day **RRFS v1 + REFS** go operational. The latest SCN 26-47 update says **14 Oct 2026 12 UTC**; one secondary source says 6 Oct 2026, and the original target was 31 Aug 2026. **HRRR and RAP continue** (HRRR also feeds two REFS members) until RRFS v2. **AIGFS/AIGEFS/HGEFS** became operational 17 Dec 2025, replacing GraphCastGFS/EAGLE on AWS. As of 2026-09-27, NAM was still publishing full volumes on AWS.

### Cited Findings
- SCN 26-47 (updated): "Effective October 14, 2026, at 1200 UTC, NCEP will discontinue the NAM, SREF, HREF, HiresW and NAM MOS", replaced by RRFS. Critical Weather Day slip rules apply — [SCN 26-47](https://www.weather.gov/media/notification/pdf_2026/scn26-47_Retirement_of_NAM_SREF_HREF_HiresW_NAM_MOS.pdf); [update aab](https://www.weather.gov/media/notification/pdf_2026/SCN26-47_Updated_Retire_NAM_SREF_HREF_HiresW_NAM_MOS.aab.pdf)
- RRFS and REFS implementation is SCN 26-48 (several updates, latest "aad") and happens the same day as the retirements — [SCN 26-48 aad](https://www.weather.gov/media/notification/pdf_2026/scn26-048_Updated_RRFS_and_REFS_Implementation_aad.pdf)
- Date conflict: GribStream reports "NOAA reschedules RRFS and REFS operations for October 6, 2026" — [GribStream](https://gribstream.com/blog/noaa-rrfs-refs-operational-august-2026). An earlier plan was Aug 31, 2026 — [open-meteo issue #1849](https://github.com/open-meteo/open-meteo/issues/1849). The page contents could not be opened; treat the latest SCN (Oct 14) as authoritative pending verification.
- HRRR and RAP are not retired with RRFS v1. HRRR keeps running and supplies two REFS members over CONUS and Alaska. RRFS/REFS v2 would replace HRRR/RAP, with no date set — [NWS RRFS/REFS webinar Q&A, Jun 25 2026](https://www.weather.gov/media/wrn/calendar/RRFS_REF-Webinar&RegistrationFormQANotes.pdf); [Windy community](https://community.windy.com/topic/44247/upcoming-us-model-changes)
- AIGFS, AIGEFS (31 members) and HGEFS (62 members = 31 AIGEFS + 31 GEFSv12) were implemented 17 Dec 2025 12Z, per SCN 25-89. AIGFS was later updated to v1.1 by SCN 26-68 — [SCN 25-89](https://www.weather.gov/media/notification/pdf_2025/scn25-89_AIGFS_AIGEFS_and_HGEFS.pdf); [SCN 26-68](https://www.weather.gov/media/notification/pdf_2026/scn26-68_AIGFS_v1.1.pdf); [EPIC](https://www.epic.noaa.gov/noaa-deploys-new-ai-driven-global-weather-models/); [NCO AIGEFS product page](https://www.nco.ncep.noaa.gov/pmb/products/aigefs/)
- The AWS registry for `noaa-nws-graphcastgfs-pds` is relabelled "NOAA EAGLE"; AIGFS/AIGEFS are the operational replacements for EAGLE SOLO/Ensemble — [AWS registry](https://registry.opendata.aws/noaa-nws-graphcastgfs-pds/)
- Measured: the last `graphcastgfs.*` daily prefix is **2026-05-05**, and `aigfs.*` has 162 daily prefixes through 2026-09-28. So GraphCastGFS output ended in early May 2026 on AWS — [S3](https://noaa-nws-graphcastgfs-pds.s3.amazonaws.com/?list-type=2&prefix=graphcastgfs.2026&delimiter=/)
- Measured: NAM (`noaa-nam-pds/nam.20260927/`, 564 GB) and HAFS-A/B (`noaa-nws-hafs-pds/hfsa|hfsb/`) were live on 2026-09-27 — [S3 NAM](https://noaa-nam-pds.s3.amazonaws.com/?list-type=2&prefix=nam.2026&delimiter=/)
- Measured: `noaa-rrfs-pds` contained only retrospective/sample prefixes (`retro_output_final/`, `rrfs_retro_maps/`, `rrfsdesi/`, `sample_rotlat_awips/`) — no real-time RRFS as of 2026-09-28. The AWS registry lists it as "[Prototype]" — [S3](https://noaa-rrfs-pds.s3.amazonaws.com/?list-type=2&delimiter=/); [AWS registry](https://registry.opendata.aws/noaa-rrfs/)
- ECMWF: the whole real-time catalogue has been open (CC-BY-4.0) since 1 Oct 2025. A 9 km open subset with ~2 h latency is planned for later in 2026 — [ECMWF](https://www.ecmwf.int/en/about/media-centre/news/2025/ecmwf-makes-its-entire-real-time-catalogue-open-all)
- Measured: ECMWF open data on AWS now includes `aifs-ens/` (4 runs/day, 0–360 h) alongside `aifs-single/` and `ifs/` — [S3](https://ecmwf-forecasts.s3.amazonaws.com/?list-type=2&prefix=20260927/00z/&delimiter=/)
- Measured: GOES-19 is the operational East satellite feeding `noaa-goes19` (ABI + GLM live on 2026-09-27); GOES-18 is West — [S3](https://noaa-goes19.s3.amazonaws.com/?list-type=2&delimiter=/)

### Inferences
- After the NAM/SREF/HREF/HiResW retirement (~mid-Oct 2026), about 0.56 TB/day of NAM (plus the NOMADS-only SREF/HREF/HiResW) disappears. It is replaced by RRFS deterministic + REFS, and by the RRFS "NAM-like" 12 km/AWIPS grids announced in SCN 26-48 (not verified). Pipelines should budget RRFS at ≥ HRRR scale, because RRFS covers the larger North American domain.
- HWRF/HMON have been replaced by HAFS since 2023 (background knowledge; no in-session source). `noaa-nws-hafs-pds` shows only `hfsa`/`hfsb`, consistent with that.
- The GFS 0.25° f000 file (494 MB), the netCDF `atmf` history (7.1 GB each) and the 0.25° GEFS `pgrb2sp25` are consistent with GFS v16 / GEFS v12 still running. There was no sign of GFS v17 / GEFS v13 in the file naming on 2026-09-27. Its implementation status could not be verified.

### Gaps
- The SCN 26-48 content (RRFS grid dimensions, REFS member count, product list, AWS/NOMADS paths, the 15-min output) could not be read (weather.gov blocked).
- Status of GFS v17/GEFS v13, SREF data after retirement, NDFD changes, CMAQ/AQM v8, and CFSv2 successor (SFS) — no in-session sources.

---

## Q3. Latency and cadence

### Takeaway
Observed on AWS (2026-09-27): the first file arrives ~50 min after cycle time for HRRR, ~1.6 h for NAM, ~3.5 h for GFS, ~3.75 h for GEFS, ~5.5 h for AIFS single, ~7.5 h for ECMWF IFS HRES/ENS, ~5.5 h for Met Office global and ~7–8 h for AIGFS. Completion lags the first file by 1–2 h for GFS/GEFS; the 35-day GEFS extended tail finished ~27 h after cycle on AWS. Cadences run from 20 s (GLM) and 1–10 min (GOES ABI), 2 min (MRMS) and hourly (HRRR, RTMA, NBM), to 6-hourly (global models) and daily (RTOFS, OISST).

### Cited Findings
All from S3 `LastModified` on 2026-09-27. Format: first file → last file after cycle time.

| Dataset | Cycles/day, length, step (observed) | First file | Last file | Source |
|---|---|---|---|---|
| HRRR CONUS | 24/day. f00–f18 hourly; 00/06/12/18z to f48. Sub-hourly 15-min in `wrfsubhf` | +51 min | +1 h 13 min (18 h run: 01z done 02:31); +1 h 49 min (48 h run) | [S3](https://noaa-hrrr-bdp-pds.s3.amazonaws.com/?list-type=2&prefix=hrrr.20260927/conus/hrrr.t00z) |
| HRRR Alaska | 8/day (3-hourly) | +42 min | ~+1.5 h | [S3](https://noaa-hrrr-bdp-pds.s3.amazonaws.com/?list-type=2&prefix=hrrr.20260927/alaska/) |
| NAM | 4/day. 3 km nests to 60 h hourly (61 files) | +1 h 39 min | ~+3 h 13 min | [S3](https://noaa-nam-pds.s3.amazonaws.com/?list-type=2&prefix=nam.20260927/) |
| GFS | 4/day. f000–f120 hourly, f123–f384 3-hourly (209 files, 0.25°); 0.5°/1.0° 129 files | +3 h 34 min | +5 h 30 min (0p25 f384); `atmanl` +3 h 53 min | [S3](https://noaa-gfs-bdp-pds.s3.amazonaws.com/?list-type=2&prefix=gfs.20260927/00/atmos/gfs.t00z.pgrb2) |
| GEFS | 4/day. 31 members. 00z to 840 h (35 d); other cycles to 384 h; 3-hourly to 240 h then 6-hourly | +3 h 46 min | 0.25° set done +5 h 42 min; 06z done +6 h 38 min; 00z 35-day tail +27 h (observed 09-28T03:11) | [S3](https://noaa-gefs-pds.s3.amazonaws.com/?list-type=2&prefix=gefs.20260927/00/atmos/) |
| GFS-Wave | 4/day; same steps as GFS | +3 h 33 min | station tars ~+5 h 34 min | [S3](https://noaa-gfs-bdp-pds.s3.amazonaws.com/?list-type=2&prefix=gfs.20260927/12/wave/) |
| CFSv2 | 4/day, 4 members/cycle. 6-hourly steps; the 00z members run longer | +7 h 10 min | +11 h 48 min | [S3](https://noaa-cfs-pds.s3.amazonaws.com/?list-type=2&prefix=cfs.20260927/00/) |
| ECMWF IFS HRES (open) | 4/day. 00/12z to 360 h (3-hourly to 144 h, then 6-hourly); 06/18z to 144 h | +7 h 34 min | +7 h 34 min (bulk push) | [S3](https://ecmwf-forecasts.s3.amazonaws.com/?list-type=2&prefix=20260927/00z/) |
| ECMWF IFS ENS (open) | 4/day, 51 members, same steps | +7 h 40 min | +7 h 52 min (ep at +8 h 01 min) | same |
| AIFS single | 4/day, 0–360 h 6-hourly | +5 h 28 min | +5 h 31 min | same |
| AIFS ENS | 4/day, 0–360 h 6-hourly | +5 h 54 min | +6 h 03–08 min | same |
| AIGFS | 4/day, 0–384 h 6-hourly (65 steps) | ~+7 h 31 min (00z) | 18z done +8 h 32 min | [S3](https://noaa-nws-graphcastgfs-pds.s3.amazonaws.com/?list-type=2&prefix=aigfs.20260927/) |
| NBM | 24/day hourly. `qmd` percentile sets on 4 synoptic cycles | core +1 h 04 min | 12z qmd +7 h 23 min | [S3](https://noaa-nbm-grib2-pds.s3.amazonaws.com/?list-type=2&prefix=blend.20260927/12/) |
| RTMA 2.5 km | 24/day | +46 min (analysis) | — | [S3](https://noaa-rtma-pds.s3.amazonaws.com/?list-type=2&prefix=rtma2p5.20260927/) |
| URMA 2.5 km | 24/day | ~+6 h 55 min – +7 h | precip URMA +25 h | [S3](https://noaa-urma-pds.s3.amazonaws.com/?list-type=2&prefix=urma2p5.20260927/) |
| RTOFS | 1/day (00z). Nowcast n-24..n00; forecast to f192 (hourly surface, 3–6-hourly 3-D) | nowcast +6 h 48 min | forecast +12 h 47 min → +19 h 00 min | [S3](https://noaa-nws-rtofs-pds.s3.amazonaws.com/?list-type=2&prefix=rtofs.20260927/) |
| Met Office global 10 km | 4/day. 00/12z 89 steps; 06/18z 60 steps | +5 h 30 min | +6 h 30 min | [S3](https://met-office-atmospheric-model-data.s3.amazonaws.com/?list-type=2&prefix=global-deterministic-10km/20260927T0000Z/) |
| Met Office UK 2 km | 12z: 55 3-D / 91 2-D steps | +3 h 30 min | +4 h | [S3](https://met-office-atmospheric-model-data.s3.amazonaws.com/?list-type=2&prefix=uk-deterministic-2km/20260927T1200Z/) |
| HAFS-A/B | 4/day per active storm, 0–126 h 3-hourly | ~+4 h 30 min | ~+6 h | [S3](https://noaa-nws-hafs-pds.s3.amazonaws.com/?list-type=2&prefix=hfsa/20260927/) |
| MRMS | 2-min for reflectivity/precip-rate; hourly QPE (Pass2 at ~+56 min) | ~1–2 min | — | [S3](https://noaa-mrms-pds.s3.amazonaws.com/?list-type=2&prefix=CONUS/MultiSensor_QPE_01H_Pass2_00.00/20260927/) |
| GOES ABI | Full disk 10 min; CONUS 5 min; Meso 1 min (M6) | minutes | — | [S3](https://noaa-goes19.s3.amazonaws.com/?list-type=2&prefix=ABI-L1b-RadF/2026/270/12/) |
| GLM | 20 s | ~20 s | — | [S3](https://noaa-goes19.s3.amazonaws.com/?list-type=2&prefix=GLM-L2-LCFA/2026/270/12/) |
| OISST v2.1 | daily; preliminary ~1–2 days, final ~2 weeks | — | — | [S3](https://noaa-cdr-sea-surface-temp-optimum-interpolation-pds.s3.amazonaws.com/?list-type=2&prefix=data/v2.1/avhrr/202609/) |

- ECMWF announced a planned 9 km open subset with ~2 h latency "due to the size of the data" — [ECMWF](https://www.ecmwf.int/en/about/media-centre/news/2025/ecmwf-makes-its-entire-real-time-catalogue-open-all)
- AIGFS produces a 16-day forecast in ~40 min of compute — [EPIC](https://www.epic.noaa.gov/noaa-deploys-new-ai-driven-global-weather-models/); [ForecastWatch](https://forecastwatch.com/2026/01/06/noaa-launches-new-suite-of-weather-models/)

### Inferences
- AWS mirror latencies are an upper bound on origin latency. NOMADS and ECMWF dissemination are typically earlier: ECMWF open data on data.ecmwf.int is normally ~+6–7 h for 00z HRES (background knowledge). The AWS ECMWF mirror pushes a whole cycle in one burst rather than step-by-step.
- Peak ingest bursts, measured:
  - ECMWF 00z/12z pushes ~560 GB of ENS in ~12 min (≈0.8 GB/s), then AIFS-ENS pushes ~273 GB in ~9 min at ~+5.9 h.
  - GFS pushes ~410 GB over ~2 h (~57 MB/s average).
  - HRRR 48 h runs push 70 GB in ~1 h.
  - Size download bandwidth for bursts, not daily averages.
- AIGFS latency (~7.5 h) exceeds GFS despite the fast compute, which is consistent with it being initialized from the GDAS/late-cutoff analysis (inference).

### Gaps
- No in-session latency data for NOMADS-only products (HiResW, HREF, SREF, RAP), DWD ICON (typically ~2.5–4 h, unverified), MSC (HRDPS ~+4–5 h, unverified), JMA, NDFD, CMAQ, Stage IV (hourly ~+1 h; 6-h/24-h mosaics after RFC QC, unverified), CPC gauge (daily, next day), PRISM (daily, provisional next day), IMS (daily), OSTIA (daily, ~+1 d), CDAS (6-hourly, ~+1 d), NASA GEOS-FP (4/day, ~+5–8 h), GEFS 0.25° wave vs. atmos.
- Could not confirm the RRFS 15-min output cadence or its planned latency (SCN 26-48 unreadable).
