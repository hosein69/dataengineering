const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
const finite=v=>Number.isFinite(v)?v:null;

export function quoteOf(symbol){
  const s=String(symbol||'').toUpperCase();
  if(s.endsWith('USDT'))return 'USDT';
  if(s.endsWith('IRT'))return 'IRT';
  return 'OTHER';
}

export function baseOf(symbol){
  const s=String(symbol||'').toUpperCase(),q=quoteOf(s);
  return q==='OTHER'?s:s.slice(0,-q.length);
}

export function marketRole(symbol){
  const base=baseOf(symbol);
  const referenceBases=new Set(['USDT','USDC','DAI','TUSD','FDUSD','USDE','RLUSD']);
  return referenceBases.has(base)?'REFERENCE':'OPPORTUNITY';
}

export function percentileRank(values,value){
  const xs=values.filter(Number.isFinite).sort((a,b)=>a-b);
  if(!xs.length||!Number.isFinite(value))return 0;
  let le=0;for(const x of xs)if(x<=value)le++;
  return xs.length===1?1:(le-1)/(xs.length-1);
}

export function basicMarketRow(provider,book,depth=20){
  const metrics=provider.metrics(book,[],depth);
  const depthLiquidity=(metrics.bidNotional>0&&metrics.askNotional>0)?Math.sqrt(metrics.bidNotional*metrics.askNotional):0;
  return {symbol:book.symbol,quote:quoteOf(book.symbol),book,metrics,depthLiquidity,spreadBps:metrics.spreadBps,usable:Boolean(book.quality?.usable)};
}

export function preRank(rows){
  const groups=Map.groupBy(rows.filter(x=>x.usable&&['IRT','USDT'].includes(x.quote)),x=>x.quote);
  const out=[];
  for(const [quote,items] of groups){
    const liqs=items.map(x=>Math.log1p(x.depthLiquidity));
    const spreads=items.map(x=>x.spreadBps).filter(Number.isFinite);
    for(const x of items){
      const liqPct=percentileRank(liqs,Math.log1p(x.depthLiquidity));
      const spreadPct=1-percentileRank(spreads,x.spreadBps);
      const preScore=100*(0.72*liqPct+0.28*spreadPct);
      out.push({...x,liqPct,spreadQuality:spreadPct,preScore});
    }
  }
  return out.sort((a,b)=>b.preScore-a.preScore);
}

export async function enrichMarket(provider,row){
  const symbol=row.symbol;
  const [tr,...framesR]=await Promise.allSettled([
    provider.trades(symbol),
    provider.ohlc(symbol,'5',40),
    provider.ohlc(symbol,'30',40),
    provider.ohlc(symbol,'D',40)
  ]);
  const tradesOk=tr.status==='fulfilled';
  const trades=tradesOk?tr.value.items.slice(0,100):[];
  const frames={};
  ['5','30','D'].forEach((k,i)=>{const r=framesR[i];if(r?.status==='fulfilled')frames[k]=provider.candleFeatures(r.value.candles)});
  const metrics=provider.metrics(row.book,trades,20);
  const state=provider.classify({quality:row.book.quality,metrics,tradesOk,frames});
  const m5=Math.abs(frames['5']?.ret1??0),m30=Math.abs(frames['30']?.ret1??0),vr=frames['5']?.volumeRatio??0;
  const flow=Math.abs(metrics.tradeImbalance??0),ob=Math.abs(metrics.orderbookImbalance??0);
  const activity=clamp((m5/0.8)*0.35+(m30/2)*0.20+(Math.min(vr,3)/3)*0.20+flow*0.15+ob*0.10);
  const attentionScore=100*(0.55*(row.preScore/100)+0.45*activity);
  return {
    symbol,rowQuote:row.quote,state,attentionScore,preScore:row.preScore,
    price:row.book.lastTradePrice,bid:metrics.bestBid,ask:metrics.bestAsk,spreadBps:metrics.spreadBps,
    depthLiquidity:row.depthLiquidity,obImbalance:metrics.orderbookImbalance,tradeImbalance:metrics.tradeImbalance,
    m5:finite(frames['5']?.ret1),m30:finite(frames['30']?.ret1),d1:finite(frames.D?.ret1),
    volume5Ratio:finite(frames['5']?.volumeRatio),bookAgeMs:row.book.quality?.ageMs,
    route:row.book.route,dnsMode:row.book.dnsMode,tradesOk
  };
}

