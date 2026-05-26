/**

 * NSE TRADING TERMINAL — Production Grade

 * ─────────────────────────────────────────────────────────────────

 * • 300+ NSE stocks searchable database

 * • Bookmarks persisted via window.storage

 * • Live data from FastAPI backend (localhost:8000) + offline simulation

 * • AI-powered predictions via Groq API

 * • Real-time signal approval/denial

 * • Professional Bloomberg-style dark terminal UI

 * ─────────────────────────────────────────────────────────────────

 * DEPLOY: Run `python main.py --mode web` then open this in browser

 */



import { useState, useEffect, useCallback, useRef, useMemo } from "react";

import {

  AreaChart, Area, LineChart, Line, BarChart, Bar,

  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine

} from "recharts";

import {

  Search, Star, TrendingUp, TrendingDown, RefreshCw, X,

  Activity, Zap, Shield, BarChart2, Bell, Settings,

  ArrowUpRight, ArrowDownRight, ChevronDown, ChevronRight,

  Bookmark, BookmarkCheck, AlertTriangle, CheckCircle,

  Eye, Filter, SortAsc, Cpu, Target, Clock, Volume2,

  Radio, Circle, Plus, Minus, Info, ExternalLink

} from "lucide-react";



// ═══════════════════════════════════════════════════════════════════
const BACKEND = import.meta.env.DEV ? "http://localhost:8000" : "";
const API_KEY = localStorage.getItem("NSE_API_KEY") || "dev-secret-key";

async function tryFetch(url, options = {}) {
  try {
    const res = await fetch(url, options);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    return null;
  }
}

// NSE STOCK DATABASE — 300+ stocks across all sectors
// ═══════════════════════════════════════════════════════════════════

