# Weathermodels.com: Catalog of Models, Products, Map Parameters and Pricing (as of Sept 2026)

**Access limits (important):** weathermodels.com, weather.us, blog.weather.us, web.archive.org and r.jina.ai were all **blocked by this environment's egress proxy** (WebFetch returned EGRESS_BLOCKED, curl returned CONNECT 403). I could not open any page directly. Everything below comes from **web-search result titles, URLs and snippets** of weathermodels.com pages (pricing, ECMWF guidelines, industry-energy, preview/link-list, model-viewer permalinks) plus third-party pages. Snippets are summaries made by the search tool, so exact wording, full parameter lists and resolutions still need to be checked against the live pages. Items marked "unverified" come only from a search-tool summary and not from a page title or URL.

## Which models/datasets does Weathermodels.com offer, and who owns it?

### Takeaway
Weathermodels.com is run by the **Kachelmann Group (Meteologix AG / Kachelmann GmbH / WeatherOK Inc.)**, the same group behind weather.us, meteologix.com and kachelmannwetter.com. Ryan Maue built it but left in June 2019. Its headline offering is ECMWF: HRES with 1-hourly data and the 6z/18z runs, EPS/ENS, and the EPS 46-day extended range. It also carries UKMET, GFS, GEFS, HRRR, NAM, CMC/GEM, RGEM, HRDPS, ICON (including ICON-D2), NWS NDFD and CAMS.

