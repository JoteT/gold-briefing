#!/usr/bin/env python3
"""
contract_transparency_agent.py — Africa Gold Intelligence
==========================================================
Tracks the hidden side of African gold markets that no mainstream
financial newsletter covers:

  1. Mining Contract Database       — Which Western companies hold contracts,
                                      on what royalty terms, for how much
                                      production. At today's spot price, how
                                      much is the host country actually earning?

  2. Shadow Economy Coefficient     — Formal production (EITI-reported) vs
                                      estimated actual production. The gap is
                                      Africa's largest unreported wealth drain.

  3. Illicit Flow Monitor           — The Dubai/UAE import-export gap: gold
                                      that leaves Africa but is never declared
                                      as an export. Sourced from Swissaid
                                      annual trade reconciliation data.

  4. Resource Nationalism Tracker   — Which governments are renegotiating,
                                      nationalising, or taking greater control
                                      of their mines — and what that means for
                                      future supply.

  5. Royalty Revenue Analyser       — At today's gold spot price, how much
                                      each country actually earns from its
                                      largest mine vs what a fair rate would pay.

DATA METHODOLOGY:
  - Mining contracts: curated from ResourceContracts.org and company disclosures.
    Update quarterly via: python3 contract_transparency_agent.py --update-check
  - Shadow economy: EITI open data + Swissaid annual reconciliation (updated yearly).
  - Illicit flows: Swissaid 2024 report (321-474t/yr; $23-35B). Updated annually.
  - Resource nationalism: tracked from company press releases and government decrees.

REFERENCES:
  ResourceContracts.org  — Natural Resource Governance Institute
  EITI Open Data Portal  — eiti.org/explore-data-portal
  Swissaid Gold Reports  — swissaid.ch (annual)
  Global Fin. Integrity  — gfintegrity.org
  OECD IFF Reports       — oecd.org
"""

import os, sys, json, datetime, math
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
_env_file  = SCRIPT_DIR.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _k, _v = _k.strip(), _v.strip()
            if _v and "REPLACE_WITH" not in _v and "your_" not in _v.lower():
                os.environ[_k] = _v

TROY_OZ_TO_GRAM = 31.1035

# ══════════════════════════════════════════════════════════════════════════════
# MINING CONTRACT DATABASE
# Sourced from: ResourceContracts.org, company annual reports, EITI disclosures
# Last updated: Q1 2026 — review quarterly
# ══════════════════════════════════════════════════════════════════════════════

