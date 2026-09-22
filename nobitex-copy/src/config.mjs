const ints=(v,d)=>Number.isFinite(Number(v))?Number(v):d;
const bool=(v,d=true)=>v==null?d:/^(1|true|yes)$/i.test(String(v));
const csv=(v,d='')=>String(v??d).split(',').map(x=>x.trim()).filter(Boolean);
export const config={
  apiBases:csv(process.env.NOBITEX_API_BASES,'https://apiv2.nobitex.ir,https://api.nobitex.ir,https://api.nobitex.net').concat(csv(process.env.NOBITEX_RELAY_BASES)),
  wsUrls:csv(process.env.NOBITEX_WS_URLS,'wss://ws.nobitex.ir/connection/websocket,wss://wss.nobitex.ir/connection/websocket').concat(csv(process.env.NOBITEX_RELAY_WS_URLS)),
  markets:csv(process.env.NOBITEX_MARKETS,'BTCIRT,ETHIRT,USDTIRT,ZECIRT').map(x=>x.toUpperCase()),
  httpTimeoutMs:ints(process.env.NOBITEX_HTTP_TIMEOUT_MS,10000),
  wsTimeoutMs:ints(process.env.NOBITEX_WS_TIMEOUT_MS,20000),
  maxBookAgeMs:ints(process.env.NOBITEX_MAX_BOOK_AGE_MS,60000),
  dohFallback:bool(process.env.NOBITEX_DOH_FALLBACK,true),
  scanQuotes:csv(process.env.NOBITEX_SCAN_QUOTES,'IRT,USDT').map(x=>x.toUpperCase()),
  scanPerQuote:ints(process.env.NOBITEX_SCAN_PER_QUOTE,8),
  scanMaxTotal:ints(process.env.NOBITEX_SCAN_MAX_TOTAL,16),
  stablePerQuote:ints(process.env.NOBITEX_STABLE_PER_QUOTE,4),
  stableMaxTotal:ints(process.env.NOBITEX_STABLE_MAX_TOTAL,8),
  stableCycles:ints(process.env.NOBITEX_STABLE_CYCLES,3),
  stableIntervalMs:ints(process.env.NOBITEX_STABLE_INTERVAL_MS,15000)
};