### Cited Findings
**Ownership**
- The Kachelmann Group "runs the successful international weather portals meteologix.com, weather.us, weathermodels.com and kachelmannwetter.com". The group (Meteologix AG, Kachelmann GmbH, WeatherOK) was founded by Jörg Kachelmann in 2015 — [Kachelmann Group LinkedIn](https://www.linkedin.com/company/kachelmann-group); [Meteologix team page](https://www.business.meteologix.com/en/team)
- Ryan Maue was COO of WeatherOK Inc./weather.us, and weathermodels.com was described as "the home of Dr. Ryan Maue's model maps" — [weather.us maue.pdf](https://weather.us/download/maue.pdf); [Welcome to Weathermodels.com, blog.weather.us](https://blog.weather.us/welcome-to-weathermodels-com/)
- Maue was COO at weather.us from Oct 2017 to Jun 2019, then joined BAMWX (Jul 2019). He was appointed NOAA Chief Scientist in 2020 — [Ryan Maue LinkedIn](https://www.linkedin.com/in/ryanmaue/) (via search snippet); [Washington Post 2020-09-21](https://www.washingtonpost.com/weather/2020/09/21/noaa-chief-scientist-maue/)
- A weathermodels.com showcase page exists on LinkedIn — [LinkedIn showcase](https://www.linkedin.com/showcase/weathermodels-com/)

**Model list (site marketing text)**
- Homepage and meta description: "ECMWF (incl. 1-hourly data and 6z/18z extra runs), EPS, EPS 46-days, UKMET, GEFS, GFS, HRRR, CMC, CAMS and many more models". Users can "animate, compare, export and create customised GIFs" — [weathermodels.com](https://weathermodels.com/)
- Pricing/marketing list of "premium models": "ECMWF, EPS, HRRR, NAM-WRF, ICON, CMC, GFS, GEFS, RGEM, NWS NDFD, UKMET and more" — [Pricing](https://weathermodels.com/index.php?r=site/pricing); repeated in [Storm2K thread](https://www.storm2k.org/phpbb2/viewtopic.php?t=122022)
- The link list includes ICON-D2, UKMET and NAM-CONUS (search snippet) — [Link list](https://weathermodels.com/index.php?r=site/preview-linklist)
- The link list also includes CMC HRDPS, HRRR "in different resolutions" and RGEM 10-km (search snippet) — [Link list](https://weathermodels.com/index.php?r=site/preview-linklist)

**Model-viewer "sets" confirmed from indexed permalink URLs.** These are the product and region groupings used in the site's `set=` URL parameter:
| Set name (as in URL) | Evidence |
|---|---|
| `9-km ECMWF USA Surface` (e.g. area Mid Atlantic, param Kuchera Snowfall) | [permalink](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=9-km+ECMWF+USA+Surface&area=Mid+Atlantic&param=Kuchera+Snowfall&offset=0) |
| `9-km ECMWF Global Pressure` (area United States, param 500 hPa Height, comparator mode) | [permalink](https://weathermodels.com/index.php?r=site%2Fpreview&mode=comparator&set=9-km+ECMWF+Global+Pressure&area=United+States&param=500+hPa+Height&offset=0&thumbs=1) |
| `14-km EPS Energy` | search snippet referencing the link list — [Link list](https://weathermodels.com/index.php?r=site/preview-linklist) |
| `GFS 50-STATES USA` (Total Precipitation, Wind Chill Temperature, Snowfall, Kuchera Snowfall; areas United States, Denver) | [permalink 1](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=GFS+50-STATES+USA&area=United+States&param=Total+Precipitation&offset=0&thumbs=1), [permalink 2](https://weathermodels.com/index.php?area=United+States&mode=animator&offset=0&param=Wind+Chill+Temperature&r=site%2Fpreview&set=GFS+50-STATES+USA&thumbs=1), [permalink 3](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=GFS+50-STATES+USA&area=Denver&param=Kuchera+Snowfall) |
| `GFS Pressure Lev` (500 hPa Rel Humidity, area Canada; cycle 2025121612) | [permalink](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=GFS+Pressure+Lev&area=Canada&param=500+hPa+Rel+Humidity) |
| `GFS International` (850 hPa Wind, area Pakistan; cycle 2026083100) | [permalink](https://weathermodels.com/index.php?area=Pakistan&mode=animator&param=850+hPa+Wind&r=site%2Fpreview&set=GFS+International) |
| `GFS Energy` (10-m Wind for India; MSLP for Northeast US) | [permalink 1](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=GFS+Energy&area=India&param=10-m+Wind&offset=0&thumbs=1), [permalink 2](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=GFS+Energy&area=Northeast+US&param=MSLP&offset=1&thumbs=1) |
| `HRRR 3-km` (Heat Index, United States) | [permalink](https://weathermodels.com/index.php?area=United+States&mode=animator&offset=4&param=Heat+Index&r=site%2Fpreview&set=HRRR+3-km&thumbs=1) |
| City-chart link lists by model: `model=eps`, `model=ecmwf_international` | [EPS city charts](https://weathermodels.com/index.php?r=site/preview-linklist-cc&model=eps); [ECMWF international city charts](https://weathermodels.com/index.php?model=ecmwf_international&r=site%2Fpreview-linklist-cc) |
| EPS city charts page | [eps_charts.php](https://weathermodels.com/models/city/eps_charts.php) |

- Permalinks show cycles from 2025 through at least **2026-08-31 00z** (GFS International), so the site was **active and updating in 2026** — see permalinks above.

**Sister-site data (same group, likely the same data feeds; not direct evidence for weathermodels.com)**
- weather.us "Model charts" shows ECMWF IFS HRES "0z/12z (15 days)" and says the IFS runs every 6 hours at 9 km. It also covers ICON, GFS, UKMO and GEM — [weather.us model-charts](https://weather.us/model-charts); [weather.us euro snow depth](https://weather.us/model-charts/euro/snow-depth-in.html)

### Inferences
- The "9-km ECMWF" label matches IFS HRES. The "14-km EPS" label looks like a **legacy** label or product: ECMWF ENS has run at about 9 km since IFS Cycle 48r1 (June 2023). Either the label is out of date or the EPS maps are drawn from a coarser grid. This needs checking.
- The HRES/EPS forecast lengths are very likely ECMWF's standard ones: HRES 00/12z to 240 h (15 days after Cycle 48r1 per weather.us), 06/18z to 90 h (144 h since 2023); ENS 51 members to 15 days; extended ENS ("EPS 46-days") 101 members to 46 days, daily since 2023. These come from ECMWF's specifications, **not** from weathermodels.com text.
- The "Precipitation Type 31ensemble" parameter name points to GEFS (31 members) ensemble products.

### Gaps
- **AIFS (ECMWF AI model):** I found no evidence that weathermodels.com offers AIFS Single or AIFS ENS. Searches returned only ECMWF's own AIFS announcements. AIFS Single became operational on 25 Feb 2025 and AIFS ENS in July 2025 ([ECMWF](https://www.ecmwf.int/en/about/media-centre/news/2025/ecmwfs-ai-forecasts-become-operational)). Unknown whether the site carries either.
- No evidence found for **JMA, RRFS, NBM, NAM 3-km nest, ARPEGE/AROME, ACCESS, GraphCast/other AI models, or ECMWF SEAS5 seasonal**. A search summary mentioned "seasonal products" and "soundings", but no page title or URL confirmed either (**unverified**).
- I could not obtain per-model resolution, forecast length, run cycles or region lists from the site itself, because it is blocked.

## What map parameters and regions does each model have?

### Takeaway
I confirmed the parameter names below from indexed URLs and snippets. They span surface fields (2-m temperature derivatives, heat index, wind chill, 10-m wind and gust, MSLP, total precipitation, snowfall including Kuchera), upper-air fields (500 hPa height and RH, 850 hPa wind, stratospheric 50/10 hPa temperature anomalies), radar (max 1-h reflectivity), simulated IR satellite, precipitation type, and model-change ("6-hr Model Delta") maps. Regions range from US sub-regions and cities to Canada and worldwide countries (India, Pakistan). I could not recover a full list of parameters for each model.

### Cited Findings
**Parameters confirmed from URL `param=` values or page titles**
- Kuchera Snowfall (ECMWF USA Surface; GFS 50-STATES) — [ECMWF permalink](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=9-km+ECMWF+USA+Surface&area=Mid+Atlantic&param=Kuchera+Snowfall&offset=0); [GFS permalink](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=GFS+50-STATES+USA&area=Denver&param=Kuchera+Snowfall)
- Snowfall, presumably the standard 10:1 or model snow (GFS) — [permalink](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=GFS+50-STATES+USA&area=United+States&param=Snowfall&offset=0&thumbs=1)
- Total Precipitation — [permalink](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=GFS+50-STATES+USA&area=United+States&param=Total+Precipitation&offset=0&thumbs=1)
- Wind Chill Temperature — [permalink](https://weathermodels.com/index.php?area=United+States&mode=animator&offset=0&param=Wind+Chill+Temperature&r=site%2Fpreview&set=GFS+50-STATES+USA&thumbs=1)
- Heat Index (HRRR 3-km) — [permalink](https://weathermodels.com/index.php?area=United+States&mode=animator&offset=4&param=Heat+Index&r=site%2Fpreview&set=HRRR+3-km&thumbs=1)
- 10-m Wind; MSLP — [GFS Energy India](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=GFS+Energy&area=India&param=10-m+Wind&offset=0&thumbs=1); [GFS Energy NE US](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=GFS+Energy&area=Northeast+US&param=MSLP&offset=1&thumbs=1)
- 500 hPa Rel Humidity; 850 hPa Wind; 500 hPa Height — [GFS Pressure Lev](https://weathermodels.com/index.php?r=site/preview&mode=animator&set=GFS+Pressure+Lev&area=Canada&param=500+hPa+Rel+Humidity); [GFS International](https://weathermodels.com/index.php?area=Pakistan&mode=animator&param=850+hPa+Wind&r=site%2Fpreview&set=GFS+International); [ECMWF Global Pressure](https://weathermodels.com/index.php?r=site%2Fpreview&mode=comparator&set=9-km+ECMWF+Global+Pressure&area=United+States&param=500+hPa+Height&offset=0&thumbs=1)

**Parameters from link-list search snippets** ([Link list](https://weathermodels.com/index.php?r=site/preview-linklist))
- "10-m Wind Gust [mph]"
- "Precipitation Type 31ensemble" (ensemble precipitation type)
- "500 hPa Geopotential Height 6-hr Model Delta" (run-to-run change maps)
- "50 hPa Temperature Anom Control", "10 hPa Temperature Anom Control" (stratospheric anomalies from an ensemble control run)
- "Max 1-h Reflectivity" (simulated radar for convection-allowing models)
- "Simulated IR Satellite"

**Regions/areas seen:** United States, Mid Atlantic, Northeast US, Denver (city or metro area), Canada, India and Pakistan (international country areas) — permalinks above. City charts cover "cities and city regions in North and South America as well as international capitals" — [weathermodels.com](https://weathermodels.com/) (snippet)

**Viewer modes:** "animator", "comparator" (compare model systems such as GFS vs ECMWF vs HRRR), a postage-stamp view with export, and GIF creation — [Model viewer](https://weathermodels.com/index.php?r=site%2Fpreview); [weathermodels.com](https://weathermodels.com/)

### Inferences
- Set names follow a pattern of `<model> <domain/level group>`, such as "USA Surface", "Global Pressure", "50-STATES USA", "International", "Energy" and "Pressure Lev". Each model therefore probably has separate US surface, global or international, pressure-level and energy parameter groups.
- Parameters I asked about but could not confirm at this site: Cobb or SLR-variable snowfall, 2-m temperature anomaly maps (only stratospheric anomalies confirmed), CAPE/SRH/STP severe parameters, cloud cover, freezing rain/ice accumulation. Given this is a comprehensive ECMWF-focused service, their presence is **plausible but unverified**.

### Gaps
- There is no complete list of parameters for each model. The link-list page (index.php?r=site/preview-linklist) would provide it but is blocked. A follow-up with unrestricted web access should scrape that page and the `preview-linklist-cc` pages.

## Special products: ensembles, meteograms, energy, tropical, long range

### Takeaway
Weathermodels.com's distinctive strengths are **deep ECMWF coverage** (hourly output, the 06/18z runs, EPS individual members, EPS 46-day) and an **Industry ENERGY tier**. That tier offers population/gas/electric-weighted degree days for 331 census cities, degree-day sums, weighted city forecasts, a model-verification table, and ensemble CDD/temperature box plots.

### Cited Findings
- **Individual ensemble member viewer:** view each of the EPS's 51 members — [blog.weather.us tutorial](https://blog.weather.us/weathermodels-com-individual-ensemble-member-viewer-tutorial/) (snippet)
- **EPS precipitation matrices** showing all members at a glance, box-plot charts and mixed-parameter bar graphs — [EPS city link list](https://weathermodels.com/index.php?r=site/preview-linklist-cc&model=eps) (snippet)
- **City charts:** precipitation matrices, meteograms, temperature and wind forecasts, and **model blends** for North/South American cities and international capitals — [weathermodels.com](https://weathermodels.com/) (snippet)
- **Industry ENERGY account:** "all the International Commercial Forecaster maps, plus an additional custom Dashboard, Weighted Degree Days, Degree Day Sums, Weighted City Forecasts, a model verification table, and additional special charts and maps" — [Industry Energy](https://weathermodels.com/index.php?r=site%2Findustry-energy) (snippet)
  - Degree-day output for **331 census cities** in a colour-coded anomaly table: CDD, HDD, mean and min/max temperature versus climatological normals — same source
  - Degree days weighted "by population, gas and electricity usage" for cities and census regions — same source
  - **Verification table** compares recent model forecasts with observations and colour-codes the deviation, which shows run skill and systematic bias — same source
  - Line graphs and **box plots for ensemble CDD, mean and min/max temperature** — same source
- **Teleconnections:** Arctic Oscillation (and similar) charts for ECMWF, EPS, EPS 46 days, GFS and GEFS, depending on subscription — search-tool summary citing [weathermodels.com](https://weathermodels.com/) (**unverified wording**)
- **Tropical:** cyclone maps, velocity potential (anomaly) and zonal-wind anomaly maps — search-tool summary citing [weathermodels.com](https://weathermodels.com/) (**unverified wording**)
- **Air quality:** CAMS (Copernicus Atmosphere Monitoring Service) is listed among models — [weathermodels.com](https://weathermodels.com/)

### Inferences
- The energy tier is aimed at gas/power traders in the same way as WeatherBELL's and StormVista's energy products. Weighted HDD/CDD combined with a verification table is the main difference from hobbyist sites such as Tropical Tidbits and Pivotal Weather.

### Gaps
- Not confirmed: skew-T soundings (a search summary mentioned them without a source page), ECMWF SEAS5 or other seasonal models, and ensemble exceedance-probability maps.
- The EPS 46-day parameter list (weekly anomalies?) is not available.

## Subscription tiers, prices and data licensing

### Takeaway
There are three account types: **Personal Forecaster** (about $15/month according to third parties), **Commercial Forecaster** ($29/month, stated in the site snippet), and **Industry ENERGY / Energy USA** (price not found). There is reportedly no free trial. Weathermodels.com says it is an ECMWF **"maximum charge" customer** that produces value-added services. Broadcasting ECMWF-based graphics needs a separate ECMWF broadcast licence.

### Cited Findings
- "Commercial usage for $29/month" — [Pricing](https://weathermodels.com/index.php?r=site/pricing) (snippet)
- Personal Forecaster: "Perfect for weather enthusiasts and hobbyists". Holders "may moderately share weather maps with friends, family, or other hobbyists, including on non-commercial websites or social media" — [Pricing](https://weathermodels.com/index.php?r=site/pricing) (snippet)
- Commercial Forecaster: "the right tool for professional meteorologists". Maps may be used "in commercial reports, videos, television shows, or on social media channels" — [Pricing](https://weathermodels.com/index.php?r=site/pricing); [Commercial weather](https://weathermodels.com/index.php?r=site/commercial-weather) (snippet)
- The Energy USA package "adds more maps, parameters and special tools" — [Pricing](https://weathermodels.com/index.php?r=site/pricing) (snippet)
- Personal price given as **$15/month** — [Storm2K forum](https://www.storm2k.org/phpbb2/viewtopic.php?t=122022). A 2026 blog says weathermodels.com offers "serious ECMWF depth — but at $15/month with no free trial" — [Forecaster HQ, 2026](https://forecasterhq.com/blog/weathermodels-alternatives-2026). This is a third-party marketing blog, so treat it with moderate confidence.
- Licensing: "Weathermodels.com is a maximum charge customer of ECMWF data and does process this data to create maps and graphics (so-called Value-Added-Services (VAS)) for its customers". Maps "can be shared without restriction by ECMWF" as long as users do not exceed the sharing allowed by their subscription type. Anyone who wants to **broadcast** ECMWF products or VAS "has to purchase a broadcast licence separately with ECMWF" — [ECMWF Guidelines](https://weathermodels.com/index.php?r=site/ecmwf-guidelines) (snippet)
- The site's pitch: access to "almost every single ECMWF parameter at a reasonable price without having to get an industrial account" — search-tool summary of [weathermodels.com](https://weathermodels.com/)
- Competitive context: Similarweb (July 2026) lists its closest competitors as tropicaltidbits.com, pivotalweather.com, weather.us, weathernerds.org and wxcharts.com — [Forecaster HQ](https://forecasterhq.com/blog/weathermodels-alternatives-2026). Storm2K users priced StormVista at $20/month at the time — [Storm2K](https://www.storm2k.org/phpbb2/viewtopic.php?t=122022)

### Inferences
- "Maximum charge customer" refers to ECMWF's old tariff model, where a licensee paying the capped maximum information cost gets unlimited VAS redistribution. ECMWF moved to a new data-pricing and open-data policy in 2024–2026 ([ECMWF old costing model page](https://www.ecmwf.int/en/forecasts/access-forecasts/data-pricing/data-pricing-old-costing-model)), so this wording on the guidelines page **may be outdated**.
- Energy-tier pricing is probably by quote or much higher than $29, but I found no source.

### Gaps
- I could not find the exact current prices for Personal and Energy, whether annual discounts exist, the difference between "International" and US Commercial tiers (the Energy text mentions "International Commercial Forecaster maps", which suggests a US versus International split), or whether prices changed in 2025–2026.