MINING_CONTRACTS = [
    # ── West Africa ──────────────────────────────────────────────────────────
    {
        "company":          "Barrick Gold",
        "hq_country":       "Canada",
        "ticker":           "GOLD (NYSE)",
        "host_country":     "DRC",
        "mine":             "Kibali",
        "annual_oz":        686_000,
        "royalty_pct":      3.0,
        "state_equity_pct": 10.0,
        "tax_holiday_yrs":  0,
        "contract_status":  "stable",
        "notes":            "JV: Barrick 45%, AngloGold 45%, DRC gov 10%. DRC's largest gold mine. Produced 686koz in 2024. Formal sector in a country where 80-98% of artisanal gold is smuggled.",
        "source":           "ResourceContracts.org / Barrick 2024 Annual Report",
        "fair_royalty_pct": 8.0,   # NRGI recommended benchmark for Africa
    },
    {
        "company":          "Barrick Gold",
        "hq_country":       "Canada",
        "ticker":           "GOLD (NYSE)",
        "host_country":     "Mali",
        "mine":             "Loulo-Gounkoto",
        "annual_oz":        723_000,
        "royalty_pct":      8.0,   # new code post-junta renegotiation
        "state_equity_pct": 20.0,  # junta demanded increase
        "tax_holiday_yrs":  0,
        "contract_status":  "resolved",
        "notes":            "Suspended Jan 2025 after employee arrests; resolved late 2025 with junta. New terms include higher royalties under Mali's 2023 mining code. Four Barrick employees detained then released.",
        "source":           "Barrick press release Nov 2025 / Mali Mining Code 2023",
        "fair_royalty_pct": 8.0,
    },
    {
        "company":          "B2Gold",
        "hq_country":       "Canada",
        "ticker":           "BTG (NYSE)",
        "host_country":     "Mali",
        "mine":             "Fekola Complex",
        "annual_oz":        530_000,
        "royalty_pct":      6.5,   # post-settlement effective rate
        "state_equity_pct": 20.0,
        "tax_holiday_yrs":  0,
        "contract_status":  "renegotiated",
        "notes":            "Paid $160M tax settlement to Mali junta in 2024. Signed MOU allowing underground expansion. Agreed to invest $10M in mine development as part of deal. Operations uninterrupted.",
        "source":           "B2Gold press release 2024-12 / Mali MOU",
        "fair_royalty_pct": 8.0,
    },
    {
        "company":          "Gold Fields",
        "hq_country":       "South Africa",
        "ticker":           "GFI (NYSE)",
        "host_country":     "Ghana",
        "mine":             "Tarkwa",
        "annual_oz":        537_000,
        "royalty_pct":      5.0,
        "state_equity_pct": 10.0,
        "tax_holiday_yrs":  0,
        "contract_status":  "stable",
        "notes":            "Ghana's Minerals Commission holds 10% carried interest. Royalty rate 5% on gross revenue. Ghana parliament reviewing rates — potential increase to 6-7% under review. Galamsey adds ~90t/yr informal sector nationally.",
        "source":           "Gold Fields 2024 Annual Report / Ghana Minerals Commission",
        "fair_royalty_pct": 8.0,
    },
    {
        "company":          "AngloGold Ashanti",
        "hq_country":       "South Africa/UK",
        "ticker":           "AU (NYSE)",
        "host_country":     "Ghana",
        "mine":             "Obuasi",
        "annual_oz":        285_000,
        "royalty_pct":      5.0,
        "state_equity_pct": 10.0,
        "tax_holiday_yrs":  0,
        "contract_status":  "stable",
        "notes":            "Phase 3 expansion underway targeting 400koz/yr. Historic Ashanti goldfields. JV discussions with Gold Fields to create Africa's largest gold mine (~900koz combined) announced 2024.",
        "source":           "AngloGold 2024 Annual Report",
        "fair_royalty_pct": 8.0,
    },
    {
        "company":          "Kinross Gold",
        "hq_country":       "Canada",
        "ticker":           "KGC (NYSE)",
        "host_country":     "Mauritania",
        "mine":             "Tasiast",
        "annual_oz":        622_000,
        "royalty_pct":      3.0,   # legacy rate; Mauritania has low royalty regime
        "state_equity_pct": 10.0,
        "tax_holiday_yrs":  0,
        "contract_status":  "stable",
        "notes":            "One of Africa's most efficient open-pit operations. Mauritania has the lowest royalty rate in Francophone West Africa at 3% — economists argue 8-10% is fair value at current prices. Government has not moved to renegotiate.",
        "source":           "Kinross 2024 Annual Report / Mauritania Mining Code",
        "fair_royalty_pct": 8.0,
    },
    {
        "company":          "Centamin",
        "hq_country":       "UK/Australia",
        "ticker":           "CEY (LSE)",
        "host_country":     "Egypt",
        "mine":             "Sukari",
        "annual_oz":        400_000,
        "royalty_pct":      3.0,
        "state_equity_pct": 50.0,  # 50/50 profit share JV with EMRA (state)
        "tax_holiday_yrs":  0,
        "contract_status":  "stable",
        "notes":            "Unique 50/50 profit-sharing JV with EMRA (Egyptian Mineral Resources Authority). Africa's largest single open-pit gold mine. Profit share structure means effective government take is much higher than royalty rate implies — Egypt receives ~35-40% of net revenue total.",
        "source":           "Centamin 2024 Annual Report / EMRA Concession Agreement",
        "fair_royalty_pct": 8.0,
    },
    {
        "company":          "AngloGold Ashanti",
        "hq_country":       "South Africa/UK",
        "ticker":           "AU (NYSE)",
        "host_country":     "Tanzania",
        "mine":             "Geita",
        "annual_oz":        480_000,
        "royalty_pct":      6.0,
        "state_equity_pct": 16.0,  # mandatory free-carry under 2017 Mining Act
        "tax_holiday_yrs":  0,
        "contract_status":  "stable",
        "notes":            "Post-Acacia dispute era — Tanzania now requires 16% government free-carry interest in all mines under 2017 Mining Act. 6% royalty rate. Stable under President Samia; new mineral wealth fund reinvests royalties locally.",
        "source":           "AngloGold 2024 Annual Report / Tanzania Mining Act 2017",
        "fair_royalty_pct": 8.0,
    },
    {
        "company":          "SOPAMIB (State)",
        "hq_country":       "Burkina Faso",
        "ticker":           "N/A (state-owned)",
        "host_country":     "Burkina Faso",
        "mine":             "Boungou + Wahgnion + 5 others",
        "annual_oz":        350_000,  # estimated combined
        "royalty_pct":      100.0,  # state now captures full value
        "state_equity_pct": 100.0,
        "tax_holiday_yrs":  0,
        "contract_status":  "nationalised",
        "notes":            "JUNTA MODEL: Military junta created SOPAMIB under new Mining Code (July 2024). Nationalized Endeavour Mining's Boungou and Wahgnion mines plus 5 others. Pays $80M to resolve prior owner disputes. Abolishes corporate tax holidays. Mandates local investor share capital. Now directs gold revenue to national gold reserve — the benchmark other Sahelian governments are watching.",
        "source":           "Burkina Faso Mining Code July 2024 / Pinsent Masons analysis",
        "fair_royalty_pct": 100.0,  # full state capture
    },
    {
        "company":          "Endeavour Mining",
        "hq_country":       "Canada/UK",
        "ticker":           "EDV (TSX)",
        "host_country":     "Côte d'Ivoire",
        "mine":             "Ity CIL + Agbaou",
        "annual_oz":        340_000,
        "royalty_pct":      5.0,
        "state_equity_pct": 10.0,
        "tax_holiday_yrs":  3,
        "contract_status":  "stable",
        "notes":            "Côte d'Ivoire remains relatively stable for foreign miners compared to its Sahelian neighbours. 5% royalty, 10% state carry. Tax holiday period has ended for Ity. Endeavour retreated from Burkina Faso (mines nationalized) to focus on Ivoirian assets.",
        "source":           "Endeavour Mining 2024 Annual Report",
        "fair_royalty_pct": 8.0,
    },
    {
        "company":          "Caledonia Mining",
        "hq_country":       "UK/Canada",
        "ticker":           "CMCL (NYSE American)",
        "host_country":     "Zimbabwe",
        "mine":             "Blanket Mine",
        "annual_oz":        75_000,
        "royalty_pct":      5.0,
        "state_equity_pct": 49.0,  # mandatory indigenisation
        "tax_holiday_yrs":  0,
        "contract_status":  "stable",
        "notes":            "Zimbabwe's Indigenisation Act mandates 51% Zimbabwean ownership — Caledonia holds 49%. All gold sold mandatorily to Fidelity Gold Refinery (state) at market rates. Zimbabwe targeting 100t/yr by 2025; fastest-growing sector in Africa. Currency reforms (ZWG) improving miner confidence.",
        "source":           "Caledonia Mining 2024 Annual Report / Zimbabwe Indigenisation Act",
        "fair_royalty_pct": 8.0,
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# SHADOW ECONOMY DATA
# Sources: EITI reports, Swissaid 2024, OECD, Global Financial Integrity
# The "coefficient" = estimated informal production / formal reported production
# Updated: 2024 data (Swissaid May 2024 report)
# ══════════════════════════════════════════════════════════════════════════════

SHADOW_ECONOMY = {
    "headline": {
        "annual_illicit_tonnes_low":   321,
        "annual_illicit_tonnes_high":  474,
        "annual_illicit_usd_low_bn":   23.7,
        "annual_illicit_usd_high_bn":  35.0,
        "africa_formal_tonnes":        1050,   # approximate 2024 total
        "shadow_coefficient":          0.38,   # illicit ≈ 38% of formal production
        "report_date":                 "May 2024",
        "source":                      "Swissaid — On the Trail of African Gold, 2024",
        "source_url":                  "https://www.swissaid.ch/en/articles/on-the-trail-of-african-gold/",
    },
    "by_country": {
        "DRC": {
            "formal_tonnes":     30,
            "estimated_total":   150,    # 80-98% smuggled per IPIS
            "shadow_pct":        80,
            "smuggle_note":      "80–98% of artisanal output is smuggled. DRC is Africa's largest informal gold producer. Most exits via Uganda, Rwanda, Burundi to UAE.",
            "asm_miners":        "2M+",
        },
        "Zimbabwe": {
            "formal_tonnes":     35,
            "estimated_total":   65,
            "shadow_pct":        46,
            "smuggle_note":      "60–70% of production estimated informal. Fidelity Gold Refinery mandatory offtake is closing the gap — formal deliveries rising. Currency reforms helping.",
            "asm_miners":        "500K+",
        },
        "Ghana": {
            "formal_tonnes":     130,
            "estimated_total":   220,
            "shadow_pct":        41,
            "smuggle_note":      "ASM sector produced 90t+ in 2025 (up 50%). Galamsey adds 3-4M oz/yr informally. Ghana-UAE 5-year gap: 229 tonnes / $11.4B undeclared.",
            "asm_miners":        "1M+",
        },
        "Mali": {
            "formal_tonnes":     65,
            "estimated_total":   100,
            "shadow_pct":        35,
            "smuggle_note":      "Significant informal production in artisanal zones. Junta crackdown on smuggling ongoing. Loulo-Gounkoto suspension (Jan-late 2025) diverted formal production.",
            "asm_miners":        "400K+",
        },
        "Sudan": {
            "formal_tonnes":     10,
            "estimated_total":   80,
            "shadow_pct":        88,
            "smuggle_note":      "Active conflict severely disrupts formal reporting. Sudan estimated to produce 80t/yr (second largest ASM sector in Africa) but reports ~10t officially. UAE primary destination.",
            "asm_miners":        "2M+",
        },
    },
    # The Dubai/UAE Import-Export Gap — the single most damning dataset
    "dubai_gap": {
        "period":               "2012–2022",
        "undeclared_tonnes":    2569,
        "undeclared_value_usd": "115.3 billion",
        "uae_share_of_smuggled": 47,   # % of illicit African gold going to UAE
        "swiss_share":           21,
        "india_share":           12,
        "zero_export_countries": 23,   # countries that reported ZERO exports to UAE in 2018 yet UAE reported $6B imports from them
        "ghana_5yr_gap_tonnes":  229,
        "ghana_5yr_gap_usd_bn":  11.4,
        "source":                "Swissaid 2024 / CNBC / ScienceDirect trade analysis",
        "source_url":            "https://www.swissaid.ch/en/media/press-release-gold-study-2024/",
        "latest_year":           2024,
        "latest_uae_africa_tonnes": 748,   # UAE imported 748t from Africa in 2024 (up 18% YoY)
        "latest_yoy_pct":        18,
    },
    # Africa's total annual losses to trade misinvoicing across sectors
    "financial_losses": {
        "gfi_africa_annual_bn":      52,     # $30-52B range
        "ghana_decade_loss_bn":      54.1,   # Ghana 2013-2022 (GFI)
        "sa_annual_loss_bn":          7.4,   # South Africa annual average (GFI)
        "source":                    "Global Financial Integrity 2023",
        "source_url":                "https://gfintegrity.org/report/trade-related-illicit-financial-flows-in-africa-2013-2022/",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# RESOURCE NATIONALISM TRACKER
# Tracks government posture toward foreign mining companies
# Status: stable | watching | renegotiating | nationalising | nationalised
# ══════════════════════════════════════════════════════════════════════════════

RESOURCE_NATIONALISM = {
    "Burkina Faso": {
        "status":         "nationalised",
        "risk_level":     "completed",
        "government":     "Military Junta (CNSP, Ibrahim Traoré)",
        "key_action":     "New Mining Code July 2024. SOPAMIB state entity created. Boungou, Wahgnion + 5 other mines nationalized. Preferential tax rates abolished. Minimum state ownership raised. Local investor share capital mandated.",
        "affected_cos":   ["Endeavour Mining (EDV)", "Lilium Mining", "West African Resources (WAF)"],
        "template_for":   ["Mali", "Niger", "Guinea"],
        "last_updated":   "Q3 2024",
        "investor_signal": "⚠️ SUPPLY RISK: Combined ~350koz/yr now under SOPAMIB. Quality of production data will decline. Watch for output disruptions as state management ramps up.",
    },
    "Mali": {
        "status":         "renegotiated",
        "risk_level":     "elevated",
        "government":     "Military Junta (CNSP, Assimi Goïta)",
        "key_action":     "2023 Mining Code raises royalties to 6-10%. Junta demanded larger state stakes. Barrick dispute resolved late 2025 (4 employees detained/released). B2Gold paid $160M tax settlement. All operators now under new fiscal terms.",
        "affected_cos":   ["Barrick Gold (GOLD)", "B2Gold (BTG)", "Resolute Mining"],
        "template_for":   ["Burkina Faso", "Niger"],
        "last_updated":   "Q4 2025",
        "investor_signal": "🟡 STABILISING: Barrick resumed. B2Gold expanding. New fiscal terms now baked in. Risk is policy reversal if junta changes — watch for stability signals.",
    },
    "Niger": {
        "status":         "watching",
        "risk_level":     "elevated",
        "government":     "Military Junta (CNSP, Abdourahamane Tiani) post-2023 coup",
        "key_action":     "Post-coup government reviewing all natural resource contracts. Uranium sector (Orano) hit first — gold sector next. No formal nationalizations yet but framework legislation expected.",
        "affected_cos":   ["GoviEx Uranium (uranium focus)", "Potential future gold operators"],
        "template_for":   [],
        "last_updated":   "Q2 2025",
        "investor_signal": "🔴 HIGH RISK: Follow Burkina Faso playbook expected. Limited current gold production but exploration permits at risk. Avoid new capital commitments.",
    },
    "Tanzania": {
        "status":         "stable",
        "risk_level":     "moderate",
        "government":     "President Samia Suluhu Hassan (democratic)",
        "key_action":     "Post-Acacia dispute (2017-2019) resolved. 2017 Mining Act now standard: 16% government free-carry, 6% royalty. Barrick/Twiga JV (North Mara, Bulyanhulu) stable. New mineral wealth fund reinvesting royalties locally.",
        "affected_cos":   ["Barrick/Twiga JV", "AngloGold Ashanti (Geita)"],
        "template_for":   [],
        "last_updated":   "Q1 2025",
        "investor_signal": "✅ STABLE: Precedent-setting 2017 dispute resolution set clear new terms. Government cooperative but firm on 16% carry. Good template for balanced resource nationalism.",
    },
    "Ghana": {
        "status":         "watching",
        "risk_level":     "moderate",
        "government":     "President John Mahama (democratic, returned Jan 2025)",
        "key_action":     "Parliament reviewing royalty rates (potential increase to 6-7% from 5%). Galamsey crackdown ongoing — armed forces deployed to illegal mining sites. AngloGold-Gold Fields JV merger talks ongoing (combined 900koz/yr). ASM formalisation bill under debate.",
        "affected_cos":   ["Gold Fields (GFI)", "AngloGold Ashanti (AU)", "Kinross (KGC)"],
        "template_for":   [],
        "last_updated":   "Q1 2026",
        "investor_signal": "🟡 MONITOR: Royalty review is a real risk — each 1% rate increase costs sector ~$65M/yr at current production. Galamsey crackdown could formalise 30-40t of ASM into the official supply chain.",
    },
    "Zimbabwe": {
        "status":         "stable",
        "risk_level":     "moderate",
        "government":     "President Emmerson Mnangagwa (ZANU-PF)",
        "key_action":     "Fastest-growing gold sector in Africa. Mandatory Fidelity Gold Refinery offtake closing informal gap. Currency reforms (ZWG) improving miner confidence. 51% indigenisation requirement remains. Targeting 100t/yr by 2025.",
        "affected_cos":   ["Caledonia Mining (CMCL)", "Great Dyke Investments"],
        "template_for":   [],
        "last_updated":   "Q1 2026",
        "investor_signal": "✅ IMPROVING: Currency stabilisation and mandatory offtake structure are formalising the sector. Investor confidence growing but indigenisation framework remains a structural hurdle.",
    },
    "DRC": {
        "status":         "watching",
        "risk_level":     "high",
        "government":     "President Félix Tshisekedi (democratic but fragile)",
        "key_action":     "Formal sector tiny vs. ASM. 2018 Mining Code raised royalties. Security costs are the primary AISC driver. Conflict minerals tracking (OECD Due Diligence) increasingly mandatory for buyers. Kibali JV (Barrick/AngloGold) stable in Ituri province.",
        "affected_cos":   ["Barrick Gold / AngloGold (Kibali JV)", "Twangiza Mining"],
        "template_for":   [],
        "last_updated":   "Q1 2026",
        "investor_signal": "🔴 ASM LEAKAGE RISK: Formal sector is an island in a sea of informal production. 80-98% of artisanal gold is smuggled. Supply data is structurally unreliable. Security situation in eastern DRC remains volatile.",
    },
    "South Africa": {
        "status":         "stable",
        "risk_level":     "low",
        "government":     "President Cyril Ramaphosa (ANC/GNU coalition)",
        "key_action":     "Mining Charter requires 30% BEE ownership (target met by most majors). DMRE royalty regime 0.5-5% sliding scale. Loadshedding structural cost headwind now easing. Deep-level mining in long-term decline; open-pit and tailings retreatment growing.",
        "affected_cos":   ["Gold Fields (GFI)", "Harmony Gold (HMY)", "Sibanye-Stillwater (SBSW)"],
        "template_for":   [],
        "last_updated":   "Q1 2026",
        "investor_signal": "✅ STABLE: Most mature regulatory framework in Africa. BEE compliance achieved by all majors. Energy costs remain the key operational variable — watch Eskom stability.",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# ROYALTY RATE BENCHMARKS
# NRGI (Natural Resource Governance Institute) recommends 8-12% as fair-value
# royalty for gold at current prices. Most African contracts are 3-6%.
# ══════════════════════════════════════════════════════════════════════════════

FAIR_ROYALTY_BENCHMARK = 8.0  # % — NRGI recommended minimum for >$1,500/oz gold
GLOBAL_BENCHMARK = {
    "Indonesia":    10.0,
    "Australia":     5.0,  # varies by state; WA is 2.5% but with other levies
    "Canada":        2.0,  # varies by province; Ontario ~3.5%
    "USA":           5.0,  # federal lands
    "Russia":        6.0,
    "Peru":          6.0,
    "Brazil":        1.5,
    "Africa_avg":    4.8,  # weighted average of tracked African contracts
    "NRGI_recommended": 8.0,
}


# ══════════════════════════════════════════════════════════════════════════════
# CORE CALCULATIONS
# ══════════════════════════════════════════════════════════════════════════════

def calc_royalty_analysis(gold_price: float) -> list:
    """
    For each mining contract, calculate:
    - Annual royalty paid to host country at today's spot price
    - What they WOULD receive at the NRGI fair-value benchmark
    - The annual revenue gap
    - Effective government take (royalty + state equity distributions)
    """
    results = []
    for c in MINING_CONTRACTS:
        if c["contract_status"] == "nationalised":
            # State captures full value
            full_value = c["annual_oz"] * gold_price
            results.append({
                **c,
                "annual_revenue_usd":     full_value,
                "royalty_paid_usd":       full_value,
                "fair_value_royalty_usd": full_value,
                "revenue_gap_usd":        0,
                "gap_pct":                0.0,
                "effective_govt_take_pct": 100.0,
                "gross_revenue_usd":      full_value,
            })
            continue

        gross = c["annual_oz"] * gold_price
        actual_royalty    = gross * (c["royalty_pct"] / 100)
        fair_royalty      = gross * (FAIR_ROYALTY_BENCHMARK / 100)
        gap               = fair_royalty - actual_royalty
        gap_pct           = (gap / gross * 100) if gross else 0

        # Rough effective govt take: royalty + state equity distributions
        # State equity ~= equity_pct * (gross - costs); assume ~40% margin
        estimated_margin  = gross * 0.40
        equity_income     = estimated_margin * (c["state_equity_pct"] / 100)
        effective_take    = ((actual_royalty + equity_income) / gross * 100) if gross else 0

        results.append({
            **c,
            "gross_revenue_usd":        round(gross),
            "royalty_paid_usd":         round(actual_royalty),
            "fair_value_royalty_usd":   round(fair_royalty),
            "revenue_gap_usd":          round(gap),
            "gap_pct":                  round(gap_pct, 1),
            "effective_govt_take_pct":  round(effective_take, 1),
        })

    return sorted(results, key=lambda x: x["revenue_gap_usd"], reverse=True)


def calc_shadow_totals(gold_price: float) -> dict:
    """Compute shadow economy totals at today's gold price."""
    se = SHADOW_ECONOMY
    headline = se["headline"]

    # Mid-point estimate
    illicit_mid_tonnes = (headline["annual_illicit_tonnes_low"] +
                          headline["annual_illicit_tonnes_high"]) / 2
    troy_oz_per_tonne  = 32_151  # 1 metric tonne = 32,151 troy oz
    illicit_mid_usd    = illicit_mid_tonnes * troy_oz_per_tonne * gold_price

    dubai_gap = se["dubai_gap"]
    undeclared_usd = dubai_gap["undeclared_tonnes"] * troy_oz_per_tonne * gold_price

    country_data = []
    for country, d in se["by_country"].items():
        gap_tonnes = d["estimated_total"] - d["formal_tonnes"]
        gap_usd    = gap_tonnes * troy_oz_per_tonne * gold_price
        country_data.append({
            "country":         country,
            "formal_tonnes":   d["formal_tonnes"],
            "estimated_total": d["estimated_total"],
            "shadow_pct":      d["shadow_pct"],
            "gap_tonnes":      gap_tonnes,
            "gap_usd":         round(gap_usd / 1e9, 1),  # in $B
            "smuggle_note":    d["smuggle_note"],
            "asm_miners":      d["asm_miners"],
        })

    return {
        "illicit_mid_tonnes":    round(illicit_mid_tonnes),
        "illicit_mid_usd_bn":    round(illicit_mid_usd / 1e9, 1),
        "illicit_low_usd_bn":    headline["annual_illicit_usd_low_bn"],
        "illicit_high_usd_bn":   headline["annual_illicit_usd_high_bn"],
        "shadow_coefficient":    headline["shadow_coefficient"],
        "country_data":          country_data,
        "dubai_gap":             dubai_gap,
        "financial_losses":      se["financial_losses"],
        "gold_price_used":       gold_price,
        "report_date":           headline["report_date"],
        "source":                headline["source"],
    }


def get_nationalism_alerts() -> list:
    """Return countries with active or recent nationalisation/renegotiation activity."""
    alerts = []
    priority_order = ["nationalised", "renegotiated", "renegotiating", "watching", "stable"]
    for country, data in RESOURCE_NATIONALISM.items():
        alerts.append({"country": country, **data})
    alerts.sort(key=lambda x: priority_order.index(x["status"]) if x["status"] in priority_order else 99)
    return alerts


def fetch_contract_news(max_items: int = 6) -> list:
    """Fetch news about African mining contracts, nationalizations, and policy changes."""
    try:
        import feedparser
    except ImportError:
        return []

    contract_feeds = [
        ("Mining Weekly",    "https://www.miningweekly.com/rss/latest"),
        ("Engineering News", "https://www.engineeringnews.co.za/rss/latest"),
        ("African Mining",   "https://www.africanmining.co.za/feed/"),
        ("Resource Govt",    "https://resourcegovernance.org/feed"),
        ("BusinessDay NG",   "https://businessday.ng/feed/"),
    ]
    contract_keywords = [
        "royalty", "mining code", "mining contract", "nationaliz", "nationalise",
        "state ownership", "mining tax", "mineral rights", "junta", "mining law",
        "artisanal", "smuggling", "illicit gold", "transfer pricing",
        "barrick mali", "b2gold mali", "endeavour burkina", "sopamib",
        "eiti", "resource nationalism", "mining reform", "gold export",
        "duty free", "gold smuggling", "informal mining", "galamsey",
        "gold trafficking", "undeclared gold",
    ]

    import socket
    items = []
    orig_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(10)
    try:
        for source, url in contract_feeds:
            if len(items) >= max_items:
                break
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:40]:
                    title   = entry.get("title", "")
                    summary = entry.get("summary", "")
                    link    = entry.get("link", "#")
                    text    = (title + " " + summary).lower()
                    if any(kw in text for kw in contract_keywords):
                        items.append({"source": source, "title": title, "link": link})
                    if len(items) >= max_items:
                        break
            except Exception:
                pass
    finally:
        socket.setdefaulttimeout(orig_timeout)
    return items[:max_items]


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run(data: dict, today: datetime.datetime) -> dict:
    """
    Run the Contract Transparency & Shadow Economy intelligence module.

    Args:
        data:  market data dict from Agent 1 (must contain gold price)
        today: current datetime

    Returns:
        contract_data dict with all transparency intelligence
    """
    gold_price = data.get("gold", {}).get("price", 0)

    print("  📋 Mining contract royalty analysis...")
    royalty_analysis = calc_royalty_analysis(gold_price)
    total_gap = sum(r["revenue_gap_usd"] for r in royalty_analysis)
    total_royalties_paid = sum(r["royalty_paid_usd"] for r in royalty_analysis)
    print(f"     {len(royalty_analysis)} contracts tracked")
    print(f"     Total royalties paid to Africa today: ${total_royalties_paid/1e6:.0f}M/yr at spot")
    print(f"     Fair-value gap (vs 8% benchmark):     ${total_gap/1e6:.0f}M/yr")

    print("  👤 Shadow economy & illicit flow calculation...")
    shadow_data = calc_shadow_totals(gold_price)
    print(f"     Illicit gold estimate: ~{shadow_data['illicit_mid_tonnes']}t/yr (${shadow_data['illicit_mid_usd_bn']}B at spot)")
    print(f"     Dubai 10-yr gap:       2,569t / $115.3B undeclared")

    print("  🏛️  Resource nationalism tracker...")
    nationalism_alerts = get_nationalism_alerts()
    active = [n for n in nationalism_alerts if n["status"] in ("nationalised", "renegotiated", "renegotiating")]
    print(f"     {len(active)} countries with active nationalisation/renegotiation")

    print("  📡 Contract transparency news...")
    contract_news = fetch_contract_news(max_items=6)
    print(f"     {len(contract_news)} contract/policy headline(s) found")

    # Spotlight: biggest royalty gap contract at today's price
    top_gap = royalty_analysis[0] if royalty_analysis else {}

    # Burkina Faso model — always highlight as the live case study
    bf_data = RESOURCE_NATIONALISM.get("Burkina Faso", {})

    return {
        "royalty_analysis":      royalty_analysis,
        "total_royalties_paid":  total_royalties_paid,
        "total_fair_value":      total_royalties_paid + total_gap,
        "total_gap_usd":         total_gap,
        "top_gap_contract":      top_gap,
        "shadow_data":           shadow_data,
        "nationalism_alerts":    nationalism_alerts,
        "contract_news":         contract_news,
        "burkina_model":         bf_data,
        "global_benchmarks":     GLOBAL_BENCHMARK,
        "gold_price":            gold_price,
        "contracts_count":       len(royalty_analysis),
        "fair_royalty_benchmark": FAIR_ROYALTY_BENCHMARK,
    }


if __name__ == "__main__":
    import sys
    if "--update-check" in sys.argv:
        print("\nContract database last-update check:")
        print("  ResourceContracts.org:  https://www.resourcecontracts.org/countries")
        print("  EITI Open Data:         https://eiti.org/explore-data-portal")
        print("  Swissaid Gold Reports:  https://www.swissaid.ch/en/articles/on-the-trail-of-african-gold/")
        print("  GFI Trade Reports:      https://gfintegrity.org/reports/")
        print("\nManually review and update MINING_CONTRACTS and SHADOW_ECONOMY quarterly.")
    else:
        # Quick test with a dummy gold price
        test_data = {"gold": {"price": 2923.0}}
        result = run(test_data, datetime.datetime.now())
        print(f"\n  Contracts tracked:   {result['contracts_count']}")
        print(f"  Total royalties:     ${result['total_royalties_paid']/1e6:.0f}M/yr")
        print(f"  Fair-value gap:      ${result['total_gap_usd']/1e6:.0f}M/yr")
        print(f"  Shadow economy:      ~{result['shadow_data']['illicit_mid_tonnes']}t/yr")
        print(f"  Nationalism alerts:  {len([n for n in result['nationalism_alerts'] if n['status'] in ('nationalised','renegotiated','renegotiating')])}")
