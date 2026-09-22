import {config} from '../config.mjs';
import {NobitexProvider} from '../providers/nobitex.mjs';
const p=new NobitexProvider({apiBase:config.apiBase,wsUrl:config.wsUrl,timeoutMs:config.httpTimeoutMs});
const symbol=config.markets[0]||'BTCIRT';
const initial=await p.orderbook(symbol);
const live=await p.streamOrderbook(symbol,{timeoutMs:config.wsTimeoutMs});
console.log(JSON.stringify({
  symbol,
  initialLastUpdate:initial.lastUpdate,
  websocketLastUpdate:live.book.lastUpdate,
  websocketReceivedAt:live.receivedAt,
  advanced:live.book.lastUpdate>=initial.lastUpdate,
  bestBid:live.book.bids[0]?.price??null,
  bestAsk:live.book.asks[0]?.price??null
},null,2));