const NSE_ALL_STOCKS = [

  // ── GLOBAL MACRO ──────────────────────────────────────────────

  {s:"BTC-USD",n:"Bitcoin",sec:"Crypto",idx:"Global",p:90000},

  {s:"ETH-USD",n:"Ethereum",sec:"Crypto",idx:"Global",p:3000},

  {s:"CL=F",n:"Crude Oil",sec:"Fuels",idx:"Global",p:75},

  {s:"NG=F",n:"Natural Gas",sec:"Fuels",idx:"Global",p:3},

  // ── NIFTY 50 ──────────────────────────────────────────────────

  {s:"RELIANCE",n:"Reliance Industries",sec:"Energy",idx:"N50",p:2950},

  {s:"TCS",n:"Tata Consultancy Services",sec:"Technology",idx:"N50",p:3800},

  {s:"HDFCBANK",n:"HDFC Bank",sec:"Banking",idx:"N50",p:1720},

  {s:"INFY",n:"Infosys",sec:"Technology",idx:"N50",p:1580},

  {s:"ICICIBANK",n:"ICICI Bank",sec:"Banking",idx:"N50",p:1340},

  {s:"HINDUNILVR",n:"Hindustan Unilever",sec:"FMCG",idx:"N50",p:2400},

  {s:"SBIN",n:"State Bank of India",sec:"Banking",idx:"N50",p:820},

  {s:"BHARTIARTL",n:"Bharti Airtel",sec:"Telecom",idx:"N50",p:1850},

  {s:"ITC",n:"ITC Ltd",sec:"FMCG",idx:"N50",p:430},

  {s:"KOTAKBANK",n:"Kotak Mahindra Bank",sec:"Banking",idx:"N50",p:1990},

  {s:"LT",n:"Larsen & Toubro",sec:"Infrastructure",idx:"N50",p:3600},

  {s:"AXISBANK",n:"Axis Bank",sec:"Banking",idx:"N50",p:1180},

  {s:"WIPRO",n:"Wipro",sec:"Technology",idx:"N50",p:480},

  {s:"BAJFINANCE",n:"Bajaj Finance",sec:"Finance",idx:"N50",p:9100},

  {s:"MARUTI",n:"Maruti Suzuki",sec:"Auto",idx:"N50",p:11500},

  {s:"SUNPHARMA",n:"Sun Pharmaceutical",sec:"Pharma",idx:"N50",p:1750},

  {s:"TITAN",n:"Titan Company",sec:"Consumer",idx:"N50",p:3300},

  {s:"ASIANPAINT",n:"Asian Paints",sec:"Consumer",idx:"N50",p:2700},

  {s:"NESTLEIND",n:"Nestle India",sec:"FMCG",idx:"N50",p:2350},

  {s:"ULTRACEMCO",n:"UltraTech Cement",sec:"Materials",idx:"N50",p:10200},

  {s:"BAJAJFINSV",n:"Bajaj Finserv",sec:"Finance",idx:"N50",p:1780},

  {s:"NTPC",n:"NTPC",sec:"Energy",idx:"N50",p:380},

  {s:"POWERGRID",n:"Power Grid Corp",sec:"Energy",idx:"N50",p:310},

  {s:"ADANIPORTS",n:"Adani Ports",sec:"Infrastructure",idx:"N50",p:1380},

  {s:"TATAMOTORS",n:"Tata Motors",sec:"Auto",idx:"N50",p:950},

  {s:"HCLTECH",n:"HCL Technologies",sec:"Technology",idx:"N50",p:1780},

  {s:"ONGC",n:"ONGC",sec:"Energy",idx:"N50",p:280},

  {s:"TATASTEEL",n:"Tata Steel",sec:"Materials",idx:"N50",p:165},

  {s:"JSWSTEEL",n:"JSW Steel",sec:"Materials",idx:"N50",p:930},

  {s:"TECHM",n:"Tech Mahindra",sec:"Technology",idx:"N50",p:1560},

  {s:"COALINDIA",n:"Coal India",sec:"Energy",idx:"N50",p:450},

  {s:"DIVISLAB",n:"Divi's Laboratories",sec:"Pharma",idx:"N50",p:4800},

  {s:"DRREDDY",n:"Dr. Reddy's Laboratories",sec:"Pharma",idx:"N50",p:6200},

  {s:"EICHERMOT",n:"Eicher Motors",sec:"Auto",idx:"N50",p:4800},

  {s:"GRASIM",n:"Grasim Industries",sec:"Materials",idx:"N50",p:2700},

  {s:"HEROMOTOCO",n:"Hero MotoCorp",sec:"Auto",idx:"N50",p:4900},

  {s:"HINDALCO",n:"Hindalco Industries",sec:"Materials",idx:"N50",p:680},

  {s:"M&M",n:"Mahindra & Mahindra",sec:"Auto",idx:"N50",p:2950},

  {s:"CIPLA",n:"Cipla",sec:"Pharma",idx:"N50",p:1680},

  {s:"TATACONSUM",n:"Tata Consumer Products",sec:"FMCG",idx:"N50",p:1080},

  {s:"INDUSINDBK",n:"IndusInd Bank",sec:"Banking",idx:"N50",p:1540},

  {s:"UPL",n:"UPL",sec:"Agri",idx:"N50",p:520},

  {s:"BRITANNIA",n:"Britannia Industries",sec:"FMCG",idx:"N50",p:5400},

  {s:"BPCL",n:"Bharat Petroleum",sec:"Energy",idx:"N50",p:330},

  {s:"HDFCLIFE",n:"HDFC Life Insurance",sec:"Insurance",idx:"N50",p:690},

  {s:"SBILIFE",n:"SBI Life Insurance",sec:"Insurance",idx:"N50",p:1680},

  {s:"PIDILITIND",n:"Pidilite Industries",sec:"Consumer",idx:"N50",p:3000},

  {s:"BAJAJ-AUTO",n:"Bajaj Auto",sec:"Auto",idx:"N50",p:9200},

  {s:"ADANIENT",n:"Adani Enterprises",sec:"Conglomerate",idx:"N50",p:2400},

  {s:"APOLLOHOSP",n:"Apollo Hospitals",sec:"Healthcare",idx:"N50",p:6800},

  // ── NIFTY NEXT 50 ─────────────────────────────────────────────

  {s:"ADANIGREEN",n:"Adani Green Energy",sec:"Energy",idx:"NN50",p:1780},

  {s:"SIEMENS",n:"Siemens",sec:"Capital Goods",idx:"NN50",p:6800},

  {s:"GODREJCP",n:"Godrej Consumer",sec:"FMCG",idx:"NN50",p:1310},

  {s:"MUTHOOTFIN",n:"Muthoot Finance",sec:"Finance",idx:"NN50",p:1900},

  {s:"RECLTD",n:"REC",sec:"Finance",idx:"NN50",p:550},

  {s:"PIIND",n:"PI Industries",sec:"Agri",idx:"NN50",p:3800},

  {s:"BIOCON",n:"Biocon",sec:"Pharma",idx:"NN50",p:325},

  {s:"PETRONET",n:"Petronet LNG",sec:"Energy",idx:"NN50",p:320},

  {s:"GAIL",n:"GAIL India",sec:"Energy",idx:"NN50",p:215},

  {s:"HAVELLS",n:"Havells India",sec:"Consumer",idx:"NN50",p:1780},

  {s:"CHOLAFIN",n:"Cholamandalam Finance",sec:"Finance",idx:"NN50",p:1350},

  {s:"TRENT",n:"Trent",sec:"Retail",idx:"NN50",p:5800},

  {s:"DABUR",n:"Dabur India",sec:"FMCG",idx:"NN50",p:540},

  {s:"NAUKRI",n:"Info Edge (Naukri)",sec:"Technology",idx:"NN50",p:7500},

  {s:"COLPAL",n:"Colgate-Palmolive",sec:"FMCG",idx:"NN50",p:2950},

  {s:"BERGEPAINT",n:"Berger Paints",sec:"Consumer",idx:"NN50",p:580},

  {s:"AUROPHARMA",n:"Aurobindo Pharma",sec:"Pharma",idx:"NN50",p:1180},

  {s:"MCDOWELL-N",n:"United Spirits (McDowell's)",sec:"FMCG",idx:"NN50",p:1050},

  {s:"OFSS",n:"Oracle Financial Services",sec:"Technology",idx:"NN50",p:10800},

  {s:"ACC",n:"ACC Cement",sec:"Materials",idx:"NN50",p:2100},

  {s:"MARICO",n:"Marico",sec:"FMCG",idx:"NN50",p:640},

  {s:"TORNTPHARM",n:"Torrent Pharmaceuticals",sec:"Pharma",idx:"NN50",p:3200},

  {s:"INDIGO",n:"IndiGo (InterGlobe Aviation)",sec:"Aviation",idx:"NN50",p:4200},

  {s:"LUPIN",n:"Lupin",sec:"Pharma",idx:"NN50",p:1980},

  {s:"OBEROIRLTY",n:"Oberoi Realty",sec:"Real Estate",idx:"NN50",p:1850},

  {s:"ICICIPRULI",n:"ICICI Prudential Life",sec:"Insurance",idx:"NN50",p:650},

  {s:"BANDHANBNK",n:"Bandhan Bank",sec:"Banking",idx:"NN50",p:190},

  {s:"ASTRAL",n:"Astral",sec:"Materials",idx:"NN50",p:2100},

  {s:"POLYCAB",n:"Polycab India",sec:"Capital Goods",idx:"NN50",p:6200},

  {s:"BALKRISIND",n:"Balkrishna Industries",sec:"Auto Ancillary",idx:"NN50",p:2650},

  {s:"IRCTC",n:"IRCTC",sec:"Tourism",idx:"NN50",p:860},

  {s:"ZOMATO",n:"Zomato",sec:"Consumer Tech",idx:"NN50",p:255},

  {s:"NYKAA",n:"FSN E-Commerce (Nykaa)",sec:"Retail",idx:"NN50",p:175},

  {s:"PAYTM",n:"One97 Communications (Paytm)",sec:"Fintech",idx:"NN50",p:620},

  {s:"DELHIVERY",n:"Delhivery",sec:"Logistics",idx:"NN50",p:390},

  {s:"POLICYBZR",n:"PB Fintech (PolicyBazaar)",sec:"Fintech",idx:"NN50",p:1580},

  // ── BANKING ───────────────────────────────────────────────────

  {s:"PNB",n:"Punjab National Bank",sec:"Banking",idx:"NIFTYBANK",p:110},

  {s:"BANKBARODA",n:"Bank of Baroda",sec:"Banking",idx:"NIFTYBANK",p:230},

  {s:"CANBK",n:"Canara Bank",sec:"Banking",idx:"NIFTYBANK",p:108},

  {s:"UNIONBANK",n:"Union Bank of India",sec:"Banking",idx:"NIFTYBANK",p:118},

  {s:"FEDERALBNK",n:"Federal Bank",sec:"Banking",idx:"NIFTYBANK",p:185},

  {s:"IDFCFIRSTB",n:"IDFC First Bank",sec:"Banking",idx:"NIFTYBANK",p:75},

  {s:"RBLBANK",n:"RBL Bank",sec:"Banking",idx:"NIFTYBANK",p:195},

  {s:"YESBANK",n:"Yes Bank",sec:"Banking",idx:"NIFTYBANK",p:23},

  {s:"SOUTHBANK",n:"South Indian Bank",sec:"Banking",idx:"NIFTYBANK",p:28},

  {s:"KARURVYSYA",n:"Karur Vysya Bank",sec:"Banking",idx:"NIFTYBANK",p:205},

  {s:"CUB",n:"City Union Bank",sec:"Banking",idx:"NIFTYBANK",p:165},

  {s:"DCBBANK",n:"DCB Bank",sec:"Banking",idx:"NIFTYBANK",p:135},

  // ── TECHNOLOGY ────────────────────────────────────────────────

  {s:"LTIM",n:"LTIMindtree",sec:"Technology",idx:"NIFTYIT",p:5800},

  {s:"MPHASIS",n:"Mphasis",sec:"Technology",idx:"NIFTYIT",p:2800},

  {s:"COFORGE",n:"Coforge",sec:"Technology",idx:"NIFTYIT",p:7200},

  {s:"PERSISTENT",n:"Persistent Systems",sec:"Technology",idx:"NIFTYIT",p:5000},

  {s:"KPITTECH",n:"KPIT Technologies",sec:"Technology",idx:"NIFTYIT",p:1690},

  {s:"TATAELXSI",n:"Tata Elxsi",sec:"Technology",idx:"NIFTYIT",p:6800},

  {s:"HEXAWARE",n:"Hexaware Technologies",sec:"Technology",idx:"NIFTYIT",p:715},

  {s:"MASTEK",n:"Mastek",sec:"Technology",idx:"NIFTYIT",p:2550},

  {s:"CYIENT",n:"Cyient",sec:"Technology",idx:"NIFTYIT",p:2000},

  {s:"NIITTECH",n:"NIIT Technologies",sec:"Technology",idx:"NIFTYIT",p:1950},

  {s:"HAPPSTMNDS",n:"Happiest Minds",sec:"Technology",idx:"NIFTYIT",p:820},

  {s:"ROUTE",n:"Route Mobile",sec:"Technology",idx:"NIFTYIT",p:1580},

  // ── PHARMA & HEALTHCARE ────────────────────────────────────────

  {s:"ALKEM",n:"Alkem Laboratories",sec:"Pharma",idx:"NIFTYPHARMA",p:5600},

  {s:"GLENMARK",n:"Glenmark Pharmaceuticals",sec:"Pharma",idx:"NIFTYPHARMA",p:1080},

  {s:"GRANULES",n:"Granules India",sec:"Pharma",idx:"NIFTYPHARMA",p:570},

  {s:"IPCA",n:"IPCA Laboratories",sec:"Pharma",idx:"NIFTYPHARMA",p:1550},

  {s:"PFIZER",n:"Pfizer India",sec:"Pharma",idx:"NIFTYPHARMA",p:5200},

  {s:"LALPATHLAB",n:"Dr Lal PathLabs",sec:"Healthcare",idx:"NIFTYPHARMA",p:2400},

  {s:"METROPOLIS",n:"Metropolis Healthcare",sec:"Healthcare",idx:"NIFTYPHARMA",p:1900},

  {s:"THYROCARE",n:"Thyrocare Technologies",sec:"Healthcare",idx:"NIFTYPHARMA",p:520},

  {s:"FORTIS",n:"Fortis Healthcare",sec:"Healthcare",idx:"NIFTYPHARMA",p:560},

  {s:"MAXHEALTH",n:"Max Healthcare",sec:"Healthcare",idx:"NIFTYPHARMA",p:850},

  {s:"ASTER",n:"Aster DM Healthcare",sec:"Healthcare",idx:"NIFTYPHARMA",p:475},

  {s:"ZYDUSLIFE",n:"Zydus Lifesciences",sec:"Pharma",idx:"NIFTYPHARMA",p:930},

  {s:"ABBOTINDIA",n:"Abbott India",sec:"Pharma",idx:"NIFTYPHARMA",p:26000},

  {s:"IPCALAB",n:"IPCA Labs",sec:"Pharma",idx:"NIFTYPHARMA",p:1560},

  // ── AUTO & AUTO ANCILLARY ─────────────────────────────────────

  {s:"MOTHERSON",n:"Motherson Sumi Wiring",sec:"Auto Ancillary",idx:"NIFTYAUTO",p:195},

  {s:"BOSCHLTD",n:"Bosch",sec:"Auto Ancillary",idx:"NIFTYAUTO",p:33500},

  {s:"MINDA",n:"Uno Minda",sec:"Auto Ancillary",idx:"NIFTYAUTO",p:1050},

  {s:"EXIDEIND",n:"Exide Industries",sec:"Auto Ancillary",idx:"NIFTYAUTO",p:400},

  {s:"AMARAJABAT",n:"Amara Raja Energy",sec:"Auto Ancillary",idx:"NIFTYAUTO",p:1150},

  {s:"SUNDRMFAST",n:"Sundram Fasteners",sec:"Auto Ancillary",idx:"NIFTYAUTO",p:1200},

  {s:"ASHOKLEY",n:"Ashok Leyland",sec:"Auto",idx:"NIFTYAUTO",p:230},

  {s:"FORCE",n:"Force Motors",sec:"Auto",idx:"NIFTYAUTO",p:7200},

  {s:"TVSMOTOR",n:"TVS Motor Company",sec:"Auto",idx:"NIFTYAUTO",p:2650},

  {s:"BAJAJHLDNG",n:"Bajaj Holdings",sec:"Finance",idx:"NIFTYAUTO",p:9800},

  // ── FMCG / CONSUMER ───────────────────────────────────────────

  {s:"EMAMILTD",n:"Emami",sec:"FMCG",idx:"NIFTYFMCG",p:580},

  {s:"JYOTHYLAB",n:"Jyothy Labs",sec:"FMCG",idx:"NIFTYFMCG",p:385},

  {s:"ZYDUSWELL",n:"Zydus Wellness",sec:"FMCG",idx:"NIFTYFMCG",p:1600},

  {s:"HONASA",n:"Honasa Consumer (Mamaearth)",sec:"FMCG",idx:"NIFTYFMCG",p:400},

  {s:"VENKEYS",n:"Venky's India",sec:"FMCG",idx:"NIFTYFMCG",p:1450},

  {s:"PATANJALI",n:"Patanjali Foods",sec:"FMCG",idx:"NIFTYFMCG",p:1950},

  // ── ENERGY / POWER ────────────────────────────────────────────

  {s:"TATAPOWER",n:"Tata Power",sec:"Energy",idx:"NIFTYENERGY",p:440},

  {s:"ADANIPOWER",n:"Adani Power",sec:"Energy",idx:"NIFTYENERGY",p:610},

  {s:"TORNTPOWER",n:"Torrent Power",sec:"Energy",idx:"NIFTYENERGY",p:1650},

  {s:"CESC",n:"CESC",sec:"Energy",idx:"NIFTYENERGY",p:190},

  {s:"NHPC",n:"NHPC",sec:"Energy",idx:"NIFTYENERGY",p:95},

  {s:"SJVN",n:"SJVN",sec:"Energy",idx:"NIFTYENERGY",p:125},

  {s:"IRFC",n:"IRFC",sec:"Finance",idx:"NIFTYENERGY",p:195},

  {s:"PGCIL",n:"Power Grid Corp",sec:"Energy",idx:"NIFTYENERGY",p:312},

  {s:"ADANITRANS",n:"Adani Transmission",sec:"Energy",idx:"NIFTYENERGY",p:980},

  {s:"GREENKO",n:"Greenko",sec:"Energy",idx:"NIFTYENERGY",p:1100},

  // ── INFRASTRUCTURE / REAL ESTATE ──────────────────────────────

  {s:"DLF",n:"DLF",sec:"Real Estate",idx:"NIFTYREALTY",p:890},

  {s:"GODREJPROP",n:"Godrej Properties",sec:"Real Estate",idx:"NIFTYREALTY",p:2700},

  {s:"PHOENIXLTD",n:"Phoenix Mills",sec:"Real Estate",idx:"NIFTYREALTY",p:3200},

  {s:"PRESTIGE",n:"Prestige Estates",sec:"Real Estate",idx:"NIFTYREALTY",p:1750},

  {s:"BRIGADE",n:"Brigade Enterprises",sec:"Real Estate",idx:"NIFTYREALTY",p:1150},

  {s:"MAHLIFE",n:"Mahindra Lifespace",sec:"Real Estate",idx:"NIFTYREALTY",p:580},

  {s:"SOBHA",n:"Sobha",sec:"Real Estate",idx:"NIFTYREALTY",p:1850},

  {s:"SUNTEK",n:"Sunteck Realty",sec:"Real Estate",idx:"NIFTYREALTY",p:580},

  {s:"KOLTEPATIL",n:"Kolte Patil Developers",sec:"Real Estate",idx:"NIFTYREALTY",p:480},

  // ── METALS & MINING ───────────────────────────────────────────

  {s:"NMDC",n:"NMDC",sec:"Mining",idx:"NIFTYMETAL",p:215},

  {s:"VEDL",n:"Vedanta",sec:"Metals",idx:"NIFTYMETAL",p:430},

  {s:"HINDCOPPER",n:"Hindustan Copper",sec:"Metals",idx:"NIFTYMETAL",p:315},

  {s:"NATIONALUM",n:"National Aluminium",sec:"Metals",idx:"NIFTYMETAL",p:200},

  {s:"SAIL",n:"SAIL",sec:"Metals",idx:"NIFTYMETAL",p:145},

  {s:"WELCORP",n:"Welspun Corp",sec:"Metals",idx:"NIFTYMETAL",p:680},

  {s:"RATNAMANI",n:"Ratnamani Metals",sec:"Metals",idx:"NIFTYMETAL",p:3600},

  {s:"APL",n:"APL Apollo Tubes",sec:"Metals",idx:"NIFTYMETAL",p:1680},

  {s:"GRAVITA",n:"Gravita India",sec:"Metals",idx:"NIFTYMETAL",p:2000},

  // ── CHEMICALS ─────────────────────────────────────────────────

  {s:"DEEPAKNTR",n:"Deepak Nitrite",sec:"Chemicals",idx:"NIFTYCHEMICALS",p:2600},

  {s:"AARTIIND",n:"Aarti Industries",sec:"Chemicals",idx:"NIFTYCHEMICALS",p:640},

  {s:"TATACHEM",n:"Tata Chemicals",sec:"Chemicals",idx:"NIFTYCHEMICALS",p:1080},

  {s:"GNFC",n:"GNFC",sec:"Chemicals",idx:"NIFTYCHEMICALS",p:680},

  {s:"VINYSCHEM",n:"Vinyl Chemicals",sec:"Chemicals",idx:"NIFTYCHEMICALS",p:725},

  {s:"IOLCP",n:"IOL Chemicals",sec:"Chemicals",idx:"NIFTYCHEMICALS",p:480},

  {s:"SUDARSCHEM",n:"Sudarshan Chemical",sec:"Chemicals",idx:"NIFTYCHEMICALS",p:1020},

  {s:"GALAXYSURF",n:"Galaxy Surfactants",sec:"Chemicals",idx:"NIFTYCHEMICALS",p:3100},

  {s:"NAVINFLUOR",n:"Navin Fluorine",sec:"Chemicals",idx:"NIFTYCHEMICALS",p:3350},

  {s:"FLUOROCHEM",n:"Gujarat Fluorochemicals",sec:"Chemicals",idx:"NIFTYCHEMICALS",p:4200},

  // ── FINANCE / NBFC ────────────────────────────────────────────

  {s:"BAJAJHFL",n:"Bajaj Housing Finance",sec:"Finance",idx:"NIFTYFINSERV",p:160},

  {s:"LICHSGFIN",n:"LIC Housing Finance",sec:"Finance",idx:"NIFTYFINSERV",p:720},

  {s:"PNBHOUSING",n:"PNB Housing Finance",sec:"Finance",idx:"NIFTYFINSERV",p:1000},

  {s:"MANAPPURAM",n:"Manappuram Finance",sec:"Finance",idx:"NIFTYFINSERV",p:215},

  {s:"SHRIRAMFIN",n:"Shriram Finance",sec:"Finance",idx:"NIFTYFINSERV",p:2850},

  {s:"M&MFIN",n:"Mahindra Finance",sec:"Finance",idx:"NIFTYFINSERV",p:305},

  {s:"SUNDARMFIN",n:"Sundaram Finance",sec:"Finance",idx:"NIFTYFINSERV",p:5000},

  {s:"SBICARD",n:"SBI Cards",sec:"Finance",idx:"NIFTYFINSERV",p:770},

  {s:"HDFCAMC",n:"HDFC AMC",sec:"Finance",idx:"NIFTYFINSERV",p:4200},

  {s:"NIPPONLIFE",n:"Nippon Life India AMC",sec:"Finance",idx:"NIFTYFINSERV",p:690},

  {s:"CAMS",n:"Computer Age Mgmt (CAMS)",sec:"Finance",idx:"NIFTYFINSERV",p:3800},

  {s:"CDSL",n:"CDSL",sec:"Finance",idx:"NIFTYFINSERV",p:1900},

  {s:"BSE",n:"BSE",sec:"Finance",idx:"NIFTYFINSERV",p:3800},

  {s:"MCX",n:"MCX India",sec:"Finance",idx:"NIFTYFINSERV",p:5800},

  {s:"ANGELONE",n:"Angel One",sec:"Finance",idx:"NIFTYFINSERV",p:3400},

  {s:"5PAISA",n:"5Paisa Capital",sec:"Finance",idx:"NIFTYFINSERV",p:580},

  // ── CONSUMER DISCRETIONARY ────────────────────────────────────

  {s:"DMART",n:"Avenue Supermarts (D-Mart)",sec:"Retail",idx:"NIFTYCONSMR",p:4800},

  {s:"VMART",n:"V-Mart Retail",sec:"Retail",idx:"NIFTYCONSMR",p:2000},

  {s:"SHOPERSTOP",n:"Shoppers Stop",sec:"Retail",idx:"NIFTYCONSMR",p:680},

  {s:"JUBLFOOD",n:"Jubilant Foodworks",sec:"QSR",idx:"NIFTYCONSMR",p:580},

  {s:"DEVYANI",n:"Devyani International",sec:"QSR",idx:"NIFTYCONSMR",p:165},

  {s:"SAPPHIRE",n:"Sapphire Foods",sec:"QSR",idx:"NIFTYCONSMR",p:320},

  {s:"WESTLIFE",n:"Westlife Foodworld",sec:"QSR",idx:"NIFTYCONSMR",p:740},

  {s:"INDHOTEL",n:"Indian Hotels",sec:"Hotels",idx:"NIFTYCONSMR",p:640},

  {s:"LEMONTREE",n:"Lemon Tree Hotels",sec:"Hotels",idx:"NIFTYCONSMR",p:145},

  {s:"EIH",n:"EIH (Oberoi Hotels)",sec:"Hotels",idx:"NIFTYCONSMR",p:490},

  {s:"CHALET",n:"Chalet Hotels",sec:"Hotels",idx:"NIFTYCONSMR",p:810},

  // ── TELECOM / MEDIA ───────────────────────────────────────────

  {s:"IDEA",n:"Vodafone Idea",sec:"Telecom",idx:"NIFTYMEDIA",p:14},

  {s:"TATACOMM",n:"Tata Communications",sec:"Telecom",idx:"NIFTYMEDIA",p:1900},

  {s:"HFCL",n:"HFCL",sec:"Telecom",idx:"NIFTYMEDIA",p:130},

  {s:"STLTECH",n:"Sterlite Technologies",sec:"Telecom",idx:"NIFTYMEDIA",p:155},

  {s:"SUNTV",n:"Sun TV Network",sec:"Media",idx:"NIFTYMEDIA",p:680},

  {s:"ZEEL",n:"Zee Entertainment",sec:"Media",idx:"NIFTYMEDIA",p:150},

  {s:"PVRINOX",n:"PVR INOX",sec:"Media",idx:"NIFTYMEDIA",p:1400},

  {s:"INOX",n:"INOX Leisure",sec:"Media",idx:"NIFTYMEDIA",p:460},

  // ── CAPITAL GOODS / DEFENCE ──────────────────────────────────

  {s:"ABB",n:"ABB India",sec:"Capital Goods",idx:"NIFTYCAPGOODS",p:7500},

  {s:"BHEL",n:"BHEL",sec:"Capital Goods",idx:"NIFTYCAPGOODS",p:290},

  {s:"BEL",n:"Bharat Electronics",sec:"Defence",idx:"NIFTYCAPGOODS",p:295},

  {s:"HAL",n:"Hindustan Aeronautics",sec:"Defence",idx:"NIFTYCAPGOODS",p:4300},

  {s:"COCHINSHIP",n:"Cochin Shipyard",sec:"Defence",idx:"NIFTYCAPGOODS",p:1650},

  {s:"MAZAGON",n:"Mazagon Dock",sec:"Defence",idx:"NIFTYCAPGOODS",p:4600},

  {s:"GRINDWELL",n:"Grindwell Norton",sec:"Capital Goods",idx:"NIFTYCAPGOODS",p:2500},

  {s:"THERMAX",n:"Thermax",sec:"Capital Goods",idx:"NIFTYCAPGOODS",p:4800},

  {s:"CUMMINSIND",n:"Cummins India",sec:"Capital Goods",idx:"NIFTYCAPGOODS",p:3500},

  {s:"KIRLOSBRNE",n:"Kirloskar Brothers",sec:"Capital Goods",idx:"NIFTYCAPGOODS",p:1850},

  // ── CEMENT & MATERIALS ────────────────────────────────────────

  {s:"AMBUJACEM",n:"Ambuja Cements",sec:"Materials",idx:"NIFTYMATERIAL",p:650},

  {s:"JKCEMENT",n:"JK Cement",sec:"Materials",idx:"NIFTYMATERIAL",p:4500},

  {s:"RAMCOCEM",n:"Ramco Cements",sec:"Materials",idx:"NIFTYMATERIAL",p:830},

  {s:"DALMIA",n:"Dalmia Bharat",sec:"Materials",idx:"NIFTYMATERIAL",p:1950},

  {s:"HEIDELBERG",n:"HeidelbergCement India",sec:"Materials",idx:"NIFTYMATERIAL",p:275},

  {s:"JKLAKSHMI",n:"JK Lakshmi Cement",sec:"Materials",idx:"NIFTYMATERIAL",p:820},

  {s:"PRISM",n:"Prism Johnson",sec:"Materials",idx:"NIFTYMATERIAL",p:195},

  // ── AGRI & FERTILIZERS ────────────────────────────────────────

  {s:"CHAMBAL",n:"Chambal Fertilisers",sec:"Agri",idx:"NIFTYAGRI",p:415},

  {s:"COROMANDEL",n:"Coromandel International",sec:"Agri",idx:"NIFTYAGRI",p:1250},

  {s:"RALLIS",n:"Rallis India",sec:"Agri",idx:"NIFTYAGRI",p:300},

  {s:"BAYERCROP",n:"Bayer CropScience",sec:"Agri",idx:"NIFTYAGRI",p:6800},

  {s:"SUMICHEM",n:"Sumitomo Chemical",sec:"Agri",idx:"NIFTYAGRI",p:440},

  {s:"GHCL",n:"GHCL",sec:"Chemicals",idx:"NIFTYAGRI",p:820},

  // ── SME & MID-CAP OTHERS ─────────────────────────────────────

  {s:"VAIBHAVGBL",n:"Vaibhav Global",sec:"Consumer",idx:"MIDCAP",p:380},

  {s:"RATEGAIN",n:"RateGain Travel Tech",sec:"Technology",idx:"MIDCAP",p:680},

  {s:"CARTRADE",n:"CarTrade Tech",sec:"Technology",idx:"MIDCAP",p:950},

  {s:"EASEMYTRIP",n:"Easy Trip Planners",sec:"Tourism",idx:"MIDCAP",p:52},

  {s:"IXIGO",n:"Le Travenues Tech (ixigo)",sec:"Tourism",idx:"MIDCAP",p:165},

  {s:"YATHARTH",n:"Yatharth Hospital",sec:"Healthcare",idx:"MIDCAP",p:530},

  {s:"SAGILITY",n:"Sagility India",sec:"Technology",idx:"MIDCAP",p:43},

  {s:"SWIGGY",n:"Bundl Technologies (Swiggy)",sec:"Consumer Tech",idx:"MIDCAP",p:410},

  {s:"DOMS",n:"DOMS Industries",sec:"Consumer",idx:"MIDCAP",p:2900},

  {s:"MANYAVAR",n:"Vedant Fashions (Manyavar)",sec:"Retail",idx:"MIDCAP",p:1250},

  {s:"CAMPUS",n:"Campus Activewear",sec:"Retail",idx:"MIDCAP",p:215},

  {s:"LATENTVIEW",n:"LatentView Analytics",sec:"Technology",idx:"MIDCAP",p:580},

  {s:"NETWEB",n:"Netweb Technologies",sec:"Technology",idx:"MIDCAP",p:2400},

  {s:"KAYNES",n:"Kaynes Technology",sec:"Technology",idx:"MIDCAP",p:4800},

  {s:"AVALON",n:"Avalon Technologies",sec:"Technology",idx:"MIDCAP",p:675},

  {s:"SYRMA",n:"Syrma SGS Technology",sec:"Technology",idx:"MIDCAP",p:490},

  {s:"IDEAFORGE",n:"ideaForge Technology",sec:"Defence",idx:"MIDCAP",p:485},

  {s:"INOX-WIND",n:"Inox Wind",sec:"Energy",idx:"MIDCAP",p:220},

  {s:"SUZLON",n:"Suzlon Energy",sec:"Energy",idx:"MIDCAP",p:58},

  {s:"WEBSOL",n:"Websol Energy System",sec:"Energy",idx:"MIDCAP",p:1350},

];



