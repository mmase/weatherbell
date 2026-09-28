# WeatherBell Analytics: Model, Product and Map Parameter Catalog (as of Sept 2026)

> **Method and access caveat (read first).** The egress proxy blocked direct fetches of `www.weatherbell.com`, `maps.weatherbell.com`, `forecasterhq.com`, and `web.archive.org` (errors: "EGRESS_BLOCKED" / "unable to fetch"). **No WeatherBell page was read in full.** Everything below comes from web-search result titles, URLs, and search-engine summaries of those pages. Those summaries are machine-generated and sometimes mix in text from other sites (Pivotal Weather, Tropical Tidbits). Treat each "Cited Finding" as *confirmed that the source exists and is summarized this way*, not as a verbatim quote. Where a summary may have pulled in another site's text, it is flagged. maps.weatherbell.com is behind a login for most content, so a full list of parameters per model could not be pulled from any source. Research date: 2026-09-28.

## 1. Which models/datasets does WeatherBell Maps offer?

### Takeaway
Sources confirm most of the user's reference list. Confirmed: observations/analyses (RTMA, MRMS 1 km radar, GOES-16/18, OPC lightning density, IMS snow/ice, OSTIA, gridded precip), NDFD, NBM, RRFS, HRRR (incl. 15-min), NAM 3 km/12 km, SREF, ECMWF IFS (0.1° upper air/wave hourly to 90h), ECMWF AIFS and AIFS Ensemble, AIGFS, GFS, GDPS/CMC, UKMET, ICON (global/EU 7 km/D2 2 km), JMA, GEFS, ECMWF ensembles/weeklies, CFSv2, CanSIPS, soundings (global) and meteograms. The remaining items (OISST, CPC, HRAP, PRISM, CDAS, NOHRSC, SPC/WPC, WRF ARW/FV3, RDPS, RTOFS, WW3, AIGEFS, GEFS-extended, CMC extended, ECMWF seasonal, CMAQ, NASA GEOS dust, HAFS/HWRF/HMON, Hovmöller, teleconnections) were **not individually confirmed** in accessible text. They are plausible, and some are only weakly supported.

