import {config} from '../config.mjs';
import {NobitexProvider} from '../providers/nobitex.mjs';

const p=new NobitexProvider({apiBases:config.apiBases,wsUrls:config.wsUrls,timeoutMs:config.httpTimeoutMs});
const out={generatedAt:new Date().toISOString(),configuredRestRoutes:config.apiBases,configuredWsRoutes:config.wsUrls,markets:[],errors:[]};
for(const symbol of config.markets){
  try{
    const s=await p.snapshot(symbol);
    out.markets.push({
      symbol:s.symbol,watchState:s.watchState,fetchedAt:s.fetchedAt,latencyMs:s.latencyMs,
      orderbookRoute:s.routes.orderbook,tradesRoute:s.routes.trades,
      lastTradePrice:s.book.lastTradePrice,lastUpdate:s.book.lastUpdate,
      bestBid:s.metrics.bestBid,bestAsk:s.metrics.bestAsk,mid:s.metrics.mid,
      spread:s.metrics.spread,spreadBps:s.metrics.spreadBps,
      orderbookImbalance:s.metrics.orderbookImbalance,tradeImbalance:s.metrics.tradeImbalance,
      recentTrades:s.trades.length,bookAgeMs:s.metrics.bookAgeMs
    });
  }catch(e){out.errors.push({symbol,error:String(e.message||e),attempts:e.attempts||null})}
}
out.routeHealth=p.health();
console.log(JSON.stringify(out,null,2));
if(!out.markets.length)process.exitCode=2;
