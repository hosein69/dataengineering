import {config} from '../config.mjs';
import {NobitexProvider} from '../providers/nobitex.mjs';
import {scanStableMarkets} from '../services/market-scanner.mjs';

const p=new NobitexProvider({...config,timeoutMs:config.httpTimeoutMs});
const out=await scanStableMarkets(p,{
  quotes:config.scanQuotes,perQuote:config.stablePerQuote,maxTotal:config.stableMaxTotal,
  cycles:config.stableCycles,intervalMs:config.stableIntervalMs
});
console.log(JSON.stringify(out,null,2));
if(!out.stableWatchlist.some(x=>x.temporalStatus!=='NO_DATA'))process.exitCode=2;