### Cited Findings
**Platform / navigation**
- WeatherBell Maps (maps.weatherbell.com) is the models/maps viewer; users "type a model or time to filter a table." Its homepage summary lists: real-time mesoscale analysis for North America (RTMA), 1 km radar data going back 6.5 hours (MRMS), GOES-16 and GOES-18, OPC Lightning Density, daily Northern Hemisphere snow and ice analysis (IMS), Operational Sea Surface Temperature and Sea Ice Analysis (OSTIA), and "various gridded precipitation datasets." It runs on Google Cloud Platform. — [WeatherBell Maps](https://maps.weatherbell.com/)
- Quick guide: pick the map/model type first. Parameters sit in a left-hand menu grouped by type (e.g., "Surface-Precipitation", "Surface-Parameter"), each group a drop-down. Regions sit in a right-hand menu grouped into master categories (e.g., "North America - US Cities", "Global & Continental"). Earlier runs are reached from a drop-down in the map info box. — [New Maps Page - Quick Guide](https://www.weatherbell.com/new-maps-page---quick-guide)
- Model URL slugs seen in indexed pages: `ndfd-conus` (region `conus`, parameter `t2m_f`), `gdps-all`, `hrrr`, `gfs-deterministic` (region `neng` = New England, parameter `total_snow_kuchera`). — [NDFD: WeatherBell Maps](https://maps.weatherbell.com/view/model/ndfd-conus?d=conus&p=t2m_f); [GDPS](https://maps.weatherbell.com/view/model/gdps-all); [HRRR](https://maps.weatherbell.com/view/model/hrrr); [GFS Kuchera](https://maps.weatherbell.com/view/model/gfs-deterministic?d=neng&p=total_snow_kuchera)
- Private/white-label instances exist, e.g., `scedison.weatherbell.com` titled "WeatherBell Maps" (probably Southern California Edison). — [scedison.weatherbell.com](https://scedison.weatherbell.com/)

**Deterministic / mesoscale (CONUS/North America)**
- HRRR: 3 km, updated hourly, assimilates real-time radar. The landing page lists "HRRR 15-min." — [WeatherBELL Glossary](https://www.weatherbell.com/glossary); [WeatherBELL Data Services](https://www.weatherbell.com/landing/data-services)
- NAM: run by NCEP at 3 km and 12 km, cycles 00/06/12/18z. — [Glossary](https://www.weatherbell.com/glossary); [Data Services](https://www.weatherbell.com/landing/data-services)
- RRFS: WeatherBell first added the experimental RRFS with soundings, meteograms and a selection of maps for the **60-hour 00/06/12/18z runs over CONUS** (X post, date not shown in snippet). Before winter 2025-26, "in anticipation of NCEP's implementation of the RRFS into operations," WeatherBell made its **full product suite** available for RRFS. — [WeatherBELL on X](https://x.com/weatherbell/status/1719035694880841811); [Increased and Expanded Product Offerings Ahead of Winter 2025-26](https://www.weatherbell.com/weatherbell-press/increased-and-expanded-product-offerings-ahead-of-winter-2025-26)
- NBM: offered. The winter 2025-26 release says NBM v5 was "expected to be implemented in April 2026." — [Winter 2025-26 press release](https://www.weatherbell.com/weatherbell-press/increased-and-expanded-product-offerings-ahead-of-winter-2025-26); [ECMWF AIFS Ensemble v1 Release and More](https://www.weatherbell.com/ecmwf-aifs-ensemble-v1-release)
- NDFD: CONUS domain, 2m temp (°F) parameter confirmed by URL. — [NDFD page](https://maps.weatherbell.com/view/model/ndfd-conus?d=conus&p=t2m_f)
- SREF, NDFD, NAM, CFS, GFS and Canadian GEM appear in an older WeatherBell models PDF. It also lists the RUC "transitioning to Rapid Refresh & HRRR," so it dates from about 2011-12 and is **outdated**. — [WeatherBELL Analytics Models PDF](https://www.weatherbell.com/images/imguploader/files/WeatherBELL%20Analytics%20Models(1).pdf)

**Global deterministic**
- ECMWF IFS: glossary says HRES to 240h and 51 ensemble members to 360h at 00/12z, with 90h (det) / 144h (ens) at 06/18z. — [Glossary](https://www.weatherbell.com/glossary)
- ECMWF upgrade (2025): "Upper air and wave data are now offered at full spatial and time resolution (0.1°) with hourly data through 90 hours." WeatherBell calls itself "the premier destination for ECMWF data and graphics." This is also the source for the **ECMWF Wave** offering. — [ECMWF AIFS Ensemble v1 Release and More](https://www.weatherbell.com/ecmwf-aifs-ensemble-v1-release); [press version](https://www.weatherbell.com/weatherbell-press/ecmwf-aifs-ensemble-v1-release/)
- GFS: NCEP global model, slug `gfs-deterministic`. — [Glossary](https://www.weatherbell.com/glossary); [GFS URL](https://maps.weatherbell.com/view/model/gfs-deterministic?d=neng&p=total_snow_kuchera)
- GDPS (Canadian global), slug `gdps-all`. — [GDPS page](https://maps.weatherbell.com/view/model/gdps-all)
- ICON (DWD): 00/06/12/18z out to 120 hours per the glossary. The landing page lists "ICON/EUR 7km/DE 2km" (i.e., ICON-EU 7 km and ICON-D2 2 km). — [Glossary](https://www.weatherbell.com/glossary); [Data Services](https://www.weatherbell.com/landing/data-services)
- UKMET: 00z/12z out to 144 hours. — [Glossary](https://www.weatherbell.com/glossary)
- JMA GSM: 00z/12z out to 192 hours. — [Glossary](https://www.weatherbell.com/glossary)

**AI models**
- ECMWF AIFS: "We have added a selection of ECMWF AIFS parameters to WeatherBELL Maps" (X status 1765061371547496875, about March 2024 by ID). — [WeatherBELL on X](https://x.com/weatherbell/status/1765061371547496875)
- ECMWF AIFS Ensemble v1: WeatherBell announced it after ECMWF's operational release on 1 July 2025. 4 runs/day, 15-day forecasts, 0.25° for all fields. It replaced the experimental AIFS ENS DIFF. The premium page describes "ECMWF's AI Ensemble model out to 15 days." — [ECMWF AIFS Ensemble Release](https://www.weatherbell.com/weatherbell-press/ecmwf-aifs-ensemble-v1-release/); [Premium](https://www.weatherbell.com/premium)
- AIGFS: the search summary said Maps "offers both ECMWF AIFS and AIGFS." That claim traces to a query mixing WeatherBell and non-WeatherBell results. **Weak confirmation.** NOAA's SCN 25-89 introduced operational AIGFS, AIGEFS and HGEFS. — [NOAA SCN 25-89](https://www.weather.gov/media/notification/pdf_2025/scn25-89_AIGFS_AIGEFS_and_HGEFS.pdf); [NOAA news release](https://www.noaa.gov/news-release/noaa-deploys-new-generation-of-ai-driven-global-weather-models)

**Ensembles / extended / seasonal**
- GEFS: medium-range ensemble, 00/06/12/18z out to 385 hours (glossary typo says "12z and 12z"). — [Glossary](https://www.weatherbell.com/glossary)
- ECMWF Weeklies: premium page lists "Euro Weeklies - Ensemble mean out 46 days" and the control out 46 days. The glossary says extended range runs "Monday and Thursday." — [Premium](https://www.weatherbell.com/premium); [Glossary](https://www.weatherbell.com/glossary)
- CFSv2: 00/06/12/18z out to 45 days (extended) and 00z out to 4 months (seasonal), per the glossary. Premium page: "Climate Forecast System U.S. model mean out 45 days." — [Glossary](https://www.weatherbell.com/glossary); [Premium](https://www.weatherbell.com/premium)
- CanSIPS: run on the 1st of each month, out to 1 year. — [Glossary](https://www.weatherbell.com/glossary)
- Premium marketing: "highest resolution European (ECMWF) operational, ensembles & seasonal models," which supports **ECMWF seasonal** (SEAS5). — [Premium](https://www.weatherbell.com/premium)

**Special products**
- Soundings: "Upper air profiles, i.e., model soundings, are now available globally" (winter 2025-26 release). Meteograms are confirmed via the RRFS announcement. — [Winter 2025-26 release](https://www.weatherbell.com/weatherbell-press/increased-and-expanded-product-offerings-ahead-of-winter-2025-26); [X RRFS post](https://x.com/weatherbell/status/1719035694880841811)
- WeatherBELL posted on X (status 1978890605037044165, about Oct 2025 by ID): "We are excited to announce the following additions and enhancements to our industry-leading weather data visualization product, WeatherBELL Maps." The details are in an image that could not be read. — [WeatherBELL on X](https://x.com/weatherbell/status/1978890605037044165)

### Inferences
- The user's reference list probably mirrors the current Maps model menu (its section names such as "HRAP 4km precip" and "OPC Lightning Density" match the homepage summary closely). Items that could not be confirmed individually are still likely present, but should be labeled "per reference list, unverified."
- The glossary's "Monday and Thursday" schedule for ECMWF extended range is **outdated**. ECMWF moved extended range to daily 00z runs with 101 members in cycle 48r1 (June 2023; general knowledge, not from a WeatherBell source). Its "51 members" for the ENS is also outdated for 2026. The glossary figures for UKMET (144h) and ICON (120h) may reflect what WeatherBell *plots*, not the native model length (ICON global runs to 180h at 00/12z).
- The 2025 ECMWF upgrade to 0.1° hourly to 90h implies WeatherBell ingests the full-resolution licensed IFS, not the 0.25° open data.
- The October 2025 X post and the winter 2025-26 release likely cover the same enhancements (RRFS full suite, global soundings, probably AI models and NBM changes).

### Gaps
- The model menu could not be enumerated from a live page (maps.weatherbell.com blocked, Wayback blocked).
- Unconfirmed items with no accessible source: OISST, CPC rainfall, HRAP 4 km, PRISM, CDAS, historical SSTs, NOHRSC, SPC outlooks, WPC QPF/winter, WRF ARW/FV3 (HREF members), RDPS/HRDPS, RTOFS, WaveWatch3, AIGEFS, GEFS extended (35-day), CMC extended (GEPS 32-day), CMC ensemble, Hovmöller, teleconnection indices, CMAQ air quality, NASA GEOS dust, TC probabilities/tracks, HAFS-A/B, HWRF, HMON. The search summary for tropical/hurricane models plainly drew on Tropical Tidbits' text, so it does **not** confirm HAFS/HWRF/HMON on WeatherBell. HWRF and HMON were retired by NCEP in 2023 in favor of HAFS, so any listing of them is probably legacy or archive.
- NBM v5: I found no confirmation that it went operational in April 2026 or that WeatherBell switched to it.

## 2. Parameters/maps per model, and regions/domains

### Takeaway
The confirmed parameter set is small. Confirmed: 2m temperature (°F), 2m temperature anomaly (°F/°C), 2m dew point, 10:1 and Kuchera snowfall (total accumulated), precipitation type, MSLP, 500 mb height. Regions are hierarchical: CONUS, New England, US cities, "Global & Continental," and an "all" global domain for GDPS. An exhaustive per-model parameter list could not be obtained.

### Cited Findings
- Parameter groups are organized as "Surface-Precipitation", "Surface-Parameter", etc. Region groups include "North America - US Cities" and "Global & Continental." — [Quick Guide](https://www.weatherbell.com/new-maps-page---quick-guide)
- `total_snow_kuchera` on GFS for the `neng` (New England) domain. — [GFS Kuchera URL](https://maps.weatherbell.com/view/model/gfs-deterministic?d=neng&p=total_snow_kuchera)
- `t2m_f` (2m temp °F) on NDFD CONUS. — [NDFD URL](https://maps.weatherbell.com/view/model/ndfd-conus?d=conus&p=t2m_f)
- Search summary: primary snowfall products are 10:1 and Kuchera; 2m Dew Point, MSLP, 500 mb height, precip type, and a "2m Anomaly (°F and °C)" parameter are selectable. (Caution: the 10:1/Kuchera explanation may come from Pivotal Weather's guide, which also ranked in results. WeatherBell parameter existence rests on the WeatherBell URL plus the summary.) — [WeatherBell Maps GFS](https://maps.weatherbell.com/view/model/gfs-deterministic?d=neng&p=total_snow_kuchera); [Winter 2025-26 release](https://www.weatherbell.com/weatherbell-press/increased-and-expanded-product-offerings-ahead-of-winter-2025-26)
- ECMWF upper-air and wave fields at 0.1° hourly to 90h. — [AIFS Ens release](https://www.weatherbell.com/ecmwf-aifs-ensemble-v1-release)
- Early RRFS domain: CONUS, 60h, 00/06/12/18z. — [X RRFS post](https://x.com/weatherbell/status/1719035694880841811)
- AIFS started with "a selection of" parameters, i.e., fewer than IFS. — [X AIFS post](https://x.com/weatherbell/status/1765061371547496875)

### Inferences
- Slug naming (`<model>-<domain-group>` such as `ndfd-conus` and `gdps-all`, plus `d=<region>` and `p=<param>`) implies each model has its own list of supported domains. `-all` likely means full global coverage.
- The user's example parameters (total precip, 850 mb temp, CAPE, simulated reflectivity, wind gusts, 500 mb anomaly) are standard on comparable platforms and very likely present. However, they were **not confirmed** from WeatherBell sources here.

### Gaps
- No exhaustive per-model parameter list. No resolution for GFS, GDPS, UKMET or JMA as plotted. No list of regional sub-domains (Europe, Asia, etc.). Getting these needs a logged-in session or an unblocked fetch of maps.weatherbell.com (the left and right menus).

## 3. Pricing and tiers

### Takeaway
WeatherBELL Premium (which includes the Models/Maps page plus Bastardi/D'Aleo/Downs content) costs **$29.99/mo or $300/yr personal** and **$69.99/mo or $690/yr business/professional**, with a **3-day free trial**. Enterprise data services and white-label Maps instances are sold separately, and no public price was found for them.

### Cited Findings
- $29.99/month or $300/year for personal/non-professional use; $69.99/month or $690/year for business/professional use. — [WeatherBELL Premium](https://www.weatherbell.com/premium); [Register/Free Trial](https://www.weatherbell.com/register/pre)
- 3-day free trial. Cancel before it ends and you are not charged; otherwise billing starts automatically. — [Free Trial](https://www.weatherbell.com/register/pre)
- Premium is "home to the leading weather models page as well as written and video content from meteorologists Joe Bastardi, Joe D'Aleo and Tom Downs." — [Premium](https://www.weatherbell.com/premium)
- Separate B2B offerings: Data Services, Energy, Agriculture, Broadcast, Winter landing pages. Spire partnership page exists. — [Data Services](https://www.weatherbell.com/landing/data-services); [Broadcast](https://www.weatherbell.com/landing/broadcast); [Agriculture](https://www.weatherbell.com/landing/agriculture); [Spire and WeatherBELL](https://insights.spire.com/weatherbell); [Energy PDF](https://www.weatherbell.com/images/imguploader/files/WeatherBELL%20Analytics%20Energy.pdf)

### Inferences
- The prices come from search-engine summaries of the live premium page in 2026, so they are probably current, but they could not be checked against the rendered page. There seems to be no separate models-only tier; Models/Maps is bundled in Premium.

### Gaps
- No enterprise, API or white-label pricing was found. It is not known whether the personal and professional tiers differ in model access or only in license terms.
