import test from 'node:test';import assert from 'node:assert/strict';
import {quoteOf,baseOf,marketRole,percentileRank,preRank} from '../src/services/market-scanner.mjs';

test('quote detection handles USDT before IRT',()=>{assert.equal(quoteOf('BTCUSDT'),'USDT');assert.equal(quoteOf('BTCIRT'),'IRT');assert.equal(quoteOf('BTCUSD'),'OTHER')});
test('percentile rank is monotonic',()=>{assert.equal(percentileRank([1,2,3],1),0);assert.equal(percentileRank([1,2,3],3),1)});
test('preRank compares liquidity within quote',()=>{const mk=(s,q,l,sp)=>({symbol:s,quote:q,usable:true,depthLiquidity:l,spreadBps:sp});const r=preRank([mk('AIRT','IRT',1000,5),mk('BIRT','IRT',100,10),mk('CUSDT','USDT',10,1),mk('DUSDT','USDT',1,2)]);assert.ok(r.find(x=>x.symbol==='AIRT').preScore>r.find(x=>x.symbol==='BIRT').preScore);assert.ok(r.find(x=>x.symbol==='CUSDT').preScore>r.find(x=>x.symbol==='DUSDT').preScore)});

test('reference stablecoin bases are separated from opportunity markets',()=>{assert.equal(baseOf('USDCUSDT'),'USDC');assert.equal(marketRole('USDCUSDT'),'REFERENCE');assert.equal(marketRole('BTCUSDT'),'OPPORTUNITY');assert.equal(marketRole('USDTIRT'),'REFERENCE')});
