# Cloud storage, compute and delivery costs for the Isobar ingest/tile pipeline (as of Sept 2026)

Method note: research date 2026-09-28. WebSearch worked, but WebFetch was **blocked by the egress proxy** for every official pricing page tried (aws.amazon.com, developers.cloudflare.com, backblaze.com, wasabi.com, docs.hetzner.com, cpc.ncep.noaa.gov). Most prices below come from search-result summaries of 2026 third-party pricing guides that quote list prices. None were checked against a live official page, so **verify every number on the official page before committing to a budget**. Items marked "(unverified, from memory)" are known list prices that I could not find a 2026 source for.

## 1. Object storage and egress unit prices

### Takeaway
For a read-heavy tile workload served to thousands of users, Cloudflare R2 ($0.015/GB-mo, $0 egress) is the default choice for the hot tile store. S3 costs about the same to store but charges about $0.09/GB for internet egress. B2 and Wasabi are cheaper to store, but each caps free egress relative to how much you store (B2 3x, Wasabi 1:1), and a small tile store with heavy delivery breaks those caps. Per-object write (PUT/Class A) fees are the cost that actually matters for a tile pipeline, not per-GB storage.

### Cited Findings
**AWS S3 (us-east-1)**
- S3 Standard: $0.023/GB-month — [CloudZero 2026 guide](https://www.cloudzero.com/blog/s3-pricing/); [DevZero](https://www.devzero.io/blog/aws-s3-pricing)
- Intelligent-Tiering: Frequent $0.023, Infrequent $0.0125 (after 30 days), Archive Instant $0.004 (after 90 days), plus opt-in archive tiers. Monitoring fee is $0.0025 per 1,000 objects/month for objects >128 KB. **Objects under 128 KB are never moved to a cheaper tier and bill at the Frequent rate.** — [nOps](https://www.nops.io/blog/aws-s3-pricing/); [CloudCostRoom](https://cloudcostroom.com/blog/s3-intelligent-tiering-when-it-saves-and-when-it-costs-more)
- Glacier Instant Retrieval $0.004/GB-mo; Glacier Flexible Retrieval $0.0036/GB-mo; Deep Archive $0.00099/GB-mo. Flexible retrievals take minutes to 12 h, and retrieval fees can be large — [CloudZero](https://www.cloudzero.com/blog/s3-pricing/); [LeanOps Glacier](https://leanopstech.com/blog/aws-s3-glacier-pricing-2026/)
- Request fees: PUT/COPY/POST/LIST $0.005 per 1,000; GET $0.0004 per 1,000 (unverified, from memory; standard long-running list price. The 2026 search did not confirm it explicitly)
- Internet egress: first 100 GB/month free (aggregate across services). Then $0.09/GB for the first 10 TB, $0.085 for the next 40 TB, $0.07 for the next 100 TB, and $0.05 above 150 TB — [EgressCost AWS](https://egresscost.com/aws/); [Bacancy](https://www.bacancytechnology.com/blog/aws-data-transfer-pricing)
- Inter-region transfer out of us-east-1: $0.02/GB to almost all other regions, including eu-central-1 — [EgressCost cross-region](https://egresscost.com/aws/cross-region-data-transfer/)

**Cloudflare R2**
- Standard storage $0.015/GB-mo; Infrequent Access $0.01/GB-mo — [Filebase 2026](https://filebase.com/blog/cloudflare-r2-pricing-costs-savings-and-alternatives-in-2026/); [Mecanik](https://mecanik.dev/en/posts/cloudflare-r2-pricing-explained-real-costs-vs-s3-and-backblaze/)
- Class A (writes/lists) $4.50/million on Standard and $9.00/million on IA. Class B (reads) $0.36/million on Standard and $0.90/million on IA. **No egress charges for any storage class.** Free tier each month: 10 GB-month, 1M Class A, 10M Class B — same sources; [official page (not fetchable)](https://developers.cloudflare.com/r2/pricing)
- Cloudflare's service terms restrict self-serve CDN plans from serving a "disproportionate" share of large/non-HTML files, except when the content is hosted on a Cloudflare service such as R2, Stream or Images. So data tiles served from R2 through the Cloudflare CDN are explicitly allowed — [Cloudflare service-specific terms](https://www.cloudflare.com/service-specific-terms-application-services/); [Cloudflare blog "updated ToS"](https://blog.cloudflare.com/th-th/updated-tos)
- Cloudflare publishes no hard bandwidth cap on Free/Pro/Business plans for proxied HTTP traffic — [BlazingCDN blog](https://blog.blazingcdn.com/en-us/what-is-the-price-per-gb-of-cloudflare-cdn) (third-party CDN vendor; possible bias)

**Backblaze B2**
- About $6–6.95/TB-month (sources disagree: $6/TB versus $6.95/TB per 30 days, which suggests a 2025/26 price change) — [LeanOps](https://leanopstech.com/blog/backblaze-b2-pricing-2026/); [CompareBestAI](https://comparebestai.com/tools/backblaze-b2)
- Free egress up to 3x average monthly storage, then $0.01/GB. Egress to CDN/compute partners (e.g. Cloudflare) is free. A "B2 Overdrive" option has unlimited free egress — [Shade 2026 review](https://shade.inc/blog/backblaze-review-video-production); [Backblaze pricing (not fetchable)](https://www.backblaze.com/cloud-storage/pricing)
- B2 API transactions are split into Class A/B/C/D, with Class A (uploads) free — [Backblaze transaction pricing](https://www.backblaze.com/cloud-storage/transaction-pricing) (details not fetched)

**Wasabi**
- Pay-as-you-go $7.99/TB-month from July 1, 2026 (previously $6.99). There is a 1 TB minimum monthly charge and a 90-day minimum storage duration, so objects deleted early are billed for the full 90 days — [bestcloudstorageguide 2026](https://bestcloudstorageguide.com/blog/wasabi-pricing-pricing-guide-2026); [Wasabi docs – min duration](https://docs.wasabi.com/docs/how-does-wasabis-minimum-storage-duration-policy-work); [Wasabi FAQ](https://wasabi.com/pricing/faq)
- No egress or API fees, but monthly egress must not exceed active storage (1:1) — [ZeroBuffer](https://www.zerobuffer.io/blogs/wasabi-costs); [LeanOps Wasabi](https://leanopstech.com/blog/wasabi-pricing-2026/)

**CDN**
- CloudFront pay-as-you-go: about $0.085/GB for the first 10 TB/month in North America and Europe — [Perfsys 2026](https://perfsys.com/blog/cloudfront-pricing-guide/); [EgressCost CloudFront](https://egresscost.com/aws/cloudfront-pricing/)
- CloudFront flat-rate plans (new since late 2025):
  - Free: $0, 100 GB, 1M requests
  - Pro: $15/mo, 50 TB, 10M requests
  - Business: $200/mo, 50 TB, 125M requests
  - Premium: $1,000/mo, 50 TB, 500M requests, configurable up to 600 TB and 6B requests
  - No overage charges
  — [AWS docs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html); [Duckbill](https://www.duckbillhq.com/blog/the-complete-guide-to-cloudfronts-flat-rate-pricing/); [Costbench](https://costbench.com/software/cdn-edge/aws-cloudfront/)
- Transfer from S3 to CloudFront is free (unverified, from memory, long-standing AWS policy). CloudFront HTTPS request fee is about $0.01 per 10,000 in US/EU (unverified, from memory)

### Inferences
- **The request cap matters more than the byte cap on CloudFront flat-rate plans.** Tiles are small (20–40 KB), so 50 TB is about 1.7B tiles, but Pro allows only 10M requests and Business 125M. A tile client will hit the request cap long before the transfer cap.
- **Small tiles make S3 Intelligent-Tiering pointless.** Tiles of 20–40 KB are under the 128 KB threshold, so they never move to a cheaper tier. Use lifecycle deletion instead.
- **Wasabi does not fit short-lived tiles.** Its 90-day minimum duration means tiles deleted after 1–2 days are billed as if stored for 90 days (roughly 45x the storage actually used).
- **B2's 3x egress cap is easy to exceed.** A tile store of a few TB serving thousands of users would go over it unless traffic goes through Cloudflare (partner egress is free). This makes B2 + Cloudflare CDN a credible alternative to R2.

### Gaps
- I could not fetch the official S3 page, so the 2026 PUT/GET request prices are unconfirmed.
- I found no source confirming the flat-rate CloudFront plans' acceptable-use limits for API/tile traffic.

## 2. Compute pricing

### Takeaway
At list prices compute is cheap for this workload: about $0.013–0.04 per vCPU-hour on spot/Graviton or serverless containers. The expensive parts are always-on capacity during run-arrival bursts, and egress when compute sits in a different cloud from the data.

### Cited Findings
- **c7g.4xlarge** (16 vCPU Graviton3), us-east-1: on-demand $0.58/h; spot from $0.2108/h — [DoiT](https://www.doit.com/compute/compute/aws/us-east-1/c7g.4xlarge)
- **c7i.4xlarge** (16 vCPU Intel), us-east-1: on-demand $0.714/h; spot from $0.2486/h — [DoiT](https://www.doit.com/compute/spot/us-east-1/c7i.4xlarge)
- **c8g.4xlarge** (16 vCPU Graviton4, 32 GiB): from $0.63808/h on-demand — [Vantage](https://instances.vantage.sh/aws/ec2/c8g.4xlarge). No 2026 spot figure found.
- **Lambda:** $0.20 per 1M requests plus $0.0000166667/GB-s on x86; Arm is about 20% cheaper (about $0.0000133/GB-s) — [Wring](https://wring.co/blog/aws-lambda-pricing-guide); [Tech-Insider](https://tech-insider.org/aws-fargate-vs-lambda-2026/)
- **Fargate:** x86 $0.04048/vCPU-h + $0.004445/GB-h; Graviton $0.03238/vCPU-h + $0.00356/GB-h — [Fortem](https://fortem.dev/blog/aws-fargate-pricing-real-costs/); [LeanOps](https://leanopstech.com/blog/aws-ecs-fargate-pricing-2026/)
- **AWS Batch:** no extra charge; you pay for the EC2/Fargate it uses (unverified, from memory)
- **Modal:** base CPU $0.0000131 per physical core-second (about $0.047/core-h, about $0.0236/vCPU-h). Region selection multiplies this by 1.5–1.75x, non-preemptible by 3x, and sandboxes by about 3x — [Blaxel](https://blaxel.ai/blog/modal-pricing-alternatives-guide); [Modal pricing](https://modal.com/pricing)
- **Fly.io:** performance-cpu Machines cost about $31/mo per dedicated vCPU, plus $5/GB-mo extra RAM and $0.15/GB-mo volumes; 100 GB/mo of outbound bandwidth is free. Sources conflict: one lists performance-1x at $15.49/mo and another says about $31/vCPU — [Fly docs](https://fly.io/docs/about/pricing/); [Deploy Handbook](https://deployhandbook.com/pricing/fly-io); [Kuberns](https://kuberns.com/blogs/flyio-pricing/)
- **Hetzner:**
  - Raised prices three times in 2026. Dedicated servers went up 3–21% on April 1, 2026 (e.g. AX41-NVMe Helsinki €35.60 to €36.70) and again with a "standardization" on June 15, 2026 for new orders; existing servers kept their terms. Hetzner cited higher operating and hardware costs — [Hetzner pressroom](https://www.hetzner.com/pressroom/standardization-and-price-adjustment-of-our-server-products/); [igor'sLAB](https://www.igorslab.de/en/hetzner-to-significantly-increase-prices-for-cloud-and-dedicated-servers-from-april-2026/); [DevOps Daily](https://devops-daily.com/posts/hetzner-price-increases-2026)
  - Hetzner dedicated servers include unmetered or very large traffic allowances (unverified, from memory; check current terms)

### Inferences
- **Effective vCPU-hour rates:**
  - c7g spot: about $0.0132/vCPU-h (0.2108/16)
  - c7g on-demand: $0.036
  - Fargate Graviton: about $0.032 + memory
  - Modal base: about $0.024
- **A Hetzner box is a strong fixed-cost floor for steady ingest.** A roughly €40–100/mo dedicated server (AX-class, 8–16 cores) matches about 3,000–7,000 vCPU-hours of Graviton spot at list price.
- **Hetzner's catch is transfer from AWS.** GFS/HRRR live in us-east-1, so pulling them to Hetzner pays the transfer charge at source. For open-data buckets that charge falls on the sponsor, not the reader, so pulling from Hetzner is usually free to Isobar. The real costs are latency (transatlantic fetch to a German or Finnish datacenter, or use Hetzner US Ashburn) and rate limits.

### Gaps
- No 2026 source found for c8g spot prices, a Hetzner price table after June 15 (the official docs page was blocked), or AWS Batch pricing.

## 3. Data transfer from open-data buckets and mirrors

### Takeaway
NOAA models (GFS, HRRR, GEFS, NBM, etc.) sit in us-east-1 open-data buckets. ECMWF's AWS mirror is in **eu-central-1**, not us-east-1, so the best home for Isobar's compute depends on the model mix.

### Cited Findings
- **NOAA GFS** is in bucket `noaa-gfs-bdp-pds`, us-east-1. `pgrb2.0p25` files are about 446–550 MB per forecast hour (anl 446 MB, f000 506 MB, later hours 535–550 MB) — [search summary of Herbie/NCO inventory pages](https://herbie.readthedocs.io/en/2025.10.0/gallery/noaa_models/gfs.html); [NCO inventory f003](https://www.nco.ncep.noaa.gov/pmb/products/gfs/gfs.t00z.pgrb2.0p25.f003.shtml)
- **ECMWF open data** (IFS and AIFS, HRES and ENS subsets):
  - AWS bucket `ecmwf-forecasts` in **eu-central-1**
  - Also mirrored on Azure (`ai4edataeuwest.blob.core.windows.net/ecmwf`, West Europe) and on Google Cloud (BigQuery public data / Marketplace)
  - ECMWF's own portal keeps a rolling archive of recent runs
  — [AWS Open Data Registry](https://registry.opendata.aws/ecmwf-forecasts/); [awslabs registry yaml](https://github.com/awslabs/open-data-registry/blob/main/datasets/ecmwf-forecasts.yaml); [ECMWF Confluence](https://confluence.ecmwf.int/display/DAC/ECMWF+open+data:+real-time+forecasts+from+IFS+and+AIFS)
- **ERA5 reanalysis** is also on the AWS Open Data Registry — [registry.opendata.aws/ecmwf-era5](https://registry.opendata.aws/ecmwf-era5/)
- **Inter-region transfer** out of us-east-1 costs $0.02/GB — [EgressCost](https://egresscost.com/aws/cross-region-data-transfer/)
- **Open Data Sponsorship Program:** AWS covers storage and egress for sponsored datasets, so readers are not billed for GETs or data transfer out of those buckets (unverified, from memory; the AWS pages were blocked). In-region reads to EC2 are free in any case.

### Inferences
- **Read only the fields you need.** Using the `.idx` sidecar and HTTP range requests (as Herbie does) means one 2D field per forecast hour is roughly 0.3–1.5 MB, not a 500 MB file. That cuts bytes read by about 500x.
- **Keep pipeline outputs in one place.** Running compute in us-east-1 and reading ECMWF from eu-central-1 costs Isobar nothing for the read (sponsor-paid). But moving pipeline outputs between regions would cost $0.02/GB, so write to a single tile store; R2 is global and has no egress.

### Gaps
- I could not confirm the current AWS Open Data Sponsorship terms for requester charges.
- I did not confirm whether any NOAA buckets have mirrors on other clouds (NODD also publishes to GCP and Azure, but I did not verify this in 2026).

## 4. GRIB2 decode and tile-generation throughput

### Takeaway
I found **no published, citable benchmark numbers** (MB/s or ms per message) for eccodes, cfgrib, wgrib2 or gribberish. Several projects ship benchmark harnesses but don't publish results. Isobar should measure this itself; the harnesses below are a good starting point.

### Cited Findings
- **gribberish** (Rust, with a Python wrapper and xarray/VirtualiZarr integration) ships `bench.py` comparing it with eccodes, but the README gives no numbers — [gribberish README](https://github.com/mpiannucci/gribberish/blob/main/python/README.md)
- **gribtract** (pure Rust) decodes simple, complex, complex+spatial-differencing and PNG packing, with JPEG2000 behind a feature flag. It is verified field by field against eccodes/wgrib2 and has a benchmark dashboard on NOAA GFS/HRRR/NBM/GEFS files, but the page publishes no numbers — [gribtract](https://github.com/jedarden/gribtract)
- **Other Rust decoders:** `grib` crate (pluggable JPEG2000/CCSDS backends) — [docs.rs/grib](https://docs.rs/grib); `fieldglass_grib2` — [docs.rs](https://docs.rs/fieldglass-grib2/latest/fieldglass_grib2/)
- **Packing and decode cost** (from wgrib2 docs): JPEG2000 gives the smallest files but is slow; complex packing is about 20% larger than JPEG2000 for global fields and much faster; AEC/CCSDS (libaec) is very fast with good compression — [wgrib2 -set_grib_type docs](https://wgrib2-docs.readthedocs.io/en/latest/options/misc/set_grib_type.html). The wgrib2 "SPEED" page exists but was blocked — [wgrib2 speed](https://www.cpc.ncep.noaa.gov/products/wesley/wgrib2/speed.html)

### Inferences
Unsourced engineering estimates, to validate by benchmark:
- **Decode:** one GFS 0.25° field is 1440×721, about 1.04M points, with complex packing. It should decode in tens of milliseconds on one modern core with eccodes or a Rust decoder. JPEG2000-packed fields (some ECMWF and older NCEP products) can be 5–10x slower.
- **Per-hour processing:** smoothing, reprojecting to Web Mercator, quantizing and compressing about 85 tiles probably takes 0.1–0.5 CPU-s per field per forecast hour.
- **Budget figure:** assume about 0.5 CPU-s per field per forecast hour, and replace it with measured numbers.

### Gaps
- No citable decode-speed numbers were found.
- No tile-generation benchmarks were found.
- I found no infrastructure-cost write-ups from weather startups.
- I did not find Mapbox/MapTiler tile-size references (not searched, because of the tool-call budget).

## 5. Retention strategy and worked cost model

### Takeaway
Per field per run, cost is dominated by **object PUT fees** when each tile is stored as a separate object. Storage, compute and ingest cost fractions of a cent. Bundling tiles (one object per field per forecast hour, or a PMTiles-style archive read with range requests) cuts write costs by about two orders of magnitude. After that, delivery egress and CDN requests are the main cost, which is why R2 or a CDN with zero or flat egress pricing fits best.

### Cited Findings (unit inputs, from Sections 1–3)
- R2 Class A $4.50/M, Class B $0.36/M, storage $0.015/GB-mo, $0 egress — [Filebase](https://filebase.com/blog/cloudflare-r2-pricing-costs-savings-and-alternatives-in-2026/)
- S3 Standard $0.023/GB-mo; PUT $0.005/1k (unverified); internet egress $0.09 → $0.05/GB — [CloudZero](https://www.cloudzero.com/blog/s3-pricing/); [EgressCost](https://egresscost.com/aws/)
- c7g.4xlarge spot $0.2108/h for 16 vCPU — [DoiT](https://www.doit.com/compute/compute/aws/us-east-1/c7g.4xlarge)
- GFS 0.25° full forecast-hour file is about 500 MB — [Herbie docs](https://herbie.readthedocs.io/en/2025.10.0/gallery/noaa_models/gfs.html)
- CloudFront flat-rate request caps (Pro 10M, Business 125M) — [AWS docs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html)

### Inferences — worked example: GFS 0.25°, one 2D field, one run (209 forecast hours)
Arithmetic is from the unit prices above. Sizing assumptions are mine.

**1. Grid and pyramid**
- The grid is 1440×721, about 1.04M values.
- A Web-Mercator world at zoom z is 256·2^z pixels wide. Native 0.25° maps to max zoom z3 (2048 px wide; z2 at 1024 px would undersample).
- Tiles for z0–z3: 1+4+16+64 = **85 tiles per forecast hour**.
- General formula: tiles ≈ (native points × oversample to next power of 2 × 4/3) / 65,536.

**2. Forecast hours**
- GFS runs hourly to f120 (121 hours), then 3-hourly to f384 (88 hours) = 209.

**3. Tiles per run and size**
- 209 × 85 = **17,765 tiles**.
- At about 30 KB each, that is about **0.53 GB per field-run**.
- 16-bit tiles are about 1.5–2x larger.

**4. Ingest bytes**
- Range-GET one message per hour: about 209 × ~1 MB ≈ 0.2 GB.
- Reading from the in-region, sponsored bucket costs $0.

**5. Compute**
- About 0.5 CPU-s × 209 ≈ 105 CPU-s ≈ 0.029 vCPU-h.
- On c7g spot ($0.0132/vCPU-h) that is about **$0.0004**. On Fargate Graviton it is about $0.001. On Lambda Arm (2 GB, 105 s) it is about $0.003.

**6. Writes**

| Layout | S3 PUT cost | R2 PUT cost |
|---|---|---|
| One object per tile (17,765 PUTs) | ≈ **$0.089** | ≈ **$0.080** |
| One bundle per forecast hour (209 PUTs) | ≈ $0.001 | ≈ $0.001 |

**7. Storage while hot**
- 0.53 GB × $0.015 ≈ $0.008 per month-kept.
- Keeping it 2 days costs about $0.0005.

**8. Total**
- With one object per tile: about **$0.09 per field-run**, over 90% of it PUT fees.
- With bundling: **under $0.005 per field-run**.

**Scaling to the full catalog.** The formula is:

`monthly cost ≈ Σ_models [runs/day × 30 × fields × hours × (tiles/hour) × (PUT price per object ÷ tiles per object + compute per tile)] + hot storage + delivery`

- **Illustrative scale:** 10 models × 4 runs/day × 100 fields, with each field-run the size of GFS (about 17.8k tiles), gives 4,000 field-runs/day and about 71M tiles/day, or about **2.1B tile PUTs/month**:
  - Unbundled: about $9.6k/mo on R2 and about $10.7k/mo on S3
  - Bundled per forecast hour: about $110/mo
  - Compute: about 4,000 × 105 CPU-s ≈ 117 vCPU-h/day ≈ 3,500 vCPU-h/mo. That is about $46/mo on spot, about $115/mo on Fargate Graviton, or one or two Hetzner dedicated boxes.
- **Higher-resolution grids add tiles in proportion to grid points.** HRRR 3 km CONUS (1799×1059, about 1.9M points, 18–48 h forecasts, 24 runs/day) is about 2x the points of GFS per hour, and hourly cycles make it the single largest producer of tiles. Max zoom is about z6–z7 over CONUS only.

**Hot storage with retention**
- Keep the last 2 runs of each model hot, e.g. 4,000 field-runs/day × 0.53 GB × 0.5 day ≈ 1 TB. That costs about $15/mo on R2 and about $23/mo on S3.
- Delete raw GRIB right after processing. It is re-fetchable from NOAA/ECMWF open data, whose rolling archives are long on AWS (the GFS BDP bucket keeps years).
- Archive only what can't be re-derived cheaply: e.g. analysis-hour (f000) tiles for a "past weather" feature, in R2 IA ($0.01/GB) or S3 Glacier Instant ($0.004/GB). Reanalysis (ERA5) is already on AWS open data and does not need copying.
- Avoid Wasabi (90-day minimum) and Deep Archive (180-day minimum, unverified) for rolling data.

**Delivery**
- Illustrative load: 5,000 subscribers × 200 MB/day of tiles ≈ 30 TB/month ≈ 1B tile requests.
- CloudFront pay-as-you-go: about $2.5k/mo in transfer (10 TB × $0.085 + 20 TB × ~$0.08), plus about $1k in request fees (unverified).
- CloudFront flat-rate: exceeds even Premium's 500M requests unless it is configured higher.
- R2 through Cloudflare CDN: $0 egress. Class B costs at most about $360/mo if every request misses the edge cache, far less with caching, plus a Cloudflare plan fee.
- S3 direct egress: about $2.5k/mo.
- **Delivery is the largest line item on AWS and close to zero on R2.**

**Point and meteogram extraction**
- Serve these from a separate chunked store (e.g. Zarr/time-series chunks per region) rather than from tiles. That keeps request counts low, and it's the same small-object/PUT trade-off.

### Gaps
- The 0.5 CPU-s per field-hour and 30 KB per tile are assumptions to replace with Isobar's own benchmarks.
- The per-subscriber traffic (200 MB/day) is illustrative.
- No weather-startup cost write-ups were found to calibrate against.