export async function scanAllMarkets(provider,{quotes=['IRT','USDT'],perQuote=8,maxTotal=16}={}){
  const all=await provider.orderbooksAll();
  const basics=Object.values(all.books).map(b=>basicMarketRow(provider,b)).filter(x=>quotes.includes(x.quote));
  const ranked=preRank(basics);
  const selected=[];
  for(const q of quotes){
    selected.push(...ranked.filter(x=>x.quote===q).slice(0,perQuote));
  }
  selected.sort((a,b)=>b.preScore-a.preScore);
  const limited=selected.slice(0,maxTotal);
  const enriched=[];
  for(const row of limited){
    try{enriched.push(await enrichMarket(provider,row))}
    catch(e){enriched.push({symbol:row.symbol,rowQuote:row.quote,state:'NO_DATA',attentionScore:0,preScore:row.preScore,error:String(e?.message||e)})}
  }
  enriched.sort((a,b)=>(b.attentionScore||0)-(a.attentionScore||0));
  return {
    source:{route:all.route,dnsMode:all.dnsMode,latencyMs:all.latencyMs},
    universeCount:basics.length,shortlistCount:limited.length,
    shortlist:enriched.map((x,i)=>({rank:i+1,...x}))
  };
}


const sign=v=>v>0?1:v<0?-1:0;
const avg=xs=>{const v=xs.filter(Number.isFinite);return v.length?v.reduce((a,b)=>a+b,0)/v.length:null};

export function temporalSummary(samples){
  const usable=samples.filter(Boolean);
  if(!usable.length)return {temporalStatus:'NO_DATA',persistence:0,flowAgreement:0};
  const states=new Map();
  for(const s of usable)states.set(s.state,(states.get(s.state)||0)+1);
  const [dominantState,dominantCount]=[...states.entries()].sort((a,b)=>b[1]-a[1])[0];
  const persistence=dominantCount/usable.length;
  const tradeSigns=usable.map(s=>sign(s.tradeImbalance??0)).filter(Boolean);
  const obSigns=usable.map(s=>sign(s.obImbalance??0)).filter(Boolean);
  const agreement=arr=>{
    if(!arr.length)return 0;
    const pos=arr.filter(x=>x>0).length,neg=arr.filter(x=>x<0).length;
    return Math.max(pos,neg)/arr.length;
  };
  const flowAgreement=(agreement(tradeSigns)+agreement(obSigns))/2;
  const actionable=new Set(['MOMENTUM_BUY_WATCH','PULLBACK_WATCH','REVERSAL_WATCH','REVERSAL_CANDIDATE_LOW_VOLUME','SELL_PRESSURE']);
  let temporalStatus='OBSERVE';
  if(actionable.has(dominantState)&&persistence>=2/3&&flowAgreement>=2/3)temporalStatus='CONFIRMED';
  else if(actionable.has(dominantState))temporalStatus='UNCONFIRMED';
  else if(dominantState==='NEUTRAL')temporalStatus='NEUTRAL';
  return {
    temporalStatus,dominantState,persistence,flowAgreement,
    avgAttentionScore:avg(usable.map(x=>x.attentionScore)),
    avgSpreadBps:avg(usable.map(x=>x.spreadBps)),
    avgTradeImbalance:avg(usable.map(x=>x.tradeImbalance)),
    avgObImbalance:avg(usable.map(x=>x.obImbalance)),
    samples:usable.length
  };
}

