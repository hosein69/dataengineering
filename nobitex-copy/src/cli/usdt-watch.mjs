import {config} from '../config.mjs';
import {NobitexProvider} from '../providers/nobitex.mjs';

const p=new NobitexProvider({...config,timeoutMs:Math.min(config.httpTimeoutMs,7000)});
const rows=[];

async function fetchOne(symbol){
  try{
    const s=await p.snapshot(symbol,{withFrames:true});
    return {
      symbol,state:s.watchState,price:s.book.lastTradePrice,bid:s.metrics.bestBid,ask:s.metrics.bestAsk,
      spreadBps:s.metrics.spreadBps,obImbalance:s.metrics.orderbookImbalance,tradeImbalance:s.metrics.tradeImbalance,
      m5:s.frames['5']?.ret1??null,m30:s.frames['30']?.ret1??null,d1:s.frames.D?.ret1??null,
      volume5Ratio:s.frames['5']?.volumeRatio??null,atr5Pct:s.frames['5']?.atrPct??null,
      realizedVol5Pct:s.frames['5']?.realizedVolPct??null,bookAgeMs:s.book.quality?.ageMs??null,
      route:s.book.route,dnsMode:s.book.dnsMode
    };
  }catch(e){return {symbol,state:'NO_DATA',error:String(e?.message||e)}}
}

for(let i=0;i<config.usdtWatch.length;i+=2){
  const batch=config.usdtWatch.slice(i,i+2);
  rows.push(...await Promise.all(batch.map(fetchOne)));
}

console.log(JSON.stringify({generatedAt:new Date().toISOString(),watchlist:rows,routeHealth:p.health()},null,2));
if(!rows.some(x=>x.state!=='NO_DATA'))process.exitCode=2;
