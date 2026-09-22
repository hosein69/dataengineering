import https from 'node:https';
import WebSocket from 'ws';
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null};
const upper=v=>String(v||'').trim().toUpperCase();
const sum=(xs,fn)=>xs.reduce((a,x)=>a+(fn(x)||0),0);
const cleanBase=v=>String(v||'').trim().replace(/\/$/,'');
const errorCode=e=>String(e?.code||e?.cause?.code||e?.message||e);
const tsMs=v=>{const n=num(v);if(n==null)return null;return n<1e12?n*1000:n};

async function dohResolve(hostname,timeoutMs=5000){
  const urls=[
    `https://dns.google/resolve?name=${encodeURIComponent(hostname)}&type=A`,
    `https://cloudflare-dns.com/dns-query?name=${encodeURIComponent(hostname)}&type=A`
  ];
  for(const url of urls){
    try{
      const headers=url.includes('cloudflare')?{accept:'application/dns-json'}:{accept:'application/json'};
      const r=await fetch(url,{headers,signal:AbortSignal.timeout(timeoutMs)});
      if(!r.ok)continue;
      const d=await r.json();
      const ips=(d.Answer||[]).filter(x=>x.type===1&&/^\d+\.\d+\.\d+\.\d+$/.test(x.data)).map(x=>x.data);
      if(ips.length)return ips;
    }catch{}
  }
  return [];
}

function httpsJson(url,{timeoutMs=10000,address=null,redirects=0}={}){
  return new Promise((resolve,reject)=>{
    const u=new URL(url);
    const opts={protocol:u.protocol,hostname:u.hostname,port:u.port||443,path:u.pathname+u.search,method:'GET',
      headers:{accept:'application/json','user-agent':'nobitex-copy-live/0.3'},timeout:timeoutMs,
      ...(address?{lookup:(hostname,options,cb)=>cb(null,address,4)}:{})};
    const req=https.request(opts,res=>{
      if(res.statusCode>=300&&res.statusCode<400&&res.headers.location&&redirects<2){
        res.resume();return httpsJson(new URL(res.headers.location,url).toString(),{timeoutMs,address,redirects:redirects+1}).then(resolve,reject);
      }
      let body='';res.setEncoding('utf8');res.on('data',c=>body+=c);res.on('end',()=>{
        if((res.statusCode||0)<200||(res.statusCode||0)>=300){const e=new Error(`HTTP ${res.statusCode}`);e.httpStatus=res.statusCode;return reject(e)}
        try{resolve(JSON.parse(body))}catch{reject(new Error('Invalid JSON response'))}
      });
    });
    req.on('timeout',()=>req.destroy(Object.assign(new Error('ETIMEDOUT'),{code:'ETIMEDOUT'})));req.on('error',reject);req.end();
  });
}