export async function scanStableMarkets(provider,{quotes=['IRT','USDT'],perQuote=4,maxTotal=8,cycles=3,intervalMs=3000}={}){
  const first=await scanAllMarkets(provider,{quotes,perQuote,maxTotal});
  const symbols=first.shortlist.map(x=>x.symbol);
  const history=new Map(symbols.map(s=>[s,[]]));
  for(const row of first.shortlist)history.get(row.symbol).push({...row,cycle:1});
  for(let cycle=2;cycle<=cycles;cycle++){
    if(intervalMs>0)await new Promise(r=>setTimeout(r,intervalMs));
    let books={},bulkError=null;
    try{
      const all=await provider.orderbooksAll();
      books=all.books;
    }catch(e){
      bulkError=String(e?.message||e);
      for(const symbol of symbols){
        try{books[symbol]=await provider.orderbook(symbol)}catch{}
      }
    }
    for(const symbol of symbols){
      const base=first.shortlist.find(x=>x.symbol===symbol);
      const book=books[symbol];
      if(!book){history.get(symbol).push({symbol,state:'NO_DATA',cycle,error:bulkError||'book unavailable'});continue}
      try{
        const tr=await provider.trades(symbol);
        const trades=tr.items.slice(0,100),metrics=provider.metrics(book,trades,20);
        const frames={
          '5':{ret1:base.m5,volumeRatio:base.volume5Ratio},
          '30':{ret1:base.m30},
          D:{ret1:base.d1}
        };
        const state=provider.classify({quality:book.quality,metrics,tradesOk:true,frames});
        const microActivity=Math.min(1,Math.abs(metrics.tradeImbalance??0)*0.55+Math.abs(metrics.orderbookImbalance??0)*0.25+Math.min(Math.abs(base.m5??0)/0.8,1)*0.20);
        const attentionScore=100*(0.65*(base.preScore/100)+0.35*microActivity);
        history.get(symbol).push({
          symbol,rowQuote:base.rowQuote,state,attentionScore,preScore:base.preScore,price:book.lastTradePrice,
          bid:metrics.bestBid,ask:metrics.bestAsk,spreadBps:metrics.spreadBps,
          obImbalance:metrics.orderbookImbalance,tradeImbalance:metrics.tradeImbalance,
          m5:base.m5,m30:base.m30,d1:base.d1,volume5Ratio:base.volume5Ratio,
          bookAgeMs:book.quality?.ageMs,cycle
        });
      }catch(e){history.get(symbol).push({symbol,state:'NO_DATA',cycle,error:String(e?.message||e)})}
    }
  }
  const stable=symbols.map(symbol=>{
    const samples=history.get(symbol);
    const summary=temporalSummary(samples);
    const latest=[...samples].reverse().find(x=>x.state!=='NO_DATA')||samples.at(-1);
    const stabilityScore=(summary.avgAttentionScore||0)*(0.55+0.45*summary.persistence)*(0.65+0.35*summary.flowAgreement);
    return {symbol,...summary,stabilityScore,latest,samples};
  }).sort((a,b)=>b.stabilityScore-a.stabilityScore).map((x,i)=>({rank:i+1,...x}));
  const classified=stable.map(x=>({...x,marketRole:marketRole(x.symbol)}));
  const confirmedOpportunities=classified.filter(x=>x.marketRole==='OPPORTUNITY'&&x.temporalStatus==='CONFIRMED');
  const monitorOnly=classified.filter(x=>x.marketRole==='OPPORTUNITY'&&x.temporalStatus!=='CONFIRMED');
  const referenceMarkets=classified.filter(x=>x.marketRole==='REFERENCE');
  return {
    generatedAt:new Date().toISOString(),cycles,intervalMs,
    universeCount:first.universeCount,shortlistCount:first.shortlistCount,
    stableWatchlist:classified,confirmedOpportunities,monitorOnly,referenceMarkets,
    routeHealth:provider.health()
  };
}
