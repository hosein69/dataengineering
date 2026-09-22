import WebSocket from 'ws';

const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null};
const upper=v=>String(v||'').trim().toUpperCase();
const sum=(xs,fn)=>xs.reduce((a,x)=>a+(fn(x)||0),0);
const cleanBase=v=>String(v||'').trim().replace(/\/$/,'');
const errText=e=>String(e?.cause?.code||e?.code||e?.message||e);

export class NobitexProvider{
  constructor({
    apiBases=['https://api.nobitex.ir','https://api.nobitex.net'],
    wsUrls=['wss://wss.nobitex.ir/connection/websocket'],
    timeoutMs=10000
  }={}){
    this.apiBases=[...new Set(apiBases.map(cleanBase).filter(Boolean))];
    this.wsUrls=[...new Set(wsUrls.map(String).map(x=>x.trim()).filter(Boolean))];
    this.timeoutMs=timeoutMs;
    this.routeHealth=new Map();
  }

  markRoute(route,patch={}){
    const prev=this.routeHealth.get(route)||{route,successes:0,failures:0};
    const next={...prev,...patch,lastCheckedAt:new Date().toISOString()};
    if(patch.ok===true)next.successes=(prev.successes||0)+1;
    if(patch.ok===false)next.failures=(prev.failures||0)+1;
    this.routeHealth.set(route,next);
    return next;
  }

  health(){
    return [...this.routeHealth.values()];
  }

  async getJson(path){
    const attempts=[];
    for(const base of this.apiBases){
      const url=base+path;
      const started=Date.now();
      try{
        const r=await fetch(url,{headers:{accept:'application/json','user-agent':'nobitex-copy-live/0.2'},signal:AbortSignal.timeout(this.timeoutMs)});
        const latencyMs=Date.now()-started;
        if(!r.ok)throw Object.assign(new Error(`HTTP ${r.status}`),{httpStatus:r.status});
        const d=await r.json();
        if(d?.status && d.status!=='ok')throw new Error(`API status=${d.status}`);
        this.markRoute(base,{ok:true,latencyMs,lastPath:path,lastError:null});
        return {data:d,route:base,latencyMs,attempts:[...attempts,{route:base,ok:true,latencyMs}]};
      }catch(e){
        const latencyMs=Date.now()-started;
        const error=errText(e);
        attempts.push({route:base,ok:false,latencyMs,error});
        this.markRoute(base,{ok:false,latencyMs,lastPath:path,lastError:error});
      }
    }
    const error=new Error(`All Nobitex REST routes failed for ${path}`);
    error.attempts=attempts;
    throw error;
  }

  async orderbook(symbol){
    symbol=upper(symbol);
    const r=await this.getJson(`/v3/orderbook/${encodeURIComponent(symbol)}`);
    return {...this.normalizeOrderbook(symbol,r.data),route:r.route,routeLatencyMs:r.latencyMs,routeAttempts:r.attempts};
  }

  async trades(symbol){
    symbol=upper(symbol);
    const r=await this.getJson(`/v2/trades/${encodeURIComponent(symbol)}`);
    const rows=Array.isArray(r.data?.trades)?r.data.trades:[];
    return {
      route:r.route,
      routeLatencyMs:r.latencyMs,
      routeAttempts:r.attempts,
      items:rows.map((t,i)=>({
        id:String(t.id??t.tradeId??`${symbol}:${t.time??i}:${t.price??''}`),
        symbol,time:t.time??t.timestamp??null,price:num(t.price),volume:num(t.volume??t.amount),
        type:String(t.type??t.side??'').toLowerCase()||null,raw:t
      }))
    };
  }

  normalizeOrderbook(symbol,d){
    const bids=(d?.bids||[]).map(x=>({price:num(x?.[0]),amount:num(x?.[1])})).filter(x=>x.price!=null&&x.amount!=null);
    const asks=(d?.asks||[]).map(x=>({price:num(x?.[0]),amount:num(x?.[1])})).filter(x=>x.price!=null&&x.amount!=null);
    return {symbol:upper(symbol),lastUpdate:num(d?.lastUpdate),lastTradePrice:num(d?.lastTradePrice),bids,asks,rawStatus:d?.status||'ok'};
  }

