import {config} from '../config.mjs';
import {NobitexProvider} from '../providers/nobitex.mjs';
import {scanAllMarkets} from '../services/market-scanner.mjs';

const p=new NobitexProvider({...config,timeoutMs:config.httpTimeoutMs});
const out=await scanAllMarkets(p,{quotes:config.scanQuotes,perQuote:config.scanPerQuote,maxTotal:config.scanMaxTotal});
console.log(JSON.stringify({generatedAt:new Date().toISOString(),...out,routeHealth:p.health()},null,2));
if(!out.shortlist.some(x=>x.state!=='NO_DATA'))process.exitCode=2;