const SECTORS = [...new Set(NSE_ALL_STOCKS.map(s => s.sec))].sort();

const INDICES = [...new Set(NSE_ALL_STOCKS.map(s => s.idx))];



// ═══════════════════════════════════════════════════════════════════

// PRICE SIMULATION ENGINE (realistic GBM-based)

// ═══════════════════════════════════════════════════════════════════

function seededRand(seed) {

  let s = seed;

  return () => {

    s = (s * 1664525 + 1013904223) & 0xFFFFFFFF;

    return (s >>> 0) / 0xFFFFFFFF;

  };

}



function simulateHistory(symbol, basePrice, days = 180) {

  const seed = symbol.split("").reduce((a, c) => a + c.charCodeAt(0), 0);

  const rng = seededRand(seed);

  const prices = [];

  let price = basePrice;

  const trend = (rng() - 0.48) * 0.0004;

  const vol = 0.015 + rng() * 0.01;

  const end = new Date();

  

  for (let i = days; i >= 0; i--) {

    const date = new Date(end);

    date.setDate(date.getDate() - i);

    if (date.getDay() === 0 || date.getDay() === 6) continue;

    const change = (rng() - 0.5) * 2 * vol + trend;

    price = Math.max(price * (1 + change), basePrice * 0.5);

    const high = price * (1 + rng() * 0.008);

    const low = price * (1 - rng() * 0.008);

    const vol_data = Math.floor(basePrice * 1500 + rng() * basePrice * 2000);

    prices.push({

      date: date.toISOString().slice(0, 10),

      close: Math.round(price * 100) / 100,

      open: Math.round(price * (1 + (rng() - 0.5) * 0.004) * 100) / 100,

      high: Math.round(high * 100) / 100,

      low: Math.round(low * 100) / 100,

      volume: vol_data,

    });

  }

  return prices;

}



