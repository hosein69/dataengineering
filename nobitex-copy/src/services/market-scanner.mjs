const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
const finite=v=>Number.isFinite(v)?v:null;

export function quoteOf(symbol){
  const s=String(symbol||'').toUpperCase();
  if(s.endsWith('USDT'))return 'USDT';
  if(s.endsWith('IRT'))return 'IRT';
  return 'OTHER';
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