export class NobitexProvider{
  constructor({apiBases=['https://apiv2.nobitex.ir','https://api.nobitex.ir','https://api.nobitex.net'],wsUrls=['wss://ws.nobitex.ir/connection/websocket','wss://wss.nobitex.ir/connection/websocket'],timeoutMs=10000,dohFallback=true,maxBookAgeMs=60000}={}){
    this.apiBases=[...new Set(apiBases.map(cleanBase).filter(Boolean))];
    this.wsUrls=[...new Set(wsUrls.map(String).map(x=>x.trim()).filter(Boolean))];
    this.timeoutMs=timeoutMs;this.dohFallback=dohFallback;this.maxBookAgeMs=maxBookAgeMs;this.routeHealth=new Map();this.dnsCache=new Map();
  }
  markRoute(route,patch={}){const prev=this.routeHealth.get(route)||{route,successes:0,failures:0};const next={...prev,...patch,lastCheckedAt:new Date().toISOString()};if(patch.ok===true)next.successes=(prev.successes||0)+1;if(patch.ok===false)next.failures=(prev.failures||0)+1;this.routeHealth.set(route,next);return next}
  health(){return [...this.routeHealth.values()]}
  async resolve(hostname){const hit=this.dnsCache.get(hostname);if(hit&&Date.now()-hit.at<300000)return hit.ips;const ips=await dohResolve(hostname,Math.min(this.timeoutMs,5000));if(ips.length)this.dnsCache.set(hostname,{ips,at:Date.now()});return ips}
  async requestRoute(base,path){
    const url=base+path,started=Date.now();
    try{return {data:await httpsJson(url,{timeoutMs:this.timeoutMs}),route:base,latencyMs:Date.now()-started,dnsMode:'system'}}
    catch(e){
      if(!this.dohFallback||!['ENOTFOUND','EAI_AGAIN'].includes(errorCode(e)))throw e;
      const ips=await this.resolve(new URL(base).hostname);if(!ips.length)throw e;let last=e;
      for(const ip of ips.slice(0,3)){try{return {data:await httpsJson(url,{timeoutMs:this.timeoutMs,address:ip}),route:base,latencyMs:Date.now()-started,dnsMode:'doh',resolvedIp:ip}}catch(err){last=err}}
      throw last;
    }
  }
  async getJson(path,{acceptApiStatus=true}={}){
    const attempts=[];
    for(const base of this.apiBases){
      const started=Date.now();
      try{
        const r=await this.requestRoute(base,path);
        if(acceptApiStatus&&r.data?.status&&r.data.status!=='ok')throw new Error(`API status=${r.data.status}`);
        this.markRoute(base,{ok:true,latencyMs:r.latencyMs,lastPath:path,lastError:null,dnsMode:r.dnsMode,resolvedIp:r.resolvedIp||null});
        return {...r,attempts:[...attempts,{route:base,ok:true,latencyMs:r.latencyMs,dnsMode:r.dnsMode,resolvedIp:r.resolvedIp||null}]};
      }catch(e){const latencyMs=Date.now()-started,error=errorCode(e);attempts.push({route:base,ok:false,latencyMs,error,httpStatus:e?.httpStatus||null});this.markRoute(base,{ok:false,latencyMs,lastPath:path,lastError:error,httpStatus:e?.httpStatus||null})}
    }
    const e=new Error(`All Nobitex REST routes failed for ${path}`);e.attempts=attempts;throw e;
  }
  normalizeOrderbook(symbol,d){
    const parse=(rows,desc)=>rows.map(x=>({price:num(x?.[0]),amount:num(x?.[1])})).filter(x=>x.price>0&&x.amount>=0).sort((a,b)=>desc?b.price-a.price:a.price-b.price);
    return {symbol:upper(symbol),lastUpdate:tsMs(d?.lastUpdate),lastTradePrice:num(d?.lastTradePrice??d?.lastTrade),bids:parse(d?.bids||[],true),asks:parse(d?.asks||[],false),rawStatus:d?.status||'ok'};
  }
  validateBook(book){
    const bestBid=book.bids[0]?.price??null,bestAsk=book.asks[0]?.price??null,ageMs=book.lastUpdate?Date.now()-book.lastUpdate:null;
    const crossed=bestBid!=null&&bestAsk!=null&&bestBid>=bestAsk,stale=ageMs!=null&&(ageMs< -5000||ageMs>this.maxBookAgeMs);
    return {usable:book.bids.length>0&&book.asks.length>0&&!crossed&&!stale,crossed,stale,ageMs,bidLevels:book.bids.length,askLevels:book.asks.length};
  }
  async orderbook(symbol){
    symbol=upper(symbol);const r=await this.getJson(`/v3/orderbook/${encodeURIComponent(symbol)}`),book=this.normalizeOrderbook(symbol,r.data);
    return {...book,quality:this.validateBook(book),route:r.route,routeLatencyMs:r.latencyMs,routeAttempts:r.attempts,dnsMode:r.dnsMode,resolvedIp:r.resolvedIp||null};
  }
  async orderbooksAll(){
    const r=await this.getJson('/v3/orderbook/all'),books={};
    for(const [symbol,data] of Object.entries(r.data||{})){
      if(symbol==='status'||!data||typeof data!=='object')continue;
      const book=this.normalizeOrderbook(symbol,data);
      books[upper(symbol)]={...book,quality:this.validateBook(book),route:r.route,dnsMode:r.dnsMode,resolvedIp:r.resolvedIp||null};
    }
    return {books,route:r.route,dnsMode:r.dnsMode,resolvedIp:r.resolvedIp||null,latencyMs:r.latencyMs};
  }
  async trades(symbol){
    symbol=upper(symbol);const r=await this.getJson(`/v2/trades/${encodeURIComponent(symbol)}`);
    const items=(Array.isArray(r.data?.trades)?r.data.trades:[]).map((t,i)=>({id:String(t.id??t.tradeId??`${symbol}:${t.time??i}:${t.price??''}`),symbol,time:tsMs(t.time??t.timestamp),price:num(t.price),volume:num(t.volume??t.amount),type:String(t.type??t.side??'').toLowerCase()||null}))
      .filter(x=>x.price>0&&x.volume>=0).sort((a,b)=>(b.time||0)-(a.time||0));
    return {route:r.route,dnsMode:r.dnsMode,routeLatencyMs:r.latencyMs,routeAttempts:r.attempts,items};
  }
  async ohlc(symbol,resolution,countback=40){
    symbol=upper(symbol);const to=Math.floor(Date.now()/1000),path=`/market/udf/history?symbol=${encodeURIComponent(symbol)}&resolution=${encodeURIComponent(resolution)}&to=${to}&countback=${countback}`;
    const r=await this.getJson(path,{acceptApiStatus:false}),d=r.data||{};if(d.s!=='ok'&&!Array.isArray(d.c))return {symbol,resolution,candles:[],route:r.route,dnsMode:r.dnsMode};
    const n=Math.min(d.t?.length||0,d.c?.length||0),candles=Array.from({length:n},(_,i)=>({t:tsMs((d.t||[])[i]),o:num((d.o||[])[i]),h:num((d.h||[])[i]),l:num((d.l||[])[i]),c:num((d.c||[])[i]),v:num((d.v||[])[i])})).filter(x=>x.t&&x.c!=null).sort((a,b)=>a.t-b.t);
    return {symbol,resolution,candles,route:r.route,dnsMode:r.dnsMode};
  }
  metrics(book,trades=[],depth=20){
    const bids=book.bids.slice(0,depth),asks=book.asks.slice(0,depth),bestBid=bids[0]?.price??null,bestAsk=asks[0]?.price??null,mid=bestBid!=null&&bestAsk!=null?(bestBid+bestAsk)/2:null,spread=bestBid!=null&&bestAsk!=null?bestAsk-bestBid:null;
    const spreadBps=spread!=null&&mid?spread/mid*10000:null,bidNotional=sum(bids,x=>x.price*x.amount),askNotional=sum(asks,x=>x.price*x.amount),orderbookImbalance=(bidNotional+askNotional)>0?(bidNotional-askNotional)/(bidNotional+askNotional):null;
    const buyNotional=sum(trades.filter(x=>x.type==='buy'),x=>x.price*x.volume),sellNotional=sum(trades.filter(x=>x.type==='sell'),x=>x.price*x.volume),tradeImbalance=(buyNotional+sellNotional)>0?(buyNotional-sellNotional)/(buyNotional+sellNotional):null;
    const bq=bids[0]?.amount||0,aq=asks[0]?.amount||0,microPrice=(bestBid!=null&&bestAsk!=null&&(bq+aq)>0)?(bestAsk*bq+bestBid*aq)/(bq+aq):mid;
    return {bestBid,bestAsk,mid,microPrice,spread,spreadBps,bidNotional,askNotional,orderbookImbalance,buyNotional,sellNotional,tradeImbalance,bookAgeMs:book.quality?.ageMs??null};
  }
  candleFeatures(candles=[]){
    const c=candles.filter(x=>x.c!=null),last=c.at(-1),prev=c.at(-2),back3=c.at(-4);
    const ret=(a,b)=>a&&b&&b.c?((a.c/b.c)-1)*100:null;
    const vols=c.slice(-10,-1).map(x=>x.v).filter(v=>v!=null&&v>=0),avgVol=vols.length?sum(vols,x=>x)/vols.length:null;
    const recent=c.slice(-15);
    const trs=recent.map((x,i)=>{
      const pc=i?recent[i-1].c:x.o;
      if(x.h==null||x.l==null||pc==null)return null;
      return Math.max(x.h-x.l,Math.abs(x.h-pc),Math.abs(x.l-pc));
    }).filter(Number.isFinite);
    const atr=trs.length?sum(trs,x=>x)/trs.length:null;
    const atrPct=atr!=null&&last?.c?atr/last.c*100:null;
    const lrets=[];
    for(let i=1;i<recent.length;i++)if(recent[i-1].c>0&&recent[i].c>0)lrets.push(Math.log(recent[i].c/recent[i-1].c));
    const mean=lrets.length?sum(lrets,x=>x)/lrets.length:0;
    const realizedVolPct=lrets.length>1?Math.sqrt(sum(lrets,x=>(x-mean)**2)/(lrets.length-1))*100:null;
    return {close:last?.c??null,ret1:ret(last,prev),ret3:ret(last,back3),volume:last?.v??null,volumeRatio:avgVol&&last?.v!=null?last.v/avgVol:null,lastCandleAt:last?.t??null,atrPct,realizedVolPct};
  }
  classify({quality,metrics,tradesOk=true,frames={}}){
    if(!quality?.usable)return quality?.stale?'STALE_DATA':quality?.crossed?'CROSSED_BOOK':'INVALID_DATA';
    if(!tradesOk)return 'DATA_DEGRADED';
    const ob=metrics.orderbookImbalance??0,ti=metrics.tradeImbalance??0;
    const f5=frames['5']?.ret1??0,f30=frames['30']?.ret1??0,vr=frames['5']?.volumeRatio??0;
    const atr5=Math.abs(frames['5']?.atrPct??0);
    const moveThr=Math.max(0.08,Math.min(0.50,atr5*0.20));
    const volOk=vr>=0.60;
    if(ob<=-0.15&&ti<=-0.10){
      if(f5<=-moveThr&&volOk)return 'SELL_PRESSURE';
      return 'FLOW_SELL_PRESSURE';
    }
    if(ob>=0.15&&ti>=0.10){
      if(f5>=moveThr&&volOk)return 'MOMENTUM_BUY_WATCH';
      return 'FLOW_BUY_PRESSURE';
    }
    if(f30>=Math.max(0.25,moveThr*2)&&f5<=-moveThr&&ob>=0.08&&volOk)return 'PULLBACK_WATCH';
    if(f30<=-Math.max(0.50,moveThr*3)&&f5>=moveThr&&ti>=0.25)return volOk?'REVERSAL_WATCH':'REVERSAL_CANDIDATE_LOW_VOLUME';
    return 'NEUTRAL';
  }
  async snapshot(symbol,{tradeLimit=100,depth=20,withFrames=false}={}){
    const started=Date.now(),book=await this.orderbook(symbol),tr=await Promise.allSettled([this.trades(symbol)]),tradesOk=tr[0].status==='fulfilled',trades=tradesOk?tr[0].value.items.slice(0,tradeLimit):[],metrics=this.metrics(book,trades,depth),frames={};
    if(withFrames){const rs=await Promise.allSettled(['5','30','D'].map(r=>this.ohlc(symbol,r,40)));['5','30','D'].forEach((r,i)=>{if(rs[i].status==='fulfilled')frames[r]=this.candleFeatures(rs[i].value.candles)})}
    return {provider:'nobitex',mode:'rest-live',symbol:upper(symbol),fetchedAt:new Date().toISOString(),latencyMs:Date.now()-started,book,trades,metrics,frames,tradesOk,watchState:this.classify({quality:book.quality,metrics,tradesOk,frames}),routes:{orderbook:book.route,trades:tradesOk?tr[0].value.route:null},errors:tradesOk?[]:[{source:'trades',error:errorCode(tr[0].reason),attempts:tr[0].reason?.attempts||null}]};
  }
  async streamOrderbook(symbol,{timeoutMs=20000}={}){
    symbol=upper(symbol);const channel=`public:orderbook-${symbol}`,attempts=[];
    for(const wsUrl of this.wsUrls){try{const v=await this.streamOne(wsUrl,channel,symbol,timeoutMs);this.markRoute(wsUrl,{ok:true,lastPath:channel,lastError:null,dnsMode:v.dnsMode,resolvedIp:v.resolvedIp||null});return {...v,route:wsUrl,attempts:[...attempts,{route:wsUrl,ok:true,dnsMode:v.dnsMode,resolvedIp:v.resolvedIp||null}]}}catch(e){const error=errorCode(e);attempts.push({route:wsUrl,ok:false,error});this.markRoute(wsUrl,{ok:false,lastPath:channel,lastError:error})}}
    const e=new Error(`All Nobitex WebSocket routes failed for ${channel}`);e.attempts=attempts;throw e;
  }
  async streamOne(wsUrl,channel,symbol,timeoutMs){
    const host=new URL(wsUrl).hostname,attempt=address=>new Promise((resolve,reject)=>{
      const ws=new WebSocket(wsUrl,address?{lookup:(hostname,opts,cb)=>cb(null,address,4)}:{});let settled=false;
      const finish=(err,value)=>{if(settled)return;settled=true;clearTimeout(timer);try{ws.close()}catch{};err?reject(err):resolve(value)},timer=setTimeout(()=>finish(Object.assign(new Error('ETIMEDOUT'),{code:'ETIMEDOUT'})),timeoutMs);
      ws.on('open',()=>ws.send(JSON.stringify({id:1,connect:{}})));ws.on('error',finish);ws.on('message',buf=>{
        const raw=String(buf);if(raw==='{}'){try{ws.send('{}')}catch{};return}
        for(const line of raw.split('\n').filter(Boolean)){let msg;try{msg=JSON.parse(line)}catch{continue}if(msg?.id===1&&msg?.connect){ws.send(JSON.stringify({id:2,subscribe:{channel}}));continue}if(msg?.push?.channel===channel&&msg?.push?.pub?.data){let data=msg.push.pub.data;try{if(typeof data==='string')data=JSON.parse(data)}catch{}const book=this.normalizeOrderbook(symbol,data);return finish(null,{provider:'nobitex',mode:'websocket-live',channel,receivedAt:new Date().toISOString(),book:{...book,quality:this.validateBook(book)},dnsMode:address?'doh':'system',resolvedIp:address||null})}}
      });
    });
    try{return await attempt(null)}catch(e){if(!this.dohFallback||!['ENOTFOUND','EAI_AGAIN'].includes(errorCode(e)))throw e;const ips=await this.resolve(host);let last=e;for(const ip of ips.slice(0,3)){try{return await attempt(ip)}catch(err){last=err}}throw last}
  }
}