  metrics(book,trades=[],depth=20){
    const bids=book.bids.slice(0,depth),asks=book.asks.slice(0,depth);
    const bestBid=bids[0]?.price??null,bestAsk=asks[0]?.price??null;
    const mid=bestBid!=null&&bestAsk!=null?(bestBid+bestAsk)/2:null;
    const spread=bestBid!=null&&bestAsk!=null?bestAsk-bestBid:null;
    const spreadBps=spread!=null&&mid?spread/mid*10000:null;
    const bidNotional=sum(bids,x=>x.price*x.amount),askNotional=sum(asks,x=>x.price*x.amount);
    const imbalance=(bidNotional+askNotional)>0?(bidNotional-askNotional)/(bidNotional+askNotional):null;
    const buyVol=sum(trades.filter(x=>x.type==='buy'),x=>x.volume);
    const sellVol=sum(trades.filter(x=>x.type==='sell'),x=>x.volume);
    const tradeImbalance=(buyVol+sellVol)>0?(buyVol-sellVol)/(buyVol+sellVol):null;
    const ageMs=book.lastUpdate?Date.now()-book.lastUpdate:null;
    return {bestBid,bestAsk,mid,spread,spreadBps,bidNotional,askNotional,orderbookImbalance:imbalance,buyVolume:buyVol,sellVolume:sellVol,tradeImbalance,bookAgeMs:ageMs};
  }

  classify(metrics){
    const ob=metrics.orderbookImbalance??0,ti=metrics.tradeImbalance??0;
    if(ob>=0.18&&ti>=0.12)return 'MOMENTUM_BUY_WATCH';
    if(ob<=-0.18&&ti<=-0.12)return 'SELL_PRESSURE';
    if(ob>=0.12&&ti<0)return 'PULLBACK_WATCH';
    if(ob<0&&ti>=0.12)return 'REVERSAL_WATCH';
    return 'NEUTRAL';
  }

  async snapshot(symbol,{tradeLimit=100,depth=20}={}){
    const started=Date.now();
    const [book,tradesR]=await Promise.all([this.orderbook(symbol),this.trades(symbol)]);
    const recent=tradesR.items.slice(0,tradeLimit);
    const metrics=this.metrics(book,recent,depth);
    return {
      provider:'nobitex',mode:'rest-live',symbol:upper(symbol),fetchedAt:new Date().toISOString(),
      latencyMs:Date.now()-started,book,trades:recent,metrics,watchState:this.classify(metrics),
      routes:{orderbook:book.route,trades:tradesR.route},
      routeAttempts:{orderbook:book.routeAttempts,trades:tradesR.routeAttempts}
    };
  }

  async streamOrderbook(symbol,{timeoutMs=20000}={}){
    symbol=upper(symbol);
    const channel=`public:orderbook-${symbol}`;
    const attempts=[];
    for(const wsUrl of this.wsUrls){
      try{
        const value=await this.streamOne(wsUrl,channel,symbol,timeoutMs);
        this.markRoute(wsUrl,{ok:true,lastPath:channel,lastError:null});
        return {...value,route:wsUrl,attempts:[...attempts,{route:wsUrl,ok:true}]};
      }catch(e){
        const error=errText(e);
        attempts.push({route:wsUrl,ok:false,error});
        this.markRoute(wsUrl,{ok:false,lastPath:channel,lastError:error});
      }
    }
    const error=new Error(`All Nobitex WebSocket routes failed for ${channel}`);
    error.attempts=attempts;
    throw error;
  }

  streamOne(wsUrl,channel,symbol,timeoutMs){
    return new Promise((resolve,reject)=>{
      const ws=new WebSocket(wsUrl);
      let settled=false;
      const finish=(err,value)=>{if(settled)return;settled=true;clearTimeout(timer);try{ws.close()}catch{};err?reject(err):resolve(value)};
      const timer=setTimeout(()=>finish(new Error(`WebSocket timeout waiting for ${channel}`)),timeoutMs);
      ws.on('open',()=>ws.send(JSON.stringify({id:1,connect:{}})));
      ws.on('error',e=>finish(e));
      ws.on('message',buf=>{
        const raw=String(buf);
        if(raw==='{}'){try{ws.send('{}')}catch{};return}
        for(const line of raw.split('\n').filter(Boolean)){
          let msg;try{msg=JSON.parse(line)}catch{continue}
          if(msg?.id===1&&msg?.connect){ws.send(JSON.stringify({id:2,subscribe:{channel}}));continue}
          if(msg?.push?.channel===channel&&msg?.push?.pub?.data){
            let data=msg.push.pub.data;try{if(typeof data==='string')data=JSON.parse(data)}catch{}
            return finish(null,{provider:'nobitex',mode:'websocket-live',channel,receivedAt:new Date().toISOString(),book:this.normalizeOrderbook(symbol,data)});
          }
        }
      });
    });
  }
}