function computeIndicators(candles) {
  if (candles.length < 20) return {};
  const closes = candles.map(c => c.close);
  
  // EMA
  const ema = (period, data = closes) => {
    const k = 2 / (period + 1);
    let ema = data[0];
    return data.map(p => (ema = p * k + ema * (1 - k)));
  };
  
  // RSI
  const deltas = closes.slice(1).map((c, i) => c - closes[i]);
  const gains = deltas.map(d => Math.max(d, 0));
  const losses = deltas.map(d => Math.max(-d, 0));
  const avgGain = gains.slice(-14).reduce((a, b) => a + b, 0) / 14;
  const avgLoss = losses.slice(-14).reduce((a, b) => a + b, 0) / 14;
  const rs = avgGain / (avgLoss || 0.001);
  const rsi = 100 - 100 / (1 + rs);
  // MACD

  const ema12 = ema(12);

  const ema26 = ema(26);

  const macdLine = ema12.map((v, i) => v - ema26[i]);

  const signalLine = ema(9, macdLine.slice(-20));

  const macdHist = macdLine[macdLine.length - 1] - signalLine[signalLine.length - 1];

  

  // BB

  const period = 20;

  const slice = closes.slice(-period);

  const mean = slice.reduce((a, b) => a + b, 0) / period;

  const std = Math.sqrt(slice.map(v => (v - mean) ** 2).reduce((a, b) => a + b, 0) / period);

  const bbUpper = mean + 2 * std;

  const bbLower = mean - 2 * std;

  

  // Volume ratio

  const vols = candles.map(c => c.volume);

  const avgVol = vols.slice(-20).reduce((a, b) => a + b, 0) / 20;

  const volRatio = vols[vols.length - 1] / avgVol;

  

  // Trend

  const ema9 = ema(9);

  const ema21 = ema(21);

  const ema50 = ema(50);

  const last = closes[closes.length - 1];

  

  return {

    rsi: Math.round(rsi * 10) / 10,

    macd: Math.round(macdHist * 100) / 100,

    macdBull: macdHist > 0,

    bbUpper: Math.round(bbUpper * 100) / 100,

    bbLower: Math.round(bbLower * 100) / 100,

    bbMid: Math.round(mean * 100) / 100,

    bbPct: Math.round(((last - bbLower) / (bbUpper - bbLower)) * 100),

    volRatio: Math.round(volRatio * 100) / 100,

    ema9: Math.round(ema9[ema9.length - 1] * 100) / 100,

    ema21: Math.round(ema21[ema21.length - 1] * 100) / 100,

    ema50: Math.round(ema50[ema50.length - 1] * 100) / 100,

    emaBull: ema9[ema9.length - 1] > ema21[ema21.length - 1],

    trendUp: last > ema50[ema50.length - 1],

    changePct: Math.round(((last - closes[closes.length - 2]) / closes[closes.length - 2]) * 10000) / 100,

    changeAmt: Math.round((last - closes[closes.length - 2]) * 100) / 100,

    high52w: Math.round(Math.max(...closes.slice(-252)) * 100) / 100,

    low52w: Math.round(Math.min(...closes.slice(-252)) * 100) / 100,

  };

}



function computeBuyScore(ind) {
  let score = 0;
  const reasons = [];
  if (ind.trendUp) { score += 20; reasons.push("Price above EMA50 (uptrend)"); }
  else reasons.push("Price below EMA50");
  
  if (ind.emaBull) { score += 20; reasons.push("EMA9 > EMA21 (short-term bullish)"); }
  else reasons.push("EMA9 < EMA21");
  
  if (ind.rsi > 40 && ind.rsi < 60) { score += 20; reasons.push("RSI Neutral/Rising"); }
  else if (ind.rsi <= 30) { score += 40; reasons.push("Oversold Bounce (Strong Buy)"); }
  else { score -= 10; reasons.push("RSI Overbought or Weak"); }
  
  if (ind.macdBull) { score += 20; reasons.push("MACD Bullish Crossover"); }
  else reasons.push("MACD Bearish");
  
  if (ind.bbPct < 20) { score += 20; reasons.push("Near Lower Bollinger Band"); }
  
  return { score: Math.min(100, Math.max(0, score)), reasons };
}

// UI COMPONENTS

// ════════════════════════════════════════════════════════════════════════════════════════════

// STORAGE HELPERS

// ═══════════════════════════════════════════════════════════════════

async function loadBookmarks() {

  try {

    const r = await window.storage.get("nse:bookmarks");

    return r ? JSON.parse(r.value) : ["RELIANCE", "TCS", "HDFCBANK", "INFY"];

  } catch { return ["RELIANCE", "TCS", "HDFCBANK", "INFY"]; }

}



async function saveBookmarks(list) {

  try { await window.storage.set("nse:bookmarks", JSON.stringify(list)); } catch {}

}



// ═══════════════════════════════════════════════════════════════════

// GROQ AI PREDICTION

// ═══════════════════════════════════════════════════════════════════

