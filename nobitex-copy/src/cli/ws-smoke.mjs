import {config} from '../config.mjs';
import {NobitexProvider} from '../providers/nobitex.mjs';
const p=new NobitexProvider({apiBases:config.apiBases,wsUrls:config.wsUrls,timeoutMs:config.httpTimeoutMs});
const symbol=config.markets[0]||'BTCIRT';
try{
  const live=await p.streamOrderbook(symbol,{timeoutMs:config.wsTimeoutMs});
  console.log(JSON.stringify({
    symbol,route:live.route,websocketLastUpdate:live.book.lastUpdate,websocketReceivedAt:live.receivedAt,
    bestBid:live.book.bids[0]?.price??null,bestAsk:live.book.asks[0]?.price??null,attempts:live.attempts
  },null,2));
}catch(e){
  console.error(JSON.stringify({symbol,error:String(e.message||e),attempts:e.attempts||null,routeHealth:p.health()},null,2));
  process.exitCode=2;
}
