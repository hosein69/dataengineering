import {config} from '../config.mjs';
import {NobitexProvider} from '../providers/nobitex.mjs';

const p=new NobitexProvider({apiBase:config.apiBase,wsUrl:config.wsUrl,timeoutMs:config.httpTimeoutMs});
const out={generatedAt:new Date().toISOString(),markets:[],errors:[]};
for(const symbol of config.markets){
  try{
    const s=await p.snapshot(symbol);
    out.markets.push({
      symbol:s.symbol,
      fetchedAt:s.fetchedAt,
      latencyMs:s.latencyMs,
      lastTradePrice:s.book.lastTradePrice,
      lastUpdate:s.book.lastUpdate,
      bestBid:s.metrics.bestBid,
      bestAsk:s.metrics.bestAsk,
      mid:s.metrics.mid,
      spread:s.metrics.spread,
      spreadBps:s.metrics.spreadBps,
      orderbookImbalance:s.metrics.orderbookImbalance,
      tradeImbalance:s.metrics.tradeImbalance,
      recentTrades:s.trades.length,
      bookAgeMs:s.metrics.bookAgeMs
    });
  }catch(e){out.errors.push({symbol,error:String(e.message||e)})}
}
if(!out.markets.length){console.error(JSON.stringify(out,null,2));process.exit(1)}
console.log(JSON.stringify(out,null,2));
