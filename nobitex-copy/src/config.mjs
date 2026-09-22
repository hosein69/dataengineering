const ints=(v,d)=>Number.isFinite(Number(v))?Number(v):d;
export const config={
  apiBase:process.env.NOBITEX_API_BASE||'https://api.nobitex.ir',
  wsUrl:process.env.NOBITEX_WS_URL||'wss://wss.nobitex.ir/connection/websocket',
  markets:String(process.env.NOBITEX_MARKETS||'BTCIRT,ETHIRT,USDTIRT,ZECIRT').split(',').map(x=>x.trim().toUpperCase()).filter(Boolean),
  httpTimeoutMs:ints(process.env.NOBITEX_HTTP_TIMEOUT_MS,10000),
  wsTimeoutMs:ints(process.env.NOBITEX_WS_TIMEOUT_MS,20000)
};