async function getAIPrediction(stock, candles, indicators) {

  const recent = candles.slice(-30).map(c => `${c.date}: ₹${c.close}`).join(", ");

  const prompt = `You are an expert market analyst with deep knowledge of global assets.



Stock: ${stock.s} — ${stock.n} (${stock.sec} sector)

Current Price: ₹${candles[candles.length-1]?.close}

52W High: ₹${indicators.high52w} | 52W Low: ₹${indicators.low52w}



Technical Indicators:

- RSI(14): ${indicators.rsi}

- MACD: ${indicators.macd} (${indicators.macdBull ? "bullish" : "bearish"})

- EMA9: ₹${indicators.ema9} | EMA21: ₹${indicators.ema21} | EMA50: ₹${indicators.ema50}

- Bollinger Bands: Upper ₹${indicators.bbUpper} | Mid ₹${indicators.bbMid} | Lower ₹${indicators.bbLower} | Position: ${indicators.bbPct}%

- Volume Ratio: ${indicators.volRatio}× average

- Trend: ${indicators.trendUp ? "BULLISH (above EMA50)" : "BEARISH (below EMA50)"}

- EMA Cross: ${indicators.emaBull ? "BULLISH" : "BEARISH"}



Recent 30-day prices: ${recent}



Provide a detailed trading analysis in this EXACT JSON format (respond with JSON only, no markdown):

{

  "bias": "BULLISH" or "BEARISH" or "NEUTRAL",

  "confidence": number 0-100,

  "entry_zone": "price range for entry e.g. ₹2900-₹2950",

  "target_1w": number (1-week price target),

  "target_1m": number (1-month price target),

  "stop_loss": number (stop loss price),

  "support": number (key support level),

  "resistance": number (key resistance level),

  "risk_reward": "e.g. 1:3.2",

  "strategy": "2-3 sentence trading strategy",

  "key_risks": ["risk1", "risk2", "risk3"],

  "catalysts": ["catalyst1", "catalyst2"],

  "summary": "3-4 sentence professional market analysis"

}`;



  try {
    const res = await fetch(`${BACKEND}/api/ml/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        stock: stock.s,
        candles: candles,
        indicators: indicators,
      }),
    });
    const data = await res.json();
    return data;
  } catch (e) {
    console.error("AI prediction failed:", e);
    return null;
  }
}



// ═══════════════════════════════════════════════════════════════════

// UI COMPONENTS

// ═══════════════════════════════════════════════════════════════════



const fmt = (n, dec = 2) => {

  if (n == null) return "—";

  const abs = Math.abs(n);

  if (abs >= 1e7) return `₹${(n / 1e7).toFixed(2)}Cr`;

  if (abs >= 1e5) return `₹${(n / 1e5).toFixed(2)}L`;

  return `₹${n.toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec })}`;

};



const fmtNum = n => n?.toLocaleString("en-IN") ?? "—";

const clr = v => v >= 0 ? "#10B981" : "#EF4444";

const clrCls = v => v >= 0 ? "text-green" : "text-red";



function PriceChange({ value, pct, small }) {

  const g = value >= 0;

  const Icon = g ? ArrowUpRight : ArrowDownRight;

  return (

    <span style={{ color: clr(value), fontSize: small ? 11 : 13, fontFamily: "var(--font-mono)", display: "inline-flex", alignItems: "center", gap: 2 }}>

      <Icon size={small ? 10 : 12} />

      {value >= 0 ? "+" : ""}{fmt(value, 2)} ({pct >= 0 ? "+" : ""}{pct?.toFixed(2)}%)

    </span>

  );

}



function RSIGauge({ rsi }) {

  const pct = ((rsi || 50) / 100) * 100;

  const color = rsi < 30 ? "#06B6D4" : rsi > 70 ? "#EF4444" : rsi > 60 ? "#F59E0B" : "#10B981";

  const label = rsi < 30 ? "OVERSOLD" : rsi > 70 ? "OVERBOUGHT" : rsi > 60 ? "ELEVATED" : rsi > 40 ? "NEUTRAL" : "WEAK";

  return (

    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>

      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#64748B" }}>

        <span>RSI(14)</span><span style={{ color, fontFamily: "var(--font-mono)" }}>{rsi} · {label}</span>

      </div>

      <div style={{ height: 4, background: "#1E2030", borderRadius: 2, overflow: "hidden" }}>

        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 2, transition: "width 0.5s ease" }} />

      </div>

      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "#334155" }}>

        <span>0 (Oversold)</span><span>30</span><span>70</span><span>100 (Overbought)</span>

      </div>

    </div>

  );

}



function BiasTag({ bias, confidence }) {

  const map = {

    BULLISH: { bg: "#052e16", border: "#10B981", text: "#10B981", icon: TrendingUp },

    BEARISH: { bg: "#450a0a", border: "#EF4444", text: "#EF4444", icon: TrendingDown },

    NEUTRAL: { bg: "#1C1917", border: "#F59E0B", text: "#F59E0B", icon: Activity },

  };

  const c = map[bias] || map.NEUTRAL;

  const Icon = c.icon;

  return (

    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 10px", background: c.bg, border: `1px solid ${c.border}`, borderRadius: 4 }}>

      <Icon size={12} color={c.text} />

      <span style={{ color: c.text, fontSize: 12, fontWeight: 700, letterSpacing: 1 }}>{bias}</span>

      {confidence != null && <span style={{ color: c.text, fontSize: 10, opacity: 0.8 }}>{confidence}%</span>}

    </div>

  );

}



function ScoreMeter({ score }) {

  const bars = 10;

  const filled = Math.round((score / 100) * bars);

  const color = score >= 60 ? "#10B981" : score >= 40 ? "#F59E0B" : "#EF4444";

  return (

    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>

      <div style={{ display: "flex", gap: 2 }}>

        {Array.from({ length: bars }).map((_, i) => (

          <div key={i} style={{ width: 6, height: 14, borderRadius: 2, background: i < filled ? color : "#1E2030" }} />

        ))}

      </div>

      <span style={{ color, fontSize: 12, fontFamily: "var(--font-mono)", fontWeight: 700 }}>{score}/100</span>

    </div>

  );

}



function CustomTooltip({ active, payload, label }) {

  if (!active || !payload?.length) return null;

  const d = payload[0]?.payload;

  return (

    <div style={{ background: "#0F1117", border: "1px solid #1E2030", borderRadius: 6, padding: "8px 12px", fontSize: 11 }}>

      <div style={{ color: "#64748B", marginBottom: 4 }}>{label}</div>

      <div style={{ color: "#E2E8F0", fontFamily: "var(--font-mono)" }}>₹{payload[0]?.value?.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>

    </div>

  );

}



function StockRow({ stock, price, change, changePct, isBookmarked, isSelected, onSelect, onToggleBookmark }) {

  const g = change >= 0;

  return (

    <div

      onClick={() => onSelect(stock)}

      style={{

        display: "flex", alignItems: "center", padding: "8px 12px", cursor: "pointer",

        background: isSelected ? "#0F1821" : "transparent",

        borderLeft: isSelected ? "2px solid #F59E0B" : "2px solid transparent",

        transition: "all 0.15s ease",

      }}

      onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = "#0A0F14"; }}

      onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = "transparent"; }}

    >

      <div style={{ flex: 1, minWidth: 0 }}>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>

          <span style={{ color: "#E2E8F0", fontSize: 13, fontWeight: 600 }}>{stock.s}</span>

          {isBookmarked && <BookmarkCheck size={10} color="#F59E0B" />}

        </div>

        <div style={{ color: "#475569", fontSize: 10, marginTop: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{stock.n}</div>

      </div>

      <div style={{ textAlign: "right" }}>

        <div style={{ color: "#E2E8F0", fontSize: 13, fontFamily: "var(--font-mono)", fontWeight: 600 }}>

          ₹{(price || stock.p).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}

        </div>

        <div style={{ color: clr(change || 0), fontSize: 10, fontFamily: "var(--font-mono)" }}>

          {(change || 0) >= 0 ? "+" : ""}{(changePct || 0).toFixed(2)}%

        </div>

      </div>

      <button

        onClick={e => { e.stopPropagation(); onToggleBookmark(stock.s); }}

        style={{ marginLeft: 8, background: "none", border: "none", cursor: "pointer", padding: 2, color: isBookmarked ? "#F59E0B" : "#334155" }}

      >

        {isBookmarked ? <Bookmark size={13} fill="#F59E0B" /> : <Bookmark size={13} />}

      </button>

    </div>

  );

}



function PredictionPanel({ stock, prediction, loading, onPredict }) {

  if (loading) return (

    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 40, gap: 12 }}>

      <div style={{ width: 36, height: 36, border: "2px solid #F59E0B", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />

      <span style={{ color: "#64748B", fontSize: 13 }}>Analysing {stock.s} with AI…</span>

    </div>

  );



  if (!prediction) return (

    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 40, gap: 16, textAlign: "center" }}>

      <Cpu size={28} color="#334155" />

      <div>

        <div style={{ color: "#94A3B8", fontSize: 14, marginBottom: 6 }}>AI Prediction Engine</div>

        <div style={{ color: "#475569", fontSize: 12, lineHeight: 1.6, maxWidth: 280 }}>

          Get AI-powered price targets, support/resistance levels, and risk analysis

        </div>

      </div>

      <button onClick={onPredict} style={{

        display: "flex", alignItems: "center", gap: 8, padding: "10px 20px",

        background: "linear-gradient(135deg, #1a1a2e, #0d1117)",

        border: "1px solid #F59E0B", borderRadius: 6, cursor: "pointer", color: "#F59E0B", fontSize: 13, fontWeight: 600

      }}>

        <Zap size={14} /> Generate Prediction

      </button>

    </div>

  );



  return (

    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>

          <Cpu size={14} color="#F59E0B" />

          <span style={{ color: "#94A3B8", fontSize: 12 }}>AI Analysis · {stock.s}</span>

        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>

          <BiasTag bias={prediction.bias} confidence={prediction.confidence} />

          <button onClick={onPredict} style={{ background: "none", border: "none", cursor: "pointer", color: "#334155" }}>

            <RefreshCw size={12} />

          </button>

        </div>

      </div>



      <div style={{ background: "#080C10", border: "1px solid #1E2030", borderRadius: 6, padding: 12, fontSize: 12, color: "#94A3B8", lineHeight: 1.7 }}>

        {prediction.summary}

      </div>



      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>

        {[

          { label: "1-Week Target", value: fmt(prediction.target_1w), color: "#10B981" },

          { label: "1-Month Target", value: fmt(prediction.target_1m), color: "#10B981" },

          { label: "Stop Loss", value: fmt(prediction.stop_loss), color: "#EF4444" },

          { label: "Risk/Reward", value: prediction.risk_reward, color: "#F59E0B" },

          { label: "Support", value: fmt(prediction.support), color: "#06B6D4" },

          { label: "Resistance", value: fmt(prediction.resistance), color: "#A78BFA" },

        ].map(item => (

          <div key={item.label} style={{ background: "#0A0F14", border: "1px solid #1E2030", borderRadius: 6, padding: "8px 10px" }}>

            <div style={{ color: "#475569", fontSize: 10, marginBottom: 3 }}>{item.label}</div>

            <div style={{ color: item.color, fontSize: 13, fontFamily: "var(--font-mono)", fontWeight: 700 }}>{item.value}</div>

          </div>

        ))}

      </div>



      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>

        <div style={{ color: "#475569", fontSize: 10, letterSpacing: 0.5 }}>ENTRY ZONE</div>

        <div style={{ color: "#F59E0B", fontSize: 13, fontFamily: "var(--font-mono)" }}>{prediction.entry_zone}</div>

      </div>



      {prediction.key_risks?.length > 0 && (

        <div>

          <div style={{ color: "#475569", fontSize: 10, letterSpacing: 0.5, marginBottom: 6 }}>KEY RISKS</div>

          {prediction.key_risks.map((r, i) => (

            <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 6, color: "#94A3B8", fontSize: 11, marginBottom: 4 }}>

              <AlertTriangle size={10} color="#EF4444" style={{ marginTop: 2, flexShrink: 0 }} />

              {r}

            </div>

          ))}

        </div>

      )}



      {prediction.catalysts?.length > 0 && (

        <div>

          <div style={{ color: "#475569", fontSize: 10, letterSpacing: 0.5, marginBottom: 6 }}>CATALYSTS</div>

          {prediction.catalysts.map((c, i) => (

            <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 6, color: "#94A3B8", fontSize: 11, marginBottom: 4 }}>

              <CheckCircle size={10} color="#10B981" style={{ marginTop: 2, flexShrink: 0 }} />

              {c}

            </div>

          ))}

        </div>

      )}



      <div style={{ padding: "8px 12px", background: "#050810", border: "1px solid #1E2030", borderRadius: 6, fontSize: 11, color: "#94A3B8", lineHeight: 1.6 }}>

        <strong style={{ color: "#F59E0B" }}>Strategy:</strong> {prediction.strategy}

      </div>



      <div style={{ fontSize: 10, color: "#334155", textAlign: "center" }}>

        ⚠ AI predictions are for informational purposes only. Always do your own research.

      </div>

    </div>

  );

}



// ═══════════════════════════════════════════════════════════════════

// MAIN APP

// ═══════════════════════════════════════════════════════════════════

export default function NSETradingTerminal() {

  const [bookmarks, setBookmarks] = useState([]);

  const [selectedStock, setSelectedStock] = useState(null);

  const [stockData, setStockData] = useState({}); // symbol -> {candles, indicators}

  const [prices, setPrices] = useState({}); // symbol -> {price, change, changePct}

  const [signals, setSignals] = useState([]);

  const [prediction, setPrediction] = useState(null);

  const [loadingPrediction, setLoadingPrediction] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");

  const [sectorFilter, setSectorFilter] = useState("ALL");

  const [indexFilter, setIndexFilter] = useState("ALL");

  const [activeTab, setActiveTab] = useState("chart");

  const [backendStatus, setBackendStatus] = useState("checking");

  const [lastRefresh, setLastRefresh] = useState(null);

  const [sidebarTab, setSidebarTab] = useState("bookmarks");

  const [showSearch, setShowSearch] = useState(false);

  const [showSettings, setShowSettings] = useState(false);

  const [credentials, setCredentials] = useState({

    ZERODHA_API_KEY: "", ZERODHA_API_SECRET: "", ZERODHA_ACCESS_TOKEN: "",

    TELEGRAM_BOT_TOKEN: "", TELEGRAM_CHAT_ID: "", 

  });

  const [credsStatus, setCredsStatus] = useState({});

  const searchRef = useRef(null);



  // Load bookmarks on mount

  useEffect(() => {

    loadBookmarks().then(bm => {

      setBookmarks(bm);

      setSelectedStock(NSE_ALL_STOCKS.find(s => s.s === bm[0]) || NSE_ALL_STOCKS[0]);

    });

    checkBackend();

    fetchSignals();

    fetchCredentials();

  }, []);



  useEffect(() => {

    if (showSearch && searchRef.current) searchRef.current.focus();

  }, [showSearch]);



  const checkBackend = async () => {

    const r = await tryFetch(`${BACKEND}/api/watchlist`);

    setBackendStatus(r ? "connected" : "offline");

  };



  const fetchSignals = async () => {

    const r = await tryFetch(`${BACKEND}/api/signals/pending`);

    if (r) setSignals(r);

  };



  const fetchCredentials = async () => {

    const r = await tryFetch(`${BACKEND}/api/credentials`);

    if (r) setCredsStatus(r);

  };



  const handleSaveCredentials = async () => {
    await fetch(`${BACKEND}/api/credentials`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY 
      },
      body: JSON.stringify(credentials)
    });

    await fetchCredentials();

    setShowSettings(false);

  };



  const toggleBookmark = useCallback(async (symbol) => {

    setBookmarks(prev => {

      const next = prev.includes(symbol) ? prev.filter(s => s !== symbol) : [...prev, symbol];

      saveBookmarks(next);

      return next;

    });

  }, []);



  const abortControllerRef = useRef(null);

  const loadStockData = useCallback(async (stock) => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

    if (stockData[stock.s]) return;
    let candles;
    const [backendData, newsData] = await Promise.all([
      tryFetch(`${BACKEND}/api/stock/${stock.s}/history`, { signal }),
      tryFetch(`${BACKEND}/api/stock/${stock.s}/news`, { signal }),
    ]);
    if (signal.aborted) return;
    if (backendData?.candles) {
      candles = backendData.candles.map(c => ({ ...c, close: c.close }));
    } else {
      candles = simulateHistory(stock.s, stock.p);
    }
    const indicators = computeIndicators(candles);
    const news = newsData || [];
    const last = candles[candles.length - 1];
    const prev = candles[candles.length - 2];
    const change = last.close - prev.close;
    const changePct = (change / prev.close) * 100;
    setStockData(prev2 => ({ ...prev2, [stock.s]: { candles, indicators, news } }));
    setPrices(prev2 => ({ ...prev2, [stock.s]: { price: last.close, change, changePct } }));
  }, [stockData]);



  const selectStock = useCallback(async (stock) => {

    setSelectedStock(stock);

    setPrediction(null);

    setActiveTab("chart");

    await loadStockData(stock);

  }, [loadStockData]);



  useEffect(() => {

    if (selectedStock) loadStockData(selectedStock);

  }, [selectedStock]);



  // Pre-load bookmark prices

  useEffect(() => {

    bookmarks.forEach(sym => {

      const s = NSE_ALL_STOCKS.find(x => x.s === sym);

      if (s && !stockData[sym]) loadStockData(s);

    });

  }, [bookmarks]);



  const handlePredict = async () => {

    if (!selectedStock) return;

    const data = stockData[selectedStock.s];

    if (!data) return;

    setLoadingPrediction(true);

    setPrediction(null);

    const result = await getAIPrediction(selectedStock, data.candles, data.indicators);

    setPrediction(result);

    setLoadingPrediction(false);

  };



  const handleRefresh = async () => {

    setStockData({});

    setPrices({});

    if (selectedStock) {

      const newData = simulateHistory(selectedStock.s, selectedStock.p);

      const indicators = computeIndicators(newData);

      const last = newData[newData.length - 1];

      const prev = newData[newData.length - 2];

      const change = last.close - prev.close;

      const changePct = (change / prev.close) * 100;

      setStockData({ [selectedStock.s]: { candles: newData, indicators } });

      setPrices({ [selectedStock.s]: { price: last.close, change, changePct } });

    }

    setLastRefresh(new Date().toLocaleTimeString("en-IN"));

    await fetchSignals();

    await checkBackend();

  };



  const approveSignal = async (id) => {
    const r = await tryFetch(`${BACKEND}/api/signals/${id}/approve`, { 
      method: "POST",
      headers: { "X-API-KEY": API_KEY }
    });
    if (r?.success) fetchSignals();
  };

  const denySignal = async (id, ticker) => {
    await tryFetch(`${BACKEND}/api/signals/${id}/deny`, {
      method: "POST", 
      headers: { 
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY 
      },
      body: JSON.stringify({ note: "Denied from terminal" }),
    });
    fetchSignals();
  };



  // Filtered stock list

  const filteredStocks = useMemo(() => {

    let list = NSE_ALL_STOCKS;

    if (sectorFilter !== "ALL") list = list.filter(s => s.sec === sectorFilter);

    if (indexFilter !== "ALL") list = list.filter(s => s.idx === indexFilter);

    if (searchQuery) {

      const q = searchQuery.toLowerCase();

      list = list.filter(s => s.s.toLowerCase().includes(q) || s.n.toLowerCase().includes(q));

    }

    return list;

  }, [searchQuery, sectorFilter, indexFilter]);



  const bookmarkedStocks = useMemo(() =>

    bookmarks.map(sym => NSE_ALL_STOCKS.find(s => s.s === sym)).filter(Boolean),

    [bookmarks]

  );



  const curData = selectedStock ? stockData[selectedStock.s] : null;

  const curPrice = selectedStock ? prices[selectedStock.s] : null;

  const ind = curData?.indicators;

  const candles = curData?.candles || [];

  const { score: buyScore, reasons: buyReasons } = ind ? computeBuyScore(ind) : { score: 0, reasons: [] };



  const chartData = candles.slice(-60).map(c => ({ date: c.date.slice(5), price: c.close, volume: c.volume }));



  return (

    <div style={{

      background: "#060A0F", minHeight: "100vh", fontFamily: "var(--font-body)",

      color: "#E2E8F0", display: "flex", flexDirection: "column",

    }}>

      <style>{`

        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Sora:wght@300;400;500;600;700&display=swap');

        :root {

          --font-mono: 'JetBrains Mono', monospace;

          --font-body: 'Sora', sans-serif;

          --gold: #F59E0B;

          --green: #10B981;

          --red: #EF4444;

          --blue: #3B82F6;

        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        ::-webkit-scrollbar { width: 4px; height: 4px; }

        ::-webkit-scrollbar-track { background: #0A0F14; }

        ::-webkit-scrollbar-thumb { background: #1E2030; border-radius: 2px; }

        @keyframes spin { to { transform: rotate(360deg); } }

        @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.4 } }

        @keyframes slideIn { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }

        .animate-in { animation: slideIn 0.3s ease; }

        input { background: transparent; border: none; outline: none; color: #E2E8F0; }

        input::placeholder { color: #334155; }

        button { font-family: var(--font-body); }

      `}</style>



      {/* HEADER */}

      <header style={{

        height: 52, background: "#060A0F", borderBottom: "1px solid #111827",

        display: "flex", alignItems: "center", padding: "0 16px", gap: 16,

        position: "sticky", top: 0, zIndex: 100,

      }}>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>

          <div style={{ width: 24, height: 24, background: "#F59E0B", borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center" }}>

            <BarChart2 size={14} color="#000" />

          </div>

          <span style={{ color: "#E2E8F0", fontWeight: 700, fontSize: 15, letterSpacing: 0.5 }}>NSE Terminal</span>

          <span style={{ color: "#334155", fontSize: 11, fontFamily: "var(--font-mono)" }}>v2.0</span>

        </div>



        <div style={{ flex: 1, maxWidth: 420, position: "relative" }}>

          <div style={{

            display: "flex", alignItems: "center", gap: 8,

            background: "#0A0F14", border: "1px solid #1E2030", borderRadius: 6,

            padding: "6px 12px",

          }}>

            <Search size={13} color="#334155" />

            <input

              ref={searchRef}

              value={searchQuery}

              onChange={e => setSearchQuery(e.target.value)}

              onFocus={() => setSidebarTab("search")}

              placeholder={`Search ${NSE_ALL_STOCKS.length}+ NSE stocks…`}

              style={{ flex: 1, fontSize: 13 }}

            />

            {searchQuery && (

              <button onClick={() => setSearchQuery("")} style={{ background: "none", border: "none", cursor: "pointer", color: "#334155" }}>

                <X size={12} />

              </button>

            )}

          </div>

        </div>



        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>

          <button onClick={() => setShowSettings(true)} style={{ background: "none", border: "none", cursor: "pointer", color: "#94A3B8" }}>

            <Settings size={16} />

          </button>

          <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11 }}>

            <Circle size={6} fill={backendStatus === "connected" ? "#10B981" : "#F59E0B"} color="transparent" style={{ animation: "pulse 2s infinite" }} />

            <span style={{ color: backendStatus === "connected" ? "#10B981" : "#F59E0B" }}>

              {backendStatus === "connected" ? "LIVE" : "SIM"}

            </span>

          </div>

          {signals.length > 0 && (

            <div style={{ display: "flex", alignItems: "center", gap: 5, padding: "3px 8px", background: "#1a0f00", border: "1px solid #F59E0B", borderRadius: 4 }}>

              <Bell size={11} color="#F59E0B" />

              <span style={{ color: "#F59E0B", fontSize: 11, fontFamily: "var(--font-mono)" }}>{signals.length}</span>

            </div>

          )}

          <button onClick={handleRefresh} style={{ background: "none", border: "none", cursor: "pointer", color: "#334155", display: "flex", alignItems: "center", gap: 4 }}>

            <RefreshCw size={13} />

          </button>

          {lastRefresh && <span style={{ color: "#334155", fontSize: 10 }}>{lastRefresh}</span>}

        </div>

      </header>



      {/* MAIN LAYOUT */}

      <div style={{ display: "flex", flex: 1, overflow: "hidden", height: "calc(100vh - 52px)" }}>



        {/* SIDEBAR */}

        <div style={{ width: 280, background: "#060A0F", borderRight: "1px solid #111827", display: "flex", flexDirection: "column", overflow: "hidden" }}>

          {/* Sidebar tabs */}

          <div style={{ display: "flex", borderBottom: "1px solid #111827" }}>

            {[

              { id: "bookmarks", label: "Watchlist", icon: Bookmark },

              { id: "search", label: "All Stocks", icon: Search },

              { id: "signals", label: `Signals${signals.length > 0 ? ` (${signals.length})` : ""}`, icon: Zap },

            ].map(tab => {

              const Icon = tab.icon;

              return (

                <button

                  key={tab.id}

                  onClick={() => setSidebarTab(tab.id)}

                  style={{

                    flex: 1, padding: "10px 4px", background: "none",

                    border: "none", borderBottom: sidebarTab === tab.id ? "2px solid #F59E0B" : "2px solid transparent",

                    color: sidebarTab === tab.id ? "#F59E0B" : "#475569",

                    fontSize: 10, cursor: "pointer", fontWeight: 600, letterSpacing: 0.3,

                    display: "flex", flexDirection: "column", alignItems: "center", gap: 3,

                  }}

                >

                  <Icon size={12} />

                  {tab.label}

                </button>

              );

            })}

          </div>



          {/* Sidebar content */}

          <div style={{ flex: 1, overflowY: "auto" }}>

            {sidebarTab === "bookmarks" && (

              <>

                {bookmarkedStocks.length === 0 ? (

                  <div style={{ padding: 24, textAlign: "center", color: "#334155", fontSize: 12 }}>

                    <Bookmark size={24} style={{ margin: "0 auto 8px", display: "block" }} />

                    Bookmark stocks to track them here

                  </div>

                ) : bookmarkedStocks.map(stock => (

                  <StockRow

                    key={stock.s} stock={stock}

                    price={prices[stock.s]?.price}

                    change={prices[stock.s]?.change}

                    changePct={prices[stock.s]?.changePct}

                    isBookmarked={true}

                    isSelected={selectedStock?.s === stock.s}

                    onSelect={selectStock}

                    onToggleBookmark={toggleBookmark}

                  />

                ))}

              </>

            )}



            {sidebarTab === "search" && (

              <>

                {/* Sector filter */}

                <div style={{ padding: "8px 12px", borderBottom: "1px solid #111827", display: "flex", gap: 4, overflowX: "auto" }}>

                  {["ALL", ...SECTORS.slice(0, 8)].map(s => (

                    <button

                      key={s}

                      onClick={() => setSectorFilter(s)}

                      style={{

                        padding: "3px 8px", borderRadius: 3,

                        background: sectorFilter === s ? "#1a1200" : "transparent",

                        border: `1px solid ${sectorFilter === s ? "#F59E0B" : "#1E2030"}`,

                        color: sectorFilter === s ? "#F59E0B" : "#475569",

                        fontSize: 10, cursor: "pointer", whiteSpace: "nowrap",

                      }}

                    >{s}</button>

                  ))}

                </div>

                <div style={{ padding: "4px 0", color: "#334155", fontSize: 10, textAlign: "center", padding: 4 }}>

                  {filteredStocks.length} stocks

                </div>

                {filteredStocks.map(stock => (

                  <StockRow

                    key={stock.s} stock={stock}

                    price={prices[stock.s]?.price}

                    change={prices[stock.s]?.change}

                    changePct={prices[stock.s]?.changePct}

                    isBookmarked={bookmarks.includes(stock.s)}

                    isSelected={selectedStock?.s === stock.s}

                    onSelect={selectStock}

                    onToggleBookmark={toggleBookmark}

                  />

                ))}

              </>

            )}



            {sidebarTab === "signals" && (

              <div style={{ padding: 8 }}>

                {signals.length === 0 ? (

                  <div style={{ padding: 24, textAlign: "center", color: "#334155", fontSize: 12 }}>

                    <Radio size={24} style={{ margin: "0 auto 8px", display: "block" }} />

                    No pending signals. Run scanner.

                  </div>

                ) : signals.map(sig => (

                  <div key={sig.id} className="animate-in" style={{

                    margin: "6px 0", padding: 12, background: "#0A0F14",

                    border: `1px solid ${sig.direction === "BUY" ? "#052e16" : "#450a0a"}`,

                    borderRadius: 6,

                  }}>

                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>

                      <div>

                        <span style={{ color: sig.direction === "BUY" ? "#10B981" : "#EF4444", fontWeight: 700, fontSize: 14 }}>

                          {sig.direction === "BUY" ? "▲" : "▼"} {sig.ticker}

                        </span>

                        <div style={{ color: "#475569", fontSize: 10, marginTop: 2 }}>Signal #{sig.id}</div>

                      </div>

                      <div style={{ textAlign: "right" }}>

                        <div style={{ color: "#E2E8F0", fontSize: 13, fontFamily: "var(--font-mono)" }}>₹{sig.entry_price?.toLocaleString("en-IN", {minimumFractionDigits:2})}</div>

                        <div style={{ color: "#F59E0B", fontSize: 10 }}>{sig.confidence_score}/100</div>

                      </div>

                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4, fontSize: 10, color: "#475569", marginBottom: 8 }}>

                      <span>SL: <span style={{ color: "#EF4444", fontFamily: "var(--font-mono)" }}>₹{sig.stop_loss?.toLocaleString("en-IN")}</span></span>

                      <span>TP: <span style={{ color: "#10B981", fontFamily: "var(--font-mono)" }}>₹{sig.take_profit?.toLocaleString("en-IN")}</span></span>

                      <span>Qty: <span style={{ color: "#E2E8F0" }}>{sig.position_size}</span></span>

                      <span>Val: <span style={{ color: "#E2E8F0" }}>₹{(sig.position_value/1000).toFixed(0)}K</span></span>

                    </div>

                    <div style={{ display: "flex", gap: 6 }}>

                      <button onClick={() => approveSignal(sig.id)} style={{

                        flex: 1, padding: "6px 0", background: "#052e16", border: "1px solid #10B981",

                        borderRadius: 4, color: "#10B981", fontSize: 11, cursor: "pointer", fontWeight: 600,

                      }}>✓ APPROVE</button>

                      <button onClick={() => denySignal(sig.id)} style={{

                        flex: 1, padding: "6px 0", background: "#450a0a", border: "1px solid #EF4444",

                        borderRadius: 4, color: "#EF4444", fontSize: 11, cursor: "pointer", fontWeight: 600,

                      }}>✕ DENY</button>

                    </div>

                  </div>

                ))}

              </div>

            )}

          </div>



          {/* Sidebar footer */}

          <div style={{ padding: "8px 12px", borderTop: "1px solid #111827", fontSize: 10, color: "#334155", display: "flex", justifyContent: "space-between" }}>

            <span>{bookmarks.length} bookmarked</span>

            <span>{NSE_ALL_STOCKS.length}+ stocks</span>

          </div>

        </div>



        {/* MAIN CONTENT */}

        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

          {selectedStock ? (

            <>

              {/* Stock header */}

              <div style={{

                padding: "12px 20px", borderBottom: "1px solid #111827",

                background: "#060A0F", display: "flex", alignItems: "center", gap: 20,

              }}>

                <div>

                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>

                    <span style={{ color: "#E2E8F0", fontSize: 22, fontWeight: 700, letterSpacing: -0.5 }}>{selectedStock.s}</span>

                    <span style={{ padding: "2px 8px", background: "#0A0F14", border: "1px solid #1E2030", borderRadius: 4, color: "#64748B", fontSize: 10 }}>{selectedStock.sec}</span>

                    <span style={{ padding: "2px 8px", background: "#1a0f00", border: "1px solid #F59E0B33", borderRadius: 4, color: "#F59E0B", fontSize: 10 }}>{selectedStock.idx}</span>

                  </div>

                  <div style={{ color: "#475569", fontSize: 12, marginTop: 2 }}>{selectedStock.n}</div>

                </div>



                <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 24 }}>

                  {curPrice && (

                    <div style={{ textAlign: "right" }}>

                      <div style={{ color: "#E2E8F0", fontSize: 28, fontFamily: "var(--font-mono)", fontWeight: 700, lineHeight: 1 }}>

                        {fmt(curPrice.price)}

                      </div>

                      <PriceChange value={curPrice.change} pct={curPrice.changePct} />

                    </div>

                  )}



                  {ind && (

                    <div style={{ display: "flex", gap: 16 }}>

                      {[

                        { label: "52W HIGH", value: fmt(ind.high52w), color: "#10B981" },

                        { label: "52W LOW", value: fmt(ind.low52w), color: "#EF4444" },

                        { label: "BUY SCORE", value: null, score: buyScore },

                      ].map(item => (

                        <div key={item.label} style={{ textAlign: "center" }}>

                          <div style={{ color: "#475569", fontSize: 9, letterSpacing: 0.5, marginBottom: 3 }}>{item.label}</div>

                          {item.score != null

                            ? <ScoreMeter score={item.score} />

                            : <div style={{ color: item.color, fontSize: 13, fontFamily: "var(--font-mono)", fontWeight: 700 }}>{item.value}</div>

                          }

                        </div>

                      ))}

                    </div>

                  )}



                  <button

                    onClick={() => toggleBookmark(selectedStock.s)}

                    style={{ background: "none", border: "none", cursor: "pointer", color: bookmarks.includes(selectedStock.s) ? "#F59E0B" : "#334155" }}

                  >

                    {bookmarks.includes(selectedStock.s) ? <BookmarkCheck size={18} /> : <Bookmark size={18} />}

                  </button>

                </div>

              </div>



              {/* Content tabs */}

              <div style={{ display: "flex", borderBottom: "1px solid #111827", padding: "0 20px" }}>

                {[

                  { id: "chart", label: "Chart" },
                  { id: "technicals", label: "Technicals" },
                  { id: "prediction", label: "AI Prediction" },
                  { id: "news", label: "News & Factors" },
                ].map(tab => (

                  <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{

                    padding: "10px 16px", background: "none", border: "none",

                    borderBottom: activeTab === tab.id ? "2px solid #F59E0B" : "2px solid transparent",

                    color: activeTab === tab.id ? "#F59E0B" : "#475569",

                    fontSize: 13, cursor: "pointer", fontWeight: 500,

                  }}>{tab.label}</button>

                ))}

              </div>



              {/* Tab content */}

              <div style={{ flex: 1, overflow: "auto" }}>

                {activeTab === "chart" && (

                  <div style={{ padding: 20 }} className="animate-in">

                    {chartData.length > 0 ? (

                      <>

                        {/* Main price chart */}

                        <div style={{ marginBottom: 20 }}>

                          <div style={{ color: "#475569", fontSize: 11, marginBottom: 12, letterSpacing: 0.5 }}>PRICE · 60 DAYS</div>

                          <ResponsiveContainer width="100%" height={280}>

                            <AreaChart data={chartData} margin={{ top: 5, right: 0, bottom: 0, left: 0 }}>

                              <defs>

                                <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">

                                  <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.15} />

                                  <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />

                                </linearGradient>

                              </defs>

                              <CartesianGrid strokeDasharray="3 3" stroke="#111827" vertical={false} />

                              <XAxis dataKey="date" tick={{ fill: "#334155", fontSize: 10 }} tickLine={false} axisLine={false} interval={9} />

                              <YAxis tick={{ fill: "#334155", fontSize: 10, fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false}

                                tickFormatter={v => `₹${v >= 1000 ? (v / 1000).toFixed(0) + "K" : v.toFixed(0)}`}

                                width={55} domain={["auto", "auto"]} />

                              <Tooltip content={<CustomTooltip />} />

                              {ind && <ReferenceLine y={ind.ema50} stroke="#3B82F6" strokeDasharray="4 4" strokeWidth={1} label={{ value: "EMA50", fill: "#3B82F6", fontSize: 9, position: "right" }} />}

                              {ind && <ReferenceLine y={ind.bbUpper} stroke="#8B5CF6" strokeDasharray="2 4" strokeWidth={1} />}

                              {ind && <ReferenceLine y={ind.bbLower} stroke="#8B5CF6" strokeDasharray="2 4" strokeWidth={1} label={{ value: "BB", fill: "#8B5CF6", fontSize: 9, position: "right" }} />}

                              <Area type="monotone" dataKey="price" stroke="#F59E0B" strokeWidth={1.5} fill="url(#priceGrad)" dot={false} />

                            </AreaChart>

                          </ResponsiveContainer>

                        </div>



                        {/* Volume chart */}

                        <div>

                          <div style={{ color: "#475569", fontSize: 11, marginBottom: 12, letterSpacing: 0.5 }}>VOLUME</div>

                          <ResponsiveContainer width="100%" height={70}>

                            <BarChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>

                              <XAxis hide />

                              <YAxis hide />

                              <Bar dataKey="volume" fill="#1E2030" radius={[1, 1, 0, 0]} />

                            </BarChart>

                          </ResponsiveContainer>

                        </div>

                      </>

                    ) : (

                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, color: "#334155" }}>

                        <RefreshCw size={20} style={{ animation: "spin 1s linear infinite" }} />

                      </div>

                    )}

                  </div>

                )}



                {activeTab === "technicals" && ind && (

                  <div style={{ padding: 20 }} className="animate-in">

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>

                      {/* RSI */}

                      <div style={{ padding: 16, background: "#080C10", border: "1px solid #111827", borderRadius: 8 }}>

                        <RSIGauge rsi={ind.rsi} />

                      </div>



                      {/* MACD */}

                      <div style={{ padding: 16, background: "#080C10", border: "1px solid #111827", borderRadius: 8 }}>

                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#64748B", marginBottom: 8 }}>

                          <span>MACD(12,26,9)</span>

                          <span style={{ color: ind.macdBull ? "#10B981" : "#EF4444", fontFamily: "var(--font-mono)" }}>

                            {ind.macd > 0 ? "+" : ""}{ind.macd}

                          </span>

                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>

                          {ind.macdBull

                            ? <TrendingUp size={16} color="#10B981" />

                            : <TrendingDown size={16} color="#EF4444" />

                          }

                          <span style={{ color: ind.macdBull ? "#10B981" : "#EF4444", fontSize: 12, fontWeight: 600 }}>

                            {ind.macdBull ? "BULLISH MOMENTUM" : "BEARISH MOMENTUM"}

                          </span>

                        </div>

                      </div>



                      {/* Bollinger Bands */}

                      <div style={{ padding: 16, background: "#080C10", border: "1px solid #111827", borderRadius: 8 }}>

                        <div style={{ fontSize: 10, color: "#64748B", marginBottom: 8 }}>BOLLINGER BANDS (20,2)</div>

                        <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11 }}>

                          <div style={{ display: "flex", justifyContent: "space-between" }}>

                            <span style={{ color: "#8B5CF6" }}>Upper</span>

                            <span style={{ color: "#8B5CF6", fontFamily: "var(--font-mono)" }}>{fmt(ind.bbUpper)}</span>

                          </div>

                          <div style={{ display: "flex", justifyContent: "space-between" }}>

                            <span style={{ color: "#64748B" }}>Mid</span>

                            <span style={{ color: "#64748B", fontFamily: "var(--font-mono)" }}>{fmt(ind.bbMid)}</span>

                          </div>

                          <div style={{ display: "flex", justifyContent: "space-between" }}>

                            <span style={{ color: "#06B6D4" }}>Lower</span>

                            <span style={{ color: "#06B6D4", fontFamily: "var(--font-mono)" }}>{fmt(ind.bbLower)}</span>

                          </div>

                          <div style={{ height: 1, background: "#1E2030", margin: "4px 0" }} />

                          <div style={{ display: "flex", justifyContent: "space-between" }}>

                            <span style={{ color: "#64748B" }}>Position</span>

                            <span style={{ color: ind.bbPct < 25 ? "#06B6D4" : ind.bbPct > 75 ? "#EF4444" : "#F59E0B", fontFamily: "var(--font-mono)" }}>{ind.bbPct}%</span>

                          </div>

                        </div>

                      </div>



                      {/* Volume */}

                      <div style={{ padding: 16, background: "#080C10", border: "1px solid #111827", borderRadius: 8 }}>

                        <div style={{ fontSize: 10, color: "#64748B", marginBottom: 8 }}>VOLUME ANALYSIS</div>

                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>

                          <Volume2 size={16} color={ind.volRatio >= 1.2 ? "#10B981" : "#334155"} />

                          <div>

                            <div style={{ color: "#E2E8F0", fontSize: 16, fontFamily: "var(--font-mono)", fontWeight: 700 }}>{ind.volRatio}×</div>

                            <div style={{ color: ind.volRatio >= 1.2 ? "#10B981" : "#EF4444", fontSize: 10 }}>

                              {ind.volRatio >= 1.8 ? "HIGH VOLUME SPIKE" : ind.volRatio >= 1.2 ? "ABOVE AVERAGE" : "BELOW AVERAGE"}

                            </div>

                          </div>

                        </div>

                      </div>

                    </div>



                    {/* EMA Summary */}

                    <div style={{ padding: 16, background: "#080C10", border: "1px solid #111827", borderRadius: 8, marginBottom: 16 }}>

                      <div style={{ fontSize: 10, color: "#64748B", marginBottom: 12, letterSpacing: 0.5 }}>EMA TREND ANALYSIS</div>

                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>

                        {[

                          { label: "EMA 9 (Fast)", value: ind.ema9, note: "Short-term" },

                          { label: "EMA 21 (Slow)", value: ind.ema21, note: "Medium-term" },

                          { label: "EMA 50 (Trend)", value: ind.ema50, note: "Long-term" },

                        ].map(item => (

                          <div key={item.label}>

                            <div style={{ color: "#475569", fontSize: 10, marginBottom: 4 }}>{item.label}</div>

                            <div style={{ color: "#E2E8F0", fontSize: 14, fontFamily: "var(--font-mono)", fontWeight: 600 }}>{fmt(item.value)}</div>

                            <div style={{ color: "#334155", fontSize: 10 }}>{item.note}</div>

                          </div>

                        ))}

                      </div>

                      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>

                        <span style={{ padding: "3px 8px", background: ind.emaBull ? "#052e16" : "#450a0a", border: `1px solid ${ind.emaBull ? "#10B981" : "#EF4444"}`, borderRadius: 4, color: ind.emaBull ? "#10B981" : "#EF4444", fontSize: 10, fontWeight: 600 }}>

                          {ind.emaBull ? "✓ EMA BULLISH CROSS" : "✕ EMA BEARISH CROSS"}

                        </span>

                        <span style={{ padding: "3px 8px", background: ind.trendUp ? "#052e16" : "#450a0a", border: `1px solid ${ind.trendUp ? "#10B981" : "#EF4444"}`, borderRadius: 4, color: ind.trendUp ? "#10B981" : "#EF4444", fontSize: 10, fontWeight: 600 }}>

                          {ind.trendUp ? "✓ ABOVE EMA50" : "✕ BELOW EMA50"}

                        </span>

                      </div>

                    </div>



                    {/* Signal Checklist */}

                    <div style={{ padding: 16, background: "#080C10", border: "1px solid #111827", borderRadius: 8 }}>

                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>

                        <span style={{ fontSize: 10, color: "#64748B", letterSpacing: 0.5 }}>BUY SIGNAL CHECKLIST</span>

                        <ScoreMeter score={buyScore} />

                      </div>

                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>

                        {buyReasons.map((r, i) => (

                          <div key={i} style={{ fontSize: 12, color: r.startsWith("✅") ? "#94A3B8" : "#475569", lineHeight: 1.4 }}>{r}</div>

                        ))}

                      </div>

                      {buyScore >= 60 && (

                        <div style={{ marginTop: 12, padding: "8px 12px", background: "#052e16", border: "1px solid #10B981", borderRadius: 6, color: "#10B981", fontSize: 12, fontWeight: 600, textAlign: "center" }}>

                          🟢 BUY SIGNAL ACTIVE — Score {buyScore}/100

                        </div>

                      )}

                    </div>

                  </div>

                )}



                {activeTab === "prediction" && (

                  <div className="animate-in">

                    <PredictionPanel

                      stock={selectedStock}

                      prediction={prediction}

                      loading={loadingPrediction}

                      onPredict={handlePredict}

                    />

                  </div>

                )}



                {activeTab === "news" && (

                  <div style={{ padding: "20px" }}>

                    <h3 style={{ fontSize: 16, fontWeight: 600, color: "#F8FAFC", marginBottom: 15 }}>Recent Factors & Headlines</h3>

                    {curData?.news?.length > 0 ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
                        {curData.news.map((item, i) => (

                          <div key={i} style={{ padding: 15, background: "#1E293B", borderRadius: 8, border: "1px solid #334155" }}>

                            <div style={{ fontSize: 14, color: "#E2E8F0", marginBottom: 5 }}>

                              {item.link ? <a href={item.link} target="_blank" rel="noopener noreferrer" style={{ color: "#38BDF8", textDecoration: "none" }}>{item.title}</a> : item.title}

                            </div>

                            <div style={{ fontSize: 12, color: "#94A3B8" }}>

                              {item.publisher} • {item.time ? new Date(item.time * 1000).toLocaleString() : ""}

                            </div>

                          </div>

                        ))}

                      </div>

                    ) : (

                      <div style={{ color: "#94A3B8", fontStyle: "italic", padding: 20 }}>No recent news data found.</div>

                    )}

                  </div>

                )}

              </div>

            </>

          ) : (

            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#334155" }}>

              <div style={{ textAlign: "center" }}>

                <BarChart2 size={40} style={{ margin: "0 auto 12px", display: "block" }} />

                <div style={{ fontSize: 16, color: "#475569", marginBottom: 8 }}>Select a stock to begin</div>

                <div style={{ fontSize: 12 }}>Search or browse {NSE_ALL_STOCKS.length}+ NSE stocks</div>

              </div>

            </div>

          )}

        </div>

      </div>



      {showSettings && (

        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.8)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>

          <div style={{ background: "#0A0F14", border: "1px solid #1E2030", borderRadius: 8, width: 400, padding: 20 }}>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>

              <h2 style={{ fontSize: 16, color: "#E2E8F0" }}>API Credentials</h2>

              <button onClick={() => setShowSettings(false)} style={{ background: "none", border: "none", color: "#94A3B8", cursor: "pointer" }}><X size={16}/></button>

            </div>

            

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

              <div>

                <label style={{ fontSize: 11, color: "#94A3B8", marginBottom: 4, display: "block" }}>Zerodha API Key {credsStatus.zerodha_configured && "✅"}</label>

                <input type="password" value={credentials.ZERODHA_API_KEY} onChange={e => setCredentials({...credentials, ZERODHA_API_KEY: e.target.value})} placeholder="Leaves unchanged if blank" style={{ width: "100%", padding: 8, background: "#050810", border: "1px solid #1E2030", borderRadius: 4, fontSize: 12 }} />

              </div>

              <div>

                <label style={{ fontSize: 11, color: "#94A3B8", marginBottom: 4, display: "block" }}>Zerodha API Secret</label>

                <input type="password" value={credentials.ZERODHA_API_SECRET} onChange={e => setCredentials({...credentials, ZERODHA_API_SECRET: e.target.value})} placeholder="Leaves unchanged if blank" style={{ width: "100%", padding: 8, background: "#050810", border: "1px solid #1E2030", borderRadius: 4, fontSize: 12 }} />

              </div>

              <div>

                <label style={{ fontSize: 11, color: "#94A3B8", marginBottom: 4, display: "block" }}>Zerodha Access Token</label>

                <input type="password" value={credentials.ZERODHA_ACCESS_TOKEN} onChange={e => setCredentials({...credentials, ZERODHA_ACCESS_TOKEN: e.target.value})} placeholder="Leaves unchanged if blank" style={{ width: "100%", padding: 8, background: "#050810", border: "1px solid #1E2030", borderRadius: 4, fontSize: 12 }} />

              </div>

              <div>

                <label style={{ fontSize: 11, color: "#94A3B8", marginBottom: 4, display: "block" }}>Telegram Bot Token {credsStatus.telegram_configured && "✅"}</label>

                <input type="password" value={credentials.TELEGRAM_BOT_TOKEN} onChange={e => setCredentials({...credentials, TELEGRAM_BOT_TOKEN: e.target.value})} placeholder="Leaves unchanged if blank" style={{ width: "100%", padding: 8, background: "#050810", border: "1px solid #1E2030", borderRadius: 4, fontSize: 12 }} />

              </div>

              <div>

                <label style={{ fontSize: 11, color: "#94A3B8", marginBottom: 4, display: "block" }}>Telegram Chat ID</label>

                <input type="text" value={credentials.TELEGRAM_CHAT_ID} onChange={e => setCredentials({...credentials, TELEGRAM_CHAT_ID: e.target.value})} placeholder="Leaves unchanged if blank" style={{ width: "100%", padding: 8, background: "#050810", border: "1px solid #1E2030", borderRadius: 4, fontSize: 12 }} />

              </div>

              <div>

                <label style={{ fontSize: 11, color: "#94A3B8", marginBottom: 4, display: "block" }}>Groq API Key {credsStatus.groq_configured && "✅"}</label>

                <input type="password" value={credentials.GROQ_API_KEY} onChange={e => setCredentials({...credentials, GROQ_API_KEY: e.target.value})} placeholder="Leaves unchanged if blank" style={{ width: "100%", padding: 8, background: "#050810", border: "1px solid #1E2030", borderRadius: 4, fontSize: 12 }} />

              </div>

              

              <button onClick={handleSaveCredentials} style={{ marginTop: 8, background: "#F59E0B", color: "#000", border: "none", padding: "10px", borderRadius: 4, cursor: "pointer", fontWeight: 600 }}>

                Save Credentials

              </button>

            </div>

          </div>

        </div>

      )}

    </div>

  );

}



